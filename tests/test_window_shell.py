"""The one window: a controls row across the top, all of the work under it.

Replaces `test_modern_ui.py`, which tested a second `MainWindow` that used to
live in `main.py` - the redesign made the entry point in `31fe7f2`. Those 66
tests all passed while the window they covered was missing the accessibility
audit, report export, fix-on-disk, undo, bulk rewrite and the preview
highlight, and while the window that had all of those was the one nobody
launched. Tests over a discarded window are worse than no tests: they read as
coverage.

So these assert two things instead. That the entry point launches the
complete window - the regression that started it - and that the complete
window's controls are where the current design puts them.

That second half was written for a left-hand column and is now written for a
top row: the Claude Design bundle (2026-08-24) replaces the column with a
strip of inline values above the results. The intent of each case survived
the move, including the one that matters most - a controls area must never
raise the window's own minimum width, because that is what puts the narrow
layouts out of reach. It did exactly that when the row was first built, at a
1271px floor, which is why the case below measures it directly.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from analysis_modes import (
        CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS, METHOD_AI, METHOD_LOCAL,
        SOURCE_FILE, SOURCE_REPO, SOURCE_SITE,
    )
    from ui import theme
    from ui.main_window import MEDIUM_BREAKPOINT, TOP_ROW_HEIGHT, MainWindow
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 not available")
class EntryPoint(unittest.TestCase):
    """`python main.py` must open the window that can do the work."""

    def test_main_launches_the_complete_window(self):
        import main
        from ui.main_window import MainWindow as Complete

        self.assertIs(main.MainWindow, Complete)

    def test_main_defines_no_window_of_its_own(self):
        """The redesign lived here as a second, weaker MainWindow."""
        import main

        self.assertEqual(main.MainWindow.__module__, "ui.main_window")


@unittest.skipIf(QApplication is None, "PySide6 not available")
class WindowCase(unittest.TestCase):
    """One window per test, closed afterwards.

    `test_modern_ui` showed dozens of windows and closed none, and the
    leaked top-level widgets changed how a *later* window could be resized -
    which is how a genuine layout regression came to depend on test order.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
    def setUp(self):
        self.window = MainWindow()
        # Every case below is about the working layout - the top row, the
        # three columns, the fields in the strip. The window opens on the
        # setup screen (artboard 3b) while nothing has run; `TheSetupScreen`
        # covers that, and covers the fact that it is where it opens.
        self.window.show_setup(False)
        # Styled, the way the app actually runs. It matters for anything
        # measured: the top row is 52px styled and 42px bare, because QSS
        # padding is what gives a control its height, so measuring the bare
        # window meant asserting a geometry no user ever sees.
        #
        # On the *window*, never on the application. `apply_theme` sets the
        # sheet on the QApplication, which re-polishes every live widget in
        # the process - including the ones earlier tests have closed but not
        # yet collected - and that segfaults the run. Scoped here, it reaches
        # this window's tree and nothing else.
        self.window.setStyleSheet(theme.build_qss(theme.current_palette("light")))
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()


