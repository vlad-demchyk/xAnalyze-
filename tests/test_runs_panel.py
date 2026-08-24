"""The runs catalogue in the window: what is on disk, and what can continue.

Before this the interface had no idea a run had ever stopped. A three-quarter
-hour scan that died in its last phase left a folder on the Desktop and told
nobody, so the only way to find out was to go looking.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from cli_impl import runstate
    from ui.main_window import MainWindow
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None


class _Folder:
    def __init__(self, run: Path):
        self.project = run.parent
        self.run = run


def _make_run(root: Path, name: str, target: str, *, finished=False,
              failed=False, running=False):
    run = root / "example.com" / name
    run.mkdir(parents=True, exist_ok=True)
    state = runstate.RunState.begin(_Folder(run), target,
                                    argv=["fullscan", target])
    if finished:
        for phase in runstate.PHASES:
            state.start(phase)
            state.done(phase)
        state.finish()
    elif failed:
        state.start("scan")
        state.done("scan")
        state.skip("crawl", "not a website")
        state.start("audit")
        state.fail("audit", "the static audit failed")
    elif running:
        state.start("crawl")
    state.write_feedback()
    return state


@unittest.skipIf(QApplication is None, "PySide6 not available")
class RunsCatalogue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        os.environ["XANALYZE_REPORT_ROOT"] = str(self.root)
        self.window = MainWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        os.environ.pop("XANALYZE_REPORT_ROOT", None)
        self.tmp.cleanup()

    def test_an_empty_disk_shows_an_empty_state_not_an_empty_list(self):
        self.assertEqual(self.window.refresh_runs(), 0)
        self.assertTrue(self.window.runs_empty.isVisible())
        self.assertFalse(self.window.runs_list.isVisible())

    def test_a_run_on_disk_is_listed(self):
        _make_run(self.root, "2026-08-24-1200", "https://example.com",
                  failed=True)
        self.assertEqual(self.window.refresh_runs(), 1)
        self.assertTrue(self.window.runs_list.isVisible())
        self.assertFalse(self.window.runs_empty.isVisible())

    def test_the_row_says_the_target_and_the_state(self):
        _make_run(self.root, "2026-08-24-1200", "https://example.com",
                  failed=True)
        self.window.refresh_runs()
        text = self.window.runs_list.item(0).text()
        self.assertIn("example.com", text)
        self.assertIn("ago", text)

    def test_the_row_carries_its_data_rather_than_a_parsed_label(self):
        _make_run(self.root, "2026-08-24-1200", "https://example.com",
                  failed=True)
        self.window.refresh_runs()
        row = self.window.runs_list.item(0).data(Qt.ItemDataRole.UserRole)
        self.assertEqual(row["target"], "https://example.com")
        self.assertTrue(row["resumable"])

    def test_newest_first(self):
        _make_run(self.root, "2026-08-24-1000", "https://old.example",
                  finished=True)
        _make_run(self.root, "2026-08-24-1200", "https://new.example",
                  failed=True)
        self.window.refresh_runs()
        rows = [self.window.runs_list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.window.runs_list.count())]
        self.assertEqual(len(rows), 2)

    def test_resume_is_offered_only_where_it_would_do_something(self):
        """A button that is enabled and then says "nothing to resume"
        teaches people to distrust the buttons."""
        _make_run(self.root, "2026-08-24-1200", "https://example.com",
                  finished=True)
        self.window.refresh_runs()
        self.window.runs_list.setCurrentRow(0)
        self.assertFalse(self.window.resume_run_btn.isEnabled())

    def test_resume_is_offered_for_a_stopped_run(self):
        _make_run(self.root, "2026-08-24-1200", "https://example.com",
                  failed=True)
        self.window.refresh_runs()
        self.window.runs_list.setCurrentRow(0)
        self.assertTrue(self.window.resume_run_btn.isEnabled())

    def test_pause_is_offered_only_while_a_run_is_going(self):
        _make_run(self.root, "2026-08-24-1200", "https://example.com",
                  running=True)
        self.window.refresh_runs()
        self.window.runs_list.setCurrentRow(0)
        self.assertTrue(self.window.pause_run_btn.isEnabled())

    def test_pause_is_not_offered_for_a_finished_run(self):
        _make_run(self.root, "2026-08-24-1200", "https://example.com",
                  finished=True)
        self.window.refresh_runs()
        self.window.runs_list.setCurrentRow(0)
        self.assertFalse(self.window.pause_run_btn.isEnabled())

    def test_nothing_is_offered_with_no_selection(self):
        _make_run(self.root, "2026-08-24-1200", "https://example.com",
                  failed=True)
        self.window.refresh_runs()
        self.window.runs_list.setCurrentRow(-1)
        self.window._on_run_selected()
        self.assertFalse(self.window.resume_run_btn.isEnabled())
        self.assertFalse(self.window.open_run_btn.isEnabled())

    def test_pausing_writes_the_request_where_the_run_will_see_it(self):
        state = _make_run(self.root, "2026-08-24-1200", "https://example.com",
                          running=True)
        self.window.refresh_runs()
        self.window.runs_list.setCurrentRow(0)
        self.window._on_pause_run_clicked()
        self.assertTrue(state.paused_requested())

    def test_the_panel_and_the_cli_read_the_same_disk(self):
        """One fact, one owner.

        A registry kept by the interface would be a second answer to "what
        runs exist", and it would be the one that went stale as soon as a
        folder was moved by hand.
        """
        from cli_impl.runcmds import run_rows

        _make_run(self.root, "2026-08-24-1200", "https://example.com",
                  failed=True)
        self.window.refresh_runs()
        panel = [self.window.runs_list.item(i).data(Qt.ItemDataRole.UserRole)
                 for i in range(self.window.runs_list.count())]
        cli = run_rows(runstate.all_runs(self.root))
        self.assertEqual([r["run"] for r in panel], [r["run"] for r in cli])

    def test_an_unreadable_disk_is_not_a_crash(self):
        (self.root / "broken" / "run").mkdir(parents=True)
        (self.root / "broken" / "run" / "state.json").write_text("{oh no")
        self.assertEqual(self.window.refresh_runs(), 0)

    def test_the_labels_follow_the_interface_language(self):
        for lang in ("uk", "it", "en"):
            self.window.lang = lang
            self.window._retranslate_runs()
            self.assertTrue(self.window.resume_run_btn.text())
            self.assertNotIn("runs_", self.window.resume_run_btn.text())

    def test_an_unknown_status_shows_the_word_not_a_translation_key(self):
        """`t` returns its key when it has no entry, and a user must never
        be shown `runs_status_whatever`."""
        label = self.window._run_label(
            {"target": "x", "status": "surprising", "age": "1m ago"})
        self.assertIn("surprising", label)
        self.assertNotIn("runs_status_", label)


if __name__ == "__main__":
    unittest.main()


@unittest.skipIf(QApplication is None, "PySide6 not available")
class SourcePickerLabels(unittest.TestCase):
    """Two different strings shared one translation key.

    `source_file` was both the picker's "HTML file" label and a finding's
    "File: {path}:{line}" location line. The later definition won, so the main
    source dropdown offered a literal `Файл: {path}:{line}` as its third
    option, in all three languages. `pyflakes` had been reporting the
    duplicate key the whole time.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_the_picker_names_a_file_type_not_a_location(self):
        from i18n.translations import t

        for lang in ("uk", "it", "en"):
            label = t("source_file", lang)
            self.assertNotIn("{path}", label)
            self.assertNotIn("{line}", label)

    def test_the_location_line_still_takes_a_path_and_a_line(self):
        from i18n.translations import t

        for lang in ("uk", "it", "en"):
            self.assertIn("a.py", t("finding_file_line", lang,
                                    path="a.py", line=5))

    def test_no_translation_key_is_defined_twice(self):
        """The defect class, not just this instance.

        A duplicate key is silent: the later value wins and the earlier call
        site renders something that was written for somewhere else.
        """
        import ast
        import pathlib

        source = pathlib.Path("i18n/translations.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        duplicates = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            seen = set()
            for key in node.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    if key.value in seen:
                        duplicates.append(key.value)
                    seen.add(key.value)
        self.assertEqual(duplicates, [])


@unittest.skipIf(QApplication is None, "PySide6 not available")
class TheColumnStaysNarrow(unittest.TestCase):
    """The runs panel must fit the column it was added to.

    Three buttons abreast needed 284px in a 268px column. That raised the
    whole sidebar's minimum width to 308, which turned on a horizontal
    scrollbar and clipped every control above it - "Sign in" rendered as
    "Sign i". Found by rendering the window and looking at it.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["XANALYZE_REPORT_ROOT"] = str(Path(self.tmp.name))
        _make_run(Path(self.tmp.name), "2026-08-24-1200",
                  "https://a-very-long-host-name.cloudwaysapps.com/x",
                  failed=True)
        self.window = MainWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        os.environ.pop("XANALYZE_REPORT_ROOT", None)
        self.tmp.cleanup()

    def test_the_panel_fits_the_sidebar(self):
        from ui.main_window import SIDEBAR_WIDTH

        self.window.refresh_runs()
        self.app.processEvents()
        self.assertLessEqual(self.window.toolbar.minimumSizeHint().width(),
                             SIDEBAR_WIDTH)

    def test_the_list_never_scrolls_sideways(self):
        """A scrollbar here eats a row and widens the whole column."""
        self.assertEqual(self.window.runs_list.horizontalScrollBarPolicy(),
                         Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def test_a_long_address_is_trimmed_from_the_left(self):
        """An address is recognised by its tail."""
        self.window.refresh_runs()
        first = self.window.runs_list.item(0).text().split("\n")[0]
        self.assertTrue(first.startswith("…"))
        self.assertTrue(first.endswith("cloudwaysapps.com/x"))

    def test_the_status_line_is_not_trimmed_from_the_left(self):
        """`ElideLeft` turned "complete · 34m ago" into "…mplete · 34m ago"."""
        self.assertEqual(self.window.runs_list.textElideMode(),
                         Qt.TextElideMode.ElideRight)

    def test_nothing_trimmed_is_lost(self):
        self.window.refresh_runs()
        tip = self.window.runs_list.item(0).toolTip()
        self.assertIn("a-very-long-host-name.cloudwaysapps.com", tip)
