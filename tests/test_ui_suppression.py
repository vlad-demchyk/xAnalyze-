"""Suppression as something the window and the settings dialog expose.

`suppression.py` already does the matching and the rescoring (see
`tests/test_suppression.py`); what is new here is the UI on top of it: a
"ignore this finding" button that writes a fingerprint and removes the row
without a re-scan, a settings tab that lists and edits the personal list, and
the on-screen note that a lowered score came from a suppression rather than
from the detector being unsure.
"""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QLabel, QListWidget
    import suppression
    from ui.main_window import MainWindow, _SUPPRESSED_NOTE
    from ui.settings_dialog import SettingsDialog
    from ui.window_parts.noise_control import HiddenRow, NoiseDialog
    from analysis_modes import SOURCE_REPO, SOURCE_SITE
    from models import AnalysisResult, Confidence, PageResult, TextBlock, TextSpan
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 not available")
class FingerprintFile(unittest.TestCase):
    """`suppression.add_fingerprint_to_ignore_file`, the write side of the
    format `suppression.Suppressions.parse` already reads."""

    def test_creates_the_file_when_none_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = suppression.add_fingerprint_to_ignore_file(tmp, "abc123")
            self.assertTrue(path.is_file())
            loaded = suppression.Suppressions.parse(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded.fingerprints, ["abc123"])

    def test_appends_without_disturbing_other_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            ignore_path = Path(tmp) / suppression.IGNORE_FILENAME
            ignore_path.write_text("[phrases]\ncomprehensive\n\n[rules]\ndashes\n",
                                    encoding="utf-8")
            suppression.add_fingerprint_to_ignore_file(tmp, "fp1")
            loaded = suppression.Suppressions.parse(ignore_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded.phrases, ["comprehensive"])
            self.assertEqual(loaded.rules, ["dashes"])
            self.assertEqual(loaded.fingerprints, ["fp1"])

    def test_the_same_fingerprint_twice_is_still_one_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            suppression.add_fingerprint_to_ignore_file(tmp, "fp1")
            path = suppression.add_fingerprint_to_ignore_file(tmp, "fp1")
            loaded = suppression.Suppressions.parse(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded.fingerprints, ["fp1"])

    def test_render_round_trips_through_parse(self):
        original = suppression.Suppressions(
            phrases=["comprehensive"], rules=["dashes"], paths=["dist/"],
            selectors=[".ad"], fingerprints=["fp1", "fp2"],
        )
        reparsed = suppression.Suppressions.parse(original.render())
        self.assertEqual(reparsed.to_dict(), original.to_dict())


