"""`perf-image-loading` guesses at geometry, and the browser settles it.

The rule assumes the first three `<img>` in DOM order are above the fold and
every later one is not. Measured 2026-08-31 at 1280x900 over four live pages
and 188 images: of the eight images the rule would have flagged, **one** sat
176px down the page - an icon on `en.wikipedia.org/wiki/Rome`. Recommending
`loading="lazy"` for an image the visitor can already see delays the largest
paint, which is the opposite of what the rule exists to do, and the rule's own
comment says so.

`P-26` in the vault was this defect, and it had been verified by construction
only. It is now measured, and this is the settling pass.
"""
from __future__ import annotations

import unittest

from audit.base import Issue, NEEDS_BROWSER, PERFORMANCE, RuleRegistry
from audit.browser import settle_image_loading


def _finding(src: str, rule_id: str = "perf-image-loading") -> Issue:
    return Issue(rule_id=rule_id, severity="minor", category=PERFORMANCE,
                 confidence=NEEDS_BROWSER, source="https://example.test/",
                 details={"src": src})


class TheRuleAdmitsItIsGuessing(unittest.TestCase):
    def test_the_finding_is_a_candidate_until_a_browser_has_looked(self):
        self.assertEqual(RuleRegistry.create("perf-image-loading").confidence,
                         NEEDS_BROWSER)


class TheBrowserSettlesIt(unittest.TestCase):
    def test_an_image_the_visitor_can_see_is_not_reported(self):
        kept = settle_image_loading(
            [_finding("/icon.svg")], {"imagesAboveFold": ["/icon.svg"]})
        self.assertEqual(kept, [])

    def test_an_image_below_the_fold_is_still_reported(self):
        found = [_finding("/hero.png")]
        self.assertEqual(settle_image_loading(
            found, {"imagesAboveFold": ["/logo.svg"]}), found)

    def test_other_rules_are_never_touched(self):
        # The pass answers one question, and an unrelated finding about the
        # same element is not that question.
        found = [_finding("/icon.svg", "image-modern-format")]
        self.assertEqual(settle_image_loading(
            found, {"imagesAboveFold": ["/icon.svg"]}), found)

    def test_no_measurement_leaves_every_finding_standing(self):
        # A browser that could not report geometry has not disproved anything.
        # Dropping findings here would be the tool hiding what it did not see.
        found = [_finding("/icon.svg")]
        for measurements in ({}, {"imagesAboveFold": []},
                             {"imagesAboveFold": None}, {"domNodes": 9}):
            with self.subTest(measurements=measurements):
                self.assertEqual(settle_image_loading(found, measurements), found)

    def test_an_image_with_no_src_cannot_be_matched_and_stays(self):
        # `srcset`-only and `data-src`-only images have no `src` for either
        # side to key on. Reported, not silently dropped.
        found = [_finding("")]
        self.assertEqual(settle_image_loading(
            found, {"imagesAboveFold": ["/icon.svg"]}), found)


class TheMeasurementScriptReportsGeometry(unittest.TestCase):
    def test_the_script_collects_images_above_the_fold(self):
        from audit.browser import MEASUREMENT_SCRIPT
        self.assertIn("imagesAboveFold", MEASUREMENT_SCRIPT)
        self.assertIn("getBoundingClientRect", MEASUREMENT_SCRIPT)
        self.assertIn("window.innerHeight", MEASUREMENT_SCRIPT)


if __name__ == "__main__":
    unittest.main()
