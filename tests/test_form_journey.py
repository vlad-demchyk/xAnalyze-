"""The form pass: the part of a page where a mistake costs the whole errand.

The state pass covered focus, keyboard, modals and reflow, and had nothing
at all about forms - no rule about a field's name in the state it is
actually in, about the browser's own verdict on what is typed in it, or
about the error text a page has just put on screen. That gap was written
down in this project's own plan and is what this file closes.

Two things are pinned here, and the second is why the file is worth its
length.

**It reads; it does not act.** Everything in `states.py` is deliberately
passive, and in a form that stops being a style choice: typing fires the
page's own handlers - autosave, a validation request, an analytics event -
and submitting is worse. So the checks read the live state the browser
already maintains (`el.validity`, the computed accessible name, the error
node on screen) and fill nothing in. The half of the journey that needs a
value typed is *not* implemented, and the plan says so rather than
pretending a static equivalent is the same thing.

**It is driven in a real browser.** The other state rules are pinned by
their source, which is reasonable for a script whose behaviour is one
condition. These four walk the DOM and compute names, and a source
assertion would only prove the text exists. The class at the bottom loads a
page with four planted defects and one correct control, and asserts what
comes back - skipped, not passed, where QtWebEngine is unavailable.
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from audit.base import ACCESSIBILITY, MODERATE, SERIOUS
from audit.states import STATE_RULES, STATE_SCRIPT, issues_from_states

#: One page, five controls, four planted defects:
#:
#: * `search` has nothing naming it at all;
#: * `email` is named only by its placeholder;
#: * `age` holds a value its own `type`/`max` rejects, and says nothing;
#: * the error sentence under `age` is referred to by no field;
#: * `name` is correct and must produce nothing, which is the half of the
#:   fixture that keeps the rules from being "flag every input".
FORM_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>form</title></head>
<body>
  <form>
    <label for="name">Your name</label>
    <input id="name" name="name" value="Ada">

    <input id="search" name="search">

    <input id="email" name="email" placeholder="Email address">

    <label for="age">Age</label>
    <input id="age" name="age" type="number" max="10" value="99">
    <p class="field-error">Age must be 10 or less.</p>

    <button type="submit">Send</button>
  </form>
</body></html>
"""


class TheRulesAreRegistered(unittest.TestCase):
    def test_all_four_have_a_severity(self):
        for rule in ("form-field-unnamed", "form-placeholder-as-label",
                     "form-invalid-not-announced", "form-error-not-associated"):
            with self.subTest(rule=rule):
                self.assertIn(rule, STATE_RULES)

    def test_a_field_nobody_can_name_is_serious(self):
        """A control with no accessible name is not a hint; it is the task
        being unavailable to anyone who cannot see the layout."""
        self.assertEqual(STATE_RULES["form-field-unnamed"], SERIOUS)
        self.assertEqual(STATE_RULES["form-error-not-associated"], SERIOUS)

    def test_a_placeholder_is_the_lesser_of_the_two(self):
        self.assertEqual(STATE_RULES["form-placeholder-as-label"], MODERATE)


class TheScriptStillTouchesNothing(unittest.TestCase):
    """The reason these checks are read-only, kept as a test because it is
    the one property that cannot be recovered after it is lost: a pass that
    submits somebody's form once has already submitted it."""

    def test_nothing_is_typed_into_a_field(self):
        for forbidden in (".value =", ".click()", ".submit()"):
            with self.subTest(call=forbidden):
                self.assertNotIn(forbidden, STATE_SCRIPT)

    def test_the_javascript_reaches_the_browser_as_written(self):
        """The script is a Python string full of JavaScript escapes.

        Held here because the two languages disagree silently. A plain
        triple-quoted string turned the selector escape into a bare quote,
        so the browser was told to replace a quote with a quote - a no-op
        where a CSS attribute selector needs the backslash - and the regex
        `\\s` in the same string is a SyntaxWarning on 3.12+ and an error
        later. Both are fixed by the string being raw, and both are checked
        here on the text the browser actually receives.
        """
        selector_escape = "id.replace(/\"/g, '" + chr(92) + chr(92) + "\"')"
        self.assertIn(selector_escape, STATE_SCRIPT)
        self.assertIn("/" + chr(92) + "s+/", STATE_SCRIPT)

    def test_validity_is_read_and_not_asked_for(self):
        """`checkValidity()` fires an `invalid` event the page can act on.
        The property is the same answer with no event behind it."""
        self.assertIn("el.validity", STATE_SCRIPT)
        self.assertNotIn("checkValidity()", STATE_SCRIPT)