@unittest.skipIf(QApplication is None, "PySide6 not available")
class IgnoreThisFinding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _span_and_block(self):
        block = TextBlock(block_id="b1", page_url="https://example.com/",
                          dom_path="main > p:nth-of-type(1)", text="Some AI-sounding copy.")
        span = TextSpan(block_id="b1", start=0, end=4, score=0.8,
                        confidence=Confidence.HIGH, detector_name="offline",
                        explanation="looks generated")
        return span, block

    def test_a_web_finding_falls_back_to_personal_settings(self):
        window = MainWindow()
        window.source = SOURCE_SITE
        window.settings.save = lambda: None  # do not touch the real settings.json
        span, block = self._span_and_block()
        window.result = AnalysisResult(root_url="https://example.com/",
                                       pages=[PageResult(url=block.page_url, depth=0,
                                                         blocks=[block])],
                                       spans=[span])
        window._on_ignore_span_clicked(span, block)
        self.assertNotIn(span, window.result.spans)
        fp = suppression.span_fingerprint(span, block)
        self.assertIn(fp, window.settings.ignore.get("fingerprints", []))

    def test_a_repo_finding_writes_the_projects_ignore_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            window = MainWindow()
            window.source = SOURCE_REPO
            window.repo_path_edit.setText(tmp)
            from models import CodeBlock

            block = CodeBlock(block_id="c1", file_path=str(Path(tmp) / "a.py"),
                              start=0, end=10, text="# comment", line_number=1)
            span = TextSpan(block_id="c1", start=0, end=9, score=0.7,
                            confidence=Confidence.HIGH, detector_name="offline")
            from models import RepoAnalysisResult, FileResult
            window.result = RepoAnalysisResult(
                root_dir=tmp, files=[FileResult(path=block.file_path, blocks=[block])],
                spans=[span])
            window._on_ignore_span_clicked(span, block)
            self.assertNotIn(span, window.result.spans)
            ignore_path = Path(tmp) / suppression.IGNORE_FILENAME
            self.assertTrue(ignore_path.is_file())
            loaded = suppression.Suppressions.parse(ignore_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded.fingerprints, [suppression.span_fingerprint(span, block)])

    def test_the_button_removes_the_row_without_a_new_scan(self):
        window = MainWindow()
        window.source = SOURCE_SITE
        window.settings.save = lambda: None  # do not touch the real settings.json
        span, block = self._span_and_block()
        window.result = AnalysisResult(root_url="https://example.com/",
                                       pages=[PageResult(url=block.page_url, depth=0,
                                                         blocks=[block])],
                                       spans=[span])
        window._populate_flagged_list()
        self.assertEqual(window.flagged_list.count(), 1)
        window._on_ignore_span_clicked(span, block)
        self.assertEqual(window.flagged_list.count(), 0)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class SuppressedNoteInTheExplanation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _labels(self, widget):
        return widget.findChildren(QLabel)

    def test_a_suppressed_span_shows_the_note(self):
        window = MainWindow()
        block = TextBlock(block_id="b1", page_url="https://example.com/",
                          dom_path="p", text="Some comprehensive copy.")
        span = TextSpan(block_id="b1", start=5, end=18, score=0.4,
                        confidence=Confidence.MEDIUM, detector_name="offline",
                        details={"source": "style", "suppressed": True,
                                 "signals": {}, "cliches": [], "structural": False})
        widget = window._build_detail_widget(span, block)
        texts = [label.text() for label in self._labels(widget)]
        self.assertTrue(any(_SUPPRESSED_NOTE in text for text in texts))

    def test_an_untouched_span_shows_no_note(self):
        window = MainWindow()
        block = TextBlock(block_id="b1", page_url="https://example.com/",
                          dom_path="p", text="Some comprehensive copy.")
        span = TextSpan(block_id="b1", start=5, end=18, score=0.9,
                        confidence=Confidence.HIGH, detector_name="offline",
                        details={"source": "style"})
        widget = window._build_detail_widget(span, block)
        texts = [label.text() for label in self._labels(widget)]
        self.assertFalse(any(_SUPPRESSED_NOTE in text for text in texts))


