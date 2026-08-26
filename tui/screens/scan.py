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
            yield Label(self.tr("tui_scan_title"), classes="menu-title")
            yield Static("")

            yield Label(self.tr("tui_target_path"))
            yield Input(placeholder="./src or ./page.html", id="target")

            # One sentence, not two labelled dropdowns - see
            # FullscanScreen.compose for why, and ui.widgets.InlineValue for
            # the Qt window's version of the same idea.
            with Horizontal(classes="sentence"):
                yield Static(self.tr("tui_label_detector"), classes="inline-label")
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
                    compact=True,
                    classes="inline-select",
                )
                yield Static("·", classes="inline-sep")
                yield Static(self.tr("tui_label_scope"), classes="inline-label")
                yield Select(
                    [
                        ("content", "content"),
                        ("technical", "technical"),
                        ("both", "both"),
                    ],
                    value="content",
                    id="scope",
                    compact=True,
                    classes="inline-select",
                )

            yield Static("")
            yield Checkbox(self.tr("tui_keep_typography"), id="no-typography")
            yield Checkbox(self.tr("tui_incremental"), id="incremental")

            yield Static("")
            with Horizontal():
                yield Button(self.tr("tui_scan_run"), id="run", variant="primary")
                yield Button(self.tr("tui_back"), id="back")

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
            self.status(self.tr("tui_need_target"))
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
        self.start_run(cmd_scan, args, title=self.tr("tui_scan_of", target=target))
