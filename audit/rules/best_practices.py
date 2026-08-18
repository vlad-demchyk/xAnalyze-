"""Best-practice rules: things that are not yet broken.

The other three categories describe a person who cannot use the page. This
one describes a page that is one small change away from that: a mixed-content
image that a stricter browser will block next year, a `target="_blank"`
without `rel="noopener"` that hands another site a handle on this one, a
character encoding the browser has to guess.

Nothing here is urgent on its own, which is exactly why it needs writing
down — these are the findings that never get noticed until something else
breaks and this turns out to be why.
"""
from __future__ import annotations

import re

from ..base import (
    BEST_PRACTICES, MINOR, MODERATE, SERIOUS, Issue, Rule, RuleRegistry,
    snippet_of,
)

_INSECURE_URL_RE = re.compile(r"^http://", re.IGNORECASE)


class BestPracticeRule(Rule):
    category = BEST_PRACTICES


class MixedContent(BestPracticeRule):
    id = "bp-mixed-content"
    severity = SERIOUS

    def check(self, document, context) -> list:
        if not context.source.lower().startswith("https://"):
            return []  # only mixed *on an HTTPS page* is mixed content
        issues = []
        for tag in document.find_all(("img", "script", "iframe", "audio", "video",
                                      "source", "link")):
            url = tag.get("src") or tag.get("href") or ""
            if not _INSECURE_URL_RE.match(url):
                continue
            # Browsers already block insecure scripts and are steadily
            # tightening on images. The page works today and stops working
            # on a browser update nobody here controls.
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, category=self.category,
                selector=selector, line=line, snippet=snippet_of(tag),
                source=context.source,
                details={"element": tag.name, "url": url[:120]},
                fix_snippet=snippet_of(tag).replace("http://", "https://", 1),
            ))
        return issues


class TargetBlankWithoutNoopener(BestPracticeRule):
    id = "bp-target-blank"
    severity = MODERATE

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all("a", href=True):
            if (tag.get("target") or "").lower() != "_blank":
                continue
            rel = {r.lower() for r in (tag.get("rel") or [])}
            if "noopener" in rel or "noreferrer" in rel:
                continue
            # The opened page gets a reference back through window.opener and
            # can navigate this tab somewhere else. Modern browsers imply
            # noopener, older ones and in-app webviews do not.
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, category=self.category,
                selector=selector, line=line, snippet=snippet_of(tag),
                source=context.source, details={"href": (tag.get("href") or "")[:120]},
                fix_snippet=_with_rel(tag, "noopener noreferrer"),
            ))
        return issues


class MissingCharset(BestPracticeRule):
    id = "bp-charset"
    severity = MODERATE

    def check(self, document, context) -> list:
        head = document.find("head")
        if head is None:
            return []
        for tag in head.find_all("meta"):
            if tag.has_attr("charset"):
                return []
            if (tag.get("http-equiv") or "").lower() == "content-type":
                return []
        # Without a declared encoding the browser guesses, and it guesses
        # wrong on exactly the content this tool exists for: Ukrainian and
        # Italian text renders as mojibake.
        return [Issue(
            rule_id=self.id, severity=self.severity, category=self.category,
            source=context.source, snippet="<head>…</head>", details={},
            fix_snippet='<meta charset="utf-8">',
        )]


class DocumentTypeMissing(BestPracticeRule):
    id = "bp-doctype"
    severity = MODERATE

    def check(self, document, context) -> list:
        if document.find("html") is None:
            return []
        from bs4 import Doctype

        for item in document.contents:
            if isinstance(item, Doctype):
                return []
        # Without a doctype the browser falls into quirks mode, where layout
        # follows twenty-year-old rules and modern CSS behaves differently.
        return [Issue(
            rule_id=self.id, severity=self.severity, category=self.category,
            source=context.source, snippet="<html>", details={},
            fix_snippet="<!DOCTYPE html>",
        )]


class InlineEventHandlers(BestPracticeRule):
    id = "bp-inline-handlers"
    severity = MINOR

    _HANDLERS = ("onclick", "onload", "onerror", "onmouseover", "onchange",
                 "onsubmit", "onkeydown", "onfocus", "onblur")

    def check(self, document, context) -> list:
        issues = []
        seen = set()
        for handler in self._HANDLERS:
            for tag in document.find_all(attrs={handler: True}):
                if id(tag) in seen:
                    continue
                seen.add(id(tag))
                # Inline handlers are what force a Content-Security-Policy to
                # allow 'unsafe-inline', which is the single change that turns
                # a CSP from a defence into a formality.
                selector, line = context.locate(tag)
                issues.append(Issue(
                    rule_id=self.id, severity=self.severity, category=self.category,
                    selector=selector, line=line, snippet=snippet_of(tag),
                    source=context.source,
                    details={"handler": handler, "element": tag.name},
                ))
        return issues


class PasswordFieldOutsideForm(BestPracticeRule):
    id = "bp-password-field"
    severity = MODERATE

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all("input"):
            if (tag.get("type") or "").lower() != "password":
                continue
            problems = []
            if tag.find_parent("form") is None:
                problems.append("no-form")
            if not (tag.get("autocomplete") or "").strip():
                problems.append("no-autocomplete")
            if not problems:
                continue
            # Outside a form, and without an autocomplete hint, password
            # managers cannot recognise the field — so people type weaker
            # passwords they can remember.
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, category=self.category,
                selector=selector, line=line, snippet=snippet_of(tag),
                source=context.source, details={"problems": problems},
            ))
        return issues


class DeprecatedElements(BestPracticeRule):
    id = "bp-deprecated-html"
    severity = MINOR

    _DEPRECATED = {
        "center": "CSS text-align / margin", "font": "CSS font properties",
        "marquee": "CSS animation", "blink": "nothing — it was removed",
        "big": "CSS font-size", "strike": "<del> or CSS", "tt": "<code> or CSS",
        "frame": "CSS layout", "frameset": "CSS layout", "acronym": "<abbr>",
    }

    def check(self, document, context) -> list:
        issues = []
        for name, replacement in self._DEPRECATED.items():
            for tag in document.find_all(name):
                selector, line = context.locate(tag)
                issues.append(Issue(
                    rule_id=self.id, severity=self.severity, category=self.category,
                    selector=selector, line=line, snippet=snippet_of(tag),
                    source=context.source,
                    details={"element": name, "replacement": replacement},
                ))
        return issues


def _with_rel(tag, value: str) -> str:
    attributes = dict(tag.attrs)
    attributes["rel"] = value
    parts = []
    for key, val in attributes.items():
        if isinstance(val, list):
            val = " ".join(val)
        parts.append(f'{key}="{val}"')
    return f"<{tag.name} " + " ".join(parts) + ">"


for _rule in (MixedContent, TargetBlankWithoutNoopener, MissingCharset,
              DocumentTypeMissing, InlineEventHandlers, PasswordFieldOutsideForm,
              DeprecatedElements):
    RuleRegistry.register(_rule)
