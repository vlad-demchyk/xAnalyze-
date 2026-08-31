"""Same-domain page crawler with a configurable link-depth limit.

Depth semantics:
  depth=0  -> only the given URL is fetched.
  depth=1  -> the given URL plus every same-domain page it links to.
  depth=N  -> follow links N hops away from the root URL.

Only same-domain links are followed so the crawl can't wander off the
target site. A hard page-count cap protects against accidentally crawling
a huge site.

## Why a page can come back empty

This crawler makes one plain HTTP request per page and reads the HTML that
comes back. It runs no JavaScript — there is no browser in the loop, by
design: rendering every page would turn a fast scan into a slow one and
pull a headless browser into the dependency list. The cost of that choice
is that several very different situations all end in "no text found", and
telling them apart is not something the user can do by looking at an empty
list.

So every page carries a `PageDiagnostics` record explaining which of these
happened:

* `js-rendered` — the response is an application shell (`<div id="root">`
  and a bundle) and the copy is written into the DOM by the browser. This
  is the single most common cause, and nothing here can fix it; the honest
  answer is "point the scanner at the rendered HTML, or at the repository
  that produces it" (repository mode exists partly for this).
* `blocked` — the server answered, but with a bot check or a consent wall
  rather than the page. Detectable by status code, or by a body that is all
  markup and no copy.
* `not-html` — a PDF, an image, a JSON endpoint. Previously these vanished
  from the result list entirely, which read as "crawled, nothing found".
* `too-short` — real copy was extracted, but every block was under
  `MIN_BLOCK_LEN`. Common on navigation-only pages and link hubs.
* `no-text` — the markup genuinely has no text nodes worth reading.
* `error` — the request failed outright (DNS, TLS, timeout, 5xx).

Text extraction itself also gained a fallback: copy that sits directly in a
`<div>` or `<section>`, with no paragraph tag around it, used to be missed
entirely because those tags aren't in `CANDIDATE_TAGS` — and adding them as
ordinary candidates would capture every wrapper element's concatenated
text. `_leaf_container_blocks` picks up only containers whose own direct
text is the copy, which keeps the wrappers out.
"""
from __future__ import annotations

import re
import uuid
from collections import deque
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString

from lang_detect import guess_language_safe
import applog
from models import PageDiagnostics, PageResult, TextBlock

USER_AGENT = "AIContentScanner/0.1 (+https://example.local)"

# Tags whose text content is never "content" a visitor reads.
SKIP_TAGS = {
    "script", "style", "noscript", "template", "svg", "path", "iframe",
    "head", "meta", "link",
}

# Minimum visible-text length (characters) for a block to be worth analysing.
MIN_BLOCK_LEN = 20

# Diagnostic reason codes; the UI maps each to a translated sentence.
EMPTY_JS_RENDERED = "js-rendered"
EMPTY_BLOCKED = "blocked"
EMPTY_NOT_HTML = "not-html"
EMPTY_TOO_SHORT = "too-short"
EMPTY_NO_TEXT = "no-text"
EMPTY_REDIRECTED = "redirected"
# The redirect landed on a page this crawl has already read. Recorded
# rather than dropped: a URL that vanishes from the report is
# indistinguishable from one nobody tried.
EMPTY_ALREADY_SEEN = "already-seen"
EMPTY_ERROR = "error"

# Markers that identify a client-rendered application shell. Matched against
# the raw HTML, so they work whether or not the framework left a comment.
_FRAMEWORK_MARKERS = (
    ("next", re.compile(r"__NEXT_DATA__|/_next/static", re.IGNORECASE)),
    ("nuxt", re.compile(r"__NUXT__|/_nuxt/", re.IGNORECASE)),
    ("sveltekit", re.compile(r"__sveltekit|/_app/immutable", re.IGNORECASE)),
    ("angular", re.compile(r"<app-root|ng-version=", re.IGNORECASE)),
    ("vue", re.compile(r"data-v-app|id=[\"']app[\"'][^>]*>\s*</div>", re.IGNORECASE)),
    ("react", re.compile(r"id=[\"'](root|__next)[\"']", re.IGNORECASE)),
)

