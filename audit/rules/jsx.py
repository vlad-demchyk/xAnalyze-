"""Checks that only mean something in a React source file.

Everything in `accessibility.py` reads markup, and markup is markup wherever
it is written: an `<img>` with no `alt` is the same defect in a `.html` file,
in a Twig template and in a component. This module is the other half - the
defects that exist **only** because the file is JSX, and that no rule reading
plain HTML can see:

* `htmlFor` is JSX's spelling of `for`. A `<label>` with neither is not
  associated with anything, and an HTML parser sees no `for` either way.
* `onClick` is a function reference React binds, not a string a browser
  evaluates. So it is not the "inline handler" finding it would be in HTML -
  it is a *keyboard* question: a `<div onClick>` is unreachable without a
  mouse.
* `dangerouslySetInnerHTML` has no HTML equivalent at all.

Measured 2026-09-01 over the repositories on this machine, before any of
this existed: 228 `<label>` without `htmlFor` and 59 `onClick` on
non-interactive elements in `~/repositories/XFormat` (526 `.tsx`), 41 more
`onClick` and 30 `dangerouslySetInnerHTML` in `~/repositories/anima`
(83 `.tsx`). None of it was reported by anything.

**A component is not a tag, and this is the trap the whole module is built
around.** An HTML parser lowercases tag names, so `<Button onClick={x}>`
arrives as `button` - and every design system in existence would then be
told its `<Button>` needs a keyboard handler it already has. So every rule
here reads the *source* spelling through `snippet_of` and stays silent on
anything that starts with a capital or contains a dot (`<Foo.Item>`). What
`<Button>` renders is that component's business, and this file cannot see it.

The list of checks and the wording of their fixes follow
`eslint-plugin-jsx-a11y`, which is the canonical statement of what is
statically visible in JSX - a developer who has seen its errors recognises
these.
"""
from __future__ import annotations

import re

from ..base import (
    ACCESSIBILITY, ADVISORY, BEST_PRACTICES, MINOR, MODERATE, SERIOUS,
    Issue, Rule, RuleRegistry, snippet_of, source_tag_name,
)

#: Elements that are keyboard-reachable and actionable on their own. A click
#: handler on one of these is ordinary code, not a finding.
_INTERACTIVE = {"a", "button", "input", "select", "textarea", "summary",
                "option", "label", "details"}

#: ARIA roles that make a non-interactive element interactive on purpose.
#: Declaring one is the author saying "I know, and I have handled it", which
#: is exactly what these rules ask for.
_INTERACTIVE_ROLES = {
    "button", "link", "checkbox", "menuitem", "menuitemcheckbox",
    "menuitemradio", "option", "radio", "switch", "tab", "textbox",
    "combobox", "slider", "spinbutton", "searchbox", "treeitem", "gridcell",
}

#: The keyboard half of a click. Any one of them is enough: which key event
#: an interaction should use is a design decision, and this rule has no
#: business having an opinion about it.
_KEY_HANDLERS = ("onkeydown", "onkeyup", "onkeypress")

#: What the source spelling of a component looks like. React requires the
#: capital - a lowercase name *is* a DOM tag, by the language's own rule -
#: and a dotted name (`<Menu.Item>`) is a namespaced component.
_COMPONENT_RE = re.compile(r"^([A-Z][\w.]*|[\w-]+\.[\w.]+)$")


def _is_component(tag) -> bool:
    """Was this written as a component rather than as a DOM element?

    Read from the source text, because the parser has already destroyed the
    evidence: `<Button>` and `<button>` are both `button` by the time a rule
    sees them. Where there is no source to read - a DOM out of a browser -
    the answer is no, and correctly so: a browser has no components.
    """
    return bool(_COMPONENT_RE.match(source_tag_name(tag)))


#: A handler that only stops the event from travelling. Measured on
#: `~/repositories/XFormat`: every modal in the app writes
#: `onClick={(e) => e.stopPropagation()}` on the card inside a click-to-close
#: overlay, and that is not an action anybody performs - it is the absence of
#: one. Reporting it asks the developer to add a keyboard handler for a
#: gesture that does nothing, which is how a rule teaches people to skip it.
_INERT_HANDLER_RE = re.compile(
    r"^\{?\s*(?:\(\s*\w*\s*\)|\w+)?\s*=>\s*\{?\s*"
    r"(?:(?:\w+\.)?(?:stopPropagation|preventDefault)\s*\(\s*\)\s*;?\s*)+"
    r"\}?\s*\}?$")


