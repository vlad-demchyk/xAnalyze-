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
RULE_SLUG_NOT_TRANSLATED = "seo-slug-not-translated"
RULE_UNTRANSLATED_CONTENT = "seo-untranslated-content"

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
    issues.extend(untranslated_slug_issues(pages))
    issues.extend(untranslated_content_issues(pages))
    return issues


#: A site has to have translated at least this many addresses before an
#: untranslated one is a gap rather than the house style. One translated pair
#: is a single editor's choice; several are a policy the site is failing to
#: apply everywhere.
_MIN_TRANSLATED_PAIRS = 2

#: A language code as it appears as a path segment.
_PATH_LANGUAGE_RE = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})?$", re.I)


def _x_default_url(markup: str, base_url: str) -> str:
    """The address the page names as its `x-default` alternative.

    `x-default` is the site's own statement about which version is the
    original. It is the only signal here that does not depend on how the
    addresses happen to be spelled, so it is asked first: `/index_en` and
    `/index_bg` carry their language as a suffix, and neither looks more like
    a translation than the other.
    """
    soup = BeautifulSoup(markup or "", "html.parser")
    for tag in soup.find_all("link", href=True):
        rels = tag.get("rel") or []
        if isinstance(rels, str):
            rels = [rels]
        if "alternate" not in [str(r).lower() for r in rels]:
            continue
        if (tag.get("hreflang") or "").strip().lower() == "x-default":
            return _normal(urljoin(base_url, tag["href"]))
    return ""


def _translation_of_the_pair(first, second):
    """Which of the two addresses is the translation, and which the source.

    The finding belongs on the translation: that is the page that was meant
    to change and did not. Three questions, in falling order of how much the
    site itself is saying:

    1. does either page declare the other as `x-default`;
    2. does exactly one address carry a language prefix;
    3. otherwise **nothing**, and the pair is left alone.

    The third answer is the important one. Measured on
    `european-union.europa.eu`, which declares no `x-default` and spells its
    languages as a suffix (`/index_en`, `/index_bg`): with a stable-order
    fallback the same string was reported against the English page, where an
    English label is correct. A finding pointed at the wrong page is worse
    than no finding, so where the site does not say which version is the
    original, this says nothing.

    :return: `(translation, source)`, or `None` when it cannot be told.
    """
    default = (_x_default_url(first.raw_html, first.url)
               or _x_default_url(second.raw_html, second.url))
    if default:
        if _normal(second.url) == default:
            return first, second
        if _normal(first.url) == default:
            return second, first
    first_prefixed = _has_language_prefix(first.url)
    second_prefixed = _has_language_prefix(second.url)
    if second_prefixed and not first_prefixed:
        return second, first
    if first_prefixed and not second_prefixed:
        return first, second
    return None


def _page_language(page) -> str:
    """The language a page declares for itself, lower-cased."""
    match = re.search(r"""<html[^>]*\slang\s*=\s*["']([^"']+)["']""",
                      getattr(page, "raw_html", "") or "", re.I)
    return match.group(1).strip().lower() if match else ""


def _has_language_prefix(url: str) -> bool:
    """Does the address start with a language segment?"""
    segments = [seg for seg in (urlsplit(url).path or "/").split("/") if seg]
    return bool(segments) and bool(_PATH_LANGUAGE_RE.match(segments[0]))


def _path_without_language(url: str) -> str:
    """The address's path with a leading language segment removed.

    `/de/veranstaltungen/` -> `/veranstaltungen`. Only the first segment is
    considered, and only when it reads as a language tag: a page really named
    `/en/` deep in a path is a page, not a prefix.
    """
    path = (urlsplit(url).path or "/")
    segments = [seg for seg in path.split("/") if seg]
    if segments and _PATH_LANGUAGE_RE.match(segments[0]):
        segments = segments[1:]
    return "/" + "/".join(segments)


