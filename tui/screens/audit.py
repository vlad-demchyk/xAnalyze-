"""Audit screen — configure and run accessibility/SEO/performance audit."""
from __future__ import annotations

import argparse

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from cli import cmd_audit


class AuditScreen(Screen):
    """Form to configure and run an audit."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("q", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="audit-form"):
            yield Label("Audit — accessibility, SEO, performance", classes="menu-title")
            yield Static("")

            yield Label("Target (URL, directory, or .html file):")
            yield Input(placeholder="https://example.com or ./src", id="target")

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

            yield Static("")
            yield Checkbox("Browser rendering (for SPA sites)", id="browser")
            yield Checkbox("AI pass (checks alt text, costs tokens)", id="ai")
            yield Checkbox("Auto-fix known issues", id="fix")

            yield Static("")
            with Horizontal():
                yield Button("Run Audit", id="run", variant="primary")
                yield Button("Back", id="back")

            yield Static("")
            yield Label("", id="audit-status")

    def action_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "run":
            self._run_audit()

    def _run_audit(self) -> None:
        target = self.query_one("#target", Input).value.strip()
        if not target:
            self.query_one("#audit-status", Label).update("Enter a target.")
            return

        language = self.query_one("#language", Select).value
        browser = self.query_one("#browser", Checkbox).value
        ai = self.query_one("#ai", Checkbox).value
        fix = self.query_one("#fix", Checkbox).value

        self.query_one("#audit-status", Label).update(f"Auditing {target}...")

        args = argparse.Namespace(
            target=target,
            url=False,
            depth=0,
            max_pages=30,
            max_files=5000,
            render=None,
            exclude=None,
            use_default_excludes=True,
            category=None,
            language=language,
            no_ignore=False,
            json=True,
            check=False,
            ai=ai,
            provider=None,
            fix=fix,
            report=None,
            browser=browser,
            breakpoints=None,
            styled_report=None,
        )

        try:
            result_code = cmd_audit(args)
            self.query_one("#audit-status", Label).update(
                f"Audit complete (exit code {result_code}). See results in terminal."
            )
        except Exception as exc:
            self.query_one("#audit-status", Label).update(f"Error: {exc}")