class TopRow(WindowCase):
    """The controls strip above the results."""

    #: The width the design draws the row at, and the width the window opens
    #: at. One line is the whole point of the inline values; if the row needs
    #: two here, the sentence has stopped fitting.
    DESIGN_WIDTH = 1300

    def test_the_controls_are_in_the_top_row(self):
        for name in ("mode_combo", "checks_combo", "source_controls_stack",
                     "analyze_btn"):
            with self.subTest(control=name):
                self.assertTrue(
                    self.window.toolbar.isAncestorOf(getattr(self.window, name)))

    def test_the_row_wraps_rather_than_clips(self):
        """Its content is wider than a small window; nothing may be lost.

        The column scrolled for the same reason. A row cannot scroll - a
        control you have to scroll sideways to reach is one you will not find
        - so it wraps onto a second line instead, which is what the design
        asks for at 1000px too.
        """
        self.window.resize(self.DESIGN_WIDTH, 800)
        self.app.processEvents()
        one_line = self.window.toolbar.height()

        self.window.resize(MEDIUM_BREAKPOINT + 60, 800)
        self.app.processEvents()
        self.assertGreater(self.window.toolbar.height(), one_line,
                           "the row did not wrap; something was clipped")

    def test_the_row_is_one_line_at_the_design_width(self):
        self.window.resize(self.DESIGN_WIDTH, 800)
        self.app.processEvents()
        self.assertLessEqual(self.window.toolbar.height(), TOP_ROW_HEIGHT + 4)

    def test_widening_the_window_widens_the_results_not_the_form(self):
        """The row keeps its one line and hands the extra width to the body,
        the way the column kept its 268px."""
        self.window.resize(self.DESIGN_WIDTH, 800)
        self.app.processEvents()
        before = self.window.toolbar.height()
        body_before = self.window.columns_splitter.width()

        self.window.resize(self.DESIGN_WIDTH + 300, 800)
        self.app.processEvents()
        self.assertEqual(self.window.toolbar.height(), before)
        self.assertGreater(self.window.columns_splitter.width(), body_before)

    def test_the_row_does_not_raise_the_window_minimum_width(self):
        """The regression this file exists to catch, in its second form.

        A `QHBoxLayout` hands its parent the sum of its children's minimum
        widths, so the first version of this row put a 1271px floor under the
        window and both narrow layouts became unreachable - the same defect
        the column once had, arriving from the other direction. The window
        has to be able to shrink past its own narrowest breakpoint.
        """
        self.assertLess(self.window.minimumSizeHint().width(),
                        MEDIUM_BREAKPOINT)

    def test_the_body_sits_under_the_row_not_beside_it(self):
        """Controls, the run summary, what went wrong, then the results.

        The summary and the diagnoses are between them because both describe
        the run the controls set up and the list underneath shows: "the
        server refused seven of twelve addresses" belongs beside "27
        findings", not inside the list of the 27."""
        layout = self.window.centralWidget().layout()
        widgets = [layout.itemAt(i).widget() for i in range(layout.count())]
        self.assertEqual(widgets, [self.window.toolbar,
                                   self.window.summary_bar,
                                   self.window.diagnosis_strip,
                                   self.window.body_stack])

    def test_the_run_history_is_behind_a_button_not_in_the_row(self):
        """A list cannot live on a one-line row. It moved into a popup, and
        the button that opens it took its place."""
        self.assertFalse(
            self.window.toolbar.isAncestorOf(self.window.runs_scroll))
        self.assertTrue(self.window.toolbar.isAncestorOf(self.window.runs_btn))
        self.assertFalse(self.window.runs_popup.isVisible())

    def test_the_run_history_opens_and_closes_from_its_button(self):
        self.window._on_runs_clicked()
        self.assertTrue(self.window.runs_popup.isVisible())
        self.window._on_runs_clicked()
        self.assertFalse(self.window.runs_popup.isVisible())

    def test_no_label_is_printed_twice(self):
        """Each selector carries its own label now. The standalone QLabels
        are kept for `_retranslate_ui` and must stay out of sight, or every
        setting reads as "глибина глибина 2"."""
        for name in ("mode_label", "checks_label", "method_label",
                     "provider_label", "url_label", "depth_label"):
            with self.subTest(label=name):
                self.assertTrue(getattr(self.window, name).isHidden())

    def test_the_source_stack_asks_only_for_the_page_it_shows(self):
        """A `QStackedWidget` asks for the widest of all its pages. Left
        alone it reserved 462px of the row for the repository fields during a
        site scan, which pushed the row onto a second line at every width."""
        stack = self.window.source_controls_stack
        shown = stack.currentWidget().sizeHint().width()
        self.assertLessEqual(stack.sizeHint().width(), max(shown, 1) + 40)

    def test_the_advanced_block_starts_hidden(self):
        self.assertFalse(self.window.advanced_row.isVisibleTo(self.window))

    def test_the_advanced_toggle_reveals_it(self):
        self.window.advanced_toggle.setChecked(True)
        self.window._on_advanced_toggle(True)
        self.app.processEvents()
        self.assertTrue(self.window.advanced_row.isVisibleTo(self.window))

    def _drag_to(self, width: int) -> None:
        """Shrink stepwise, the way a person drags a window edge.

        A single `resize` to a much smaller width is clamped by Qt against
        the layout as it stands, so the breakpoint is never crossed. Each
        step folds whatever its own width folds, which lowers the minimum
        and makes the next step reachable - the same approach
        `test_ui_breakpoints` takes, and for the same reason.
        """
        current = self.window.width()
        while current > width:
            current = max(width, current - 250)
            self.window.resize(current, 700)
            self.app.processEvents()

    def test_the_row_grows_once_the_body_has_folded(self):
        """The column shrank to give the findings list room. The row cannot
        shrink sideways, so what it does instead is wrap - and the cost is
        height taken from the body, which is the trade the design makes."""
        self.window.resize(1400, 800)
        self.app.processEvents()
        wide = self.window.toolbar.height()
        self._drag_to(MEDIUM_BREAKPOINT - 100)
        self.assertGreater(self.window.toolbar.height(), wide)

    def test_the_row_returns_to_one_line(self):
        """Wrapping must be reversible: a row that stayed two lines high
        after the window was widened again would keep the space it borrowed."""
        self._drag_to(MEDIUM_BREAKPOINT - 100)
        self.window.resize(1400, 800)
        self.app.processEvents()
        self.assertLessEqual(self.window.toolbar.height(), TOP_ROW_HEIGHT + 4)


