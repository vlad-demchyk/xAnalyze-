"""Six rules in a category that had none, and the six things they must not do.

`security` was in `CATEGORIES` with nothing registered against it:
`audit.repo_facts` filed a committed `.env` there and nothing else ever did,
so the word in a report meant "one repository check ran" rather than "the
markup was read for this".

Opening a category is where a scanner earns or loses trust fastest, so the
pairs below spend most of their length on the negative case. A wrong
accessibility finding is a wasted hour; a wrong security finding is a wasted
hour plus a reader who stops believing the next one.
"""
from __future__ import annotations

import unittest

from bs4 import BeautifulSoup

import audit  # noqa: F401 - registers the rules
from audit.base import RuleContext, RuleRegistry


def _run(rule_id: str, markup: str, source: str = "https://example.com/p") -> list:
    rule = RuleRegistry.create(rule_id)
    document = BeautifulSoup(markup, "html.parser")
    context = RuleContext(source=source)
    context.dom_path = lambda tag: tag.name
    return rule.check(document, context)


class AFrameWithTheRunOfThePage(unittest.TestCase):
    def test_a_cross_origin_frame_without_sandbox_is_reported(self):
        self.assertTrue(_run("sec-frame-sandbox",
                             '<iframe src="https://other.example/e"></iframe>'))

    def test_a_sandboxed_frame_is_not(self):
        self.assertFalse(_run("sec-frame-sandbox",
                              '<iframe src="https://other.example/e" sandbox></iframe>'))

    def test_a_same_document_frame_is_not(self):
        """A relative `src` is this site's own page."""
        self.assertFalse(_run("sec-frame-sandbox", '<iframe src="/embed"></iframe>'))

    def test_a_computed_src_is_not_guessed_at(self):
        """A template that computes the address may well compute a trusted
        one, and guessing would be a finding about the framework."""
        self.assertFalse(_run("sec-frame-sandbox",
                              '<iframe src="{{ embedUrl }}"></iframe>'))


class PermissionsHandedToAFrame(unittest.TestCase):
    def test_camera_and_microphone_are_reported(self):
        found = _run("sec-frame-permissions",
                     '<iframe src="https://other.example/e" allow="camera; microphone"></iframe>')
        self.assertEqual(found[0].details["granted"], ["camera", "microphone"])

    def test_an_ordinary_allow_is_not(self):
        self.assertFalse(_run(
            "sec-frame-permissions",
            '<iframe src="https://other.example/e" allow="fullscreen"></iframe>'))

    def test_no_allow_is_not(self):
        self.assertFalse(_run("sec-frame-permissions",
                              '<iframe src="https://other.example/e"></iframe>'))


class AFormOverHttp(unittest.TestCase):
    def test_an_http_action_is_critical(self):
        found = _run("sec-form-insecure-action",
                     '<form action="http://example.com/s" method="post"></form>')
        self.assertEqual(found[0].severity, "critical")

    def test_https_is_not(self):
        self.assertFalse(_run("sec-form-insecure-action",
                              '<form action="https://example.com/s"></form>'))

    def test_a_relative_action_is_not(self):
        """It inherits the page's scheme, which is the recommended fix."""
        self.assertFalse(_run("sec-form-insecure-action",
                              '<form action="/session"></form>'))

    def test_a_form_with_no_action_is_not(self):
        self.assertFalse(_run("sec-form-insecure-action", '<form></form>'))


class AScriptLoadedOnTrust(unittest.TestCase):
    def test_a_cross_origin_script_without_integrity_is_reported(self):
        self.assertTrue(_run("sec-script-integrity",
                             '<script src="https://cdn.other/lib.js"></script>'))

    def test_one_with_integrity_is_not(self):
        self.assertFalse(_run(
            "sec-script-integrity",
            '<script src="https://cdn.other/lib.js" integrity="sha384-x"></script>'))

    def test_a_script_from_this_host_is_not(self):
        self.assertFalse(_run("sec-script-integrity",
                              '<script src="https://example.com/app.js"></script>'))

    def test_a_local_script_is_not(self):
        self.assertFalse(_run("sec-script-integrity",
                              '<script src="/app.js"></script>'))

    def test_an_inline_script_is_not(self):
        self.assertFalse(_run("sec-script-integrity", '<script>var x = 1;</script>'))


class AKeyWrittenIntoTheMarkup(unittest.TestCase):
    _REAL = "sk_live_9f2c41ab77de05639bc8"

    def test_a_long_value_in_a_named_attribute_is_critical(self):
        found = _run("sec-secret-in-markup", f'<div data-api-key="{self._REAL}"></div>')
        self.assertEqual(found[0].severity, "critical")

    def test_a_template_binding_is_not(self):
        """`data-api-key="{{ config.key }}"` is a template doing it right."""
        self.assertFalse(_run("sec-secret-in-markup",
                              '<div data-api-key="{{ config.mapsKey }}"></div>'))

    def test_a_placeholder_is_not(self):
        """Shouting about `YOUR_KEY_HERE` teaches people to ignore the rule."""
        for value in ("YOUR_API_KEY_HERE", "your-key-here", "xxxxxxxxxxxxxxxxxx"):
            with self.subTest(value=value):
                self.assertFalse(_run("sec-secret-in-markup",
                                      f'<div data-secret="{value}"></div>'))

    def test_a_short_value_is_an_identifier_not_a_secret(self):
        self.assertFalse(_run("sec-secret-in-markup", '<div data-token="42"></div>'))

    def test_reacts_list_key_is_never_touched(self):
        """`data-key` is on every list in the world; a rule that fires on it
        is noise wearing a scary label."""
        self.assertFalse(_run("sec-secret-in-markup",
                              f'<li data-key="{self._REAL}"></li>'))


class APasswordTheBrowserIsToldToKeep(unittest.TestCase):
    def test_autocomplete_on_is_reported(self):
        self.assertTrue(_run("sec-autocomplete-secret",
                             '<input type="password" autocomplete="on">'))

    def test_current_password_is_not(self):
        self.assertFalse(_run("sec-autocomplete-secret",
                              '<input type="password" autocomplete="current-password">'))

    def test_no_autocomplete_is_not(self):
        """Absent is the browser's own default, not a decision to flag."""
        self.assertFalse(_run("sec-autocomplete-secret", '<input type="password">'))

    def test_a_text_field_is_not(self):
        self.assertFalse(_run("sec-autocomplete-secret",
                              '<input type="text" autocomplete="on">'))


class EveryRuleCanBeRead(unittest.TestCase):
    """A finding nobody can read is a finding that was not delivered."""

    def test_each_rule_has_an_explanation_in_all_three_languages(self):
        from audit.base import Issue
        from audit.explanations import render

        details = {"src": "https://a/b", "action": "http://a/b",
                   "host": "cdn.other", "granted": ["camera"],
                   "attribute": "data-api-key", "length": 22,
                   "autocomplete": "on"}
        for rule in RuleRegistry.all_rules(categories=["security"]):
            for lang in ("uk", "en", "it"):
                with self.subTest(rule=rule.id, language=lang):
                    issue = Issue(rule_id=rule.id, severity=rule.severity,
                                  category=rule.category, source="x",
                                  details=details)
                    explanation = render(issue, lang)
                    for part in (explanation.title, explanation.why,
                                 explanation.fix):
                        self.assertFalse(part.startswith("a11y_"),
                                         f"{rule.id}/{lang}: untranslated key")


if __name__ == "__main__":
    unittest.main()
