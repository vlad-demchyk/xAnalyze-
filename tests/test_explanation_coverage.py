"""No finding may reach the screen as a raw translation key.

This is the failure that a row count cannot catch: the browser pass added
dozens of findings, every one of them rendered as `a11y_axe:region_title`,
and the list looked full while being unreadable. The test below is deliberately
about the *shape* of the output rather than its wording - what matters is that
something a person can read comes out for every rule the tool can produce.
"""
import unittest

from audit.base import ACCESSIBILITY, MODERATE, RuleRegistry, Issue
from audit.explanations import render
from audit.states import STATE_RULES


def rendered(rule_id, details=None, lang="uk"):
    return render(Issue(rule_id=rule_id, severity=MODERATE,
                        category=ACCESSIBILITY, source="x",
                        details=details or {}), lang)


class NoRawKeysTests(unittest.TestCase):

    def assert_readable(self, explanation, rule_id):
        for field in ("title", "found", "why", "fix"):
            value = getattr(explanation, field)
            self.assertFalse(
                value.startswith("a11y_"),
                f"{rule_id}: {field} rendered as the raw key {value!r}")

    def test_every_registered_rule_renders_in_every_language(self):
        for lang in ("uk", "it", "en"):
            for rule_id in RuleRegistry.available():
                self.assert_readable(rendered(rule_id, lang=lang), rule_id)

    def test_every_state_rule_renders(self):
        """The state pass is ours, so it gets our explanations, not the
        engine fallback."""
        for lang in ("uk", "it", "en"):
            for rule in STATE_RULES:
                rule_id = f"state:{rule}"
                explanation = rendered(rule_id, {"navLinks": 12, "count": 3},
                                       lang=lang)
                self.assert_readable(explanation, rule_id)
                self.assertTrue(explanation.why)

    def test_an_axe_rule_we_have_never_seen_still_reads(self):
        """axe and HTML_CodeSniffer ship hundreds of rules between them, and
        new ones arrive with every release. None of them can be allowed to
        turn into a key on screen."""
        explanation = rendered("axe:some-rule-invented-tomorrow", {
            "engine": "axe-core", "rule": "some-rule-invented-tomorrow",
            "help": "Elements must do the thing",
            "description": "Ensures elements do the thing",
        })
        self.assert_readable(explanation, "axe:some-rule-invented-tomorrow")
        self.assertEqual(explanation.title, "Elements must do the thing")

    def test_the_engine_is_named_so_english_wording_is_not_passed_off_as_ours(self):
        explanation = rendered("htmlcs:1_3_1", {
            "engine": "HTML_CodeSniffer", "code": "WCAG2AA.X.1_3_1",
            "why": "Heading markup should be used.",
        })
        self.assertIn("HTML_CodeSniffer", explanation.found)


if __name__ == "__main__":
    unittest.main()
