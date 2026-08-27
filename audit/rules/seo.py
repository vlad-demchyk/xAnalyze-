"""SEO rules: whether a machine reading this page can tell what it is about.

Why these live next to the accessibility rules rather than in their own
tool: they are the same checks seen from a different angle. A `<title>`, a
`lang` attribute, a heading outline and image `alt` text are each
simultaneously how a screen reader user understands the page and how a
search engine does. Writing them twice would guarantee the two copies drift.

What is deliberately **not** here: anything that needs the network or an
account — rankings, backlinks, indexation status, competitor comparisons.
Those are a different product. These are the things a page either has in its
own markup or does not.
"""
from __future__ import annotations

import re

from ..base import (
    MINOR, MODERATE, NEEDS_BROWSER, SEO, SERIOUS, Issue, Rule, RuleRegistry,
    snippet_of,
)

_WHITESPACE_RE = re.compile(r"\s+")

# Practical limits, not standards: search results truncate around these, so
# past them the tail of the text simply is not shown to anyone.
TITLE_MIN, TITLE_MAX = 15, 60
DESCRIPTION_MIN, DESCRIPTION_MAX = 70, 160


def _text_of(tag) -> str:
    return _WHITESPACE_RE.sub(" ", " ".join(tag.stripped_strings)).strip()


class SeoRule(Rule):
    """Base, so the category is declared once for the module."""
    category = SEO


class TitleLength(SeoRule):
    id = "seo-title-length"
    web_only = True
    page_level = True
    severity = MODERATE

    def check(self, document, context) -> list:
        if document.find("html") is None:
            return []
        title = document.find("title")
        text = _text_of(title) if title is not None else ""
        if not text:
            return []  # a missing title is `document-title`, already reported
        if TITLE_MIN <= len(text) <= TITLE_MAX:
            return []
        selector, line = context.locate(title)
        return [Issue(
            rule_id=self.id, severity=self.severity, category=self.category,
            selector=selector, line=line, snippet=text[:120], source=context.source,
            details={"length": len(text), "min": TITLE_MIN, "max": TITLE_MAX,
                     "title": text[:120]},
        )]


class MetaDescription(SeoRule):
    id = "seo-meta-description"
    web_only = True
    page_level = True
    severity = MODERATE

    def check(self, document, context) -> list:
        if document.find("html") is None:
            return []
        for tag in document.find_all("meta"):
            if (tag.get("name") or "").lower() != "description":
                continue
            content = (tag.get("content") or "").strip()
            if not content:
                break
            if DESCRIPTION_MIN <= len(content) <= DESCRIPTION_MAX:
                return []
            selector, line = context.locate(tag)
            return [Issue(
                rule_id=self.id, severity=MINOR, category=self.category,
                selector=selector, line=line, snippet=content[:160],
                source=context.source,
                details={"length": len(content), "min": DESCRIPTION_MIN,
                         "max": DESCRIPTION_MAX, "present": True},
            )]
        return [Issue(
            rule_id=self.id, severity=self.severity, category=self.category,
            source=context.source, snippet="<head>…</head>",
            details={"length": 0, "min": DESCRIPTION_MIN, "max": DESCRIPTION_MAX,
                     "present": False},
            fix_snippet='<meta name="description" content="…">',
        )]


class CanonicalLink(SeoRule):
    id = "seo-canonical"
    web_only = True
    page_level = True
    severity = MODERATE

    def check(self, document, context) -> list:
        if document.find("html") is None:
            return []
        canonicals = [t for t in document.find_all("link")
                      if "canonical" in (t.get("rel") or [])]
        if len(canonicals) == 1:
            return []
        if not canonicals:
            return [Issue(
                rule_id=self.id, severity=self.severity, category=self.category,
                source=context.source, snippet="<head>…</head>",
                details={"count": 0},
                fix_snippet='<link rel="canonical" href="https://example.com/page">',
            )]
        # Two canonicals is worse than none: the engine picks one or ignores
        # both, and which one is not something the site controls.
        selector, line = context.locate(canonicals[1])
        return [Issue(
            rule_id=self.id, severity=SERIOUS, category=self.category,
            selector=selector, line=line, snippet=snippet_of(canonicals[1]),
            source=context.source, details={"count": len(canonicals)},
        )]


