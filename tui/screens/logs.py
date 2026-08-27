"""Logs screen - what the app wrote about its own runs.

The same records `xanalyze logs` prints and the window's log panel shows,
because all three read `applog.read_records`. A viewer that parsed the files
itself would be a second reader of the format, and the second reader is the
one that goes out of date.

Newest last, so it reads forwards like a terminal.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Label, Static

import applog

from tui.screens.base import XScreen

#: How many records the table holds. Enough to cover a long run, small
#: enough that opening the screen is instant.
SHOWN = 300


class LogsScreen(XScreen):
    """The application log, filtered by level."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("r", "refresh", "Refresh"),
        ("e", "only_errors", "Errors"),
        ("a", "show_all", "All"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._level = ""

    def compose(self) -> ComposeResult:
        yield from self.compose_chrome()
        with Vertical(id="logs-view"):
            yield Label(self.tr("tui_logs_title"), classes="menu-title")
            yield Label("", id="logs-summary")
            yield Static("")
            yield DataTable(id="logs-table", cursor_type="row")
            yield Static("")
            with Horizontal():
                yield Button(self.tr("tui_logs_errors"), id="errors", variant="primary")
                yield Button(self.tr("tui_logs_all"), id="all")
                yield Button(self.tr("tui_refresh"), id="refresh")
                yield Button(self.tr("tui_back"), id="back")
            yield Label(self.tr("tui_logs_hint"), classes="hint")

    def on_mount(self) -> None:
        table = self.query_one("#logs-table", DataTable)
        table.add_columns(self.tr("tui_col_when"), self.tr("tui_col_level"),
                          self.tr("tui_col_event"), self.tr("tui_col_detail"))
        self.action_refresh()

    def on_screen_resume(self) -> None:
        self.action_refresh()

    def action_refresh(self) -> None:
        table = self.query_one("#logs-table", DataTable)
        table.clear()
        summary = applog.summary()
        megabytes = summary["bytes"] / (1024 * 1024)
        self.query_one("#logs-summary", Label).update(
            self.tr("tui_logs_summary", files=len(summary["files"]),
                    mb=f"{megabytes:.2f}", days=summary["retention_days"],
                    level=summary["level"]))
        records = applog.read_records(limit=SHOWN, level=self._level)
        for record in reversed(records):
            rest = {k: v for k, v in record.items()
                    if k not in ("at", "level", "event", "run")}
            table.add_row((record.get("at") or "")[11:19],
                          record.get("level", ""),
                          str(record.get("event", ""))[:34],
                          " ".join(f"{k}={v}" for k, v in rest.items())[:80])

    def action_only_errors(self) -> None:
        self._level = "warning"
        self.action_refresh()

    def action_show_all(self) -> None:
        self._level = ""
        self.action_refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "errors":
            self.action_only_errors()
        elif event.button.id == "all":
            self.action_show_all()
        elif event.button.id == "refresh":
            self.action_refresh()
        elif event.button.id == "back":
            self.action_back()