@unittest.skipIf(QApplication is None, "PySide6 not available")
class NoiseControl(unittest.TestCase):
    """Artboard 3k: what is hidden, where the record lives, and undoing it.

    The settings tab this replaced showed five list boxes of raw values, so a
    dismissed finding was sixteen hex characters and a Remove button - the one
    action it offered could not be taken on purpose.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self, ignore=None, root=None):
        window = MainWindow()
        window.settings.ignore = ignore or {}
        window.settings.save = lambda: None  # never the real settings.json
        return NoiseDialog(window.settings, window.lang, root=root,
                           palette=window.palette_tokens, parent=window), window

    def _rows(self, dialog):
        return [dialog.hidden_layout.itemAt(i).widget()
                for i in range(dialog.hidden_layout.count())
                if isinstance(dialog.hidden_layout.itemAt(i).widget(), HiddenRow)]

    def test_a_hidden_finding_is_shown_by_its_note(self):
        dialog, _ = self._dialog({
            "fingerprints": ["4c1f9a2b7d3e5061"],
            "labels": {"4c1f9a2b7d3e5061": "empty-heading \u00b7 about.html"},
        })
        row = self._rows(dialog)[0]
        text = " ".join(child.text() for child in row.findChildren(QLabel))
        self.assertIn("empty-heading", text)
        self.assertIn("4c1f9a2b7d3e5061", text)

    def test_the_row_says_which_list_the_record_is_in(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, suppression.IGNORE_FILENAME).write_text(
                "[phrases]\nrobust\n", encoding="utf-8")
            dialog, _ = self._dialog({"phrases": ["comprehensive"]}, root=folder)
            said = {" ".join(c.text() for c in row.findChildren(QLabel)): row
                    for row in self._rows(dialog)}
            personal = [k for k in said if "comprehensive" in k][0]
            project = [k for k in said if "robust" in k][0]
            self.assertIn("personal", personal)
            self.assertIn(suppression.IGNORE_FILENAME, project)

    def test_restoring_a_personal_entry_takes_it_out_of_settings(self):
        dialog, window = self._dialog({"phrases": ["comprehensive", "robust"]})
        row = [r for r in self._rows(dialog) if r.value == "comprehensive"][0]
        row.restore_btn.click()
        dialog._on_accept()
        self.assertEqual(window.settings.ignore["phrases"], ["robust"])

    def test_restoring_a_project_entry_rewrites_that_file_and_keeps_the_rest(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, suppression.IGNORE_FILENAME)
            path.write_text("# ours, decided in review\n[phrases]\nrobust\n"
                            "comprehensive\n", encoding="utf-8")
            dialog, _ = self._dialog(root=folder)
            row = [r for r in self._rows(dialog) if r.value == "robust"][0]
            row.restore_btn.click()
            dialog._on_accept()
            written = path.read_text(encoding="utf-8")
            self.assertNotIn("robust", written)
            self.assertIn("comprehensive", written)
            self.assertIn("# ours, decided in review", written)

    def test_a_disabled_rule_is_a_chip_and_clicking_it_switches_it_back_on(self):
        dialog, window = self._dialog({"rules": ["region", "meta-viewport"]})
        chips = [dialog.rules_flow.itemAt(i).widget()
                 for i in range(dialog.rules_flow.count())]
        self.assertEqual(len(chips), 2)
        [chip for chip in chips if chip.text().startswith("region")][0].click()
        dialog._on_accept()
        self.assertEqual(window.settings.ignore["rules"], ["meta-viewport"])

    def test_the_files_box_cannot_drop_a_rule_below_it(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder, suppression.IGNORE_FILENAME)
            path.write_text("[paths]\n# vendored\nvendor/\n\n[rules]\n"
                            "region  # decided in review\n", encoding="utf-8")
            dialog, _ = self._dialog(root=folder)
            self.assertIn("# vendored", dialog.paths_edit.toPlainText())
            dialog.paths_edit.setPlainText("# generated\ndist/")
            dialog._on_accept()
            written = path.read_text(encoding="utf-8")
            self.assertIn("dist/", written)
            self.assertNotIn("vendor/", written)
            self.assertIn("# generated", written)
            # The pane below it is untouched, note and all.
            self.assertIn("region  # decided in review", written)

    def test_the_settings_tab_says_how_much_is_hidden_before_it_is_opened(self):
        window = MainWindow()
        window.settings.ignore = {"phrases": ["comprehensive", "robust"],
                                  "rules": ["region"]}
        window.settings.save = lambda: None
        dlg = SettingsDialog(window.settings, window.lang, parent=window)
        self.assertIn("3", dlg.noise_count.text())

    def test_a_phrase_can_still_be_added_by_hand(self):
        dialog, window = self._dialog()
        dialog.level_combo.setCurrentIndex(
            [dialog.level_combo.itemData(i) for i in range(dialog.level_combo.count())]
            .index("phrases"))
        dialog.hidden_entry.setText("cutting-edge")
        dialog._on_add_hidden()
        dialog._on_accept()
        self.assertEqual(window.settings.ignore["phrases"], ["cutting-edge"])


@unittest.skipIf(QApplication is None, "PySide6 not available")
class ADismissedFindingIsReadable(unittest.TestCase):
    """A fingerprint is a one-way hash, so the note is the only record."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_dismissing_a_finding_writes_the_note_beside_it(self):
        with tempfile.TemporaryDirectory() as folder:
            window = MainWindow()
            window.source = SOURCE_REPO
            window.repo_path_edit.setText(folder)
            from models import CodeBlock, FileResult, RepoAnalysisResult

            block = CodeBlock(block_id="c1", file_path=str(Path(folder) / "about.md"),
                              start=0, end=27, line_number=1,
                              text="Our comprehensive platform.")
            span = TextSpan(block_id="c1", start=4, end=17, score=0.8,
                            detector_name="offline", confidence=Confidence.HIGH,
                            details={"source": "style"})
            window.result = RepoAnalysisResult(
                root_dir=folder,
                files=[FileResult(path=block.file_path, blocks=[block])],
                spans=[span])
            window._on_ignore_span_clicked(span, block)
            written = (Path(folder) / suppression.IGNORE_FILENAME).read_text()
            self.assertIn("style", written)
            self.assertIn("about.md", written)
            # And the note does not become part of the entry on the way back.
            parsed = suppression.Suppressions.parse(written)
            self.assertEqual(len(parsed.fingerprints), 1)
            self.assertEqual(len(parsed.fingerprints[0]), 16)


if __name__ == "__main__":
    unittest.main()
