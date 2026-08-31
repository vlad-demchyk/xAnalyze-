"""The browser pass: loading audited pages in a real browser, at one or
several viewport widths, and folding what it finds back into the static
result. Also the small pieces of crawl plumbing the audit command shares
with fullscan - when to render, how to turn a source into a URL.
"""
from __future__ import annotations

import sys

import applog


#: `--breakpoints` with no value means all of them.
def _chosen_breakpoints(args):
    """The widths to audit at, or () for the engine's default single pass."""
    from audit import responsive

    raw = getattr(args, "breakpoints", None)
    if not raw:
        return ()
    if raw == "all":
        return responsive.BREAKPOINTS
    wanted = [name.strip() for name in raw.split(",") if name.strip()]
    known = {name: (name, w, h) for name, w, h in responsive.BREAKPOINTS}
    unknown = [name for name in wanted if name not in known]
    if unknown:
        raise SystemExit(
            f"unknown breakpoint: {', '.join(unknown)}. "
            f"Valid: {', '.join(known)}")
    # Kept in the canonical order, widest first, whatever order they were
    # typed in: the first pass to see a finding is the one whose selector the
    # merged row keeps, and that should not depend on typing order.
    return tuple(known[name] for name, _w, _h in responsive.BREAKPOINTS
                 if name in wanted)


def _audit_at_widths(urls, options, sizes, progress=None, markup=None) -> list:
    """One browser, every page, every width - skipping what has not changed.

    `markup` maps a url to the bytes the crawler already received for it.
    Given that, a page whose markup is identical to one a previous run
    audited is read from `browser_cache` instead of being loaded again: this
    is the expensive half of an audit (12 s per page at four widths against
    0.05 s for every static rule) and a re-run of an unchanged page was
    paying it in full.

    Without `markup` nothing is cached, because there would be nothing
    honest to key on: a URL is where a page lives, not what it says.
    """
    from audit import driver
    from audit import responsive
    from dataclasses import replace

    import browser_cache

    markup = markup or {}
    cache = browser_cache.BrowserCache(options, sizes) if markup else None

    results = []
    todo = []
    for url in urls:
        stored = cache.get(markup[url], url) if (cache and url in markup) else None
        results.append(stored)
        if stored is None:
            todo.append(url)

    if todo:
        driver.ensure_headless_application()
        first = (replace(options, viewport=(sizes[0][1], sizes[0][2]))
                 if sizes else options)
        runner = driver.BrowserAuditRunner(first)
        try:
            done = 0
            for index, url in enumerate(urls):
                if results[index] is not None:
                    continue
                done += 1
                if progress:
                    progress(done, url)
                # No widths asked for is one pass at the engine's own
                # viewport, which is what `audit` does without
                # `--breakpoints`. Both shapes go through here so both are
                # cached; they are different questions and the key says so.
                audited = (responsive.audit_responsive(url, sizes, options,
                                                       runner=runner)
                           if sizes else runner.audit(url))
                results[index] = audited
                if cache is not None and url in markup:
                    cache.put(markup[url], audited)
        finally:
            runner.close()

    if cache is not None:
        cache.save()
        note = cache.summary()
        if note:
            import sys

            print(f"# [browser] {note}", file=sys.stderr, flush=True)
    return results


