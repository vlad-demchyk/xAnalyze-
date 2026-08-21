"""Fullscan screen — combined AI patterns + accessibility in one run."""
from __future__ import annotations

import argparse

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from cli import cmd_fullscan


class FullscanScreen(Screen):
    """Form to configure and run a full scan."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("q", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="fullscan-form"):
            yield Label("Full Scan — AI + accessibility + SEO", classes="menu-title")
            yield Static("")

            yield Label("Target (URL, directory, or .html file):")
            yield Input(placeholder="https://example.com or ./repo", id="target")

            yield Label("Language:")
            yield Select(
                [
                    ("English", "en"),
                    ("Українська", "uk"),
                    ("Italiano", "it"),
                ],
                value="en",
                id="language",
            )

            yield Label("Breakpoints:")
            yield Select(
                [
                    ("All (desktop + tablet + mobile)", "all"),
                    ("Desktop only", "desktop"),
                    ("Desktop + mobile", "desktop,mobile"),
                    ("Mobile only", "mobile"),
                ],
                value="all",
                id="breakpoints",
            )

            yield Static("")
            yield Checkbox("Agent mode (offline + agent judges)", id="agent")

            yield Static("")
            with Horizontal():
                yield Button("Run Full Scan", id="run", variant="primary")
                yield Button("Back", id="back")

            yield Static("")
            yield Label("", id="fullscan-status")

    def action_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "run":
            self._run_fullscan()

    def _run_fullscan(self) -> None:
        target = self.query_one("#target", Input).value.strip()
        if not target:
            self.query_one("#fullscan-status", Label).update("Enter a target.")
            return

        language = self.query_one("#language", Select).value
        breakpoints = self.query_one("#breakpoints", Select).value
        agent = self.query_one("#agent", Checkbox).value

        self.query_one("#fullscan-status", Label).update(f"Full scan of {target}...")

        args = argparse.Namespace(
            target=target,
            url=False,
            depth=2,
            max_pages=0,
            max_files=5000,
            ext=None,
            exclude=None,
            no_default_excludes=False,
            detector="offline",
            scope="both",
            no_typography=False,
            styled_report=None,
            report=None,
            check=False,
            language=language,
            breakpoints=breakpoints,
            agent=agent,
            json=True,
        )

        try:
            result_code = cmd_fullscan(args)
            self.query_one("#fullscan-status", Label).update(
                f"Full scan complete (exit code {result_code}). See results in terminal."
            )
        except Exception as exc:
            self.query_one("#fullscan-status", Label).update(f"Error: {exc}")