def _expression_of(tag, attribute: str) -> str:
    """The JSX expression written for `attribute`, straight from the file.

    The parsed value is useless for this: an HTML parser splits
    `onClick={(e) => e.stopPropagation()}` at the first space, so the rule
    receives `{(e)` and three attributes made of debris. The source has the
    whole thing, and the braces are balanced by hand because the expression
    may contain any number of them.
    """
    text = snippet_of(tag, limit=4000)
    lowered = text.lower()
    at = lowered.find(attribute.lower() + "=")
    if at == -1:
        return ""
    start = text.find("{", at)
    if start == -1:
        return ""
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return ""


def _is_inert_handler(tag, attribute: str = "onClick") -> bool:
    """Does this handler do nothing but stop the event?"""
    expression = _expression_of(tag, attribute)
    return bool(expression) and bool(_INERT_HANDLER_RE.match(expression.strip()))


def _has_any(tag, names) -> bool:
    return any(tag.has_attr(name) for name in names)


def _role_of(tag) -> str:
    role = tag.get("role") or ""
    return role.strip().lower() if isinstance(role, str) else ""


def _is_interactive(tag) -> bool:
    """Does this element already behave like a control?

    `<a>` counts only with an `href`: without one it is not focusable and
    not announced as a link, which is a defect of its own (see
    `JsxAnchorNotALink`) rather than a reason to excuse the missing keyboard
    handler.
    """
    if tag.name == "a":
        return tag.has_attr("href")
    if tag.name in _INTERACTIVE:
        return True
    return _role_of(tag) in _INTERACTIVE_ROLES


class JsxRule(Rule):
    """Base for this module: JSX only, declared once."""
    category = ACCESSIBILITY
    syntaxes = ("jsx",)


class JsxLabelNotAssociated(JsxRule):
    """A `<label>` that names nothing.

    Silent on a label that *wraps* its control, which is the other valid
    association - and silent on one that wraps a component, because
    `<Input />` very probably renders the input this label is for and this
    file cannot see inside it. Both exclusions cost recall on purpose: a
    false "this label is broken" on a working form is the finding that
    teaches a developer to stop reading the report.
    """
    id = "jsx-label-not-associated"
    severity = SERIOUS
    wcag = ("1.3.1", "3.3.2", "4.1.2")

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all("label"):
            if _is_component(tag):
                continue
            if tag.has_attr("htmlfor") or tag.has_attr("for"):
                continue
            # A wrapped control, DOM or component, is an association.
            if tag.find(["input", "select", "textarea"]) is not None:
                continue
            if any(_is_component(child) for child in tag.find_all(True)):
                continue
            selector, line = context.locate(tag)
            text = " ".join(tag.stripped_strings)[:60]
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector,
                line=line, snippet=snippet_of(tag), source=context.source,
                category=self.category, details={"text": text},
            ))
        return issues


class JsxClickWithoutKey(JsxRule):
    """A click handler no keyboard can reach.

    `jsx-a11y/click-events-have-key-events`. The element is not a control,
    so nothing focuses it and nothing fires a click on Enter or Space; a
    person navigating by keyboard has no way to do what a mouse can.
    """
    id = "jsx-click-without-key"
    severity = SERIOUS
    wcag = ("2.1.1",)

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all(attrs={"onclick": True}):
            if _is_component(tag) or _is_interactive(tag):
                continue
            # An `<a>` with a handler and no `href` has its own finding, and
            # it is the one that names the actual fix. Reporting it here as
            # well made one anchor three rows.
            if tag.name == "a":
                continue
            if _is_inert_handler(tag):
                continue
            if _has_any(tag, _KEY_HANDLERS):
                continue
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector,
                line=line, snippet=snippet_of(tag), source=context.source,
                category=self.category, details={"element": tag.name},
            ))
        return issues


class JsxNoninteractiveHandler(JsxRule):
    """A click handler on something nothing announces as a control.

    `jsx-a11y/no-static-element-interactions`, and deliberately a separate
    finding from the missing key handler: adding `onKeyDown` to a `<div>`
    makes it *operable* by keyboard and still leaves it unreachable, because
    nothing focuses it and a screen reader still calls it a group of text.
    Fixing one without the other produces a control only a sighted keyboard
    user who already knows it is there can use.
    """
    id = "jsx-noninteractive-handler"
    severity = MODERATE
    wcag = ("4.1.2",)

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all(attrs={"onclick": True}):
            if _is_component(tag) or _is_interactive(tag) or tag.name == "a":
                continue
            if _is_inert_handler(tag):
                continue
            # A role plus a tabIndex is the author doing this on purpose and
            # doing it correctly; either alone leaves half of it undone.
            if _role_of(tag) in _INTERACTIVE_ROLES and tag.has_attr("tabindex"):
                continue
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector,
                line=line, snippet=snippet_of(tag), source=context.source,
                category=self.category,
                details={"element": tag.name,
                         "role": _role_of(tag) or "-",
                         # A bool, not a word: `explanations` turns it into
                         # one in the reader's language.
                         "focusable": tag.has_attr("tabindex")},
            ))
        return issues