def _run_browser_pass(result, suppressions, args=None) -> None:
    """Load each audited page in a real browser and fold the findings in.

    Runs for a crawled site and for a single self-contained HTML file. Not for
    repo mode: a browser has nothing to load for a `.jsx` fragment that was
    never a page, and half-auditing a template would report problems the built
    page does not have.

    The suppression list is handed to the engines rather than applied to
    their output, so an excluded region is never analysed in the first place
    — for axe that is the difference between "ignore these results" and "do
    not spend seconds computing them".
    """
    if result.mode not in ("web", "file"):
        return
    from audit import browser as browser_mod
    from audit import driver

    usable, reason = driver.available()
    if not usable:
        applog.warning("browser.skipped", reason=str(reason))
        print(f"# browser pass skipped: {reason}", file=sys.stderr)
        return

    targets = [d for d in result.documents if not d.error]
    if not targets:
        return

    options = browser_mod.BrowserAuditOptions(
        exclude=list(suppressions.selectors),
        disabled_rules=list(suppressions.rules),
        allow_local_files=result.mode == "file",
    )
    sizes = _chosen_breakpoints(args) if args is not None else ()
    where = (f" at {len(sizes)} widths" if sizes else "")
    print(f"# browser pass over {len(targets)} page(s){where}", file=sys.stderr)
    # The document is still keyed by its own source (a path, in file mode), so
    # the findings land back on the row the user recognises rather than on a
    # `file://` URL they never typed.
    urls = [_browser_url(d.source) for d in targets]

    def _show(page_no: int, url: str) -> None:
        widths = f" at {len(sizes)} width(s)" if sizes else ""
        print(f"# [browser {page_no}/{len(urls)}{widths}] {url}",
              file=sys.stderr, flush=True)

    # The markup the crawl already received, keyed by the browser url the
    # pass will use. It is what makes the cache honest: the same bytes get
    # the same answer, a changed page gets a fresh browser.
    served = getattr(result, "markup_by_source", None) or {}
    markup = {url: served[document.source]
              for document, url in zip(targets, urls)
              if document.source in served}
    audits = _audit_at_widths(urls, options, sizes, progress=_show,
                              markup=markup)
    by_url = {a.url: a for a in audits}
    for document, url in zip(targets, urls):
        page_audit = by_url.get(url)
        if page_audit is None:
            continue
        if page_audit.error:
            print(f"# {document.source}: {page_audit.error}", file=sys.stderr)
            continue
        for name, message in page_audit.engine_errors.items():
            applog.error("browser.engine_error", engine=name,
                         source=document.source, message=str(message)[:300])
            print(f"# {document.source}: {name} {message}", file=sys.stderr)
        # One function, shared with the window: axe and our own rule both
        # report a missing `alt` and a `--browser` run must not double every
        # such row, and a static finding the browser disproved must not reach
        # the merge at all. See `browser.merge_into_document`.
        browser_mod.merge_into_document(document, page_audit)
    # Again, because the findings the browser brought arrived after the crawl
    # attributed the ones it had. A second engine's finding is owned by
    # whoever emitted the element, exactly as the first engine's is.
    if getattr(result, "mode", "") == "web":
        from audit.engine import attribute_ownership

        attribute_ownership(result)


#: Extensions that make a file a page rather than a piece of a project.
PAGE_FILE_SUFFIXES = (".html", ".htm", ".xhtml")


def _is_page_file(target: str) -> bool:
    """Is this one HTML file rather than a folder or a URL?"""
    from pathlib import Path
    path = Path(target)
    return path.is_file() and path.suffix.lower() in PAGE_FILE_SUFFIXES


#: Last labels that read as a file suffix rather than a TLD. Everything the
#: scanner can open, plus the archive and document suffixes a person is most
#: likely to point at by mistake. Only consulted for a target with no slash
#: and no port - see `looks_like_url`.
_FILE_SUFFIXES = frozenset((
    ".html", ".htm", ".xhtml", ".xml", ".jsx", ".tsx", ".vue", ".svelte",
    ".js", ".ts", ".mjs", ".cjs", ".py", ".php", ".rb", ".erb", ".go",
    ".java", ".cs", ".json", ".yml", ".yaml", ".md", ".txt", ".css",
    ".scss", ".less", ".zip", ".tar", ".gz", ".pdf", ".png", ".jpg",
    ".jpeg", ".svg", ".webp", ".lock", ".log", ".toml", ".ini", ".cfg",
    ".sh", ".bak",
))

#: A bare host, with an optional port and path: `example.com`,
#: `www.example.co.uk/pricing`, `localhost:8000`, `127.0.0.1:8000/admin`.
#: Anchored, so a shell path never matches by accident. Built on first use.
_BARE_HOST = None


def _bare_host_pattern():
    """Compiled lazily and cached: `cmd_scan` never needs it."""
    global _BARE_HOST
    if _BARE_HOST is None:
        import re
        label = r"[A-Za-z0-9¡-￿](?:[A-Za-z0-9¡-￿-]*[A-Za-z0-9¡-￿])?"
        _BARE_HOST = re.compile(
            r"^(?:"
            # dotted host whose last label is a TLD-shaped word: example.com
            rf"{label}(?:\.{label})*\.[A-Za-z¡-￿]{{2,}}"
            # or a name that only makes sense with a port: localhost:8000
            rf"|{label}(?=:\d)"
            # or a dotted-quad address
            r"|\d{1,3}(?:\.\d{1,3}){3}"
            r")"
            r"(?::\d{1,5})?"      # optional port
            r"(?:[/?#].*)?$",     # optional path, query, fragment
            re.IGNORECASE)
    return _BARE_HOST


