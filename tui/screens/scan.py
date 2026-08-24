"""Scan screen — configure and run AI pattern detection."""
from __future__ import annotations

import argparse

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from cli import cmd_scan
from tui.screens.base import RunScreen


class ScanScreen(RunScreen):
    """Form to configure and run a scan."""

    status_id = "scan-status"

    def compose(self) -> ComposeResult:
        yield from self.compose_chrome()
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
            yield Checkbox("Keep proper typography (skip em dashes, curly quotes)",
                           id="no-typography")
            yield Checkbox("Incremental — reuse the cache for unchanged files",
                           id="incremental")

            yield Static("")
            with Horizontal():
                yield Button("Run Scan", id="run", variant="primary")
                yield Button("Back", id="back")

            yield Static("")
            yield Label("", id="scan-status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.action_back()
        elif event.button.id == "run":
            self._run_scan()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in the target field runs the scan, as it does in a shell."""
        if event.input.id == "target":
            self._run_scan()

    def _run_scan(self) -> None:
        target = self.query_one("#target", Input).value.strip()
        if not target:
            self.status("Enter a target path.")
            return

        args = argparse.Namespace(
            paths=[target],
            ext=None,
            exclude=None,
            use_default_excludes=True,
            max_files=5000,
            detector=self.query_one("#detector", Select).value,
            scope=self.query_one("#scope", Select).value,
            no_typography=self.query_one("#no-typography", Checkbox).value,
            no_ignore=False,
            no_unicode=False,
            categories=None,
            # JSON, always: the results screen reads the machine-readable
            # form and lays it out. The human listing is in the run log.
            json=True,
            check=False,
            incremental=self.query_one("#incremental", Checkbox).value,
            styled_report=None,
            language=None,
            provider=None,
        )
        self.start_run(cmd_scan, args, title=f"Scan of {target}")
