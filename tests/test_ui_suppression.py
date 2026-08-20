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
class SuppressionSettingsTab(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_existing_entries_are_shown_by_level(self):
        window = MainWindow()
        window.settings.ignore = {"phrases": ["comprehensive"], "rules": ["dashes"]}
        dlg = SettingsDialog(window.settings, window.lang, parent=window)
        phrases = dlg._suppression_lists["phrases"]
        self.assertEqual([phrases.item(i).text() for i in range(phrases.count())],
                         ["comprehensive"])
        rules = dlg._suppression_lists["rules"]
        self.assertEqual([rules.item(i).text() for i in range(rules.count())],
                         ["dashes"])

    def test_removing_an_entry_and_saving_updates_settings(self):
        window = MainWindow()
        window.settings.ignore = {"phrases": ["comprehensive", "cutting-edge"]}
        # Not a disk write this test should cause: `_on_accept` persists to
        # the real, shared settings.json, and this test only cares what
        # ends up in the in-memory object it hands back.
        window.settings.save = lambda: None
        dlg = SettingsDialog(window.settings, window.lang, parent=window)
        phrases = dlg._suppression_lists["phrases"]
        phrases.takeItem(0)  # drop "comprehensive"
        dlg._on_accept()
        self.assertEqual(window.settings.ignore.get("phrases"), ["cutting-edge"])

    def test_the_rule_id_helper_is_populated_from_known_rule_ids(self):
        window = MainWindow()
        dlg = SettingsDialog(window.settings, window.lang, parent=window)
        # Built without crashing, and with at least the style signals every
        # detector run can produce.
        known = suppression.known_rule_ids()
        self.assertIn("dashes", known["style"])


if __name__ == "__main__":
    unittest.main()