class RobotsNoindex(SeoRule):
    id = "seo-noindex"
    web_only = True
    page_level = True
    severity = SERIOUS

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all("meta"):
            if (tag.get("name") or "").lower() not in ("robots", "googlebot"):
                continue
            content = (tag.get("content") or "").lower()
            if "noindex" not in content and "nofollow" not in content:
                continue
            # Almost always a staging directive that shipped. Reported as
            # serious because nothing else on the page matters if it holds.
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, category=self.category,
                selector=selector, line=line, snippet=snippet_of(tag),
                source=context.source, details={"content": content[:120]},
            ))
        return issues


class OpenGraph(SeoRule):
    id = "seo-open-graph"
    web_only = True
    page_level = True
    severity = MINOR

    _REQUIRED = ("og:title", "og:description", "og:image")

    def check(self, document, context) -> list:
        if document.find("html") is None:
            return []
        present = {
            (t.get("property") or t.get("name") or "").lower()
            for t in document.find_all("meta")
        }
        missing = [p for p in self._REQUIRED if p not in present]
        if not missing:
            return []
        return [Issue(
            rule_id=self.id, severity=self.severity, category=self.category,
            source=context.source, snippet="<head>…</head>",
            details={"missing": missing},
            fix_snippet='<meta property="og:title" content="…">',
        )]


class StructuredData(SeoRule):
    id = "seo-structured-data"
    web_only = True
    page_level = True
    severity = MINOR

    def check(self, document, context) -> list:
        if document.find("html") is None:
            return []
        has_jsonld = any(
            (t.get("type") or "").lower() == "application/ld+json"
            for t in document.find_all("script")
        )
        has_microdata = document.find(attrs={"itemscope": True}) is not None
        if has_jsonld or has_microdata:
            return []
        return [Issue(
            rule_id=self.id, severity=self.severity, category=self.category,
            source=context.source, snippet="<head>…</head>", details={},
        )]


class ImagesMissingDimensions(SeoRule):
    """Also a performance and layout-stability problem — filed here because
    it is the same markup fix, and duplicating it across categories would
    make one page's report list the same image twice."""
    id = "seo-image-dimensions"
    severity = MINOR
    needs_external_css = True
    # An external stylesheet can still reserve the space this markup does
    # not - same ambiguity `perf-layout-shift` already marks honestly for
    # lazy images; this is its eager-image counterpart, on the same tags.
    confidence = NEEDS_BROWSER

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all("img"):
            style = (tag.get("style") or "").lower()
            if (tag.get("width") and tag.get("height")) or "aspect-ratio" in style:
                continue
            # Space reserved in the inline style is space reserved. Only
            # `aspect-ratio` was accepted, so `style="width:96px;height:96px"`
            # - which reserves the box exactly - was reported as reserving
            # nothing.
            if "width:" in style and "height:" in style:
                continue
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, category=self.category,
                selector=selector, line=line, snippet=snippet_of(tag),
                source=context.source, confidence=self.confidence,
                details={"src": (tag.get("src") or "")[:120]},
            ))
        return issues


class LinksWithoutText(SeoRule):
    id = "seo-empty-link"
    severity = MODERATE

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all("a", href=True):
            if _text_of(tag) or tag.find("img") is not None:
                continue
            if (tag.get("aria-label") or "").strip():
                continue
            if (tag.get("aria-labelledby") or "").strip():
                continue
            # A logo is an `<svg>`, not an `<img>`, and an `<svg>` names
            # itself with a `<title>` or an `aria-label`. Measured on
            # `ghost.org`, where every header and footer logo link came back
            # as an empty link - beside a `control-name` finding about the
            # same element, which is the rule that owns "this control has no
            # name". Two rows, one problem, and one of them wrong.
            svg = tag.find("svg")
            if svg is not None and (svg.find("title") is not None
                                    or (svg.get("aria-label") or "").strip()
                                    or (svg.get("aria-labelledby") or "").strip()):
                continue
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, category=self.category,
                selector=selector, line=line, snippet=snippet_of(tag),
                source=context.source, details={"href": (tag.get("href") or "")[:120]},
            ))
        return issues


for _rule in (TitleLength, MetaDescription, CanonicalLink, RobotsNoindex,
              OpenGraph, StructuredData, ImagesMissingDimensions, LinksWithoutText):
    RuleRegistry.register(_rule)
