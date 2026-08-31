"""Facts about whether the crawl could reach the pages a site links to.

This pass does not guess whether a URL *should* be indexed. It reports only
what the crawl itself established: an HTTP failure already reached by an
internal link, or a response header explicitly instructing search engines not
to index a page. URLs outside the bounded crawl remain unknown rather than
being called broken.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as etree
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from .base import EXACT, MODERATE, SEO, SERIOUS, Issue

#: How much of a declared sitemap is read before the answer is "too big".
#:
#: The body arrives from a site this tool is auditing, not from a source it
#: trusts, and the only thing being established is whether the file parses as
#: XML. Real sitemaps are capped at 50MB uncompressed by the protocol itself
#: and are almost always a tiny fraction of that; reading without a ceiling
#: means a hostile or broken endpoint decides how much memory this process
#: uses.
SITEMAP_BYTE_CAP = 4 * 1024 * 1024

#: An internal entity declaration, which is the whole of the "billion laughs"
#: shape. `xml.etree` does not resolve external entities, so a document that
#: declares none of these is safe to hand it; one that declares them is not
#: worth parsing to find out. Refusing here rather than adding `defusedxml`
#: keeps the dependency list as it is - the check needed is this narrow.
_ENTITY_DECLARATION = re.compile(r"<!ENTITY\b", re.IGNORECASE)


def _normal(url: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path or "/"
    if len(path) > 1:
        path = path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path,
                       parsed.query, ""))


def _same_origin(a: str, b: str) -> bool:
    return (urlsplit(a).scheme.lower(), urlsplit(a).netloc.lower()) == (
        urlsplit(b).scheme.lower(), urlsplit(b).netloc.lower())


def _site_root(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, "/", "", ""))


def _robots_disallows_root(text: str) -> bool:
    """Whether the generic robots group shuts the whole site out.

    This deliberately understands only the unambiguous global directive. A
    crawler-specific group can be intended for another bot, and treating it
    as a universal indexing verdict would be a false alarm.

    `Allow:` is part of that unambiguity, and reading `Disallow: /` without
    it was a SERIOUS false alarm on a very common shape:

        User-agent: *
        Disallow: /
        Allow: /public

    That site is not hiding; it is publishing a list. Every real crawler
    resolves the two by longest match, so a group that carries any `Allow:`
    is no longer making a global statement and this function says nothing
    about it. Under-reporting here is the cheap direction: the finding
    claims a site has forbidden its own indexing, which is worth saying only
    when it is certainly true.
    """
    agents: list[str] = []
    disallows_root = False
    allows_anything = False
    in_directives = False

    def verdict() -> bool:
        return disallows_root and not allows_anything

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if in_directives:
                if verdict():
                    return True
                agents = []
                disallows_root = False
                allows_anything = False
                in_directives = False
            agents.append(value.lower())
        elif key in ("allow", "disallow"):
            in_directives = True
            if "*" not in agents:
                continue
            if key == "disallow" and value == "/":
                disallows_root = True
            elif key == "allow" and value:
                allows_anything = True
    return verdict()


def _sitemap_urls(text: str, robots_url: str) -> list[str]:
    urls = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        if key.lower() == "sitemap" and value:
            urls.append(urljoin(robots_url, value))
    return urls


def _get(fetch, url: str, timeout: float):
    """Fetch one site-control file without following it somewhere else.

    `allow_redirects=False` because the same-origin check above is only worth
    something if the address checked is the address fetched. A same-origin
    sitemap answering `302` to any host would otherwise turn an untrusted
    `robots.txt` into a request proxy after all - the exact thing the origin
    check exists to prevent.

    A `fetch` that does not accept the argument is called without it: the
    parameter exists so tests can supply a two-line stub, and a stub is not
    the place this guarantee matters.
    """
    try:
        return fetch(url, timeout=timeout, allow_redirects=False)
    except TypeError:
        return fetch(url, timeout=timeout)


def _parses_as_xml(text: str) -> bool:
    """Whether a declared sitemap is XML, read under a ceiling.

    Two refusals rather than one verdict: a body past `SITEMAP_BYTE_CAP` and
    a body declaring internal entities are both reported as not parsing,
    because from the report's point of view they are the same fact - the
    site declared a sitemap this tool could not read.
    """
    if len(text.encode("utf-8", "replace")) > SITEMAP_BYTE_CAP:
        return False
    if _ENTITY_DECLARATION.search(text):
        return False
    try:
        etree.fromstring(text.encode("utf-8", "replace"))
    except etree.ParseError:
        return False
    return True


def site_control_issues(root_url: str, fetch=None, timeout: float = 10.0) -> list:
    """Inspect a declared robots file and same-origin sitemaps on request.

    Missing `robots.txt` and a sitemap that was never declared are not
    findings: both are valid for a small public site. A result is emitted
    only for an explicit universal crawl block, or a sitemap that the site's
    own robots file declares but cannot serve or parse. Cross-origin sitemap
    URLs are never fetched, avoiding an untrusted robots file becoming a
    request proxy.
    """
    fetch = fetch or requests.get
    robots_url = urljoin(_site_root(root_url), "robots.txt")
    try:
        robots_response = _get(fetch, robots_url, timeout)
    except requests.RequestException:
        return []
    status = getattr(robots_response, "status_code", None)
    if status != 200:
        return []
    robots_text = getattr(robots_response, "text", "") or ""
    issues = []
    if _robots_disallows_root(robots_text):
        issues.append(Issue(
            rule_id="seo-robots-root-disallowed", severity=SERIOUS,
            category=SEO, confidence=EXACT, source=robots_url,
            details={"path": "/"}, engine="robots.txt"))

    origin = _site_root(root_url)
    for sitemap_url in dict.fromkeys(_sitemap_urls(robots_text, robots_url)):
        if not _same_origin(origin, sitemap_url):
            continue
        try:
            response = _get(fetch, sitemap_url, timeout)
        except requests.RequestException:
            continue
        sitemap_status = getattr(response, "status_code", None)
        if not isinstance(sitemap_status, int) or sitemap_status >= 400:
            issues.append(Issue(
                rule_id="seo-sitemap-http-error", severity=MODERATE,
                category=SEO, confidence=EXACT, source=sitemap_url,
                details={"status": sitemap_status or "unknown"}, engine="sitemap"))
            continue
        if not _parses_as_xml(getattr(response, "text", "") or ""):
            issues.append(Issue(
                rule_id="seo-sitemap-invalid", severity=MODERATE,
                category=SEO, confidence=EXACT, source=sitemap_url,
                details={}, engine="sitemap"))
    return issues


def _anchors_of(pages_entry) -> list:
    """The page's anchors, read by whoever got there first.

    `PageResult.links` is `None` only when the producer does not extract
    them; the crawl fills it at every depth. So this parses markup as a
    fallback, not as the normal path - which is the point, because the same
    HTML was already read to find text blocks, to find links, and to run the
    rules, and a fourth pass here was a fourth full parse of every page.
    """
    links = getattr(pages_entry, "links", None)
    if links is not None:
        return list(links)
    markup = getattr(pages_entry, "raw_html", "") or ""
    if not markup:
        return []
    from crawler import _find_links
    return _find_links(markup, pages_entry.url)


def issues_for(pages) -> list:
    """Return crawl-established indexability and internal-link findings."""
    status_by_url = {}
    for page in pages:
        diagnostics = getattr(page, "diagnostics", None)
        status = getattr(diagnostics, "status_code", None)
        if not isinstance(status, int):
            continue
        status_by_url[_normal(page.url)] = status
        final_url = getattr(diagnostics, "final_url", "") or ""
        if final_url:
            status_by_url[_normal(final_url)] = status

    issues = []
    for page in pages:
        diagnostics = getattr(page, "diagnostics", None)
        status = getattr(diagnostics, "status_code", None)
        headers = dict(getattr(diagnostics, "headers", {}) or {})
        robots = (headers.get("x-robots-tag") or "").lower()
        if "noindex" in robots or "none" in robots:
            issues.append(Issue(
                rule_id="seo-x-robots-noindex", severity=SERIOUS,
                category=SEO, confidence=EXACT, source=page.url,
                details={"header": "x-robots-tag", "content": robots[:200]},
                engine="headers"))
        if isinstance(status, int) and status >= 400:
            issues.append(Issue(
                rule_id="seo-crawl-http-error", severity=SERIOUS,
                category=SEO, confidence=EXACT, source=page.url,
                details={"status": status}, engine="crawl"))

        if getattr(page, "error", None):
            continue
        for link in _anchors_of(page):
            target = _normal(urljoin(page.url, link.url))
            if not _same_origin(page.url, target):
                continue
            target_status = status_by_url.get(target)
            if not isinstance(target_status, int) or target_status < 400:
                continue
            issues.append(Issue(
                rule_id="seo-internal-link-failed", severity=MODERATE,
                category=SEO, confidence=EXACT, source=page.url,
                snippet=link.snippet,
                details={"href": link.href[:200], "target": target[:300],
                         "status": target_status}, engine="crawl"))
    return issues


def as_documents(pages, root_url: str = "", site_controls: bool = False) -> list:
    """Keep crawl-wide facts in one synthetic document for the report."""
    from .engine import DocumentReport

    issues = issues_for(pages)
    if site_controls and root_url:
        issues.extend(site_control_issues(root_url))
    if not issues:
        return []
    return [DocumentReport(source=issues[0].source, issues=issues,
                           elements_checked=len(pages))]