class JsxTabIndexOnStatic(JsxRule):
    """Something in the tab order that does nothing when you get there.

    `jsx-a11y/no-noninteractive-tabindex`. A `tabIndex={0}` on a plain
    element is a stop on the keyboard path with no action behind it - the
    person tabs onto a paragraph, hears nothing useful, and tabs on.
    """
    id = "jsx-tabindex-on-static"
    severity = MINOR
    wcag = ("2.4.3",)

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all(attrs={"tabindex": True}):
            if _is_component(tag) or _is_interactive(tag):
                continue
            if tag.has_attr("onclick") or _has_any(tag, _KEY_HANDLERS):
                # It does something; whether that is reachable is the other
                # two rules' question and reporting it here as well would be
                # the same div three times.
                continue
            value = (tag.get("tabindex") or "").strip()
            # `tabIndex={-1}` is a deliberate focus target for scripts and is
            # not in the tab order at all.
            if "-1" in value:
                continue
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector,
                line=line, snippet=snippet_of(tag), source=context.source,
                category=self.category,
                details={"element": tag.name, "value": value[:20]},
            ))
        return issues


class JsxAutofocus(JsxRule):
    """Focus moved before the person has read anything.

    `jsx-a11y/no-autofocus`. A screen reader starts reading from the focused
    element, so everything above it - including what the form is for - is
    skipped, and a magnifier user is moved somewhere they did not ask to go.
    Advisory rather than exact: on a dedicated search page or a modal that
    exists for one field this is the right call, and the markup cannot say
    which page it is on.
    """
    id = "jsx-autofocus"
    severity = MODERATE
    confidence = ADVISORY
    wcag = ("2.4.3", "3.2.1")

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all(attrs={"autofocus": True}):
            if _is_component(tag):
                continue
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector,
                line=line, snippet=snippet_of(tag), source=context.source,
                category=self.category, confidence=self.confidence,
                details={"element": tag.name},
            ))
        return issues


class JsxAnchorNotALink(JsxRule):
    """An `<a>` with a handler and nowhere to go.

    `jsx-a11y/anchor-is-valid`. Without an `href` an anchor is not focusable
    and is not announced as a link; it looks like one and behaves like one
    for a mouse only. `href="#"` is the same thing with a destination that
    scrolls to the top.
    """
    id = "jsx-anchor-not-a-link"
    severity = SERIOUS
    wcag = ("2.1.1", "4.1.2")

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all("a"):
            if _is_component(tag) or not tag.has_attr("onclick"):
                continue
            href = (tag.get("href") or "").strip()
            if href and href != "#":
                continue
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector,
                line=line, snippet=snippet_of(tag), source=context.source,
                category=self.category,
                details={"href": href or "(none)"},
            ))
        return issues


class JsxDangerousHtml(JsxRule):
    """Markup written straight into the page.

    Not an accessibility finding: whatever reaches
    `dangerouslySetInnerHTML` is parsed as HTML, so a `<script>` or an
    `onerror` in that string runs. React's own name for the prop is the
    warning, and it is worth repeating in a report because the value usually
    arrives from somewhere else - a CMS field, an API, a Markdown renderer -
    and the file that renders it is not the file that sanitises it.

    **Not filed under `security`, deliberately.** That category was opened on
    one condition - nothing in it may infer - and this rule infers: a
    sanitised value here is correct code, and a static pass cannot follow
    where the string came from. So it is a best practice with an advisory
    label, which is what it honestly is: "prove this one is sanitised", not
    "this is a hole". Filing it as a security finding would buy severity with
    the credibility of every other finding in that category.
    """
    id = "jsx-dangerous-html"
    category = BEST_PRACTICES
    severity = SERIOUS
    confidence = ADVISORY

    def check(self, document, context) -> list:
        issues = []
        for tag in document.find_all(attrs={"dangerouslysetinnerhtml": True}):
            selector, line = context.locate(tag)
            issues.append(Issue(
                rule_id=self.id, severity=self.severity, selector=selector,
                line=line, snippet=snippet_of(tag), source=context.source,
                category=self.category, confidence=self.confidence,
                details={"element": tag.name},
            ))
        return issues


for _rule in (
    JsxLabelNotAssociated, JsxClickWithoutKey, JsxNoninteractiveHandler,
    JsxTabIndexOnStatic, JsxAutofocus, JsxAnchorNotALink, JsxDangerousHtml,
):
    RuleRegistry.register(_rule)