# Status codes that mean "the server refused to show you the page" rather
# than "the page has no text". 403 and 429 are the usual bot-check answers;
# 401 is an auth wall.
_BLOCKED_STATUSES = {401, 403, 405, 429}

_TAG_RE = re.compile(r"<[^>]+>")


#: When to hand a page to a browser instead of reading the fetch.
#:
#: `never` is the historical behaviour and the fast one. `always` renders every
#: page. `auto` is the useful default: fetch first, and render only the pages
#: whose fetch came back as an application shell - which is exactly the case
#: the diagnostics already detect and could previously only report.
RENDER_NEVER = "never"
RENDER_AUTO = "auto"
RENDER_ALWAYS = "always"

#: Recorded on a page whose text and links came from a browser, not the fetch.
#: Kept as a reason rather than a silent substitution: "this page had to be
#: rendered to be read" is a fact about the site worth showing.
RENDERED = "rendered"


@dataclass
class CrawlConfig:
    max_depth: int = 1
    max_pages: int = 30
    timeout: float = 10.0
    render_timeout: float = 30.0
    same_domain_only: bool = True
    render_mode: str = RENDER_NEVER


def _normalize(url: str) -> str:
    parsed = urlparse(url)
    # Drop fragments; keep query since some sites route content via query params.
    # Collapse a trailing slash so `/about/` and `/about` dedupe into one page;
    # the root keeps its slash so `https://site` and `https://site/` also meet.
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return parsed._replace(path=path, fragment="").geturl()


