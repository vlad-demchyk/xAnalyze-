"""The one window: a controls column on the left, all of the work behind it.

Replaces `test_modern_ui.py`, which tested a second `MainWindow` that used to
live in `main.py` - the redesign made the entry point in `31fe7f2`. Those 66
tests all passed while the window they covered was missing the accessibility
audit, report export, fix-on-disk, undo, bulk rewrite and the preview
highlight, and while the window that had all of those was the one nobody
launched. Tests over a discarded window are worse than no tests: they read as
coverage.

So these assert two things instead. That the entry point launches the
complete window - the regression that started it - and that the complete
window's controls are in the left column the redesign was reaching for.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QScrollArea
    from analysis_modes import (
        CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS, METHOD_AI, METHOD_LOCAL,
        SOURCE_FILE, SOURCE_REPO, SOURCE_SITE,
    )
    from ui.main_window import (
        MEDIUM_BREAKPOINT, SIDEBAR_WIDTH, SIDEBAR_WIDTH_NARROW, MainWindow,
    )
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
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()


class SidebarColumn(WindowCase):
    def test_controls_are_in_a_scrollable_left_column(self):
        self.assertIsInstance(self.window.sidebar_scroll, QScrollArea)
        self.assertIs(self.window.sidebar_scroll.widget(), self.window.toolbar)

    def test_the_column_can_scroll_rather_than_clip(self):
        """Its content is taller than a small window; nothing may be lost."""
        self.assertTrue(self.window.sidebar_scroll.widgetResizable())

    def test_the_column_opens_at_its_designed_width(self):
        self.assertEqual(self.window.body_splitter.sizes()[0], SIDEBAR_WIDTH)

    def test_widening_the_window_widens_the_results_not_the_form(self):
        before = self.window.body_splitter.sizes()
        self.window.resize(self.window.width() + 300, self.window.height())
        self.app.processEvents()
        after = self.window.body_splitter.sizes()
        self.assertEqual(after[0], before[0])
        self.assertGreater(after[1], before[1])

    def test_the_column_can_be_squeezed(self):
        """A hard minimum here raises the whole window's minimum width.

        That is what broke the narrow layout the first time this column was
        built: with a fixed width and no horizontal scrolling, the window
        could not shrink far enough to reach its own breakpoints.
        """
        self.assertEqual(self.window.sidebar_scroll.minimumWidth(), 0)

    def test_the_body_sits_beside_the_column_not_under_it(self):
        splitter = self.window.body_splitter
        self.assertEqual(
            [splitter.widget(i) for i in range(splitter.count())],
            [self.window.sidebar_scroll, self.window.columns_splitter])

    def test_the_column_is_the_only_thing_in_the_central_layout(self):
        layout = self.window.centralWidget().layout()
        widgets = [layout.itemAt(i).widget() for i in range(layout.count())]
        self.assertEqual(widgets, [self.window.body_splitter])

    def test_every_per_scan_control_is_in_the_column(self):
        column = self.window.sidebar_scroll
        for name in ("mode_combo", "checks_combo", "method_combo",
                     "provider_combo", "source_controls_stack",
                     "analyze_btn", "cancel_btn", "settings_btn",
                     "advanced_toggle", "advanced_row"):
            widget = getattr(self.window, name)
            with self.subTest(control=name):
                self.assertTrue(column.isAncestorOf(widget),
                                f"{name} is not in the controls column")

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

    def test_the_column_narrows_once_the_body_has_folded(self):
        self._drag_to(MEDIUM_BREAKPOINT - 100)
        self.assertEqual(self.window.body_splitter.sizes()[0],
                         SIDEBAR_WIDTH_NARROW)

    def test_the_column_widens_again(self):
        self._drag_to(MEDIUM_BREAKPOINT - 100)
        self.window.resize(1400, 800)
        self.app.processEvents()
        self.window._update_layout_mode(force=True)
        self.assertEqual(self.window.body_splitter.sizes()[0], SIDEBAR_WIDTH)


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