class TheSetupScreen(unittest.TestCase):
    """Artboard 3b: the screen the window opens on.

    It used to open on the working layout - three columns of results, all
    empty - with the whole of the run's settings folded into one line of
    inline values above them. That line is right during work and wrong
    before any: it is the entire task, written in eight words across the top
    of a blank window.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_the_window_opens_on_it(self):
        self.assertEqual(self.window.body_stack.currentIndex(), 0)
        self.assertFalse(self.window.inline_strip.isVisible())

    def test_the_target_fields_move_there_and_come_back(self):
        """One set of fields, lent to whichever surface is asking. A second
        address field on the setup screen would be a second place for the
        same value to be wrong in."""
        screen = self.window.setup_screen
        self.assertGreaterEqual(
            screen.target_layout.indexOf(self.window.source_controls_stack), 0)
        self.window.show_setup(False)
        self.assertEqual(
            self.window._strip_layout.indexOf(self.window.source_controls_stack),
            self.window._strip_target_index)
        self.assertEqual(
            self.window._toolbar_actions.indexOf(self.window.analyze_btn),
            self.window._analyze_index)
        self.window.show_setup(True)
        self.assertGreaterEqual(
            screen.target_layout.indexOf(self.window.source_controls_stack), 0)

    def test_starting_a_run_gives_the_window_to_the_working_layout(self):
        self.window._reset_scan_ui()
        self.assertEqual(self.window.body_stack.currentIndex(), 1)
        self.assertTrue(self.window.inline_strip.isVisible())

    def test_a_choice_made_here_is_the_same_choice_the_top_row_shows(self):
        """Both surfaces render one `AppState`, rather than each keeping a
        copy of the decision."""
        screen = self.window.setup_screen
        screen.source_buttons[SOURCE_REPO][0].setChecked(True)
        self.assertEqual(self.window.app_state.source, SOURCE_REPO)
        self.window.app_state.set_source(SOURCE_SITE)
        self.assertTrue(screen.source_buttons[SOURCE_SITE][0].isChecked())

    def test_it_does_not_put_a_floor_under_the_window(self):
        """Four cards side by side are wide, and a stacked widget asks for
        the widest of all its pages whether it is showing them or not."""
        self.window.show_setup(False)
        self.assertLess(self.window.minimumSizeHint().width(), MEDIUM_BREAKPOINT)

    def test_the_summary_names_what_the_run_will_be(self):
        self.window.app_state.set_target("example.com")
        self.window.setup_screen.refresh()
        text = self.window.setup_screen.summary.text()
        self.assertIn("example.com", text)


class ThreeColumnsInReadingOrder(WindowCase):
    """The body, as artboard 3a lays it out.

    The columns are built preview-first, because the preview owns the width
    switcher and the stack the run panels are pushed onto. They were also
    *added* in that order, so the window opened with the preview on the left
    and the list of findings in the middle - the list being the thing the
    window is for.
    """

    def test_the_findings_come_first_and_the_preview_second(self):
        splitter = self.window.columns_splitter
        self.assertEqual(splitter.count(), 3)
        self.assertIs(splitter.widget(1), self.window.col1)   # the preview
        self.assertIs(splitter.widget(2), self.window.col3)   # the detail
        # And the first is the one holding the findings list.
        self.assertIn(self.window.results_stack,
                      splitter.widget(0).findChildren(type(self.window.results_stack)))

    def test_the_preview_is_the_widest_of_the_three(self):
        sizes = self.window.columns_splitter.sizes()
        self.assertEqual(max(sizes), sizes[1], sizes)


class AnEmptyPreview(WindowCase):
    """What the preview column shows before a run has opened anything.

    It used to show an empty `QWebEngineView`, which paints its own
    background over the panel: a canvas-coloured rectangle with square
    corners where the design has a surface, saying nothing.
    """

    def test_it_shows_the_empty_state_not_the_browser(self):
        self.window.current_preview_url = None
        self.window._apply_mode_visibility()
        self.assertIs(self.window.col1_stack.currentWidget(),
                      self.window.preview_empty)

    def test_the_empty_state_says_which_absence_it_is(self):
        self.window.current_preview_url = None
        self.window._apply_mode_visibility()
        self.assertTrue(self.window.preview_empty.title.text().strip())
        self.assertTrue(self.window.preview_empty.body.text().strip())

    def test_a_page_gives_the_column_back_to_the_browser(self):
        self.window.current_preview_url = "https://example.com/"
        self.window._apply_mode_visibility()
        self.assertIs(self.window.col1_stack.currentWidget(),
                      self.window.site_view)


class SourceFields(WindowCase):
    """The source picker swaps the fields, as the redesign's chips did."""

    def test_a_site_shows_the_url_and_the_depth(self):
        self.window.app_state.set_source(SOURCE_SITE)
        self.window._apply_mode_visibility()
        self.assertEqual(self.window.source_controls_stack.currentIndex(), 0)

    def test_a_repository_shows_the_path_and_the_scope(self):
        self.window.app_state.set_source(SOURCE_REPO)
        self.window.source = SOURCE_REPO
        self.window._apply_mode_visibility()
        self.assertEqual(self.window.source_controls_stack.currentIndex(), 1)

    def test_a_single_file_shows_only_a_path(self):
        self.window.app_state.set_source(SOURCE_FILE)
        self.window.source = SOURCE_FILE
        self.window._apply_mode_visibility()
        self.assertEqual(self.window.source_controls_stack.currentIndex(), 2)


