"""The window's side of starting a dev server for a repo target.

`_start_audit`/`_start_copy_pass` read `source`/`target` straight off
`AppState`, not from a request object - so making them read a freshly
started local server means briefly resolving `AppState` to it and putting
the user's actual choice (Repository) straight back once the run has
started. These tests are about that resolve-then-restore, and about the
server always being stopped once the analysis it was started for is done -
not about the real subprocess, which `tests/test_devserver.py` and a live
run already cover.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QMessageBox

    import config
    from analysis_modes import SOURCE_REPO, SOURCE_SITE
    from ui.main_window import MainWindow
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None

#: This file is where the settings leak was found: a test checked the real
#: auto-start toggle for real and left it flipped on disk for whoever opened
#: the actual app next, with no failure anywhere to say so. The workaround
#: here - patching `Settings.save` for the whole module - was written with a
#: note that the gap was codebase-wide and closing it properly was a larger
#: change than this file's tests were the reason to make.
#:
#: It has since been closed properly (`P-13`): `config.config_file()` resolves
#: the path at the moment of the write, and `tests/conftest.py` points
#: `XDG_CONFIG_HOME` at a temporary directory for the whole run. The patch
#: below is kept anyway, because these tests assert *that* a save happened,
#: and a no-op save is a cheaper way to say so than reading a file back.
_save_patch = None


def setUpModule():
    global _save_patch
    if QApplication is None:
        return
    _save_patch = patch.object(config.Settings, "save", lambda self: None)
    _save_patch.start()


def tearDownModule():
    if _save_patch is not None:
        _save_patch.stop()


@unittest.skipIf(QApplication is None, "PySide6 not available")
class DevServerStackDetection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.window = MainWindow()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.tmp.cleanup()

    def test_a_non_repo_source_is_never_checked(self):
        self.window.app_state.set_source(SOURCE_SITE)
        self.assertIsNone(self.window._devserver_stack_for_repo())

    def test_a_repo_with_satisfied_deps_is_still_detected(self):
        """Deps being ready is not the same question as "is there a
        stack" - conflating them once meant a repo with `node_modules/`
        already installed never started a server at all."""
        (self.repo / "package.json").write_text("{}", encoding="utf-8")
        (self.repo / "node_modules").mkdir()
        self.window.app_state.set_source(SOURCE_REPO)
        self.window.repo_path_edit.setText(str(self.repo))
        stack = self.window._devserver_stack_for_repo()
        self.assertIsNotNone(stack)
        self.assertEqual(stack.name, "node")

    def test_a_repo_with_missing_deps_is_detected(self):
        (self.repo / "package.json").write_text("{}", encoding="utf-8")
        self.window.app_state.set_source(SOURCE_REPO)
        self.window.repo_path_edit.setText(str(self.repo))
        stack = self.window._devserver_stack_for_repo()
        self.assertIsNotNone(stack)
        self.assertEqual(stack.name, "node")

    def test_a_repo_with_no_stack_is_not_detected(self):
        self.window.app_state.set_source(SOURCE_REPO)
        self.window.repo_path_edit.setText(str(self.repo))
        self.assertIsNone(self.window._devserver_stack_for_repo())


@unittest.skipIf(QApplication is None, "PySide6 not available")
class ResolveThenRestore(unittest.TestCase):
    """`_on_devserver_ready` must leave the UI's own choice untouched."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = str(Path(self.tmp.name))
        self.window = MainWindow()
        self.window.app_state.set_source(SOURCE_REPO)
        self.window.repo_path_edit.setText(self.repo)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.tmp.cleanup()

    def test_source_and_target_are_site_and_the_url_during_the_call(self):
        seen = {}

        def fake_analyze():
            seen["source"] = self.window.app_state.source
            seen["target"] = self.window.app_state.target
            return None

        with patch.object(self.window.view_model, "analyze", side_effect=fake_analyze):
            self.window._on_devserver_ready("http://localhost:5173", MagicMock())

        self.assertEqual(seen["source"], SOURCE_SITE)
        self.assertEqual(seen["target"], "http://localhost:5173")

    def test_source_and_target_are_restored_after_the_call(self):
        with patch.object(self.window.view_model, "analyze", return_value=None):
            self.window._on_devserver_ready("http://localhost:5173", MagicMock())

        self.assertEqual(self.window.app_state.source, SOURCE_REPO)
        self.assertEqual(self.window.app_state.target, self.repo)

    def test_restored_even_when_analyze_raises(self):
        with patch.object(self.window.view_model, "analyze",
                          side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self.window._on_devserver_ready("http://localhost:5173", MagicMock())

        self.assertEqual(self.window.app_state.source, SOURCE_REPO)
        self.assertEqual(self.window.app_state.target, self.repo)

    def test_no_source_changed_signal_is_emitted(self):
        """The combo box must not flicker to "Website" and back."""
        seen = []
        self.window.app_state.source_changed.connect(seen.append)
        with patch.object(self.window.view_model, "analyze", return_value=None):
            self.window._on_devserver_ready("http://localhost:5173", MagicMock())
        self.assertEqual(seen, [])

    def test_the_running_process_is_remembered(self):
        proc = MagicMock()
        with patch.object(self.window.view_model, "analyze", return_value=None):
            self.window._on_devserver_ready("http://localhost:5173", proc)
        self.assertIs(self.window._devserver_proc, proc)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class FallbackAndCleanup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_a_failed_devserver_still_calls_analyze(self):
        """Falls back to the static scan - the CLI's own rule."""
        with patch.object(self.window.view_model, "analyze",
                          return_value=None) as analyze:
            self.window._on_devserver_failed("no output for 30s")
        analyze.assert_called_once_with()

    def test_the_button_is_recovered_only_when_nothing_started(self):
        self.window.analyze_btn.setEnabled(False)
        self.window._recover_button_if_nothing_started(None)
        self.assertFalse(self.window.analyze_btn.isEnabled())  # a run is going

        self.window._recover_button_if_nothing_started("browser_failed")
        self.assertTrue(self.window.analyze_btn.isEnabled())

    def test_busy_going_false_stops_a_running_devserver(self):
        proc = MagicMock()
        self.window._devserver_proc = proc
        self.window._on_busy_changed(False)
        proc.stop.assert_called_once()
        self.assertIsNone(self.window._devserver_proc)

    def test_busy_going_true_does_not_touch_the_devserver(self):
        proc = MagicMock()
        self.window._devserver_proc = proc
        self.window._on_busy_changed(True)
        proc.stop.assert_not_called()

    def test_close_stops_a_running_devserver(self):
        proc = MagicMock()
        self.window._devserver_proc = proc
        self.window.close()
        proc.stop.assert_called_once()


@unittest.skipIf(QApplication is None, "PySide6 not available")
class AutoStartIsOffByDefault(unittest.TestCase):
    """A repo's dev server may already be running elsewhere - Analyze must
    not start a second one unless the toggle says to."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / "package.json").write_text("{}", encoding="utf-8")
        self.window = MainWindow()
        self.window.app_state.set_source(SOURCE_REPO)
        self.window.repo_path_edit.setText(str(self.repo))

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.tmp.cleanup()

    def test_the_checkbox_reflects_the_setting_on_open(self):
        self.assertFalse(self.window.settings.auto_start_devserver)
        self.assertFalse(self.window.auto_devserver_check.isChecked())

    def test_toggling_the_checkbox_persists_the_setting(self):
        with patch.object(self.window.settings, "save") as save:
            self.window.auto_devserver_check.setChecked(True)
        self.assertTrue(self.window.settings.auto_start_devserver)
        save.assert_called_once()

    def test_unchecked_analyze_does_not_start_a_server(self):
        with patch.object(self.window, "_begin_devserver_flow") as begin, \
             patch.object(self.window.view_model, "analyze", return_value=None):
            self.window._on_analyze_clicked()
        begin.assert_not_called()

    def test_unchecked_analyze_still_runs_the_static_scan(self):
        with patch.object(self.window.view_model, "analyze",
                          return_value=None) as analyze:
            self.window._on_analyze_clicked()
        analyze.assert_called_once_with()

    def test_unchecked_analyze_shows_the_accuracy_note(self):
        with patch.object(self.window.view_model, "analyze", return_value=None):
            self.window._on_analyze_clicked()
        self.assertIn("node", self.window.status_bar.currentMessage())

    def test_no_stack_detected_shows_no_note(self):
        (self.repo / "package.json").unlink()
        with patch.object(self.window.view_model, "analyze", return_value=None):
            self.window._on_analyze_clicked()
        self.assertEqual(self.window.status_bar.currentMessage(), "")

    def test_checked_analyze_starts_the_devserver_flow_instead(self):
        self.window.auto_devserver_check.setChecked(True)
        with patch.object(self.window, "_begin_devserver_flow") as begin, \
             patch.object(self.window.view_model, "analyze") as analyze:
            self.window._on_analyze_clicked()
        begin.assert_called_once()
        analyze.assert_not_called()


@unittest.skipIf(QApplication is None, "PySide6 not available")
class SatisfiedDepsStartWithoutAsking(unittest.TestCase):
    """The bug this session found: `deps_satisfied() == True` and
    `deps_satisfied() == False` (declined) both read as "don't start" when
    detection and confirmation were the same question. They are not - only
    a *missing* dependency needs a yes/no."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        (self.repo / "package.json").write_text("{}", encoding="utf-8")
        (self.repo / "node_modules").mkdir()
        self.window = MainWindow()
        self.window.app_state.set_source(SOURCE_REPO)
        self.window.repo_path_edit.setText(str(self.repo))

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.tmp.cleanup()

    def test_satisfied_deps_start_without_a_confirm_dialog(self):
        stack = self.window._devserver_stack_for_repo()
        with patch.object(self.window, "_start_devserver_then_analyze") as start, \
             patch("PySide6.QtWidgets.QMessageBox.question") as question:
            self.window._begin_devserver_flow(stack)
        question.assert_not_called()
        start.assert_called_once_with(True)

    def test_missing_deps_do_ask_first(self):
        (self.repo / "node_modules").rmdir()
        stack = self.window._devserver_stack_for_repo()
        with patch.object(self.window, "_start_devserver_then_analyze") as start, \
             patch("PySide6.QtWidgets.QMessageBox.question",
                  return_value=QMessageBox.StandardButton.Yes) as question:
            self.window._begin_devserver_flow(stack)
        question.assert_called_once()
        start.assert_called_once_with(True)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class StartServerButton(unittest.TestCase):
    """The explicit, one-time equivalent of the auto-start toggle."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.window = MainWindow()
        self.window.app_state.set_source(SOURCE_REPO)
        self.window.repo_path_edit.setText(str(self.repo))

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.tmp.cleanup()

    def test_click_with_a_detected_stack_starts_the_flow(self):
        (self.repo / "package.json").write_text("{}", encoding="utf-8")
        with patch.object(self.window, "_begin_devserver_flow") as begin:
            self.window._on_start_server_clicked()
        begin.assert_called_once()

    def test_click_with_no_stack_shows_a_message_and_does_nothing(self):
        with patch.object(self.window, "_begin_devserver_flow") as begin:
            self.window._on_start_server_clicked()
        begin.assert_not_called()
        self.assertNotEqual(self.window.status_bar.currentMessage(), "")

    def test_works_even_when_the_toggle_is_off(self):
        (self.repo / "package.json").write_text("{}", encoding="utf-8")
        (self.repo / "node_modules").mkdir()
        self.assertFalse(self.window.settings.auto_start_devserver)
        with patch.object(self.window, "_start_devserver_then_analyze") as start:
            self.window._on_start_server_clicked()
        start.assert_called_once_with(True)


if __name__ == "__main__":
    unittest.main()
