"""Fullscan screen — combined AI patterns + accessibility in one run."""
from __future__ import annotations

import argparse

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from cli import cmd_fullscan
from tui.screens.base import RunScreen


class FullscanScreen(RunScreen):
    """Form to configure and run a full scan."""

    status_id = "fullscan-status"

    def compose(self) -> ComposeResult:
        yield from self.compose_chrome()
        with Vertical(id="fullscan-form"):
            yield Label("Full Scan — AI + accessibility + SEO",
                        classes="menu-title")
            yield Static("")

            yield Label("Target (URL, directory, or .html file):")
            # `example.com` is enough - the scheme is added for you.
            yield Input(placeholder="example.com or ./repo", id="target")

            yield Label("Report language:")
            yield Select(
                [
                    ("auto — detect from the content", ""),
                    ("English", "en"),
                    ("Українська", "uk"),
                    ("Italiano", "it"),
                ],
                value="",
                id="language",
            )

            yield Label("Crawl depth (URLs only):")
            yield Select(
                [
                    ("1 — the page and what it links to", "1"),
                    ("0 — the given page only", "0"),
                    ("2", "2"),
                    ("3", "3"),
                ],
                value="1",
                id="depth",
            )

            yield Label("Breakpoints:")
            yield Select(
                [
                    ("Desktop only", "desktop"),
                    ("All (desktop + tablet + mobile)", "all"),
                    ("Desktop + mobile", "desktop,mobile"),
                    ("Mobile only", "mobile"),
                ],
                value="desktop",
                id="breakpoints",
            )

            yield Static("")
            yield Checkbox("Agent mode (offline + agent judges)", id="agent")
            yield Checkbox("No browser (static fetch only, much faster)",
                           id="no-browser")

            yield Static("")
            with Horizontal():
                yield Button("Run Full Scan", id="run", variant="primary")
                yield Button("Back", id="back")

            yield Static("")
            yield Label("", id="fullscan-status")
            yield Label("Documents go to a folder per target on your Desktop.",
                        classes="hint")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.action_back()
        elif event.button.id == "run":
            self._run_fullscan()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "target":
            self._run_fullscan()

    def _run_fullscan(self) -> None:
        target = self.query_one("#target", Input).value.strip()
        if not target:
            self.status("Enter a target.")
            return

        args = argparse.Namespace(
            target=target,
            url=False,
            depth=int(self.query_one("#depth", Select).value or 0),
            max_pages=30,
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
            # Empty means "work it out from the page content" - see
            # `cli_impl.fullscan._detect_report_language`.
            language=self.query_one("#language", Select).value or None,
            breakpoints=self.query_one("#breakpoints", Select).value,
            agent=self.query_one("#agent", Checkbox).value,
            no_browser=self.query_one("#no-browser", Checkbox).value,
            json=True,
        )
        self.start_run(cmd_fullscan, args, title=f"Full scan of {target}")
