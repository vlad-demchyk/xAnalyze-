"""What is wrong with an email, as opposed to what is wrong with a page.

`audit.medium` already stops the page-only rules - canonical URLs, Open
Graph, skip links - from firing on a deliverable that lands in a mail
client. That was the negative half of the job and it made those reports
honest. This module is the positive half: the checks that only make sense
*because* it is an email.

The three here are the ones that could be measured on the deliverables in
`~/repositories/VSC` (18 emails out of 209 HTML files), because a rule that
cannot show a number on real work has not earned a place in a report:

* **10 emails** declare a font with no generic family behind it. A browser
  downloads a webfont; Outlook does not, and falls back to Times New Roman.
* **11 links in 3 emails** carry no colour of their own. Clients repaint an
  unstyled link - purple in Gmail, blue-and-underlined elsewhere - and a
  brand-coloured button turns into a default link.
* **12 of 18** ship no preheader, so the inbox preview is whatever text
  comes first, which in a template is usually "View in browser".

Two more checks were written against the same corpus and are deliberately
**not** here: a layout table wider than 640 px (0 found) and a
`background-image` with no fallback colour (0 found). They are real Outlook
defects and these particular deliverables do not have them; a rule with no
measurement behind it is how a rule list stops being trustworthy.
"""
from __future__ import annotations

import re

from ..base import (
    ACCESSIBILITY, BEST_PRACTICES, MINOR, MODERATE, Issue, Rule,
    RuleRegistry, snippet_of,
)

#: A family every client already has, or a keyword that resolves to one.
#: The point of the check is that *something* renders, not which something.
_GENERIC_FAMILIES = ("sans-serif", "serif", "monospace", "cursive", "fantasy",
                     "system-ui", "ui-sans-serif", "ui-serif", "ui-monospace",
                     "inherit", "initial", "unset")

_FONT_FAMILY_RE = re.compile(r"font-family\s*:\s*([^;\"'}]+)", re.I)
#: `color:` but not `background-color:`, which paints behind the text and
#: says nothing about the text itself.
_COLOR_RE = re.compile(r"(?<!-)\bcolor\s*:", re.I)
#: A stylesheet rule that paints links for the whole document. Present, and
#: the individual link is not the place to ask.
_STYLED_LINKS_RE = re.compile(r"(^|[},])\s*[^{}]*\ba(?::link|:visited)?\b[^{}]*\{"
                              r"[^}]*(?<!-)\bcolor\s*:", re.I | re.S)

#: How a preheader is written: a block that carries text for the inbox
#: preview and is hidden in the body. All three spellings are in use.
_PREHEADER_RE = re.compile(
    r"preheader"
    r"|display\s*:\s*none[^>]{0,160}?max-height\s*:\s*0"
    r"|max-height\s*:\s*0[^>]{0,160}?display\s*:\s*none"
    r"|mso-hide\s*:\s*all", re.I)


class EmailRule(Rule):
    """Base for this module: mail clients only, declared once."""
    category = BEST_PRACTICES
    email_only = True


class EmailFontWithoutFallback(EmailRule):
    """A font stack that ends at a font the client may not have.

    Reported once per distinct declaration rather than once per element: a
    template repeats the same `font-family` on every cell, and the fix is one
    edit to the stack, not forty to the cells.
    """
    id = "email-font-no-fallback"
    category = BEST_PRACTICES
    severity = MODERATE

    def check(self, document, context) -> list:
        issues = []
        seen = set()
        for tag in document.find_all(True):
            declarations = []
            style = tag.get("style")
            if isinstance(style, str):
                declarations.append(style)
            if tag.name == "style":
                declarations.append(tag.get_text())
            for text in declarations:
                for match in _FONT_FAMILY_RE.finditer(text):
                    stack = " ".join(match.group(1).split()).strip().rstrip(",")
                    lowered = stack.lower()
                    if not stack or lowered in seen:
                        continue
                    if any(family in lowered for family in _GENERIC_FAMILIES):
                        continue
                    seen.add(lowered)
                    selector, line = context.locate(tag)
                    issues.append(Issue(
                        rule_id=self.id, severity=self.severity,
                        selector=selector, line=line,
                        snippet=snippet_of(tag), source=context.source,
                        category=self.category,
                        details={"value": stack[:80]},
                    ))
        return issues


class EmailLinkWithoutColour(EmailRule):
    """A link the client will repaint in its own colour.

    Silent when the document styles links in a `<style>` block: Gmail and
    Apple Mail honour that, and asking every anchor to repeat what the
    stylesheet already says would be forty findings for a fix that is not
    needed. Outlook.com strips `<style>`, which is why the inline form is
    still the safer one - said in the fix rather than made a second finding.
    """
    id = "email-link-no-colour"
    category = ACCESSIBILITY
    severity = MINOR

    def check(self, document, context) -> list:
        for style in document.find_all("style"):
            if _STYLED_LINKS_RE.search(style.get_text() or ""):
                return []
        issues = []
        for tag in document.find_all("a"):
            style = tag.get("style")
            if isinstance(style, str) and _COLOR_RE.search(style):
                continue
            # An anchor wrapping nothing but an image has no text to paint.
            if not "".join(tag.stripped_strings):
                continue
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector,
                line=line, snippet=snippet_of(tag), source=context.source,
                category=self.category,
                details={"text": " ".join(tag.stripped_strings)[:60]},
            ))
        return issues


class EmailWithoutPreheader(EmailRule):
    """Nothing written for the line the inbox shows under the subject.

    With no preheader the client takes whatever text comes first, and in a
    template that is "View in browser" or an unsubscribe line - the two
    sentences written for the people who do *not* want the email.
    """
    id = "email-no-preheader"
    category = BEST_PRACTICES
    severity = MODERATE
    page_level = True

    def check(self, document, context) -> list:
        from ..base import document_source

        markup = document_source(document) or str(document)
        if _PREHEADER_RE.search(markup):
            return []
        body = document.find("body") or document
        selector, line = context.locate(body) if hasattr(body, "name") else ("", None)
        return [Issue(
            rule_id=self.id, severity=self.severity, selector=selector,
            line=line, snippet="", source=context.source,
            category=self.category, details={},
        )]


for _rule in (EmailFontWithoutFallback, EmailLinkWithoutColour,
              EmailWithoutPreheader):
    RuleRegistry.register(_rule)
