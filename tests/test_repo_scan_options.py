from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from PySide6.QtWidgets import (
        QApplication, QCheckBox, QDialog, QLineEdit, QPlainTextEdit, QSpinBox,
    )
    from ui.main_window import MainWindow, TOP_ROW_HEIGHT
except Exception:  # noqa: BLE001 - GUI tests skip where PySide6 is unavailable
    QApplication = None


class IncrementalExtraction(unittest.TestCase):
    def test_extension_choice_limits_candidates(self):
        from repo_scanner import ScanConfig, scan_repo

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "page.html").write_text("<p>Page copy</p>", encoding="utf-8")
            (root / "page.php").write_text("<p>Server copy</p>", encoding="utf-8")

            files = scan_repo(
                tmp, ScanConfig(extensions=(".php",), scope="content"))

        self.assertEqual([Path(file.path).suffix for file in files], [".php"])

    def test_unchanged_text_reuses_blocks_and_changed_text_is_extracted_again(self):
        import repo_scanner

        ScanConfig = repo_scanner.ScanConfig
        scan_repo = repo_scanner.scan_repo

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.html"
            path.write_text("<p>First copy</p>", encoding="utf-8")
            before = scan_repo(tmp, ScanConfig(scope="content"))

            with mock.patch("repo_scanner._extract_blocks",
                            wraps=repo_scanner._extract_blocks) as extract:
                unchanged = scan_repo(
                    tmp, ScanConfig(scope="content"), reusable_files=before)
            extract.assert_not_called()
            self.assertEqual(unchanged[0].blocks, before[0].blocks)

            old_stat = path.stat()
            path.write_text("<p>Other copy</p>", encoding="utf-8")
            os.utime(path, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
            self.assertEqual(path.stat().st_size, old_stat.st_size)
            self.assertEqual(path.stat().st_mtime_ns, old_stat.st_mtime_ns)

            with mock.patch("repo_scanner._extract_blocks",
                            wraps=repo_scanner._extract_blocks) as extract:
                changed = scan_repo(
                    tmp, ScanConfig(scope="content"), reusable_files=before)
            extract.assert_called_once()
            self.assertEqual(changed[0].raw_text, "<p>Other copy</p>")
            self.assertNotEqual(changed[0].blocks, before[0].blocks)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class WindowScanOptions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_applies_file_limit_extensions_and_exclusions(self):
        window = MainWindow()
        self.addCleanup(window.close)
        window.settings.save = mock.Mock()

        def accept(dialog):
            dialog.findChild(QSpinBox, "scan-max-files").setValue(750)
            dialog.findChild(QLineEdit, "scan-extensions").setText("html, .PHP")
            dialog.findChild(QPlainTextEdit, "scan-exclusions").setPlainText("build/\n*.min.js")
            return QDialog.DialogCode.Accepted

        with mock.patch.object(QDialog, "exec", accept):
            window._on_exclusions_clicked()

        self.assertEqual(window.settings.max_files, 750)
        self.assertEqual(window.app_state.extensions, (".html", ".php"))
        self.assertEqual(window.repo_ignore_patterns, ["build/", "*.min.js"])
        self.assertIs(window.view_model.repo_ignore_patterns,
                      window.repo_ignore_patterns)
        window.settings.save.assert_called_once_with()

    def test_repository_controls_fit_the_design_width(self):
        from analysis_modes import SOURCE_REPO

        window = MainWindow()
        self.addCleanup(window.close)
        window.resize(1300, 800)
        window.show()
        window.app_state.set_source(SOURCE_REPO)
        self.app.processEvents()

        self.assertTrue(window.exclusions_btn.isVisible())
        self.assertGreaterEqual(window.repo_path_edit.width(), 180)
        self.assertLessEqual(window.toolbar.height(), TOP_ROW_HEIGHT + 4)

    def test_incremental_checkbox_reaches_the_repository_worker(self):
        from analysis_modes import SOURCE_REPO
        from models import FileResult

        with tempfile.TemporaryDirectory() as tmp:
            window = MainWindow()
            self.addCleanup(window.close)
            state = window.app_state
            state.set_source(SOURCE_REPO)
            state.set_target(tmp)
            window.settings.save = mock.Mock()
            def accept_dialog(dialog):
                dialog.findChild(QCheckBox, "scan-incremental").setChecked(True)
                return QDialog.DialogCode.Accepted

            with mock.patch.object(QDialog, "exec", accept_dialog):
                window._on_exclusions_clicked()
            state.set_extensions(("html",))
            reusable = [FileResult(path=str(Path(tmp) / "old.html"),
                                   raw_text="<p>old</p>", blocks=[])]
            window.view_model._reusable_files = lambda: reusable

            with mock.patch("ui.view_model.RepoAnalysisWorker.start"):
                window.view_model._start_repo_analysis(tmp)

            worker = window.view_model._worker
            self.assertTrue(state.incremental)
            self.assertTrue(worker.incremental)
            self.assertIs(worker.files, reusable)
            self.assertEqual(worker.extensions, (".html",))

            with mock.patch("ui.worker.AuditWorker.start"):
                window.view_model._start_audit()

            audit_worker = window.view_model._worker
            self.assertTrue(audit_worker.incremental)
            self.assertIs(audit_worker.files, reusable)
            self.assertEqual(audit_worker.extensions, (".html",))

    def test_both_repository_workers_use_the_extension_filter_and_cache(self):
        from models import FileResult
        import repo_scanner
        from ui.worker import AuditWorker, RepoAnalysisWorker

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "page.html").write_text("<p>Web copy</p>", encoding="utf-8")
            php = root / "page.php"
            php.write_text("<p>Mail copy</p>", encoding="utf-8")
            cached = [FileResult(path=str(php), raw_text=php.read_text(), blocks=[])]

            class Detector:
                display_name = "test detector"

                @staticmethod
                def analyze_blocks(_blocks):
                    return []

            analysis_worker = RepoAnalysisWorker(
                root_dir=tmp, ignore_patterns=[], detector_name="offline",
                detector_config={}, settings=None, files=cached,
                extensions=(".php",), incremental=True,
            )
            with mock.patch("ui.worker.scan_repo",
                            wraps=repo_scanner.scan_repo) as scan, \
                    mock.patch("ui.worker.DetectorFactory.create",
                               return_value=Detector()):
                analysis_worker.run()
            analysis_call = scan.call_args
            self.assertEqual(analysis_call.args[1].extensions, (".php",))
            self.assertIs(analysis_call.kwargs["reusable_files"], cached)

            audit_worker = AuditWorker(
                target=tmp, depth=0, is_repo=True, settings=None,
                files=cached, extensions=(".php",), incremental=True,
            )
            with mock.patch("ui.worker.scan_repo",
                            wraps=repo_scanner.scan_repo) as scan, \
                    mock.patch("audit.analyze_files",
                               return_value=mock.Mock(documents=[])):
                audit_worker.run()
            audit_call = scan.call_args
            self.assertEqual(audit_call.args[1].extensions, (".php",))
            self.assertIs(audit_call.kwargs["reusable_files"], cached)


if __name__ == "__main__":
    unittest.main()