class WhatComesBackAsAFinding(unittest.TestCase):
    def test_a_form_finding_is_an_accessibility_finding(self):
        found = issues_from_states({"findings": [{
            "rule": "form-field-unnamed", "selector": "input#search",
            "html": '<input id="search">',
        }]}, "https://example.test/")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].category, ACCESSIBILITY)
        self.assertEqual(found[0].severity, SERIOUS)

    def test_the_placeholder_travels_with_the_finding(self):
        """It is what the explanation quotes: "the only name this field has
        is …" reads as an accusation without the words it is about."""
        found = issues_from_states({"findings": [{
            "rule": "form-placeholder-as-label", "selector": "input#email",
            "html": "<input>", "placeholder": "Email address",
        }]}, "https://example.test/")
        self.assertEqual(found[0].details.get("placeholder"), "Email address")

    def test_every_form_rule_renders_in_every_language(self):
        from audit.explanations import render

        for rule in ("form-field-unnamed", "form-placeholder-as-label",
                     "form-invalid-not-announced", "form-error-not-associated"):
            issue = issues_from_states({"findings": [{
                "rule": rule, "selector": "input", "html": "<input>",
                "placeholder": "Email", "reason": "constraint",
                "message": "Age must be 10 or less.",
            }]}, "https://example.test/")[0]
            for lang in ("uk", "it", "en"):
                with self.subTest(rule=rule, lang=lang):
                    explanation = render(issue, lang)
                    self.assertFalse(explanation.title.startswith("a11y_"))
                    self.assertTrue(explanation.why)
                    self.assertTrue(explanation.fix)


class InARealBrowser(unittest.TestCase):
    """The four rules, run against the page above by QtWebEngine."""

    @classmethod
    def setUpClass(cls):
        from audit import driver

        usable, reason = driver.available()
        if not usable:
            raise unittest.SkipTest(reason)
        cls.rules = cls._audit_the_fixture()

    @staticmethod
    def _audit_the_fixture() -> dict:
        from audit import browser, driver

        with TemporaryDirectory() as folder:
            path = Path(folder) / "form.html"
            path.write_text(FORM_PAGE, encoding="utf-8")
            options = browser.BrowserAuditOptions(
                run_axe=False, run_htmlcs=False, run_states=True,
                run_measurements=False, allow_local_files=True, settle_ms=300)
            driver.ensure_headless_application()
            runner = driver.BrowserAuditRunner(options)
            try:
                result = runner.audit(path.resolve().as_uri())
            finally:
                runner.close()
        found: dict = {}
        for issue in result.issues:
            found.setdefault(issue.rule_id, []).append(issue)
        return found

    def test_a_field_with_no_name_is_found(self):
        self.assertIn("state:form-field-unnamed", self.rules)

    def test_the_labelled_field_is_not_among_them(self):
        """The half that stops this being "flag every input"."""
        unnamed = self.rules.get("state:form-field-unnamed", [])
        for issue in unnamed:
            self.assertNotIn('id="name"', issue.snippet)

    def test_a_placeholder_only_field_is_told_apart_from_it(self):
        placeholders = self.rules.get("state:form-placeholder-as-label", [])
        self.assertEqual(len(placeholders), 1)
        self.assertEqual(placeholders[0].details.get("placeholder"),
                         "Email address")

    def test_a_value_the_browser_rejects_is_reported_unannounced(self):
        found = self.rules.get("state:form-invalid-not-announced", [])
        self.assertTrue(found, "the browser's own validity verdict was not read")
        self.assertIn('id="age"', found[0].snippet)

    def test_error_text_nothing_points_at_is_reported(self):
        found = self.rules.get("state:form-error-not-associated", [])
        self.assertTrue(found)
        self.assertIn("Age must be 10 or less",
                      found[0].details.get("message", ""))

    def test_the_page_produced_findings_at_all(self):
        """A rule that found nothing and a pass that never ran are different
        results, and only one of them is good news."""
        self.assertTrue(any(self.rules.values()))


if __name__ == "__main__":
    unittest.main()