class TheWorkTheRedesignLost(WindowCase):
    """Each of these was absent from the window that shipped as the app."""

    def test_the_accessibility_audit_is_reachable(self):
        self.assertTrue(hasattr(self.window.view_model, "_start_audit"))
        self.assertTrue(hasattr(self.window, "_on_audit_finished"))

    def test_the_check_choice_reaches_the_request(self):
        """The redesign computed `wants_audit` and never read it."""
        self.window.app_state.set_checks((CHECK_ACCESSIBILITY,))
        self.assertTrue(self.window.view_model.current_request()
                        .wants_accessibility)
        self.window.app_state.set_checks((CHECK_AI_PATTERNS,))
        request = self.window.view_model.current_request()
        self.assertTrue(request.wants_ai_patterns)
        self.assertFalse(request.wants_accessibility)

    def test_both_checks_at_once_ask_both_questions(self):
        self.window.app_state.set_checks(
            (CHECK_AI_PATTERNS, CHECK_ACCESSIBILITY))
        request = self.window.view_model.current_request()
        self.assertTrue(request.wants_ai_patterns)
        self.assertTrue(request.wants_accessibility)

    def test_the_method_choice_reaches_the_detector(self):
        """The redesign hardcoded the scope and ignored the method."""
        self.window.app_state.set_checks((CHECK_AI_PATTERNS,))
        self.window.app_state.set_methods((METHOD_LOCAL,))
        name, _config = self.window.view_model._detector_for_request()
        self.assertEqual(name, "offline")

    def test_report_export_exists(self):
        self.assertIsNotNone(self.window.download_btn)
        self.assertTrue(hasattr(self.window, "_on_export_report_clicked"))
        self.assertTrue(hasattr(self.window, "_on_styled_report_clicked"))

    def test_writing_a_fix_and_taking_it_back_both_exist(self):
        self.assertTrue(hasattr(self.window, "_on_fix_on_disk_clicked"))
        self.assertTrue(hasattr(self.window, "_on_undo_fix_clicked"))

    def test_bulk_rewrite_exists(self):
        self.assertTrue(hasattr(self.window, "_on_auto_replace_clicked"))
        self.assertTrue(hasattr(self.window, "_on_generate_list_clicked"))

    def test_the_preview_highlight_exists(self):
        self.assertTrue(hasattr(self.window, "_load_preview_and_highlight"))
        self.assertTrue(hasattr(self.window, "_run_pending_highlight"))

    def test_a_finding_can_be_suppressed(self):
        self.assertTrue(hasattr(self.window, "_on_ignore_span_clicked"))
        self.assertTrue(hasattr(self.window, "_on_ignore_issue_clicked"))

    def test_the_preview_has_a_width_switcher(self):
        self.assertTrue(self.window.breakpoint_buttons)


class DisabledUntilThereIsSomethingToDo(WindowCase):
    """A button that writes to disk is only pressable when it has work."""

    def test_export_is_off_before_a_scan(self):
        self.window._update_audit_buttons_enabled()
        self.assertFalse(self.window.download_btn.isEnabled())

    def test_fix_on_disk_is_off_before_a_scan(self):
        self.window._update_audit_buttons_enabled()
        self.assertFalse(self.window.fix_on_disk_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
