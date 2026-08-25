"""Two runs against each other: what was fixed, what appeared, what stayed.

The question a second run is actually asked is not "what is wrong" - the
report answers that - but "did the last round of work help". Three answers,
and they are three because they are acted on differently: what was fixed is
finished, what appeared is new work, and what has not moved is the list that
decides whether the current approach to it is working at all.

Two things must not slip.

A measurement that moved is not work done. `perf-first-paint` fires on ten
pages in one run and none in the next because the second run hit a warm
cache, and a comparison that counts that as "ten places fixed" tells the one
lie a comparison cannot tell. `compare_runs` already separates them; the
view and the panel have to keep them separated.

And the streak - how many consecutive runs a rule has survived - is evidence,
so it must not be inflated. A run recorded before per-rule counts existed
cannot say whether a rule fired, so it ends the streak rather than extending
it through a gap nobody has data for.

The view model is plain Python and tested without Qt; the panel follows.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from cli_impl.reports import comparison_view, runs_open

try:
    from PySide6.QtWidgets import QApplication

    from ui import theme
    from ui.window_parts.run_comparison import (
        APPEARED, FIXED, UNCHANGED, RunComparisonPanel,
    )
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None


ROOT, MODE = "https://example.com", "web"


def entry(at: str, rule_counts: dict, *, measured=(), root=ROOT, mode=MODE) -> dict:
    return {"at": at, "root": root, "mode": mode,
            "counts": {"critical": sum(rule_counts.values())},
            "distinct": len(rule_counts),
            "rules": sorted(rule_counts),
            "rule_counts": dict(rule_counts),
            "measured_rules": sorted(measured)}


def payload(history: list, now: dict, *, measured=(), titles=None) -> dict:
    """A report payload shaped the way `_write_report` hands it back."""
    titles = titles or {}
    return {
        "generated": history[-1]["at"] if history else "now",
        "root": ROOT, "mode": MODE,
        "summary": {"total": sum(now.values()),
                    "distinct_problems": len(now)},
        "measured_rules": sorted(measured),
        "history": history,
        "problems": [{"rule": rule} for rule in now],
        "by_rule": [{"rule": rule, "count": count,
                     "severity": "critical", "category": "a11y",
                     "title": titles.get(rule, rule.replace("-", " ")),
                     "fix": "", "where": [f"/page:{i}" for i in range(count)]}
                    for rule, count in now.items()],
    }


class Streak(unittest.TestCase):
    def test_a_rule_present_in_every_run_counts_them_all(self):
        history = [entry("1", {"label": 1}), entry("2", {"label": 1}),
                   entry("3", {"label": 1})]
        self.assertEqual(runs_open(history, "label", ROOT, MODE), 3)

    def test_the_streak_is_the_current_one_not_the_whole_career(self):
        """A rule fixed and then broken again is one run old, not four."""
        history = [entry("1", {"label": 1}), entry("2", {}),
                   entry("3", {"label": 1})]
        self.assertEqual(runs_open(history, "label", ROOT, MODE), 1)

    def test_a_run_with_no_per_rule_counts_ends_the_streak(self):
        """It cannot say whether the rule fired, and guessing would inflate
        exactly the number that is meant to be evidence."""
        history = [entry("1", {"label": 1}),
                   {"at": "2", "root": ROOT, "mode": MODE},
                   entry("3", {"label": 1})]
        self.assertEqual(runs_open(history, "label", ROOT, MODE), 1)

    def test_another_target_s_runs_are_not_this_one_s_history(self):
        history = [entry("1", {"label": 1}),
                   entry("2", {"label": 1}, root="https://other.test"),
                   entry("3", {"label": 1})]
        self.assertEqual(runs_open(history, "label", "https://other.test", MODE), 1)

    def test_a_rule_absent_from_the_latest_run_has_no_streak(self):
        history = [entry("1", {"label": 1}), entry("2", {})]
        self.assertEqual(runs_open(history, "label", ROOT, MODE), 0)


class View(unittest.TestCase):
    """`comparison_view`: `compare_runs` arranged as the three answers."""

    def view(self, before: dict, now: dict, **kwargs):
        history = [entry("2026-08-23-2110", before, **kwargs),
                   entry("2026-08-24-0930", now, **kwargs)]
        return comparison_view(payload(history, now, **kwargs))

    def test_a_first_run_has_nothing_to_compare_against(self):
        history = [entry("2026-08-24-0930", {"label": 1})]
        self.assertIsNone(comparison_view(payload(history, {"label": 1})))

    def test_a_rule_that_fires_in_fewer_places_is_fixed(self):
        view = self.view({"image-alt": 7}, {"image-alt": 2})
        self.assertEqual(view["fixed"]["places"], 5)
        self.assertEqual(view["fixed"]["rules"][0]["delta"], -5)
        self.assertEqual(view["appeared"]["places"], 0)

    def test_a_rule_that_fires_in_more_places_appeared(self):
        view = self.view({"color-contrast": 1}, {"color-contrast": 4})
        self.assertEqual(view["appeared"]["places"], 3)
        self.assertEqual(view["appeared"]["rules"][0]["delta"], 3)

    def test_a_rule_that_stopped_firing_entirely_is_named(self):
        """That the rule is gone is the useful fact, more than its count."""
        view = self.view({"label": 3, "image-alt": 1}, {"image-alt": 1})
        self.assertIn("label", view["fixed"]["solved"])

    def test_a_rule_nobody_had_before_is_named_as_new(self):
        view = self.view({"image-alt": 1}, {"image-alt": 1, "region": 2})
        self.assertIn("region", view["appeared"]["new"])

    def test_a_rule_that_did_not_move_is_still_open(self):
        view = self.view({"label": 4}, {"label": 4})
        self.assertEqual([r["rule"] for r in view["unchanged"]["rules"]], ["label"])
        self.assertEqual(view["unchanged"]["places"], 4)

    def test_a_rule_that_moved_is_not_also_listed_as_unchanged(self):
        """`still_open_rules` means "present in both runs", which includes
        every rule whose count moved - so a rule fixed from seven places to
        two was reported as fixed *and* as untouched. The section is read as
        the list of what the last round of work did not reach."""
        view = self.view({"image-alt": 7, "label": 2}, {"image-alt": 2, "label": 2})
        self.assertEqual([r["rule"] for r in view["unchanged"]["rules"]], ["label"])
        self.assertEqual(view["unchanged"]["places"], 2)

    def test_the_unchanged_list_puts_the_oldest_first(self):
        """A rule that has outlived six rounds of work is the one worth
        talking about; sorting by size would bury it under a fresh one."""
        history = [entry("1", {"old": 1}), entry("2", {"old": 1}),
                   entry("3", {"old": 1, "fresh": 30}),
                   entry("4", {"old": 1, "fresh": 30})]
        view = comparison_view(payload(history, {"old": 1, "fresh": 30}))
        self.assertEqual([r["rule"] for r in view["unchanged"]["rules"]],
                         ["old", "fresh"])

    def test_a_measurement_that_moved_is_not_counted_as_work(self):
        """A warm cache is not a fix. This is the one thing a comparison
        must never get wrong."""
        view = self.view({"perf-first-paint": 10}, {"perf-first-paint": 0},
                         measured=("perf-first-paint",))
        self.assertEqual(view["fixed"]["places"], 0)
        self.assertEqual([m["rule"] for m in view["measurements"]],
                         ["perf-first-paint"])

    def test_a_measurement_is_not_listed_among_the_unchanged_either(self):
        view = self.view({"perf-first-paint": 3, "label": 1},
                         {"perf-first-paint": 9, "label": 1},
                         measured=("perf-first-paint",))
        self.assertNotIn("perf-first-paint",
                         [r["rule"] for r in view["unchanged"]["rules"]])
        self.assertEqual(view["appeared"]["places"], 0)

    def test_the_totals_come_from_the_run_not_from_the_rules(self):
        view = self.view({"image-alt": 7}, {"image-alt": 2})
        self.assertEqual(view["findings_before"], 7)
        self.assertEqual(view["findings_now"], 2)

    def test_a_rule_in_this_run_carries_its_human_title(self):
        view = self.view({"image-alt": 3}, {"image-alt": 1})
        self.assertEqual(view["fixed"]["rules"][0]["title"], "image alt")


@unittest.skipIf(QApplication is None, "PySide6 not available")
class Panel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.palette = theme.current_palette("light")

    def panel(self) -> "RunComparisonPanel":
        widget = RunComparisonPanel(self.palette)
        self._alive = getattr(self, "_alive", [])
        self._alive.append(widget)
        return widget

    def view(self, before: dict, now: dict, **kwargs):
        history = [entry("2026-08-23-2110", before, **kwargs),
                   entry("2026-08-24-0930", now, **kwargs)]
        return comparison_view(payload(history, now, **kwargs))

    def rows(self, panel, kind) -> list:
        layout = panel.sections[kind].rows_layout
        return [layout.itemAt(i).widget() for i in range(layout.count())]

    def texts(self, panel, kind) -> list:
        from PySide6.QtWidgets import QLabel
        return [[label.text() for label in row.findChildren(QLabel)]
                for row in self.rows(panel, kind)]

    def test_the_three_sections_are_all_shown(self):
        panel = self.panel()
        panel.show_comparison(self.view({"image-alt": 3}, {"image-alt": 1}))
        for kind in (FIXED, APPEARED, UNCHANGED):
            with self.subTest(section=kind):
                self.assertFalse(panel.sections[kind].isHidden())

    def test_an_empty_section_still_says_zero(self):
        """"Nothing was fixed" is an answer. A section that vanishes when it
        is empty makes the reader work out which one is missing."""
        panel = self.panel()
        panel.show_comparison(self.view({"image-alt": 1}, {"image-alt": 4}))
        self.assertIn("0", panel.sections[FIXED].count.text())

    def test_a_delta_is_always_signed(self):
        """"5" says nothing about which way it went, and which way things
        went is the entire subject of this panel."""
        panel = self.panel()
        panel.show_comparison(self.view({"image-alt": 7}, {"image-alt": 2}))
        self.assertTrue(any("-5" in text for row in self.texts(panel, FIXED)
                            for text in row), self.texts(panel, FIXED))

        panel.show_comparison(self.view({"region": 1}, {"region": 4}))
        self.assertTrue(any("+3" in text for row in self.texts(panel, APPEARED)
                            for text in row), self.texts(panel, APPEARED))

    def test_an_unchanged_rule_says_how_long_it_has_been_there(self):
        history = [entry("1", {"label": 2}), entry("2", {"label": 2}),
                   entry("3", {"label": 2})]
        panel = self.panel()
        panel.show_comparison(comparison_view(payload(history, {"label": 2})))
        flat = [text for row in self.texts(panel, UNCHANGED) for text in row]
        self.assertTrue(any("3" in text for text in flat), flat)

    def test_a_second_comparison_replaces_the_first_one_s_rows(self):
        """`deleteLater` only schedules the deletion, so an unparented row
        would otherwise stay on screen under the new one."""
        from PySide6.QtWidgets import QWidget
        panel = self.panel()
        panel.show_comparison(self.view({"a": 3, "b": 3}, {"a": 1, "b": 1}))
        panel.show_comparison(self.view({"a": 3}, {"a": 1}))
        section = panel.sections[FIXED]
        live = [child for child in section.rows.findChildren(QWidget)
                if child.parent() is section.rows]
        self.assertEqual(len(live), 1)

    def test_the_measurements_are_named_and_kept_out_of_the_totals(self):
        panel = self.panel()
        panel.show_comparison(self.view({"perf-first-paint": 10},
                                        {"perf-first-paint": 0},
                                        measured=("perf-first-paint",)))
        self.assertFalse(panel.measurements.isHidden())
        self.assertIn("perf-first-paint", panel.measurements.text())

    def test_a_run_with_no_measurements_says_nothing_about_them(self):
        panel = self.panel()
        panel.show_comparison(self.view({"image-alt": 3}, {"image-alt": 1}))
        self.assertTrue(panel.measurements.isHidden()
                        or not panel.measurements.text())

    def test_the_document_button_is_only_there_when_the_document_is(self):
        panel = self.panel()
        view = self.view({"image-alt": 3}, {"image-alt": 1})
        panel.show_comparison(view, None)
        self.assertTrue(panel.changes_btn.isHidden()
                        or not panel.changes_btn.isVisibleTo(panel))
        panel.show_comparison(view, "/tmp/x/changes.md")
        self.assertTrue(panel.changes_btn.isVisibleTo(panel))

    def test_a_rule_with_no_title_is_not_printed_twice(self):
        """A rule that stopped firing is not in this run, so it has no
        title and falls back to its id. Printing the id in both columns
        reads as two facts when it is one."""
        panel = self.panel()
        panel.show_comparison(self.view({"label": 2, "image-alt": 1},
                                        {"image-alt": 1}))
        row = self.texts(panel, FIXED)[0]
        self.assertEqual([text for text in row if text == "label"], ["label"])

    def test_the_headline_is_the_two_totals(self):
        panel = self.panel()
        panel.show_comparison(self.view({"image-alt": 7}, {"image-alt": 2}))
        self.assertIn("7", panel.total_label.text())
        self.assertIn("2", panel.total_label.text())


@unittest.skipIf(QApplication is None, "PySide6 not available")
class InTheWindow(unittest.TestCase):
    """Reached from the documents panel, which is where `changes.md` lives."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from ui.main_window import MainWindow
        self.window = MainWindow()
        self.addCleanup(self.window.deleteLater)
        self.addCleanup(self.window.close)

    def documents(self, comparison=None, changes=None):
        from pathlib import Path

        from cli_impl.runfolder import RunDocuments, RunFolder
        written = {"report.pdf": Path("/tmp/x/report.pdf")}
        if changes:
            written["changes.md"] = Path(changes)
        return RunDocuments(
            folder=RunFolder(Path("/tmp/x"), Path("/tmp/x/2026-08-25-1200")),
            target="example.com", written=written, absent={},
            comparison=comparison)

    def view(self):
        history = [entry("1", {"image-alt": 3}), entry("2", {"image-alt": 1})]
        return comparison_view(payload(history, {"image-alt": 1}))

    def test_the_offer_is_not_made_on_a_first_run(self):
        """There is nothing to compare against, and a button that shows the
        difference between one run and nothing is an empty promise."""
        self.window._show_run_documents(self.documents())
        self.assertTrue(self.window.run_documents.comparison_btn.isHidden())

    def test_a_second_run_offers_it(self):
        self.window._show_run_documents(
            self.documents(self.view(), "/tmp/x/changes.md"))
        self.assertFalse(self.window.run_documents.comparison_btn.isHidden())

    def test_it_takes_the_column_and_renames_the_header(self):
        before = self.window.col1_header.text()
        self.window._show_run_documents(
            self.documents(self.view(), "/tmp/x/changes.md"))
        self.window.run_documents.comparison_btn.click()
        self.assertEqual(self.window.col1_stack.currentIndex(), 4)
        self.assertNotEqual(self.window.col1_header.text(), before)

    def test_back_gives_the_column_to_the_preview(self):
        before = self.window.col1_header.text()
        self.window._show_run_documents(
            self.documents(self.view(), "/tmp/x/changes.md"))
        self.window.run_documents.comparison_btn.click()
        self.window.run_comparison.back_btn.click()
        self.assertNotEqual(self.window.col1_stack.currentIndex(), 4)
        self.assertEqual(self.window.col1_header.text(), before)

    def test_asking_for_a_comparison_that_is_not_there_does_nothing(self):
        self.window._show_run_documents(self.documents())
        self.window._show_run_comparison()
        self.assertNotEqual(self.window.col1_stack.currentIndex(), 4)


if __name__ == "__main__":
    unittest.main()
