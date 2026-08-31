"""What only a whole crawl can see.

Every rule in `audit.rules` reads one document, which makes a class of real
problem invisible by construction: the same `<title>` on forty pages is
perfectly valid markup on each of them and a broken site taken together. The
crawl already holds every page, so this costs nothing but the comparison.

Reported once, on the run, rather than once per page. Forty findings saying
"this title is also on thirty-nine other pages" would be the same inflation
`duplicates` exists to remove, arriving from a different direction.

Two things this does not do:

* **Report a duplicate as a duplicate when the pages are the same page.**
  A crawl that reached `/about` and `/about/` already collapses them, and
  what survives here is compared by final address.
* **Judge similarity.** Two titles are the same or they are not. "Nearly the
  same title" is a threshold nobody can defend, and the moment it exists
  someone tunes it.
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from .base import EXACT, Issue, MINOR, MODERATE, SEO

RULE_DUPLICATE_TITLE = "seo-duplicate-title"
RULE_DUPLICATE_DESCRIPTION = "seo-duplicate-description"
RULE_DUPLICATE_CANONICAL = "seo-duplicate-canonical"
RULE_HREFLANG_NOT_RECIPROCAL = "seo-hreflang-not-reciprocal"

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_META_DESC_RE = re.compile(
    r"""<meta[^>]+name\s*=\s*["']description["'][^>]*>""", re.I)
_CANONICAL_RE = re.compile(
    r"""<link[^>]+rel\s*=\s*["']canonical["'][^>]*>""", re.I)
_CONTENT_RE = re.compile(r"""content\s*=\s*["']([^"']*)["']""", re.I)
_HREF_RE = re.compile(r"""href\s*=\s*["']([^"']*)["']""", re.I)

#: Below this a run has nothing to compare. One page cannot duplicate itself,
#: and two pages sharing a title is a coincidence worth a minor note at most.
_MIN_PAGES = 2


def _first(pattern, markup: str, group_re=None) -> str:
    match = pattern.search(markup or "")
    if not match:
        return ""
    raw = match.group(0)
    if group_re is None:
        return " ".join(match.group(1).split())
    inner = group_re.search(raw)
    return " ".join(inner.group(1).split()) if inner else ""


def facts_of(markup: str) -> dict:
    """The three page-identity strings, as the served markup gives them."""
    return {
        "title": _first(_TITLE_RE, markup),
        "description": _first(_META_DESC_RE, markup, _CONTENT_RE),
        "canonical": _first(_CANONICAL_RE, markup, _HREF_RE),
    }


def _normal(url: str) -> str:
    parsed = urlsplit(url)
    path = parsed.path or "/"
    if len(path) > 1:
        path = path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path,
                       parsed.query, ""))


def _alternates(markup: str, base_url: str) -> list[dict]:
    """The declared language alternatives, resolved to fetchable URLs."""
    soup = BeautifulSoup(markup or "", "html.parser")
    links = []
    for tag in soup.find_all("link", href=True):
        if "alternate" not in (tag.get("rel") or []):
            continue
        language = (tag.get("hreflang") or "").strip().lower()
        if not language:
            continue
        links.append({"language": language,
                      "url": _normal(urljoin(base_url, tag["href"]))})
    return links


#: field -> (rule, severity). The canonical is the serious one: two pages
#: naming the same canonical are telling a search engine that one of them
#: does not exist, which is a request to be dropped rather than a missed
#: opportunity.
_FIELDS = {
    "title": (RULE_DUPLICATE_TITLE, MODERATE),
    "description": (RULE_DUPLICATE_DESCRIPTION, MINOR),
    "canonical": (RULE_DUPLICATE_CANONICAL, MODERATE),
}


def issues_for(pages) -> list:
    """One `Issue` per repeated value, naming every page that carries it."""
    readable = [p for p in pages
                if getattr(p, "raw_html", "") and not getattr(p, "error", None)]
    if len(readable) < _MIN_PAGES:
        return []

    seen: dict = {field: {} for field in _FIELDS}
    for page in readable:
        facts = facts_of(page.raw_html)
        for field, value in facts.items():
            if not value:
                continue  # absent is a different problem, and already reported
            seen[field].setdefault(value, []).append(page.url)

    issues = []
    for field, (rule, severity) in _FIELDS.items():
        for value, urls in seen[field].items():
            places = list(dict.fromkeys(urls))
            if len(places) < 2:
                continue
            issues.append(Issue(
                rule_id=rule, severity=severity, category=SEO, confidence=EXACT,
                source=places[0], selector="", line=None, snippet=value[:200],
                details={"value": value, "count": len(places),
                         "pages": places[:15]},
                engine="crawl"))
    # Reciprocity is only testable when both addresses were actually crawled.
    # A depth-limited run does not know whether an unvisited translation lacks
    # a return link, so it remains unknown rather than being called broken.
    by_url = {}
    for page in readable:
        by_url[_normal(page.url)] = page
        final = getattr(getattr(page, "diagnostics", None), "final_url", "") or ""
        if final:
            by_url[_normal(final)] = page
    reported = set()
    for page in readable:
        source_url = _normal(page.url)
        for alternate in _alternates(page.raw_html, page.url):
            target = by_url.get(alternate["url"])
            if target is None or target is page:
                continue
            target_links = _alternates(target.raw_html, target.url)
            if any(link["url"] == source_url for link in target_links):
                continue
            key = (source_url, alternate["url"], alternate["language"])
            if key in reported:
                continue
            reported.add(key)
            issues.append(Issue(
                rule_id=RULE_HREFLANG_NOT_RECIPROCAL, severity=MODERATE,
                category=SEO, confidence=EXACT, source=page.url,
                details={"language": alternate["language"],
                         "target": alternate["url"]}, engine="crawl"))
    return issues


def as_documents(pages) -> list:
    """The run-level findings, in one report addressed to the run."""
    from .engine import DocumentReport

    issues = issues_for(pages)
    if not issues:
        return []
    return [DocumentReport(source=issues[0].source, issues=issues,
                           elements_checked=len(pages))]
