"""The window's selectors after the swap from `QComboBox` to `InlineValue`.

`tests/test_inline_value.py` holds the widget to its own contract. This file
asks the question that one cannot: does the *window* still work once its six
selectors are no longer combo boxes?

The swap was done by keeping the names - `self.mode_combo` is still called
`mode_combo` - so nothing in the window, the mixins or the other test files
had to change. That is exactly what makes it worth testing directly: a rename
would have failed loudly, while a missing method on a compatible-looking
widget fails only on the one code path that calls it, and several of those
paths (populating providers, retranslating scopes) run only in situations a
casual click-through never reaches.

Headless: Qt runs on the offscreen platform, like the other widget tests.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from ui.main_window import MainWindow
    from ui.widgets import InlineValue
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None

#: Every selector the window builds, by the name it is addressed through.
SELECTORS = ("mode_combo", "scope_combo", "provider_combo",
             "checks_combo", "method_combo")


@unittest.skipIf(QApplication is None, "PySide6 not available")
class SelectorsInTheWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        # One window for the read-only checks: building it is the expensive
        # part, and none of these mutate it. The cases that do change state
        # build their own below.
        cls.window = MainWindow()

    @classmethod
    def tearDownClass(cls):
        cls.window.close()
        cls.window.deleteLater()

    def test_every_selector_is_an_inline_value(self):
        for name in SELECTORS:
            with self.subTest(selector=name):
                self.assertIsInstance(getattr(self.window, name), InlineValue)

    def test_every_selector_is_populated(self):
        """A selector with no items shows an empty word where a value should
        be - and `currentData()` returns None, which the run then reads as
        "no choice made" rather than as the default."""
        for name in ("mode_combo", "checks_combo", "method_combo"):
            with self.subTest(selector=name):
                selector = getattr(self.window, name)
                self.assertGreater(selector.count(), 0)
                self.assertIsNotNone(selector.currentData())

    def test_the_selectors_are_reachable_from_the_keyboard(self):
        """The window reports mouse-only controls as a finding on other
        people's pages."""
        for name in ("mode_combo", "checks_combo", "method_combo"):
            with self.subTest(selector=name):
                self.assertEqual(getattr(self.window, name).focusPolicy(),
                                 Qt.StrongFocus)

    def test_the_scope_names_kept_their_long_form(self):
        """`_retranslate_choices` writes the full scope name in as a tooltip
        under `ToolTipRole`. It is the only place in the window that uses a
        role other than `UserRole`, so it is the one most likely to have been
        dropped in the swap - and losing it is invisible until someone hovers.
        """
        scope = self.window.scope_combo
        self.assertGreater(scope.count(), 0)
        tips = [scope.itemData(i, Qt.ItemDataRole.ToolTipRole)
                for i in range(scope.count())]
        self.assertTrue(any(tips), "no scope kept a long form")

    def test_the_payloads_survived_the_swap(self):
        """`itemData` under the default role is what the run is built from."""
        mode = self.window.mode_combo
        payloads = [mode.itemData(i) for i in range(mode.count())]
        self.assertEqual(len(payloads), len(set(map(str, payloads))))
        self.assertNotIn(None, payloads)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class SelectorsDriveTheWindow(unittest.TestCase):
    """The half that mutates: each case gets its own window."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.addCleanup(self.window.deleteLater)
        self.addCleanup(self.window.close)

    def test_choosing_a_mode_still_switches_the_source(self):
        """The signal has to reach `_on_mode_changed`, which is the whole
        reason the widget emits `currentIndexChanged` under Qt's spelling."""
        mode = self.window.mode_combo
        self.assertGreater(mode.count(), 1)
        starting = self.window.source

        other = next(i for i in range(mode.count())
                     if mode.itemData(i) != starting)
        mode.setCurrentIndex(other)
        self.assertEqual(self.window.source, mode.itemData(other))
        self.assertNotEqual(self.window.source, starting)

    def test_stepping_with_the_keyboard_switches_it_too(self):
        """The keyboard path goes through `set_index`, not `setCurrentIndex`.
        Both must land in the same place - an arrow key that changes the
        shown value without changing what gets scanned is the worst of the
        failure modes here, because the window then disagrees with itself."""
        from PySide6.QtGui import QKeyEvent

        mode = self.window.mode_combo
        mode.setCurrentIndex(0)
        mode.keyPressEvent(
            QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Right, Qt.NoModifier))
        self.assertEqual(self.window.source, mode.currentData())
        self.assertEqual(mode.currentIndex(), 1)

    def test_refilling_the_providers_does_not_re_enter_its_own_handler(self):
        """`_populate_providers` clears and refills the list. If adding the
        first item announced a change, the handler that triggered the refill
        would run again inside itself."""
        provider = self.window.provider_combo
        calls = []
        provider.currentIndexChanged.connect(calls.append)
        self.window._populate_providers()
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
