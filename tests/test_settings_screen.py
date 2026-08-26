"""The settings screen as the design draws it (artboards 3d, 3q).

The shape is the claim here: five sections in a rail rather than a tab
strip, a row per decision, and a control chosen by what the decision is - a
switch for on/off, a segmented control for two to four alternatives, a combo
box only where the list is open-ended. The tests below check what that shape
has to keep true: every rail entry reaches a page, every control still saves
the setting it stands for, and nothing on screen is in the wrong language.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QComboBox
    import config
    from i18n.translations import t
    from ui.settings_dialog import SettingsDialog, _UNBUILT_ROWS
    from ui.widgets import Segmented, Switch
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 not available")
class Controls(unittest.TestCase):
    """The two controls the design introduced, on their own."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_a_switch_is_checkable_and_keeps_its_size(self):
        switch = Switch(None)
        self.assertTrue(switch.isCheckable())
        self.assertEqual(switch.size().width(), Switch.WIDTH)
        switch.setChecked(True)
        self.assertTrue(switch.isChecked())

    def test_a_segmented_control_holds_one_choice_at_a_time(self):
        seg = Segmented([("A", "a"), ("B", "b"), ("C", "c")])
        seg.set_current_data("b")
        self.assertEqual(seg.current_data(), "b")
        seg.set_current_data("c")
        self.assertEqual(seg.current_data(), "c")
        self.assertEqual(sum(1 for b in seg._buttons if b.isChecked()), 1)

    def test_an_unknown_value_falls_back_to_the_first_choice(self):
        """A settings file from another build must not leave it blank."""
        seg = Segmented([("A", "a"), ("B", "b")])
        seg.set_current_data("something-else")
        self.assertEqual(seg.current_data(), "a")


@unittest.skipIf(QApplication is None, "PySide6 not available")
class Screen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self, **overrides):
        settings = config.Settings(**overrides)
        return SettingsDialog(settings, "uk"), settings

    def test_every_rail_entry_reaches_a_page(self):
        dialog, _ = self._dialog()
        self.assertEqual(len(dialog._rail_buttons), dialog.stack.count())
        for index, button in enumerate(dialog._rail_buttons):
            button.click()
            self.assertEqual(dialog.stack.currentIndex(), index)

    def test_the_buttons_speak_the_interface_language(self):
        """The old dialog's OK/Cancel came from Qt and stayed English."""
        dialog, _ = self._dialog()
        self.assertEqual(dialog.save_btn.text(), t("save_button", "uk"))
        self.assertEqual(dialog.cancel_btn.text(), t("cancel_button", "uk"))

    def test_a_row_label_is_a_statement_not_a_field(self):
        dialog, _ = self._dialog()
        labels = [w.text() for w in dialog.findChildren(type(dialog.cache_label))]
        self.assertNotIn(t("theme_label", "uk"), labels)  # the one with a colon
        self.assertIn(t("theme_label", "uk").rstrip(":"), labels)

    def test_the_theme_is_a_segmented_control_and_saves(self):
        dialog, settings = self._dialog(theme="auto")
        self.assertIsInstance(dialog.theme_seg, Segmented)
        dialog.theme_seg.set_current_data("dark")
        dialog.settings.save = lambda: None
        dialog._on_accept()
        self.assertEqual(settings.theme, "dark")

    def test_the_switches_save_what_they_show(self):
        dialog, settings = self._dialog(unicode_check_enabled=True,
                                        auto_start_devserver=False)
        self.assertIsInstance(dialog.unicode_enabled_box, Switch)
        dialog.unicode_enabled_box.setChecked(False)
        dialog.devserver_switch.setChecked(True)
        dialog.settings.save = lambda: None
        dialog._on_accept()
        self.assertFalse(settings.unicode_check_enabled)
        self.assertTrue(settings.auto_start_devserver)

    def test_a_category_row_goes_dead_when_the_pass_is_off(self):
        """The categories mean nothing while the pass is off, and a row that
        still looks settable would be the screen contradicting itself."""
        dialog, _ = self._dialog(unicode_check_enabled=True)
        row = dialog.category_boxes["invisible"].parentWidget()
        self.assertTrue(row.isEnabled())
        dialog.unicode_enabled_box.setChecked(False)
        self.assertFalse(row.isEnabled())

    def test_the_categories_still_save(self):
        dialog, settings = self._dialog()
        for key, switch in dialog.category_boxes.items():
            switch.setChecked(key in ("invisible", "space"))
        dialog.settings.save = lambda: None
        dialog._on_accept()
        self.assertEqual(sorted(settings.unicode_categories),
                         ["invisible", "space"])

    def test_the_language_and_model_stay_dropdowns(self):
        """Open-ended lists are the one place a combo box is still right."""
        dialog, _ = self._dialog()
        self.assertIsInstance(dialog.lang_combo, QComboBox)
        self.assertIsInstance(dialog.cc_model_combo, QComboBox)

    def test_what_the_design_shows_and_this_does_not_is_written_down(self):
        for reason in _UNBUILT_ROWS.values():
            self.assertTrue(reason.strip())

    def test_the_cache_row_says_where_the_cache_is(self):
        import judgment_cache

        dialog, _ = self._dialog()
        self.assertIn(str(judgment_cache.cache_dir()), dialog.cache_label.text())


if __name__ == "__main__":
    unittest.main()