def looks_like_url(target: str) -> bool:
    """Is this target meant as a website rather than a path on disk?

    `https://example.com` is unambiguous; `example.com` is what people
    actually type, and answering it with `path not found: example.com` is
    the wrong answer to a question that had one obvious reading. So a target
    with no scheme is treated as a host when it *looks* like one and there
    is no such file or directory - an existing path always wins, so a folder
    genuinely named `example.com` still scans as a folder.

    Deliberately not "anything without a slash": `./src`, `src`, `~/repo`
    and `page.html` must keep resolving as paths, and a single word with no
    dot and no port is far more likely a typo'd directory than a hostname.
    """
    if not target:
        return False
    if target.startswith(("http://", "https://")):
        return True
    # Another scheme entirely (file://, ftp://, mailto:) is not ours to crawl.
    if "://" in target:
        return False
    from pathlib import Path
    try:
        if Path(target).exists():
            return False
    except OSError:
        pass  # a name too long or otherwise unopenable is not a path
    if target.startswith(("/", ".", "~")):
        return False
    if not _bare_host_pattern().match(target):
        return False
    # `page.html` matches the host shape - `.html` is TLD-shaped - but a
    # target with no slash, no port and a file suffix is a file the user
    # expected to find, and reporting it as an unreachable website would
    # hide the real answer: it is not there. A suffix inside a path
    # (`example.com/page.html`) is unaffected; the host is what is checked.
    host = target.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if ":" in host:
        return True
    import posixpath
    return posixpath.splitext(host)[1].lower() not in _FILE_SUFFIXES


def with_scheme(target: str) -> str:
    """`example.com` -> `https://example.com`; an explicit scheme is kept."""
    if target.startswith(("http://", "https://")):
        return target
    return "https://" + target


def _render_mode(args) -> str:
    """When to hand a page to a browser during the crawl.

    Defaults to following the browser pass: auditing a page means loading
    it for real, and a client-rendered site is precisely where the plain
    fetch finds nothing to audit. `--no-browser` turns both off together.
    `--render` overrides either way, because "audit what the server sends"
    is also a legitimate question.
    """
    from crawler import RENDER_AUTO, RENDER_NEVER

    explicit = getattr(args, "render", None)
    if explicit:
        return explicit
    if getattr(args, "no_browser", False):
        return RENDER_NEVER
    return RENDER_AUTO


def _crawl_maybe_rendering(target: str, config, progress_cb=None):
    """Crawl, starting a browser only if the configuration can use one."""
    from crawler import RENDER_NEVER, crawl

    if config.render_mode == RENDER_NEVER:
        return crawl(target, config, progress_cb=progress_cb)

    from audit import driver

    usable, reason = driver.available()
    if not usable:
        print(f"# Browser rendering unavailable: {reason}", file=sys.stderr)
        print(f"# SPA/React/Vue pages may return empty results.", file=sys.stderr)
        print(f"# Install PySide6 and QtWebEngine for full SPA support.", file=sys.stderr)
        return crawl(target, config, progress_cb=progress_cb)
    with driver.html_renderer() as render:
        return crawl(target, config, render=render, progress_cb=progress_cb)


def _browser_url(source: str) -> str:
    """The address the browser should open for a document.

    A crawled page already is a URL. A file has to become one, and it has to
    be absolute: `file://page.html` is not a path the browser can resolve.
    """
    if source.startswith(("http://", "https://", "file://")):
        return source
    from pathlib import Path
    return Path(source).resolve().as_uri()


def _wrap(text: str, width: int = 96, indent: str = "      ") -> str:
    """Fold a paragraph for terminal output; the explanations are written as
    prose, and prose at 400 columns is unreadable."""
    import textwrap
    lines = textwrap.wrap(text, width=width)
    return ("\n" + indent).join(lines)
