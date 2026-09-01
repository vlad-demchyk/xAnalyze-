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
    BEST_PRACTICES, MINOR, MODERATE, SERIOUS, Issue, is_binding, Rule, RuleRegistry,
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


def _same_site(host: str, page_host: str) -> bool:
    """The page's own domain, subdomains included.

    `forum.squarespace.com` opened from `www.squarespace.com` is the same
    organisation opening its own forum, and tabnabbing needs somebody else.
    Exact host equality made every such link a finding - the same mistake
    `sec-script-integrity` had, and fixed the same way: a suffix match
    against the page's domain with `www.` removed, never a
    registrable-domain guess.
    """
    if not host or not page_host:
        return False
    root = page_host[4:] if page_host.startswith("www.") else page_host
    return host == page_host or host == root or host.endswith("." + root)


class TargetBlankWithoutNoopener(BestPracticeRule):
    """A new tab handed to somebody else's page, with a way back.

    Two corrections, both measured on a run over ten live sites that
    produced 325 of these:

    * **Cross-origin only.** 144 of the 325 pointed at the page's own host.
      The risk is that the *opened* page steers the tab that opened it, and
      a page opening its own site cannot be an attacker without already
      being one - so those were 144 rows of nothing.
    * **`minor`, not `moderate`.** Every current browser implies `noopener`
      for `target="_blank"` and has since 2021. What is left is old
      in-app webviews, which is a real audience and a much smaller claim
      than the rule was making.
    """
    id = "bp-target-blank"
    severity = MINOR

    def check(self, document, context) -> list:
        from urllib.parse import urlparse

        page_host = urlparse(context.source or "").netloc.lower()
        issues = []
        for tag in document.find_all("a", href=True):
            if (tag.get("target") or "").lower() != "_blank":
                continue
            rel = {r.lower() for r in (tag.get("rel") or [])}
            if "noopener" in rel or "noreferrer" in rel:
                continue
            href = (tag.get("href") or "").strip()
            target_host = urlparse(href).netloc.lower()
            if not target_host or (page_host and _same_site(target_host, page_host)):
                # The page's own host, or a relative link. Nothing to hand
                # away. A repo-mode fragment has no host to compare against,
                # so an absolute link there is still reported.
                continue
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
    page_level = True
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
    page_level = True
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
                # `onClick={close}` in a component file is a framework
                # binding, not an inline handler: it compiles to an event
                # listener and never reaches the served HTML, so it costs the
                # CSP nothing. Judging it as inline made React source read as
                # thousands of security findings.
                if is_binding(tag.get(handler)):
                    continue
                # `onload` on a `<link>` or a `<script>` is a loading
                # callback, not a user interaction - and on a `<link>` it is
                # the documented way to load CSS without blocking the render
                # (`media="print" onload="this.media='all'"`). Reporting the
                # recommended technique as a defect is how a rule teaches
                # people to skip the category.
                if tag.name in ("link", "script") and handler in ("onload", "onerror"):
                    continue
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


class InPageAnchorMissing(BestPracticeRule):
    """A link to a place on this page that is not on this page.

    On a site that is one file - a landing page, an exported layout, a
    single-page brochure - `#pricing` is not a convenience, it *is* the
    navigation. When the id was renamed and the link was not, the menu item
    silently does nothing: no error, no 404, the page simply stays where it
    is, and nothing in a normal audit says why.

    Measured 2026-09-01 on `~/repositories/VSC`, 191 non-email documents:
    18 anchors in 15 files pointed at an id that does not exist.

    `page_level`, and that is the whole safety of it: in a component or a
    partial the target legitimately lives in another file, and a rule that
    did not know the difference would report every well-built React nav.
    """
    id = "link-fragment-missing"
    severity = SERIOUS
    page_level = True

    #: Fragments every browser resolves by itself, to the top of the
    #: document. Neither needs an element to exist.
    _BUILT_IN = {"top", "#"}

    def check(self, document, context) -> list:
        targets = {tag.get("id") for tag in document.find_all(attrs={"id": True})}
        targets |= {tag.get("name") for tag in document.find_all("a", attrs={"name": True})}
        targets.discard(None)
        targets.discard("")
        issues = []
        for tag in document.find_all("a", href=True):
            href = (tag.get("href") or "").strip()
            if not href.startswith("#") or len(href) < 2:
                continue
            fragment = href[1:]
            if fragment in self._BUILT_IN or fragment in targets:
                continue
            # `href={`#${id}`}` and its friends: the value is not written
            # yet, so there is nothing to resolve and nothing to report.
            if is_binding(fragment):
                continue
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector,
                line=line, snippet=snippet_of(tag), source=context.source,
                details={"href": href[:80],
                         "text": " ".join(tag.stripped_strings)[:60]},
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
              DeprecatedElements, InPageAnchorMissing):
    RuleRegistry.register(_rule)
