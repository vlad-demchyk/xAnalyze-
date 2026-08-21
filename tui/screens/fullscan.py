"""Fullscan screen — combined AI patterns + accessibility in one run."""
from __future__ import annotations

import argparse
import sys
import threading

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from cli import cmd_fullscan


class _StatusTee:
    """A stderr stand-in that lifts `# ...` progress lines out of the scan
    and hands them to the status label, so a run that takes minutes shows
    where it is instead of looking frozen."""

    def __init__(self, original, on_line):
        self._original = original
        self._on_line = on_line
        self._buffer = ""

    def write(self, text: str) -> None:
        self._original.write(text)
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line = line.strip()
            if line.startswith("#"):
                self._on_line(line)

    def flush(self) -> None:
        self._original.flush()


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
                value="desktop",
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
        if getattr(self, "_scan_running", False):
            return
        target = self.query_one("#target", Input).value.strip()
        if not target:
            self.query_one("#fullscan-status", Label).update("Enter a target.")
            return
        self._scan_running = True

        language = self.query_one("#language", Select).value
        breakpoints = self.query_one("#breakpoints", Select).value
        agent = self.query_one("#agent", Checkbox).value

        self.query_one("#fullscan-status", Label).update(
            f"Full scan of {target}... (starting)")

        args = argparse.Namespace(
            target=target,
            url=False,
            depth=1,
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
            language=language,
            breakpoints=breakpoints,
            agent=agent,
            json=True,
        )

        status = self.query_one("#fullscan-status", Label)

        def report_line(line: str) -> None:
            self.app.call_from_thread(status.update, line)

        def work() -> None:
            # The scan prints its stage banners to stderr; tee them into the
            # label so the run stays legible. The worker thread keeps the UI
            # responsive while the crawl and the browser pass grind.
            tee = _StatusTee(sys.stderr, report_line)
            old_stderr = sys.stderr
            sys.stderr = tee
            try:
                result_code = cmd_fullscan(args)
                self.app.call_from_thread(
                    status.update,
                    f"Full scan complete (exit code {result_code}). "
                    f"See results in terminal.")
            except Exception as exc:
                self.app.call_from_thread(status.update, f"Error: {exc}")
            finally:
                sys.stderr = old_stderr
                self._scan_running = False

        threading.Thread(target=work, daemon=True).start()