def untranslated_slug_issues(pages) -> list:
    """Addresses left in the source language on a site that translates them.

    An identical path across two languages is not a defect by itself: plenty
    of sites keep one set of slugs on purpose, and reporting those would be
    this tool arguing with a strategy. What is a defect is a site that
    translates its addresses **and misses some** - the seven pages a human
    reviewer had to list by hand on a site whose other twenty were done.

    So the evidence is the site's own inconsistency, and the rule needs both
    halves before it says anything: proof that translating slugs is the
    policy here, and the addresses that escaped it.
    """
    readable = [p for p in pages
                if getattr(p, "raw_html", "") and not getattr(p, "error", None)]
    if len(readable) < _MIN_PAGES:
        return []

    by_url = {_normal(p.url): p for p in readable}
    translated = 0
    untranslated: dict = {}
    for page in readable:
        here = _normal(page.url)
        for alternate in _alternates(page.raw_html, page.url):
            target = by_url.get(alternate["url"])
            if target is None or target is page:
                continue
            # One unordered pair, judged once: A->B and B->A are the same
            # comparison and must not count twice towards the evidence.
            if here > alternate["url"]:
                continue
            if _path_without_language(page.url) != _path_without_language(alternate["url"]):
                translated += 1
                continue
            # The finding belongs on the version that failed to translate,
            # not on whichever of the two sorts first. The default language
            # is the one served without a prefix, so the prefixed address is
            # the translation - and the one still carrying the other's slug.
            decided = _translation_of_the_pair(page, target)
            if decided is None:
                continue
            subject, other = decided
            untranslated[(_normal(subject.url), _normal(other.url))] = (
                _page_language(other) or alternate["language"])

    if translated < _MIN_TRANSLATED_PAIRS or not untranslated:
        return []
    return [Issue(
        rule_id=RULE_SLUG_NOT_TRANSLATED, severity=MINOR, category=SEO,
        confidence=EXACT, source=source, engine="crawl",
        details={"language": language, "target": target,
                 "translated": translated})
        for (source, target), language in sorted(untranslated.items())]


#: Text-bearing elements worth comparing between two language versions.
#: Chrome and prose both, because both were found untranslated by hand: a
#: breadcrumb crumb, a filter option, and a whole paragraph left in the
#: source language inside an otherwise translated page.
_COMPARABLE_TAGS = (
    "title", "h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "a", "button",
    "option", "label", "th", "figcaption", "summary", "blockquote", "dt", "dd",
)

#: Below this a string is not a sentence and not a translatable label. Two
#: words is where proper nouns live - street names, organisations, brands -
#: and the reviewer's own report says those are *supposed* to stay in the
#: source language. Three words keeps every real case that was found by hand
#: ("Dentro le mura", "Vivere il comune", "Scuola Secondaria di I grado")
#: and drops the class that would be wrong to report.
_MIN_WORDS_TO_COMPARE = 3

#: And above this a string is an article headline or a paragraph of news,
#: not a label. Measured on `european-union.europa.eu`, whose home page
#: repeats its English news items on every language version by editorial
#: policy: without a cap this rule reported sixteen of them as defects on a
#: site that has not made a mistake. Every case that was found by hand is a
#: piece of interface - a crumb, a filter option, a section title - and the
#: longest of them is five words.
_MAX_WORDS_TO_COMPARE = 8

#: The pair has to look translated before a match inside it means anything.
_MIN_DIFFERING_STRINGS = 5
#: And the matches have to be the exception rather than the rule; above this
#: the two addresses are the same content served twice, which is a different
#: finding and not this one's business.
_MAX_IDENTICAL_SHARE = 0.5

_COLLAPSE_WS_RE = re.compile(r"\s+")
#: A run of four or more digits is a postal code, a year range or a
#: reference number, and the string around it is an address or a citation:
#: those are identical across languages on purpose. Narrow on purpose - it
#: must not swallow a shouted title like "FORTRESS CITY OF UNESCO", which is
#: exactly the kind of untranslated string this rule exists to find.
_REFERENCE_NUMBER_RE = re.compile(r"\d{4,}")

_NOT_PROSE_RE = re.compile(
    r"""^(?:[\d\s.,:;/|+()\-–—]*|\S+@\S+|(?:https?:)?//\S+|[^\w\s]+)$""")


