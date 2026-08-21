"""The browser pass: loading audited pages in a real browser, at one or
several viewport widths, and folding what it finds back into the static
result. Also the small pieces of crawl plumbing the audit command shares
with fullscan - when to render, how to turn a source into a URL.
"""
from __future__ import annotations

import sys


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


def _audit_at_widths(urls, options, sizes, progress=None) -> list:
    """One browser, every page, every width."""
    from audit import driver
    from audit import responsive
    from dataclasses import replace

    driver.ensure_headless_application()
    runner = driver.BrowserAuditRunner(
        replace(options, viewport=(sizes[0][1], sizes[0][2])))
    try:
        results = []
        for i, url in enumerate(urls, 1):
            if progress:
                progress(i, url)
            results.append(responsive.audit_responsive(url, sizes, options,
                                                       runner=runner))
        return results
    finally:
        runner.close()


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

    audits = (_audit_at_widths(urls, options, sizes, progress=_show) if sizes
              else driver.audit_urls(urls, options, progress=_show))
    by_url = {a.url: a for a in audits}
    for document, url in zip(targets, urls):
        page_audit = by_url.get(url)
        if page_audit is None:
            continue
        if page_audit.error:
            print(f"# {document.source}: {page_audit.error}", file=sys.stderr)
            continue
        for name, message in page_audit.engine_errors.items():
            print(f"# {document.source}: {name} {message}", file=sys.stderr)
        # Deduplicated against the static findings too, not just among
        # themselves: axe and our own rule both report a missing `alt`, and
        # a run with --browser must not double every such row.
        document.issues = browser_mod.deduplicate(
            list(document.issues) + list(page_audit.issues),
            markup=getattr(page_audit, "html", "") or "")


#: Extensions that make a file a page rather than a piece of a project.
PAGE_FILE_SUFFIXES = (".html", ".htm", ".xhtml")


def _is_page_file(target: str) -> bool:
    """Is this one HTML file rather than a folder or a URL?"""
    from pathlib import Path
    path = Path(target)
    return path.is_file() and path.suffix.lower() in PAGE_FILE_SUFFIXES


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
