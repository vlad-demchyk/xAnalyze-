"""Reports screen — list, read and open previous analysis reports.

Clicking a row used to do nothing at all: the table had no selection
handler, the list was built once and never refreshed, and the history it
read from lived in `.xanalyze/` in the working directory - so starting
`xanalyze` from anywhere else showed "No reports found" even when there were
dozens. All three are fixed here; the history itself moved to
`~/.xanalyze/history/` (see `cli_impl.reports._history_dir`).
"""
from __future__ import annotations

import json
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Label, Static

from tui.screens.base import XScreen
from tui.screens.results import open_in_os


def _history_files() -> list:
    """Every history file worth reading, new location first.

    The legacy per-working-directory store is still read so a history
    recorded before the move is not invisible.
    """
    from cli_impl.reports import _history_dir

    paths = []
    for directory in (_history_dir(), Path.cwd() / ".xanalyze"):
        if directory.is_dir():
            paths.extend(sorted(directory.glob("*.json")))
    return paths


def load_runs() -> list:
    """Every recorded run, newest first.

    Each history file holds the runs of one target, so all of them are read
    and merged rather than only the newest entry of each - the point of the
    screen is the history, and showing one row per file threw it away.
    """
    runs = []
    for path in _history_files():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, list):
            continue
        runs.extend(entry for entry in data if isinstance(entry, dict))
    seen = set()
    unique = []
    for run in sorted(runs, key=lambda r: r.get("at") or "", reverse=True):
        key = (run.get("at"), run.get("root"), run.get("mode"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(run)
    return unique


def _total(run: dict) -> int:
    counts = run.get("counts")
    return sum(counts.values()) if isinstance(counts, dict) else 0


class ReportsScreen(XScreen):
    """Previous runs, and the documents they wrote."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("r", "refresh", "Refresh"),
        ("o", "open_selected", "Open report"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._runs: list = []

    def compose(self) -> ComposeResult:
        yield from self.compose_chrome()
        with Vertical(id="reports-view"):
            yield Label("Previous runs", classes="menu-title")
            yield Static("")
            yield DataTable(id="reports-table", cursor_type="row")
            yield Static("")
            yield Label("", id="report-detail")
            with Horizontal():
                yield Button("Open report", id="open", variant="primary")
                yield Button("Open folder", id="open-folder")
                yield Button("Refresh", id="refresh")
                yield Button("Back", id="back")
            yield Label("", id="report-status")
            yield Label("Enter or o opens the selected report.", classes="hint")

    def on_mount(self) -> None:
        table = self.query_one("#reports-table", DataTable)
        table.add_columns("When", "Target", "Mode", "Findings", "Problems")
        self.action_refresh()

    def on_screen_resume(self) -> None:
        """Rebuild on every visit.

        Screens are installed once and reused, so `on_mount` runs exactly
        once - the list a person saw after their first scan was the list
        they kept seeing after every later one.
        """
        self.action_refresh()

    def action_refresh(self) -> None:
        table = self.query_one("#reports-table", DataTable)
        table.clear()
        self._runs = load_runs()
        if not self._runs:
            self.query_one("#report-status", Label).update(
                "No runs recorded yet. Run a scan, audit or full scan first.")
            self._enable_actions(False)
            return
        for run in self._runs[:200]:
            distinct = run.get("distinct")
            table.add_row(
                (run.get("at") or "?").replace(" UTC", ""),
                str(run.get("root") or "?")[-46:],
                str(run.get("mode") or "?"),
                str(_total(run)),
                "-" if distinct is None else str(distinct),
            )
        self.query_one("#report-status", Label).update(
            f"{len(self._runs)} run(s) recorded.")
        self._show_detail(0)

    def _enable_actions(self, enabled: bool) -> None:
        self.query_one("#open", Button).disabled = not enabled
        self.query_one("#open-folder", Button).disabled = not enabled

    def _selected(self) -> dict | None:
        table = self.query_one("#reports-table", DataTable)
        index = table.cursor_row
        if index is None or not (0 <= index < len(self._runs)):
            return None
        return self._runs[index]

    def _show_detail(self, index: int) -> None:
        if not (0 <= index < len(self._runs)):
            return
        run = self._runs[index]
        counts = run.get("counts") or {}
        report = run.get("report") or ""
        exists = report and Path(report).exists()
        lines = [
            f"{run.get('root', '?')}  ·  {run.get('mode', '?')}",
            f"critical {counts.get('critical', 0)}  serious "
            f"{counts.get('serious', 0)}  moderate {counts.get('moderate', 0)}"
            f"  minor {counts.get('minor', 0)}",
            f"documents examined: {run.get('documents', '?')}"
            f"   corrections written: {run.get('fixed', 0)}",
        ]
        if report:
            lines.append(f"report: {report}"
                         + ("" if exists else "   (no longer on disk)"))
        else:
            # Runs recorded before the report path was stored.
            lines.append("report: not recorded for this run")
        self.query_one("#report-detail", Label).update("\n".join(lines))
        self._enable_actions(bool(exists))

    def on_data_table_row_highlighted(
            self, event: DataTable.RowHighlighted) -> None:
        self._show_detail(event.cursor_row)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Enter, or a click, opens the report - the thing a row is for."""
        self._show_detail(event.cursor_row)
        self.action_open_selected()

    def action_open_selected(self) -> None:
        run = self._selected()
        status = self.query_one("#report-status", Label)
        if run is None:
            status.update("Nothing selected.")
            return
        report = run.get("report")
        if not report:
            status.update("This run did not record where its report went.")
            return
        status.update(open_in_os(report))

    def action_open_folder(self) -> None:
        run = self._selected()
        status = self.query_one("#report-status", Label)
        report = (run or {}).get("report")
        if not report:
            status.update("No folder recorded for this run.")
            return
        status.update(open_in_os(str(Path(report).parent)))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.action_back()
        elif event.button.id == "refresh":
            self.action_refresh()
        elif event.button.id == "open":
            self.action_open_selected()
        elif event.button.id == "open-folder":
            self.action_open_folder()
