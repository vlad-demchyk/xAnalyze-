"""What a scan says about itself, and what it does with copies of one file.

Both halves of this file exist because of the same run: the tool was pointed
at eight real projects in August 2026, and two of its answers turned out to
be unreadable rather than wrong.

`No findings.` was returned for a repository whose 161 files and 202 blocks
of text had all been read and scored below the threshold - the same words,
and the same `{"total": 0, "files": 0}`, that a run which matched no files at
all produces. And one en dash in a Cherry Bank address was reported four
times, once per copy of the file it lives in.
"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import duplicates
from models import ScanDiagnostics
from repo_scanner import ScanConfig, scan_repo


def project(folder: Path, files: dict) -> Path:
    for name, text in files.items():
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return folder


PAGE = "<html><body><p>A sentence of ordinary copy for the extractor.</p></body></html>"


class WhatTheWalkSaw(unittest.TestCase):
    def test_it_reports_files_and_blocks_even_when_nothing_is_flagged(self):
        with TemporaryDirectory() as folder:
            root = project(Path(folder), {"a.html": PAGE, "b.html": PAGE})
            walk = ScanDiagnostics()
            scan_repo(str(root), ScanConfig(scope="content"), diagnostics=walk)

        self.assertEqual(walk.files_read, 2)
        self.assertGreater(walk.blocks_found, 0)
        self.assertFalse(walk.truncated)
        self.assertTrue(walk.complete)

    def test_an_excluded_file_is_counted_as_excluded(self):
        with TemporaryDirectory() as folder:
            root = project(Path(folder), {"a.html": PAGE, "node_modules/b.html": PAGE})
            walk = ScanDiagnostics()
            scan_repo(str(root), ScanConfig(scope="content"), diagnostics=walk)

        self.assertEqual(walk.files_read, 1)
        self.assertEqual(walk.skipped_ignored, 1)

    def test_the_cap_records_itself_instead_of_stopping_quietly(self):
        """The defect this replaces: the walk hit its limit with a bare
        `break`, so a partial result was indistinguishable from a whole one.
        Measured on a real repository, the window read 500 files of 1732."""
        with TemporaryDirectory() as folder:
            root = project(Path(folder), {f"p{i}.html": PAGE for i in range(5)})
            walk = ScanDiagnostics()
            scan_repo(str(root), ScanConfig(scope="content", max_files=2),
                      diagnostics=walk)

        self.assertTrue(walk.truncated)
        self.assertFalse(walk.complete)
        self.assertEqual(walk.limit, 2)
        self.assertEqual(walk.files_read, 2)

    def test_one_default_cap_for_every_caller(self):
        """The window used to pass no `max_files` and get the library's 500
        while the CLI passed 5000, so the same repository gave two different
        answers depending on which one asked."""
        self.assertEqual(ScanConfig().max_files, 5000)

    def test_the_diagnostics_are_optional(self):
        """Callers that only want the files must keep working unchanged."""
        with TemporaryDirectory() as folder:
            root = project(Path(folder), {"a.html": PAGE})
            files = scan_repo(str(root), ScanConfig(scope="content"))
        self.assertEqual(len(files), 1)


class Copies(unittest.TestCase):
    def finding(self, file="a.ts", text="–", line=1):
        return {"file": file, "line": line, "text": text, "replacement": "-",
                "source": "characters", "explanation": "[typography] U+2013",
                "detector": "offline", "confidence": "medium", "offset": 0}

    def test_the_same_text_in_a_build_copy_is_one_row(self):
        grouped = duplicates.group([
            self.finding(file="src/T.ts"),
            self.finding(file="lib/T.js", line=47),
            self.finding(file="release/assets/T.js", line=33),
        ])
        self.assertEqual(len(grouped), 1)
        first, others = grouped[0]
        self.assertEqual(first["file"], "src/T.ts")
        self.assertEqual(len(others), 2)

    def test_nothing_is_dropped_from_the_list_itself(self):
        """Every copy is a real file a fix has to edit; grouping is only
        what the reader is shown first."""
        findings = [self.finding(file="src/T.ts"), self.finding(file="lib/T.js")]
        grouped = duplicates.group(findings)
        kept = [grouped[0][0], *grouped[0][1]]
        self.assertEqual([f["file"] for f in kept], [f["file"] for f in findings])

    def test_different_text_stays_separate(self):
        grouped = duplicates.group([self.finding(text="–"), self.finding(text="…")])
        self.assertEqual(len(grouped), 2)

    def test_a_finding_with_no_twin_still_comes_back_grouped(self):
        grouped = duplicates.group([self.finding()])
        self.assertEqual(len(grouped), 1)
        self.assertEqual(grouped[0][1], [])


class CliOutput(unittest.TestCase):
    def test_the_counts_name_how_many_are_distinct(self):
        import cli

        findings = [
            {"file": "src/T.ts", "text": "–", "replacement": "-",
             "source": "characters", "explanation": "e", "detector": "offline"},
            {"file": "lib/T.js", "text": "–", "replacement": "-",
             "source": "characters", "explanation": "e", "detector": "offline"},
        ]
        counts = cli._counts(findings)
        self.assertEqual(counts["total"], 2)
        self.assertEqual(counts["distinct"], 1)

    def test_the_coverage_line_says_what_was_read(self):
        import cli

        walk = ScanDiagnostics(files_read=161, blocks_found=202, skipped_ignored=7)
        line = cli._coverage_line([("/repo", walk)])
        self.assertIn("161", line)
        self.assertIn("202", line)

    def test_a_truncated_walk_says_so_in_the_coverage_line(self):
        import cli

        walk = ScanDiagnostics(files_read=500, blocks_found=2083, truncated=True,
                               limit=500)
        line = cli._coverage_line([("/repo", walk)])
        self.assertIn("500", line)
        self.assertIn("--max-files", line)

    def test_the_json_carries_what_was_read(self):
        import cli
        import io
        import contextlib

        walk = ScanDiagnostics(files_read=3, blocks_found=9)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            cli._print_json([], walked=[("/repo", walk)])
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload["read"][0]["files_read"], 3)
        self.assertEqual(payload["read"][0]["blocks_found"], 9)


class WindowList(unittest.TestCase):
    """The same grouping, where the findings are actually read."""

    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        try:
            from PySide6.QtWidgets import QApplication
            from ui.main_window import MainWindow
        except Exception as exc:  # noqa: BLE001
            raise unittest.SkipTest(str(exc))
        cls.app = QApplication.instance() or QApplication([])
        cls.window = MainWindow()

    def _span(self, block_id, text_block, start, end):
        from models import Confidence, TextSpan
        return TextSpan(block_id=block_id, start=start, end=end, score=0.5,
                        confidence=Confidence.MEDIUM, detector_name="offline",
                        details={"source": "characters"}, replacement="-")

    def test_the_same_defect_in_two_copies_is_one_row_that_counts_them(self):
        from models import CodeBlock, RepoAnalysisResult, FileResult

        text = "Via San Marco, 11 – 35129 Padova"
        blocks = [
            CodeBlock(block_id=f"b{i}", file_path=path, start=0, end=len(text),
                      text=text, line_number=1, language_hint="it")
            for i, path in enumerate(("src/T.ts", "lib/T.js", "release/T.js"))
        ]
        result = RepoAnalysisResult(
            root_dir="/repo",
            files=[FileResult(path=b.file_path, blocks=[b]) for b in blocks],
        )
        dash = text.index("–")
        result.spans = [self._span(b.block_id, b, dash, dash + 1) for b in blocks]

        self.window.result = result
        self.window._last_request = None
        self.window._populate_flagged_list()

        rows = [self.window.flagged_list.item(i).text()
                for i in range(self.window.flagged_list.count())]
        self.assertEqual(len(rows), 1, rows)
        self.assertIn("2", rows[0])


if __name__ == "__main__":
    unittest.main()
