"""Two widths at once, which is what artboard 3o asks for.

The width switcher answers one width at a time, so checking "this only breaks
on mobile" meant flipping back and forth and holding the desktop layout in
your head. Side by side, the difference is the thing on screen.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    from ui.main_window import MainWindow
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 not available")
class SideBySide(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.window.settings.ui_language = "en"
        self.window.lang = "en"
        self.window._retranslate_ui()
        self.window.show_setup(False)
        self.addCleanup(self.window.close)

    def test_the_second_view_is_not_built_until_it_is_asked_for(self):
        """A QWebEngineView is a renderer process. Making one for a
        comparison nobody asked for costs every user of this window."""
        self.assertIsNone(self.window.compare_pane)
        self.assertIsNone(self.window.compare_view)

    def test_turning_it_on_builds_the_pane_and_shows_it(self):
        self.window._on_compare_widths(True)
        self.assertIsNotNone(self.window.compare_view)
        # `isVisibleTo`, not `isVisible`: the window itself is never shown
        # in these tests, and an unshown parent makes every child invisible.
        self.assertTrue(
            self.window.compare_pane.isVisibleTo(self.window.compare_pane.parent()))

    def test_turning_it_off_hides_it_and_keeps_the_view(self):
        self.window._on_compare_widths(True)
        self.window._on_compare_widths(False)
        self.assertFalse(
            self.window.compare_pane.isVisibleTo(self.window.compare_pane.parent()))
        self.assertIsNotNone(self.window.compare_view)

    def test_the_narrow_pane_is_the_narrowest_audited_width(self):
        """Not a number invented here: the audit runs at these widths, and a
        preview labelled 320 has to be the same 320 the finding came from."""
        from ui.main_window import responsive_breakpoints

        self.window._on_compare_widths(True)
        self.assertEqual(self.window._compare_width,
                         responsive_breakpoints()[-1][1])

    def test_the_narrow_view_is_never_scaled_up(self):
        """A 320px layout blown up to fill 500px is a picture of a phone,
        not a page at 320."""
        self.window._on_compare_widths(True)
        self.window.compare_pane.resize(900, 600)
        self.window._fit_compare_zoom()
        self.assertEqual(self.window.compare_view.zoomFactor(), 1.0)
        self.assertEqual(self.window.compare_view.maximumWidth(),
                         self.window._compare_width)

    def test_a_column_narrower_than_the_width_scales_down(self):
        self.window._on_compare_widths(True)
        self.window.compare_pane.resize(160, 600)
        self.window._fit_compare_zoom()
        self.assertLess(self.window.compare_view.zoomFactor(), 1.0)

    def test_the_button_reads_as_a_sentence_in_every_language(self):
        from i18n.translations import t

        for lang in ("uk", "it", "en"):
            for key in ("compare_widths", "compare_widths_full"):
                self.assertNotEqual(t(key, lang), key)


if __name__ == "__main__":
    unittest.main()
