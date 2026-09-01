"""The project profile decides something, and says what it decided.

Until now the window drew a card that named the detected stack and changed
nothing: a person who chose an SPFx checkout still had to know that
`--web-parts` existed, that it needed the address of the site the parts ship
into, and that the CLI was the only place to ask for it.

The risk that comes with fixing it is the one these tests are mostly about:
a default that changes the run without saying so. So every suggestion the
window applies has to be on screen, with the marker file that justified it,
and a switch the person set themselves has to survive the next detection.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from analysis_modes import SOURCE_REPO, SOURCE_SITE


class _Window(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def tree(self, files: dict) -> Path:
        for name, content in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return self.root

    def window(self):
        from ui.main_window import MainWindow

        window = MainWindow()
        self.addCleanup(window.deleteLater)
        return window


class WhatTheTargetAsksFor(_Window):
    def test_a_folder_that_serves_itself_pre_ticks_its_dev_server(self):
        window = self.window()
        folder = self.tree({"vite.config.ts": "export default {}"})
        window.app_state.set_source(SOURCE_REPO)
        window.repo_path_edit.setText(str(folder))
        self.assertTrue(window.auto_devserver_check.isChecked())

    def test_the_reason_is_on_screen_with_the_file_that_proved_it(self):
        window = self.window()
        folder = self.tree({"vite.config.ts": "export default {}"})
        window.app_state.set_source(SOURCE_REPO)
        window.repo_path_edit.setText(str(folder))
        note = window.setup_screen.profile_note
        self.assertTrue(note.isVisibleTo(window.setup_screen))
        self.assertIn("vite.config.ts", note.text())

    def test_a_plain_folder_asks_for_nothing_and_shows_nothing(self):
        window = self.window()
        folder = self.tree({"index.html": "<html></html>"})
        window.app_state.set_source(SOURCE_REPO)
        window.repo_path_edit.setText(str(folder))
        self.assertEqual(window.setup_screen.profile_note.text(), "")

    def test_a_site_paired_with_an_spfx_checkout_confines_the_audit(self):
        window = self.window()
        checkout = self.tree({"config/package-solution.json": "{}"})
        window.app_state.set_source(SOURCE_SITE)
        window.url_edit.setText("https://contoso.sharepoint.com/sites/intranet")
        window.paired_repo_edit.setText(str(checkout))
        self.assertTrue(window.app_state.web_parts)
        self.assertTrue(
            window.setup_screen.web_parts_box.isVisibleTo(window.setup_screen))

    def test_a_site_without_a_checkout_does_not(self):
        window = self.window()
        window.app_state.set_source(SOURCE_SITE)
        window.url_edit.setText("https://example.com")
        self.assertFalse(window.app_state.web_parts)

    def test_a_switch_the_person_turned_off_stays_off(self):
        """The whole feature's risk in one test: a suggestion must never
        undo a deliberate choice."""
        window = self.window()
        checkout = self.tree({"config/package-solution.json": "{}"})
        window.app_state.set_source(SOURCE_SITE)
        window.url_edit.setText("https://contoso.sharepoint.com/sites/a")
        window.paired_repo_edit.setText(str(checkout))
        window.app_state.set_web_parts(False)          # by hand
        window.url_edit.setText("https://contoso.sharepoint.com/sites/b")
        self.assertFalse(window.app_state.web_parts)

    def test_several_projects_in_a_folder_are_named(self):
        window = self.window()
        folder = self.tree({"one/config/package-solution.json": "{}",
                            "two/config/package-solution.json": "{}"})
        window.app_state.set_source(SOURCE_REPO)
        window.repo_path_edit.setText(str(folder))
        text = window.setup_screen.projects_note.text()
        self.assertIn("one", text)
        self.assertIn("two", text)


class WhatReachesTheRun(_Window):
    def test_the_parts_are_read_from_the_paired_checkout(self):
        """`--web-parts` with no parts audits the whole page, exactly as
        before - it does not start a run with nothing to confine."""
        window = self.window()
        empty = self.tree({"config/package-solution.json": "{}"})
        window.app_state.set_source(SOURCE_SITE)
        window.url_edit.setText("https://contoso.sharepoint.com/sites/a")
        window.paired_repo_edit.setText(str(empty))
        self.assertEqual(window.view_model._web_parts_for_run(), ())

    def test_nothing_is_read_when_no_checkout_was_named(self):
        window = self.window()
        window.app_state.set_source(SOURCE_SITE)
        window.url_edit.setText("https://example.com")
        window.app_state.set_web_parts(True)
        self.assertEqual(window.view_model._web_parts_for_run(), ())


if __name__ == "__main__":
    unittest.main()
