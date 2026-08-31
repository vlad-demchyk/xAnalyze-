"""Every new run parameter and finding reaches the surfaces it should.

A feature that exists only in the CLI is half-built, and a merge written
twice drifts. Both happened here: the window kept its own copy of the
browser merge and so never settled `perf-image-loading`, and the TUI's width
list predated two of the four breakpoints.
"""
from __future__ import annotations

import inspect
import unittest

from audit import browser, responsive
from audit.base import CATEGORIES, GEO, RuleRegistry


class TheBrowserMergeHasOneOwner(unittest.TestCase):
    def test_both_surfaces_call_the_same_merge(self):
        from cli_impl import auditpass
        import ui.main_window as main_window

        for module in (auditpass, main_window):
            source = inspect.getsource(module)
            with self.subTest(module=module.__name__):
                self.assertIn("merge_into_document", source)
                # Not the two calls open-coded a second time.
                self.assertNotIn("settle_image_loading(", source)

    def test_the_merge_settles_before_it_deduplicates(self):
        """Order is the reason the function exists.

        A static finding the browser disproved must not reach `deduplicate`,
        or a real finding corroborates it and it is reported anyway.
        """
        from audit.base import Issue, NEEDS_BROWSER, PERFORMANCE

        class Doc:
            issues = [Issue(rule_id="perf-image-loading", severity="minor",
                            category=PERFORMANCE, confidence=NEEDS_BROWSER,
                            source="https://example.test/",
                            details={"src": "/icon.svg"})]

        class Audit:
            issues = []
            measurements = {"imagesAboveFold": ["/icon.svg"]}
            html = ""

        document = Doc()
        browser.merge_into_document(document, Audit())
        self.assertEqual(document.issues, [])

    def test_a_page_audit_without_measurements_keeps_the_findings(self):
        from audit.base import Issue, PERFORMANCE

        class Doc:
            issues = [Issue(rule_id="perf-image-loading", severity="minor",
                            category=PERFORMANCE, source="x",
                            details={"src": "/hero.png"})]

        class Audit:
            issues = []
            measurements = None
            html = ""

        document = Doc()
        browser.merge_into_document(document, Audit())
        self.assertEqual(len(document.issues), 1)


class EveryBreakpointIsReachableFromTheTui(unittest.TestCase):
    def test_the_width_list_offers_every_breakpoint_the_audit_knows(self):
        import tui.screens.audit as screen

        source = inspect.getsource(screen)
        for name, _w, _h in responsive.BREAKPOINTS:
            with self.subTest(name):
                self.assertIn(f'"{name}"', source)


class TheGeoCategoryIsAWholeCategory(unittest.TestCase):
    def test_geo_is_one_of_the_categories_the_tool_knows(self):
        self.assertIn(GEO, CATEGORIES)

    def test_the_geo_rules_are_registered_under_it(self):
        grouped = RuleRegistry.by_category()
        self.assertEqual(sorted(grouped.get(GEO, [])),
                         ["geo-article-provenance", "geo-article-schema"])

    def test_the_report_names_the_category_in_every_language(self):
        # Otherwise the badge reads `geo` in a report that is otherwise
        # translated, which is the raw-key failure with extra steps.
        from report.template import _LABELS

        for lang in ("en", "uk", "it"):
            with self.subTest(lang):
                label = _LABELS[lang]["cat"].get(GEO, "")
                self.assertTrue(label)
                self.assertNotEqual(label, GEO)

    def test_a_window_scan_runs_the_geo_rules(self):
        """The window passes no rule list, so it gets all of them.

        The missing piece is a *filter*, not the pass: GEO findings do appear
        in the window's list. See `P-23`.
        """
        import inspect as _inspect

        from audit.engine import analyze_pages

        signature = _inspect.signature(analyze_pages)
        self.assertIsNone(signature.parameters["rules"].default)
        self.assertIn(GEO, RuleRegistry.by_category())


if __name__ == "__main__":
    unittest.main()
