"""Reports screen — list and view previous analysis reports."""
from __future__ import annotations

import json
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Label, Static


def _history_dir() -> Path:
    return Path.cwd() / ".xanalyze"


class ReportsScreen(Screen):
    """List previous reports from .xanalyze/ directory."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("q", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="reports-view"):
            yield Label("Previous Reports", classes="menu-title")
            yield Static("")
            yield DataTable(id="reports-table")
            yield Static("")
            yield Label("", id="report-status")
            yield Static("")
            yield Button("Back", id="back")

    def on_mount(self) -> None:
        table = self.query_one("#reports-table", DataTable)
        table.add_columns("Date", "Target", "Mode", "Findings")

        history_dir = _history_dir()
        if not history_dir.exists():
            self.query_one("#report-status", Label).update("No reports found.")
            return

        reports = []
        for f in history_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(data, list) and data:
                    latest = data[-1]
                    reports.append(latest)
            except (json.JSONDecodeError, OSError):
                continue

        if not reports:
            self.query_one("#report-status", Label).update("No reports found.")
            return

        reports.sort(key=lambda r: r.get("at", ""), reverse=True)
        for r in reports[:50]:
            counts = r.get("counts", {})
            total = sum(counts.values()) if isinstance(counts, dict) else 0
            table.add_row(
                r.get("at", "?"),
                r.get("root", "?")[:40],
                r.get("mode", "?"),
                str(total),
            )

    def action_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
