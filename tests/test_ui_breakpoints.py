"""The window's two responsive breakpoints, checked at three widths.

A single breakpoint used to fold the whole detail column and leave the
preview column to be squeezed by whatever was left, which read as the window
jumping from three columns to one. Two breakpoints fold one column at a time:
first the detail column (which already has an inline fallback), then, only
once there truly isn't room, the preview column.

Headless: Qt runs on the offscreen platform. Unlike a bare resize() on a
QMainWindow with no top-level backing, resizeEvent does fire here once the
window has been shown, which is what MainWindow's own layout switch depends
on - see `_update_layout_mode`.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from ui.main_window import MEDIUM_BREAKPOINT, WIDE_BREAKPOINT, MainWindow
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 not available")
class Breakpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _drag_to(self, window: MainWindow, width: int) -> None:
        """Shrink stepwise like a user dragging the window edge.

        Each step fires resizeEvent, folds the column whose breakpoint was
        crossed and lowers the window's minimum width, so the next smaller
        size becomes reachable - something a single jump-resize never achieves
        because Qt clamps it against the not-yet-folded layout.
        """
        current = window.width()
        while current > width:
            current = max(width, current - 250)
            window.resize(current, 800)
            self.app.processEvents()

    def _window_at(self, width: int) -> MainWindow:
        window = MainWindow()
        window.show()
        self.app.processEvents()
        window.resize(WIDE_BREAKPOINT + 400, 800)
        self.app.processEvents()
        self._drag_to(window, width)
        return window

    def test_the_two_breakpoints_are_ordered(self):
        self.assertLess(MEDIUM_BREAKPOINT, WIDE_BREAKPOINT)

    def test_a_wide_window_shows_all_three_columns(self):
        window = self._window_at(1400)
        self.assertFalse(window.col3.isHidden())
        self.assertFalse(window.col1.isHidden())

    def test_a_medium_window_folds_only_the_detail_column(self):
        window = self._window_at((MEDIUM_BREAKPOINT + WIDE_BREAKPOINT) // 2)
        self.assertTrue(window.col3.isHidden())
        self.assertFalse(window.col1.isHidden(),
                         "the preview column must not fold at the same time as the detail column")

    def test_a_narrow_window_folds_the_preview_column_too(self):
        window = self._window_at(MEDIUM_BREAKPOINT - 100)
        self.assertTrue(window.col3.isHidden())
        self.assertTrue(window.col1.isHidden())

    def test_crossing_a_breakpoint_collapses_any_open_inline_detail(self):
        window = self._window_at((MEDIUM_BREAKPOINT + WIDE_BREAKPOINT) // 2)
        from PySide6.QtWidgets import QListWidgetItem
        item = QListWidgetItem("x")
        window._expanded_item = item
        # Drag down through the wide breakpoint, then across the medium one,
        # mirroring how a real resize travels.
        self._drag_to(window, MEDIUM_BREAKPOINT - 100)
        self.assertIsNone(window._expanded_item)


if __name__ == "__main__":
    unittest.main()
