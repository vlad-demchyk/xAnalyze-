"""The three empty states, and the move that follows from each.

Nothing on screen is three different situations, not one. "Nothing scanned
yet" is an instruction. "Scanned, nothing flagged" is a result, and one that
has to say plainly it is not proof of anything. "Scanned but the crawler got
no text" is the only one that is actually a problem, and it is the reason
`PageDiagnostics` exists at all - without it a JavaScript-rendered site is
indistinguishable from a clean one.

Artboard 3i adds what each of them was missing: what to do next. A diagnosis
with no way to act on it is half an answer, and the third state is the clear
case - "the markup is drawn by JavaScript" is only useful beside the button
that re-reads the page in a browser.

The rule the actions have to keep is that they are only offered when they
are real. A button leading to a control this run cannot use promises a way
out and then refuses, which is how someone concludes the tool is broken
rather than that the option does not apply here.

Headless: Qt runs on the offscreen platform, like the other widget tests.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    from analysis_modes import (
        METHOD_AI, METHOD_LOCAL, SOURCE_REPO, SOURCE_SITE,
    )
    from models import (
        AnalysisResult, Confidence, PageResult, RepoAnalysisResult, TextBlock,
        TextSpan,
    )
    from ui import theme
    from ui.main_window import MainWindow
    from ui.widgets import TONE_CLEAN, TONE_IDLE, TONE_PROBLEM, EmptyState
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 not available")
class Widget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.palette = theme.current_palette("light")

    def state(self) -> "EmptyState":
        widget = EmptyState(self.palette)
        self._alive = getattr(self, "_alive", [])
        self._alive.append(widget)
        return widget

    def test_the_three_tones_are_three_different_marks(self):
        """"Nothing found" and "nothing was read" are opposite pieces of
        news, and two grey paragraphs of the same weight hide that."""
        widget = self.state()
        marks = set()
        for tone in (TONE_IDLE, TONE_CLEAN, TONE_PROBLEM):
            widget.show_message("t", "b", tone=tone)
            marks.add(widget.mark.text())
        self.assertEqual(len(marks), 3)

    def test_the_three_tones_are_three_different_inks(self):
        widget = self.state()
        inks = set()
        for tone in (TONE_IDLE, TONE_CLEAN, TONE_PROBLEM):
            widget.show_message("t", "b", tone=tone)
            inks.add(widget.mark.styleSheet())
        self.assertEqual(len(inks), 3)

    def test_a_state_with_no_tone_shows_no_mark(self):
        widget = self.state()
        widget.show_message("t", "b")
        self.assertTrue(widget.mark.isHidden() or not widget.mark.text())

    def test_the_actions_are_buttons_that_call_back(self):
        widget = self.state()
        called = []
        widget.show_message("t", "b", actions=[("Go", lambda: called.append(1))])
        self.assertEqual(widget.actions_layout.count(), 1)
        widget.actions_layout.itemAt(0).widget().click()
        self.assertEqual(called, [1])

    def test_showing_a_second_state_replaces_the_first_one_s_actions(self):
        """A stale button is worse than none: it does the previous state's
        job on the current state's screen."""
        widget = self.state()
        widget.show_message("t", "b", actions=[("A", lambda: None),
                                               ("B", lambda: None)])
        widget.show_message("t", "b", actions=[("C", lambda: None)])
        self.assertEqual(widget.actions_layout.count(), 1)

    def test_the_replaced_buttons_leave_the_screen_as_well_as_the_layout(self):
        """The layout said one and the window showed two. `deleteLater` only
        schedules the deletion, so until the event loop runs the old buttons
        are still visible children sitting at their old geometry - which is
        how "Open the page" ended up beside a stale "A past run"."""
        widget = self.state()
        widget.resize(400, 200)
        widget.show_message("t", "b", actions=[("Aaa", lambda: None),
                                               ("Bbb", lambda: None)])
        widget.show_message("t", "b", actions=[("Ccc", lambda: None)])
        from PySide6.QtWidgets import QPushButton
        live = [c.text() for c in widget.actions.findChildren(QPushButton)
                if c.parent() is widget.actions]
        self.assertEqual(live, ["Ccc"])

    def test_a_state_with_no_actions_hides_the_row(self):
        widget = self.state()
        widget.show_message("t", "b", actions=[("A", lambda: None)])
        widget.show_message("t", "b")
        self.assertEqual(widget.actions_layout.count(), 0)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class InTheWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        # Shown, because two of these assertions are about focus, and focus
        # does not move inside a window that was never on screen.
        self.window.show()
        self.app.processEvents()
        self.addCleanup(self.window.deleteLater)
        self.addCleanup(self.window.close)

    def labels(self) -> list:
        layout = self.window.empty_state.actions_layout
        return [layout.itemAt(i).widget().text() for i in range(layout.count())]

    def clean_result(self) -> "AnalysisResult":
        """A page that was read and produced nothing worth flagging."""
        block = TextBlock(block_id="b1", page_url="https://example.com/",
                          dom_path="p", text="A perfectly ordinary sentence.")
        page = PageResult(url="https://example.com/", depth=0, blocks=[block])
        return AnalysisResult(root_url="https://example.com/", pages=[page],
                              spans=[])

    def silent_result(self) -> "AnalysisResult":
        """A page that was fetched and yielded no text at all."""
        return AnalysisResult(root_url="https://example.com/",
                              pages=[PageResult(url="https://example.com/",
                                                depth=0)],
                              spans=[])

    # -- nothing scanned yet ---------------------------------------------

    def test_an_unscanned_window_offers_a_target_and_the_history(self):
        self.window.result = None
        self.window._show_empty_state()
        self.assertEqual(len(self.labels()), 2)
        self.assertEqual(self.window.empty_state.tone, TONE_IDLE)

    def test_choosing_a_target_puts_the_cursor_in_the_field(self):
        """Saying where the answer goes and not going there is the kind of
        instruction that gets read twice."""
        self.window.result = None
        self.window._show_empty_state()
        self.window._focus_target()
        self.assertTrue(self.window.url_edit.hasFocus())

    def test_in_a_repository_it_is_the_other_field(self):
        self.window.source = SOURCE_REPO
        self.window._focus_target()
        self.assertTrue(self.window.repo_path_edit.hasFocus())

    # -- scanned and clean ------------------------------------------------

    def test_a_clean_run_is_told_apart_from_an_unscanned_one(self):
        self.window.result = self.clean_result()
        self.window._show_empty_state()
        self.assertEqual(self.window.empty_state.tone, TONE_CLEAN)

    def test_a_clean_run_offers_the_report(self):
        self.window.result = self.clean_result()
        self.window._show_empty_state()
        self.assertTrue(any("eport" in label or "вар" in label
                            or "звіт" in label.lower() for label in self.labels()),
                        f"no report action among {self.labels()}")

    def test_the_ai_pass_is_only_offered_when_the_selector_has_it(self):
        """The account check is asynchronous, so `_ai_available()` can say
        yes while the method selector was filled before it answered and has
        no AI entry to select. Asked of the control, the button is either
        real or absent."""
        self.window.result = self.clean_result()
        self.window._show_empty_state()
        expected = 2 if self.window._ai_choice_index() >= 0 else 1
        self.assertEqual(len(self.labels()), expected, self.labels())

    def test_the_ai_pass_is_not_offered_when_it_already_ran(self):
        """Re-running the same pass answers the same question again."""
        index = self.window._ai_choice_index()
        if index < 0:
            self.skipTest("this build's method selector has no AI entry")
        self.window.method_combo.setCurrentIndex(index)
        self.window.result = self.clean_result()
        self.window._show_empty_state()
        self.assertEqual(len(self.labels()), 1, self.labels())

    # -- scanned and silent ----------------------------------------------

    def test_a_page_that_gave_no_text_is_the_problem_tone(self):
        self.window.result = self.silent_result()
        self.window._show_empty_state()
        self.assertEqual(self.window.empty_state.tone, TONE_PROBLEM)

    def test_it_offers_to_go_and_look_at_the_page(self):
        """Not "re-read in a browser", which the artboard draws: this build
        reads every site both ways already (`ui.mode_rules.auto_readers`),
        so that button would re-run the pass that just produced nothing.
        Looking at the page is the move that is actually left."""
        self.window.source = SOURCE_SITE
        self.window.url_edit.setText("https://example.com/")
        self.window.result = self.silent_result()
        self.window._show_empty_state()
        self.assertEqual(len(self.labels()), 1, self.labels())

    def test_there_is_nothing_to_open_without_an_address(self):
        self.window.source = SOURCE_SITE
        self.window.url_edit.setText("")
        self.window.result = self.silent_result()
        self.window._show_empty_state()
        self.assertEqual(self.labels(), [])

    def test_a_half_typed_address_is_not_offered_as_a_link(self):
        """`QDesktopServices` would hand "example" to the shell as a path."""
        self.window.source = SOURCE_SITE
        self.window.url_edit.setText("example")
        self.window.result = self.silent_result()
        self.window._show_empty_state()
        self.assertEqual(self.labels(), [])

    def test_a_repository_with_no_text_offers_nothing_to_open(self):
        """There is no page behind a folder of files to go and look at."""
        self.window.result = RepoAnalysisResult(root_dir="/tmp/x")
        self.window._show_empty_state()
        self.assertEqual(self.labels(), [])
        self.assertEqual(self.window.empty_state.tone, TONE_PROBLEM)


if __name__ == "__main__":
    unittest.main()
