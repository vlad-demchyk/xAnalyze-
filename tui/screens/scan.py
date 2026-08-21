"""Scan screen — configure and run AI pattern detection."""
from __future__ import annotations

import json
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Input, Label, Select, Static

from cli import cmd_scan


class ScanScreen(Screen):
    """Form to configure and run a scan."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("q", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="scan-form"):
            yield Label("Scan — AI patterns & characters", classes="menu-title")
            yield Static("")

            yield Label("Target (file or directory):")
            yield Input(placeholder="./src or ./page.html", id="target")

            yield Label("Detector:")
            yield Select(
                [
                    ("offline — heuristic, free", "offline"),
                    ("embedding — semantic, free", "embedding"),
                    ("hybrid — offline + AI", "hybrid"),
                    ("llm-judge — AI only, paid", "llm-judge"),
                    ("none — characters only", "none"),
                ],
                value="offline",
                id="detector",
            )

            yield Label("Scope:")
            yield Select(
                [
                    ("content — user-facing copy", "content"),
                    ("technical — comments & docstrings", "technical"),
                    ("both", "both"),
                ],
                value="content",
                id="scope",
            )

            yield Static("")
            with Horizontal():
                yield Button("Run Scan", id="run", variant="primary")
                yield Button("Back", id="back")

            yield Static("")
            yield Label("", id="scan-status")

    def action_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "run":
            self._run_scan()

    def _run_scan(self) -> None:
        target = self.query_one("#target", Input).value.strip()
        if not target:
            self.query_one("#scan-status", Label).update("Enter a target path.")
            return

        detector = self.query_one("#detector", Select).value
        scope = self.query_one("#scope", Select).value

        self.query_one("#scan-status", Label).update(f"Scanning {target}...")

        class Args:
            paths = [target]
            ext = None
            exclude = None
            use_default_excludes = True
            max_files = 5000
            detector = detector
            scope = scope
            no_typography = False
            no_ignore = False
            no_unicode = False
            categories = None
            json = True
            check = False
            incremental = False
            styled_report = None
            language = None

        try:
            result_code = cmd_scan(Args())
            self.query_one("#scan-status", Label).update(
                f"Scan complete (exit code {result_code}). See results in terminal."
            )
        except Exception as exc:
            self.query_one("#scan-status", Label).update(f"Error: {exc}")
