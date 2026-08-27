"""A reader can ask for only what the markup settles.

Every finding has carried a confidence since the rules were written, and
nothing let anyone act on it. So HTML_CodeSniffer's "this element is
absolutely positioned and the background color can not be determined" sat in
the same list as a missing `alt`, and an axe `incomplete` sat there too.
Measured on ten pages of `https://www.gov.uk/`: 60 of 61 contrast findings
were the first kind.

Weighting them down was the first half of the fix. This is the second: a
floor the person running the scan chooses, because which half they want
depends on what they are doing. Someone about to file tickets wants only
facts; someone doing an accessibility review wants the candidates too.

The findings are still *produced* either way. A floor is a view over one
pass, exactly like `--category` - not a different run, and never a decision
made on the reader's behalf.
"""
from __future__ import annotations

import unittest

from audit.base import (
    CONFIDENCE_ORDER, EXACT, NEEDS_BROWSER, Issue, meets_confidence,
)


def _issue(confidence: str) -> Issue:
    return Issue(rule_id="r", severity="serious", source="x",
                 confidence=confidence, details={})


class TheOrderIsWeakestFirst(unittest.TestCase):
    def test_needs_browser_is_below_exact(self):
        self.assertEqual(CONFIDENCE_ORDER, (NEEDS_BROWSER, EXACT))


class AFloorKeepsWhatMeetsIt(unittest.TestCase):
    def test_exact_keeps_only_what_the_markup_settles(self):
        self.assertTrue(meets_confidence(_issue(EXACT), EXACT))
        self.assertFalse(meets_confidence(_issue(NEEDS_BROWSER), EXACT))

    def test_the_lowest_floor_keeps_everything(self):
        for level in CONFIDENCE_ORDER:
            with self.subTest(level=level):
                self.assertTrue(meets_confidence(_issue(level), NEEDS_BROWSER))

    def test_no_floor_keeps_everything(self):
        for floor in ("", None):
            with self.subTest(floor=floor):
                self.assertTrue(meets_confidence(_issue(NEEDS_BROWSER), floor))


class WhatIsUnknownIsNotDropped(unittest.TestCase):
    """A finding nobody recorded a confidence for is not evidence of a weak
    finding, and dropping it would be the tool hiding what it does not know
    about itself."""

    def test_an_unrecognised_confidence_survives_any_floor(self):
        self.assertTrue(meets_confidence(_issue("who-knows"), EXACT))

    def test_an_unrecognised_floor_filters_nothing(self):
        self.assertTrue(meets_confidence(_issue(NEEDS_BROWSER), "very-sure"))


class TheEnginesAgreeWithTheFloor(unittest.TestCase):
    """The two vendored engines' uncertainty has to land below the floor,
    or the flag would not remove the thing it was built to remove."""

    def test_an_axe_incomplete_is_below_exact(self):
        import json

        from audit.browser import issues_from_axe

        payload = json.dumps({"violations": [], "incomplete": [{
            "id": "aria-valid-attr-value", "impact": "critical",
            "help": "", "description": "",
            "nodes": [{"target": "button", "html": "<button></button>",
                       "failureSummary": "Unable to determine…"}]}]})
        issue = issues_from_axe(payload, "https://site/")[0]
        self.assertFalse(meets_confidence(issue, EXACT))

    def test_an_undetermined_contrast_is_below_exact(self):
        import json

        from audit.browser import issues_from_htmlcs

        payload = json.dumps({"messages": [{
            "type": 1, "code": "WCAG2AA.Principle1.Guideline1_4.1_4_3.G18.Abs",
            "html": "<p>x</p>", "msg": "…", "tag": "p"}]})
        issue = issues_from_htmlcs(payload, "https://site/")[0]
        self.assertFalse(meets_confidence(issue, EXACT))

    def test_a_real_failure_survives_the_floor(self):
        """The half that must not be lost."""
        import json

        from audit.browser import issues_from_htmlcs

        payload = json.dumps({"messages": [{
            "type": 1, "code": "WCAG2AA.Principle1.Guideline1_4.1_4_3.G18.Fail",
            "html": "<p>x</p>", "msg": "…", "tag": "p"}]})
        issue = issues_from_htmlcs(payload, "https://site/")[0]
        self.assertTrue(meets_confidence(issue, EXACT))


class EverySecurityRuleIsExact(unittest.TestCase):
    """The category was opened on that condition.

    A security finding that turns out to be wrong costs more trust than any
    other kind, so nothing that has to infer belongs in it - and a rule added
    later must not quietly relax that.
    """

    def test_no_security_rule_needs_a_browser(self):
        import audit  # noqa: F401 - registers the rules
        from audit.base import RuleRegistry

        for rule in RuleRegistry.all_rules(categories=["security"]):
            with self.subTest(rule=rule.id):
                self.assertEqual(rule.confidence, EXACT)

    def test_the_category_is_no_longer_empty(self):
        import audit  # noqa: F401
        from audit.base import RuleRegistry

        self.assertTrue(RuleRegistry.all_rules(categories=["security"]))


if __name__ == "__main__":
    unittest.main()
