"""The window has to be operable without a mouse.

This tool reports `control-name` and keyboard reachability as critical
findings on other people's pages. Measured on its own window before this:
zero calls to `setTabOrder`, `setFocusPolicy`, `setAccessibleName` or
`setShortcut` in the whole of `ui/`. Qt's default tab order is creation
order, and this window is *built* preview-first while it is *read*
findings-first - so Tab from the address field landed in the preview pane
rather than on the button that starts the run. On macOS a `QPushButton` is
not in the tab chain at all by default, which is right for an app whose
buttons are decoration and wrong for one whose main action is a button.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from ui.main_window import MainWindow
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 not available")
class KeyboardCase(unittest.TestCase):
    LANG = "en"

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.window.settings.ui_language = self.LANG
        self.window.lang = self.LANG
        self.window._retranslate_ui()
        self.window.show_setup(False)
        self.addCleanup(self.window.close)


class EveryControlCanTakeFocus(KeyboardCase):
    def test_the_action_buttons_are_in_the_tab_chain(self):
        """Qt follows the platform here, and the platform is wrong for this
        window: on macOS Tab visits text fields and lists only."""
        for name in ("analyze_btn", "cancel_btn", "settings_btn",
                     "browse_btn", "sign_in_site_btn"):
            widget = getattr(self.window, name)
            self.assertNotEqual(widget.focusPolicy(), Qt.FocusPolicy.NoFocus,
                                f"{name} cannot be reached by keyboard")

    def test_the_order_is_the_reading_order(self):
        """Say what to look at, say what to look for, start, read results."""
        order = self.window.KEYBOARD_ORDER
        self.assertLess(order.index("url_edit"), order.index("analyze_btn"))
        self.assertLess(order.index("checks_combo"), order.index("analyze_btn"))
        self.assertLess(order.index("analyze_btn"), order.index("flagged_list"))

    def test_every_name_in_the_order_exists(self):
        """A renamed widget must not silently drop out of the tab chain."""
        missing = [name for name in self.window.KEYBOARD_ORDER
                   if getattr(self.window, name, None) is None]
        self.assertEqual(missing, [])


class EveryUnlabelledControlHasAName(KeyboardCase):
    def test_the_named_controls_are_named(self):
        for name in self.window.ACCESSIBLE_NAMES:
            widget = getattr(self.window, name, None)
            if widget is None:
                continue
            self.assertTrue(widget.accessibleName().strip(),
                            f"{name} has no accessible name")

    def test_a_name_is_never_a_raw_translation_key(self):
        for name in self.window.ACCESSIBLE_NAMES:
            widget = getattr(self.window, name, None)
            if widget is None:
                continue
            said = widget.accessibleName()
            self.assertFalse(said.endswith("_full") and " " not in said,
                             f"{name} announces the key {said!r}")

    def test_the_names_follow_the_interface_language(self):
        english = self.window.url_edit.accessibleName()
        self.window.settings.ui_language = "uk"
        self.window.lang = "uk"
        self.window._retranslate_ui()
        self.assertNotEqual(self.window.url_edit.accessibleName(), english)


class TheShortcutsExist(KeyboardCase):
    def _sequences(self):
        from PySide6.QtGui import QShortcut

        return {s.key().toString() for s in self.window.findChildren(QShortcut)}

    def test_a_run_can_be_started_from_the_keyboard(self):
        """Plain Return in a text field means "I finished typing", so the
        run needs a chord of its own."""
        keys = self._sequences()
        self.assertTrue({"Ctrl+Return", "Ctrl+Enter"} & keys, keys)

    def test_settings_and_the_target_field_have_their_usual_keys(self):
        keys = self._sequences()
        self.assertIn("Ctrl+K", keys)
        self.assertIn("Ctrl+,", keys)


if __name__ == "__main__":
    unittest.main()