def _comparable_strings(markup: str) -> dict:
    """Structural position -> text, for the strings worth comparing.

    Keyed by position rather than by text so the two documents are compared
    element against element: the same crumb in the same place, not "does this
    string appear anywhere on the other page".
    """
    soup = BeautifulSoup(markup or "", "html.parser")
    found: dict = {}
    counters: dict = {}
    for element in soup.find_all(_COMPARABLE_TAGS):
        parent = element.parent.name if element.parent else ""
        key_base = f"{parent}>{element.name}"
        index = counters.get(key_base, 0)
        counters[key_base] = index + 1
        text = _COLLAPSE_WS_RE.sub(" ", element.get_text(" ", strip=True)).strip()
        if not text or _NOT_PROSE_RE.match(text):
            continue
        if _REFERENCE_NUMBER_RE.search(text):
            continue
        words = len(text.split())
        if words < _MIN_WORDS_TO_COMPARE or words > _MAX_WORDS_TO_COMPARE:
            continue
        found[f"{key_base}[{index}]"] = text
    return found


def untranslated_content_issues(pages) -> list:
    """Text that stayed the same on a page whose other text was translated.

    The comparison is exact - two strings are identical or they are not -
    and the judgement is left to the surrounding evidence: this speaks only
    when the same page in another language differs almost everywhere else.
    An identical string on a pair that is identical throughout is two
    addresses serving one page, which `seo-duplicate-title` and the canonical
    rules already describe.

    What it deliberately cannot see: a two-word proper noun. Street names and
    the names of organisations are meant to survive translation, and a rule
    that reported those would be arguing with the house style of every
    multilingual site.
    """
    readable = [p for p in pages
                if getattr(p, "raw_html", "") and not getattr(p, "error", None)]
    if len(readable) < _MIN_PAGES:
        return []

    by_url = {_normal(p.url): p for p in readable}
    texts: dict = {}
    issues = []
    seen = set()
    for page in readable:
        here = _normal(page.url)
        for alternate in _alternates(page.raw_html, page.url):
            target = by_url.get(alternate["url"])
            if target is None or target is page:
                continue
            if here > alternate["url"]:
                continue  # one unordered pair, judged once
            for candidate in (page, target):
                if candidate.url not in texts:
                    texts[candidate.url] = _comparable_strings(candidate.raw_html)
            mine, theirs = texts[page.url], texts[target.url]
            shared = set(mine) & set(theirs)
            if not shared:
                continue
            identical = sorted(k for k in shared if mine[k] == theirs[k])
            differing = len(shared) - len(identical)
            if differing < _MIN_DIFFERING_STRINGS:
                continue
            if len(identical) / len(shared) > _MAX_IDENTICAL_SHARE:
                continue
            # The finding belongs on the translation, i.e. the address that
            # carries a language prefix, for the same reason as the slug rule.
            decided = _translation_of_the_pair(page, target)
            if decided is None:
                continue
            subject, other = decided
            for key in identical:
                text = mine[key]
                if (subject.url, text) in seen:
                    continue  # one string, named once, however many nodes hold it
                seen.add((subject.url, text))
                issues.append(Issue(
                    rule_id=RULE_UNTRANSLATED_CONTENT, severity=MODERATE,
                    category=SEO, confidence=EXACT, source=subject.url,
                    engine="crawl",
                    details={"text": text[:160], "where": key,
                             "language": _page_language(other) or alternate["language"],
                             "target": _normal(other.url), "translated": differing}))
    return issues


def as_documents(pages, root_url: str = "") -> list:
    """One document per address, and the run-level ones addressed to the run.

    A repeated title belongs to the page that repeats it, and that is what
    `source` on each issue already says. Handing them all back under the
    first page's address made that page look like the site's worst - the
    same miscount `crawlability.as_documents` carried, and for the same
    reason.

    `root_url`, when given, is where a finding with no page of its own goes.
    """
    from .engine import DocumentReport

    issues = issues_for(pages)
    if not issues:
        return []
    by_source: dict = {}
    for issue in issues:
        by_source.setdefault(issue.source or root_url, []).append(issue)
    return [DocumentReport(source=source, issues=found, elements_checked=1)
            for source, found in by_source.items()]
