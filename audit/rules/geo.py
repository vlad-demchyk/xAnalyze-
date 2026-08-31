"""GEO readiness signals that the document itself can establish.

Generative engines do not publish a stable ranking formula and no local tool
can truthfully predict whether an answer will cite a page. These checks
therefore never manufacture a score. They look only for machine-readable
article identity and provenance, two signals a publisher controls and an
assistant can use when it decides what a page is and who stands behind it.

An absent signal is a candidate for editorial review, not proof that a page
is wrong. The findings are deliberately `advisory`: no browser and no second
pass will settle whether a page ought to carry a byline, so labelling them
`needs-browser` would promise an answer that never arrives.
"""
from __future__ import annotations

import json

from ..base import ADVISORY, GEO, MINOR, Issue, Rule, RuleRegistry, snippet_of

_ARTICLE_TYPES = {"article", "newsarticle", "blogposting", "report"}


def _jsonld_nodes(document):
    """Yield JSON-LD objects, including objects inside a top-level graph.

    Invalid JSON-LD belongs to the SEO rule that owns syntax validation. GEO
    treats it as unavailable rather than emitting a second, less precise row.
    """
    for tag in document.find_all("script"):
        if (tag.get("type") or "").lower() != "application/ld+json":
            continue
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except (TypeError, ValueError):
            continue
        values = data if isinstance(data, list) else [data]
        for value in values:
            if not isinstance(value, dict):
                continue
            yield value
            graph = value.get("@graph")
            if isinstance(graph, list):
                yield from (node for node in graph if isinstance(node, dict))


def _types(node: dict) -> set[str]:
    value = node.get("@type")
    values = value if isinstance(value, list) else [value]
    return {str(item).strip().lower() for item in values if item}


def _has_article_microdata(document) -> bool:
    for tag in document.find_all(attrs={"itemtype": True}):
        type_url = str(tag.get("itemtype") or "").rstrip("/").lower()
        if type_url.rsplit("/", 1)[-1] in _ARTICLE_TYPES:
            return True
    return False


class GeoRule(Rule):
    """Base class for advisory, page-level GEO checks."""
    category = GEO
    severity = MINOR
    confidence = ADVISORY
    web_only = True
    page_level = True


class ArticleSchema(GeoRule):
    id = "geo-article-schema"

    def check(self, document, context) -> list:
        article = document.find("article")
        if article is None:
            return []
        if _has_article_microdata(document):
            return []
        if any(_types(node) & _ARTICLE_TYPES for node in _jsonld_nodes(document)):
            return []
        selector, line = context.locate(article)
        return [Issue(
            rule_id=self.id, severity=self.severity, category=self.category,
            confidence=self.confidence, selector=selector, line=line,
            snippet=snippet_of(article), source=context.source,
            details={},
        )]


class ArticleProvenance(GeoRule):
    id = "geo-article-provenance"

    def check(self, document, context) -> list:
        article = document.find("article")
        if article is None:
            return []
        nodes = [node for node in _jsonld_nodes(document)
                 if _types(node) & _ARTICLE_TYPES]
        has_author = (
            document.find("meta", attrs={"name": lambda value: (value or "").lower() == "author"})
            is not None
            or article.find(attrs={"itemprop": lambda value: (value or "").lower() == "author"})
            is not None
            or any(node.get("author") for node in nodes)
        )
        has_date = (
            article.find("time", attrs={"datetime": True}) is not None
            or document.find("meta", attrs={"property": lambda value: (value or "").lower() == "article:published_time"})
            is not None
            or article.find(attrs={"itemprop": lambda value: (value or "").lower() in ("datepublished", "datemodified")})
            is not None
            or any(node.get("datePublished") or node.get("dateModified") for node in nodes)
        )
        missing = [name for name, present in (("author", has_author),
                                              ("publication date", has_date))
                   if not present]
        if not missing:
            return []
        selector, line = context.locate(article)
        return [Issue(
            rule_id=self.id, severity=self.severity, category=self.category,
            confidence=self.confidence, selector=selector, line=line,
            snippet=snippet_of(article), source=context.source,
            details={"missing": ", ".join(missing)},
        )]


for _rule in (ArticleSchema, ArticleProvenance):
    RuleRegistry.register(_rule)