def _host_key(url: str) -> str:
    """The host, in the form two URLs can be compared by.

    Case and the default port are noise; `www.` is the part that matters. A
    site that redirects its apex to `www` links to itself under both names, and
    comparing `netloc` literally made those two names two different sites - so
    a crawl that started at the apex followed nothing at all, and the emptiness
    looked like a site without links.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    port = parsed.port
    default = {"http": 80, "https": 443}.get(parsed.scheme, None)
    if port and port != default:
        return f"{host}:{port}"
    return host


def _same_domain(a: str, b: str) -> bool:
    return _host_key(a) == _host_key(b)


def _should_render(mode: str, diagnostics) -> bool:
    """Is this page worth handing to a browser?"""
    if mode == RENDER_ALWAYS:
        return True
    if mode != RENDER_AUTO:
        return False
    # Exactly the cases where reading the fetch produced nothing to read. A
    # page that came back with its copy in it is not rendered again: it would
    # cost seconds per page to confirm what is already known.
    return (EMPTY_JS_RENDERED in diagnostics.reasons
            or not diagnostics.blocks_kept)


CANDIDATE_TAGS = [
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "a", "button",
    "span", "figcaption", "blockquote", "td", "th", "label",
]

# Containers that often hold copy directly, with no paragraph tag inside.
# Only their *own* text nodes are read (see `_leaf_container_blocks`), never
# the concatenation of their children — otherwise a page wrapper would come
# back as one enormous "block" containing the whole page.
CONTAINER_TAGS = ["div", "section", "article", "dd", "dt", "figure", "summary", "caption"]


def _extract_text_blocks(html: str, page_url: str,
                          diagnostics: PageDiagnostics | None = None) -> list[TextBlock]:
    soup = BeautifulSoup(html, "html.parser")
    blocks: list[TextBlock] = []
    dropped_short = 0
    dropped_dup = 0

    # Walk block-level-ish containers so each highlighted chunk maps to a
    # coherent piece of UI copy (heading, paragraph, button label, list item...)
    candidates = soup.find_all(CANDIDATE_TAGS)

    # Normalized text per candidate, computed exactly once. The previous
    # version rebuilt each ancestor's text with a fresh stripped_strings
    # join inside the per-candidate loop, which re-walked the same subtrees
    # over and over on deep pages.
    texts: dict[int, str] = {}
    for tag in candidates:
        texts[id(tag)] = re.sub(r"\s+", " ", " ".join(tag.stripped_strings)).strip()

    for tag in candidates:
        text = texts[id(tag)]
        if tag.find_parent(SKIP_TAGS):
            continue
        if len(text) < MIN_BLOCK_LEN:
            if text:
                dropped_short += 1
            continue

        # Skip a node when an ancestor candidate carries exactly the same
        # text (e.g. <li><a>same words</a></li> would otherwise be captured
        # twice). Deliberately identity-based: two *separate* elements that
        # happen to share wording are both kept, because the user needs to
        # review and fix every occurrence on the page, not just the first.
        parent_dup = False
        for parent in tag.parents:
            parent_text = texts.get(id(parent))
            if parent_text is not None and parent_text == text:
                parent_dup = True
                break
        if parent_dup:
            dropped_dup += 1
            continue

        blocks.append(_make_block(tag, text, page_url))

    covered = {id(tag) for tag in candidates}
    extra, extra_short = _leaf_container_blocks(soup, page_url, covered)
    blocks.extend(extra)
    dropped_short += extra_short

    if diagnostics is not None:
        diagnostics.candidates_found = len(candidates)
        diagnostics.blocks_kept = len(blocks)
        diagnostics.dropped_too_short = dropped_short
        diagnostics.dropped_duplicate = dropped_dup
    return blocks


def _leaf_container_blocks(soup, page_url: str, covered: set) -> tuple[list[TextBlock], int]:
    """Copy sitting directly inside a `<div>`/`<section>`/... with no inner
    tag of its own — `<div class="lead">Some sentence.</div>`.

    Only the container's *direct* text children are read, and only when the
    container has no candidate descendant already carrying that text, so a
    page-level wrapper never turns into one giant block.
    """
    blocks: list[TextBlock] = []
    dropped_short = 0
    for tag in soup.find_all(CONTAINER_TAGS):
        if tag.find_parent(SKIP_TAGS):
            continue
        own_text = " ".join(
            str(child) for child in tag.children if isinstance(child, NavigableString)
        )
        own_text = re.sub(r"\s+", " ", own_text).strip()
        if not own_text:
            continue
        if len(own_text) < MIN_BLOCK_LEN:
            dropped_short += 1
            continue
        if id(tag) in covered:
            continue
        blocks.append(_make_block(tag, own_text, page_url))
    return blocks, dropped_short


def _make_block(tag, text: str, page_url: str) -> TextBlock:
    return TextBlock(
        block_id=str(uuid.uuid4()),
        page_url=page_url,
        dom_path=_dom_path(tag),
        text=text,
        # Tagged here so a rewrite request can tell the model which language
        # to answer in. `guess_language_safe`, not `guess_language`: the
        # difference is what happens to a string too short to read. The
        # unsafe one answers "en", which is a fallback wearing the clothes of
        # a reading, and it is what every consumer downstream then believes.
        # Measured 2026-08-31 on a live Italian page: 29 of 71 blocks were
        # tagged `en` while `guess_language_safe` said `None`, so short
        # Italian strings were judged by the English cliché list and would
        # have been handed to the rewrite provider as English. `None` is the
        # honest answer and the one every consumer already knows how to
        # handle - the detectors check every list, and `prompt_language`
        # names no language rather than the wrong one.
        language_hint=guess_language_safe(text),
    )


def _dom_path(tag) -> str:
    """Build a CSS selector for `tag`.

    Sibling position is found by identity (`is`), not by list.index(): bs4
    Tags compare equal by *content*, so index() would return the position
    of the first same-named sibling with matching markup and silently
    produce a selector pointing at the wrong element.
    """
    parts = []
    node = tag
    while node is not None and getattr(node, "name", None) not in (None, "[document]"):
        idx = 1
        if node.parent is not None:
            siblings = node.parent.find_all(node.name, recursive=False)
            for i, sibling in enumerate(siblings):
                if sibling is node:
                    idx = i + 1
                    break
        parts.append(f"{node.name}:nth-of-type({idx})")
        node = node.parent
    return " > ".join(reversed(parts))


def _find_links(html: str, page_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        links.append(_normalize(urljoin(page_url, href)))
    return links


# ------------------------------------------------------------- diagnostics

def _detect_framework(html: str) -> str:
    for name, pattern in _FRAMEWORK_MARKERS:
        if pattern.search(html):
            return name
    return ""


def _text_ratio(html: str) -> float:
    """Share of the response that is visible text rather than markup. An
    application shell sits near zero; a content page is typically well
    above 0.1."""
    if not html:
        return 0.0
    stripped = _TAG_RE.sub(" ", html)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return len(stripped) / len(html)


def _diagnose(diag: PageDiagnostics, url: str, html: str, blocks: list) -> None:
    """Fill in `diag.reasons` — only meaningful when nothing was extracted,
    but the measurements are recorded either way so a thin page can be
    explained too."""
    diag.html_bytes = len(html)
    diag.text_ratio = round(_text_ratio(html), 4)
    diag.js_framework = _detect_framework(html)
    diag.has_noscript_notice = "<noscript" in html.lower()

    if (diag.final_url and _normalize(diag.final_url) != _normalize(url)
            and EMPTY_REDIRECTED not in diag.reasons):
        diag.reasons.append(EMPTY_REDIRECTED)
    if blocks:
        return

    if diag.status_code in _BLOCKED_STATUSES:
        diag.reasons.append(EMPTY_BLOCKED)
    if diag.js_framework or (diag.text_ratio < 0.05 and diag.html_bytes > 500):
        diag.reasons.append(EMPTY_JS_RENDERED)
    elif diag.dropped_too_short and not diag.blocks_kept:
        diag.reasons.append(EMPTY_TOO_SHORT)
    elif not diag.candidates_found or diag.text_ratio < 0.01:
        diag.reasons.append(EMPTY_NO_TEXT)
    else:
        diag.reasons.append(EMPTY_TOO_SHORT)


def page_from_html(html: str, url: str, depth: int = 0) -> PageResult:
    """One page's worth of result, built from HTML somebody else obtained.

    The crawl is the usual way to get HTML, but not the only one: a single
    local file opened in a browser has no crawl to be part of - there is one
    document, already rendered, and `requests` cannot even fetch it (it does
    not speak `file://`). Extracting and diagnosing it still has to happen the
    same way, so that path is this function rather than a second copy of the
    body of `crawl`.
    """
    diagnostics = PageDiagnostics()
    diagnostics.final_url = url
    diagnostics.html_bytes = len(html or "")
    diagnostics.reasons = [RENDERED]
    blocks = _extract_text_blocks(html or "", url, diagnostics)
    _diagnose(diagnostics, url, html or "", blocks)
    return PageResult(url=url, depth=depth, blocks=blocks, raw_html=html,
                      diagnostics=diagnostics)


def crawl(root_url: str, config: CrawlConfig | None = None, progress_cb=None,
          render=None, walk=None) -> list[PageResult]:
    """Breadth-first crawl starting at root_url up to config.max_depth hops.

    progress_cb, if given, is called as progress_cb(url, depth) right before
    each page is fetched, so a UI can show live progress.

    render, if given, is called as render(url) and returns the DOM a browser
    built, or "" when it could not. It is injected rather than imported so the
    crawler keeps no opinion about which browser, and stays importable without
    Qt: the walk is the crawler's job, and rendering is one way of reading a
    page. `config.render_mode` decides when it is called at all.

    walk, if given, is a `models.CrawlDiagnostics` filled in as the crawl
    ends. Passed in rather than returned so every existing caller keeps
    working unchanged - the same shape `PageDiagnostics` already uses. What
    it records is what the crawl did *not* reach: one that stopped at its
    page limit leaves a queue behind, and once the results are a list of
    `PageResult` those addresses are gone. "30 pages, no findings" then
    reads as a verdict on the site rather than on the thirty.

    Named `walk` and not `diagnostics` for a reason worth keeping: the loop
    below binds `diagnostics` to a fresh `PageDiagnostics` on every page, so
    a parameter of that name is shadowed by the first iteration. It was, and
    the end-of-crawl numbers went onto the last page's diagnostics instead -
    silently, because both objects take an attribute assignment happily.
    """
    config = config or CrawlConfig()
    root_url = _normalize(root_url)

    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(root_url, 0)])
    results: list[PageResult] = []
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    while queue and (config.max_pages == 0 or len(results) < config.max_pages):
        url, depth = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        if progress_cb:
            progress_cb(url, depth)

        diagnostics = PageDiagnostics()
        try:
            resp = session.get(url, timeout=config.timeout)
            diagnostics.status_code = resp.status_code
            diagnostics.final_url = resp.url
            diagnostics.content_type = resp.headers.get("Content-Type", "")
            diagnostics.headers = {k.lower(): v for k, v in resp.headers.items()}
            applog.debug("crawl.page", url=url, depth=depth,
                         status=resp.status_code,
                         type=diagnostics.content_type[:40])
            resp.raise_for_status()
            content_type = diagnostics.content_type
            if "text/html" not in content_type and not content_type.startswith("text/"):
                # Recorded rather than skipped. Dropping it silently was
                # indistinguishable from a page that was crawled and found
                # clean, which is exactly the confusion this whole
                # diagnostics path exists to remove.
                diagnostics.reasons.append(EMPTY_NOT_HTML)
                results.append(PageResult(url=url, depth=depth, diagnostics=diagnostics))
                continue
            html = resp.text
            landing = _normalize(resp.url)
            if landing != _normalize(url):
                # Three URLs redirecting to one page are one page. Analysing
                # the landing page once per address counted the same copy
                # three times, spent three AI calls on it, and reported a
                # site larger than it is.
                diagnostics.reasons.append(EMPTY_REDIRECTED)
                if landing in visited:
                    diagnostics.reasons.append(EMPTY_ALREADY_SEEN)
                    results.append(
                        PageResult(url=url, depth=depth, diagnostics=diagnostics))
                    continue
                visited.add(landing)
                # Links on the page are relative to where it landed, not to
                # where it was asked for.
                url_base = resp.url
            else:
                url_base = url
        except requests.RequestException as exc:
            applog.warning("crawl.page_failed", url=url, depth=depth,
                           error=f"{type(exc).__name__}: {exc}")
            diagnostics.reasons.append(EMPTY_ERROR)
            results.append(
                PageResult(url=url, depth=depth, error=str(exc), diagnostics=diagnostics)
            )
            continue

        blocks = _extract_text_blocks(html, url, diagnostics)
        _diagnose(diagnostics, url, html, blocks)

        # The page was read as it arrived. If that reading is empty because the
        # copy is written by JavaScript, the browser is the only reader that can
        # answer - and the fetch already said so.
        if render is not None and _should_render(config.render_mode, diagnostics):
            rendered = ""
            try:
                import signal

                def _timeout_handler(signum, frame):
                    raise TimeoutError(f"render timed out after {config.render_timeout}s")

                old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
                signal.setitimer(signal.ITIMER_REAL, config.render_timeout)
                try:
                    rendered = render(url) or ""
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    signal.signal(signal.SIGALRM, old_handler)
            except (TimeoutError, Exception) as exc:  # noqa: BLE001
                diagnostics.render_error = str(exc)
            if rendered:
                html = rendered
                diagnostics.html_bytes = len(rendered)
                # Re-diagnosed from scratch: the reasons recorded a moment ago
                # described the shell, and every one of them may now be false.
                diagnostics.reasons = [RENDERED]
                blocks = _extract_text_blocks(html, url, diagnostics)
                _diagnose(diagnostics, url, html, blocks)

        results.append(
            PageResult(url=url, depth=depth, blocks=blocks, raw_html=html,
                       diagnostics=diagnostics)
        )

        if depth < config.max_depth:
            for link in _find_links(html, url_base):
                if link in visited:
                    continue
                if config.same_domain_only and not _same_domain(link, root_url):
                    continue
                queue.append((link, depth + 1))

    if walk is not None:
        walk.pages_read = len(results)
        walk.limit = config.max_pages
        # What is still queued, minus anything already visited: the queue
        # holds links as they were found, and a page linked from three
        # others is in it three times. Counting the raw length would report
        # a site three times larger than it is.
        remaining = {url for url, _depth in queue if url not in visited}
        walk.queued_when_stopped = len(remaining)
    return results
