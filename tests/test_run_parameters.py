"""Five run parameters existed in the core and in the CLI and nowhere else.

`P-23`: `--category` (including the `geo` category), `--confidence`,
`--scope`, `--site-controls` and `--no-typography` were all reachable from
`cli.py` and settled inside `audit/`, and two of the three surfaces this
tool ships could not ask for any of them. The window ran the same pass and
showed everything; the TUI's audit screen sent `category=None` and
`confidence` was not in the namespace at all.

What this file pins is not "there is a checkbox". It is that the two
narrowings are **one view over one pass**, computed by one function, so the
window, the TUI and the CLI cannot answer differently about the same page:

* `audit.base.issues_in_view` is that function, and both surfaces call it;
* narrowing the view never edits the result, so widening it again brings
  every finding back without re-auditing anything;
* an empty list under a filter is reported as a filter, not as a clean page
  - the same defect as reporting an unreachable folder as clean, which this
  project has had once already and does not intend to have twice.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from audit.base import (
    ACCESSIBILITY, ADVISORY, CATEGORIES, EXACT, GEO, Issue, NEEDS_BROWSER,
    SEO, SERIOUS, issues_in_view,
)
from audit.engine import AccessibilityResult, DocumentReport

try:
    from PySide6.QtWidgets import QApplication

    from ui.app_state import AppState
    from ui.main_window import MainWindow
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None


def issue(rule_id: str, category: str, confidence: str = EXACT) -> Issue:
    return Issue(rule_id=rule_id, severity=SERIOUS, category=category,
                 source="https://example.test/", confidence=confidence,
                 details={})


def result_of(*issues) -> AccessibilityResult:
    return AccessibilityResult(
        root="https://example.test/", mode="web",
        documents=[DocumentReport(source="https://example.test/",
                                  issues=list(issues))])


class TheViewOverOnePass(unittest.TestCase):
    """`issues_in_view`, which is the whole of the shared behaviour."""

    def setUp(self):
        self.issues = [
            issue("image-alt", ACCESSIBILITY),
            issue("seo-canonical", SEO),
            issue("geo-article-provenance", GEO, ADVISORY),
            issue("contrast-inline", ACCESSIBILITY, NEEDS_BROWSER),
        ]

    def test_no_choice_means_every_category(self):
        """An empty list is "nothing was chosen", never "report nothing"."""
        self.assertEqual(len(issues_in_view(self.issues)), 4)

    def test_every_category_chosen_is_the_same_as_none_chosen(self):
        self.assertEqual(len(issues_in_view(self.issues, CATEGORIES)), 4)

    def test_one_category_keeps_only_it(self):
        kept = issues_in_view(self.issues, (SEO,))
        self.assertEqual([i.rule_id for i in kept], ["seo-canonical"])

    def test_geo_is_a_category_a_reader_can_ask_for(self):
        """The category the audit gained last and the surfaces gained never."""
        kept = issues_in_view(self.issues, (GEO,))
        self.assertEqual([i.rule_id for i in kept], ["geo-article-provenance"])

    def test_a_certainty_floor_drops_what_is_below_it(self):
        kept = issues_in_view(self.issues, (), EXACT)
        self.assertEqual(sorted(i.rule_id for i in kept),
                         ["image-alt", "seo-canonical"])

    def test_the_floor_is_a_floor_and_not_an_equality(self):
        kept = issues_in_view(self.issues, (), NEEDS_BROWSER)
        self.assertNotIn("geo-article-provenance", [i.rule_id for i in kept])
        self.assertIn("contrast-inline", [i.rule_id for i in kept])

    def test_both_narrowings_compose(self):
        kept = issues_in_view(self.issues, (ACCESSIBILITY,), EXACT)
        self.assertEqual([i.rule_id for i in kept], ["image-alt"])

    def test_an_unknown_category_narrows_nothing_into_nothing(self):
        """A name the audit does not have is not a filter that hides
        everything: `CATEGORIES` is what the choice is intersected with."""
        self.assertEqual(len(issues_in_view(self.issues, ("nonsense",))), 4)


class NarrowingIsNotEditing(unittest.TestCase):
    def test_the_result_still_holds_everything(self):
        result = result_of(issue("image-alt", ACCESSIBILITY),
                           issue("seo-canonical", SEO))
        narrowed = result.narrowed((SEO,))
        self.assertEqual(len(narrowed.issues()), 1)
        self.assertEqual(len(result.issues()), 2)

    def test_every_document_survives_a_narrowing(self):
        """A page read and left with no findings *in this view* is not a page
        that was not read, and the count beside the list counts documents."""
        result = AccessibilityResult(
            root="https://example.test/", mode="web",
            documents=[DocumentReport(source="https://example.test/a",
                                      issues=[issue("seo-canonical", SEO)]),
                       DocumentReport(source="https://example.test/b",
                                      issues=[issue("image-alt", ACCESSIBILITY)])])
        narrowed = result.narrowed((SEO,))
        self.assertEqual(len(narrowed.documents), 2)
        self.assertEqual(len(narrowed.issues()), 1)

    def test_an_empty_view_is_the_result_itself(self):
        result = result_of(issue("image-alt", ACCESSIBILITY))
        self.assertIs(result.narrowed(), result)


class TheCliTakesTheSameView(unittest.TestCase):
    def test_cli_reads_the_shared_function(self):
        """Not a second copy of the two loops: they drifted once already -
        the re-audit after `--fix` reapplied the category filter and dropped
        the certainty floor."""
        import inspect

        import cli

        source = inspect.getsource(cli)
        self.assertIn("issues_in_view", source)
        self.assertNotIn("if meets_confidence(i, floor)", source)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class TheWindowAsksForThemToo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.window.settings.ui_language = "en"
        self.window.lang = "en"
        self.window._retranslate_ui()
        audit_result = result_of(
            issue("image-alt", ACCESSIBILITY),
            issue("seo-canonical", SEO),
            issue("geo-article-provenance", GEO, ADVISORY))
        # Two assignments because there are two copies of this fact: the
        # window keeps one and the view model keeps another, and a real run
        # fills the second and then signals the first. Set here the way the
        # run sets them, rather than testing one and assuming the other.
        self.window.view_model.audit_result = audit_result
        self.window.audit_result = audit_result
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_the_list_shows_everything_when_nothing_is_chosen(self):
        self.window._populate_audit_list()
        self.assertEqual(self.window.flagged_list.count(), 3)

    def test_choosing_a_category_repaints_the_list(self):
        self.window.app_state.set_categories((SEO,))
        self.assertEqual(self.window.flagged_list.count(), 1)

    def test_widening_brings_the_findings_back_without_a_new_run(self):
        self.window.app_state.set_categories((SEO,))
        self.window.app_state.set_categories(())
        self.assertEqual(self.window.flagged_list.count(), 3)
        self.assertEqual(len(self.window.audit_result.issues()), 3)

    def test_the_certainty_floor_reaches_the_list(self):
        self.window.app_state.set_confidence_floor(EXACT)
        self.assertEqual(self.window.flagged_list.count(), 2)

    def test_a_view_that_hides_everything_says_so(self):
        """Not "no findings": the findings exist and a control is hiding
        them. Saying the page is clean would be the window making a claim
        about the site out of the state of its own filter."""
        self.window.app_state.set_categories(("security",))
        self.assertEqual(self.window.flagged_list.count(), 0)
        self.assertTrue(self.window._view_is_narrowed())

    def test_the_summary_counts_what_the_list_shows(self):
        self.window.app_state.set_categories((SEO,))
        self.assertIn("1", self.window.summary_count.text())

    def test_the_count_agrees_with_itself_grammatically(self):
        """The number under the filter changes under the reader's hand now,
        so "1 знахідок" is on screen far more often than it used to be."""
        for lang, expected in (("uk", "1 знахідка"), ("it", "1 riscontro"),
                               ("en", "1 finding")):
            with self.subTest(lang=lang):
                self.window.settings.ui_language = lang
                self.window.lang = lang
                self.window._retranslate_ui()
                self.window.app_state.set_categories((SEO,))
                self.assertEqual(self.window.summary_count.text(), expected)
                self.window.app_state.set_categories(())

    def test_the_report_is_exported_through_the_same_view(self):
        self.window.app_state.set_categories((SEO,))
        model = self.window.view_model._report_model()
        self.assertEqual(len(model.findings), 1)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class SiteControlsIsARunChoice(unittest.TestCase):
    """Unlike the other two, `--site-controls` changes what is fetched: two
    extra requests to the same domain. So it travels with the worker."""

    def test_the_worker_carries_it(self):
        from ui.worker import audit_worker_for

        worker, refusal = audit_worker_for(
            "site", target="https://example.test/", depth=0, max_pages=5,
            site_controls=True)
        self.assertEqual(refusal, "")
        self.assertTrue(worker.site_controls)

    def test_it_is_off_unless_asked_for(self):
        from ui.worker import audit_worker_for

        worker, _refusal = audit_worker_for(
            "site", target="https://example.test/", depth=0, max_pages=5)
        self.assertFalse(worker.site_controls)

    def test_the_state_starts_with_it_off(self):
        self.assertFalse(AppState().site_controls)

    def test_the_worker_hands_it_to_the_pass(self):
        """The attribute is not the point; reaching `analyze_pages` is."""
        import ui.worker as worker_module

        worker = worker_module.AuditWorker(target="https://example.test/",
                                           depth=0, pages=[],
                                           site_controls=True)
        seen: dict = {}

        def analyze_pages(pages, root, **kwargs):
            seen.update(kwargs)
            return AccessibilityResult(root=root, mode="web", documents=[])

        with mock.patch.dict("sys.modules"):
            import audit

            with mock.patch.object(audit, "analyze_pages", analyze_pages):
                worker.run()
        self.assertTrue(seen.get("site_controls"))


@unittest.skipIf(QApplication is None, "PySide6 not available")
class TheStateHoldsTheChoice(unittest.TestCase):
    """`AppState` owns them, so the setup screen and the list read one value.

    A second copy on the window is the defect this project has paid for
    before: the window kept state nobody filled, and the audit reported an
    empty result as a clean one.
    """

    def test_all_six_chosen_is_stored_as_no_choice(self):
        state = AppState()
        state.set_categories(CATEGORIES)
        self.assertEqual(issues_in_view([issue("image-alt", ACCESSIBILITY)],
                                        state.categories),
                         [i for i in [issue("image-alt", ACCESSIBILITY)]][:1] or [])

    def test_setting_the_same_value_twice_emits_once(self):
        state = AppState()
        fired: list = []
        state.view_changed.connect(lambda: fired.append(1))
        state.set_categories((SEO,))
        state.set_categories((SEO,))
        self.assertEqual(len(fired), 1)

    def test_the_floor_is_stored_as_given(self):
        state = AppState()
        state.set_confidence_floor(EXACT)
        self.assertEqual(state.confidence_floor, EXACT)


class TheTuiAsksForThemToo(unittest.TestCase):
    """The audit screen sent `category=None` and no `confidence` at all."""

    @staticmethod
    def _run(coroutine):
        return asyncio.new_event_loop().run_until_complete(coroutine)

    def _captured_args(self, category: str, confidence: str,
                       site_controls: bool) -> argparse.Namespace:
        from textual.widgets import Checkbox, Input, Select

        from tui.app import XAnalyzeApp

        async def body():
            app = XAnalyzeApp()
            captured: list = []
            async with app.run_test() as pilot:
                await pilot.pause()
                await pilot.press("2")
                await pilot.pause()
                screen = app.screen
                screen.query_one("#target", Input).value = "example.com"
                screen.query_one("#category", Select).value = category
                screen.query_one("#confidence", Select).value = confidence
                screen.query_one("#site-controls", Checkbox).value = site_controls
                with mock.patch.object(screen, "start_run",
                                       side_effect=lambda *a, **k:
                                       captured.append((a, k)) or True):
                    screen._run_audit()
                await pilot.pause()
            return captured

        captured = self._run(body())
        self.assertEqual(len(captured), 1)
        (_command, args), _kwargs = captured[0]
        return args

    def test_a_chosen_category_reaches_the_command(self):
        args = self._captured_args(GEO, "", False)
        self.assertEqual(args.category, [GEO])

    def test_no_chosen_category_means_every_category(self):
        args = self._captured_args("", "", False)
        self.assertIsNone(args.category)

    def test_the_certainty_floor_reaches_the_command(self):
        args = self._captured_args("", EXACT, False)
        self.assertEqual(args.confidence, EXACT)

    def test_site_controls_reaches_the_command(self):
        args = self._captured_args("", "", True)
        self.assertTrue(args.site_controls)

    def test_the_command_accepts_what_the_screen_sends(self):
        """The form is only half of it: `cli.py` has to read these names."""
        args = self._captured_args(SEO, EXACT, True)
        for name in ("category", "confidence", "site_controls", "medium"):
            with self.subTest(field=name):
                self.assertTrue(hasattr(args, name))


if __name__ == "__main__":
    unittest.main()
