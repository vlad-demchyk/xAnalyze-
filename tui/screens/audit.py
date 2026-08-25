"""Audit screen — configure and run accessibility/SEO/performance audit."""
from __future__ import annotations

import argparse

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from cli import cmd_audit
from tui.screens.base import RunScreen


class AuditScreen(RunScreen):
    """Form to configure and run an audit."""

    status_id = "audit-status"

    def compose(self) -> ComposeResult:
        yield from self.compose_chrome()
        with Vertical(id="audit-form"):
            yield Label("Audit — accessibility, SEO, performance",
                        classes="menu-title")
            yield Static("")

            yield Label("Target (URL, directory, or .html file):")
            # No scheme needed: `example.com` is accepted, the same as in the
            # CLI. See `cli_impl.auditpass.looks_like_url`.
            yield Input(placeholder="example.com or ./src", id="target")

            # One sentence, not three labelled dropdowns - see
            # FullscanScreen.compose for why, and ui.widgets.InlineValue for
            # the Qt window's version of the same idea.
            with Horizontal(classes="sentence"):
                yield Static("language", classes="inline-label")
                yield Select(
                    [
                        ("English", "en"),
                        ("Українська", "uk"),
                        ("Italiano", "it"),
                    ],
                    value="en",
                    id="language",
                    compact=True,
                    classes="inline-select",
                )
                yield Static("·", classes="inline-sep")
                yield Static("depth", classes="inline-label")
                yield Select(
                    [
                        ("0", "0"),
                        ("1", "1"),
                        ("2", "2"),
                        ("3", "3"),
                    ],
                    value="0",
                    id="depth",
                    compact=True,
                    classes="inline-select",
                )
                yield Static("·", classes="inline-sep")
                yield Static("breakpoints", classes="inline-label")
                yield Select(
                    [
                        ("default", ""),
                        ("all", "all"),
                        ("desktop", "desktop"),
                        ("desktop + mobile", "desktop,mobile"),
                        ("mobile", "mobile"),
                    ],
                    value="",
                    id="breakpoints",
                    compact=True,
                    classes="inline-select",
                )

            yield Static("")
            yield Checkbox("Browser rendering (for SPA sites)", id="browser")
            yield Checkbox("AI pass (checks alt text, costs tokens)", id="ai")
            yield Checkbox("Auto-fix known issues (writes files, keeps .bak)",
                           id="fix")

            yield Static("")
            with Horizontal():
                yield Button("Run Audit", id="run", variant="primary")
                yield Button("Back", id="back")

            yield Static("")
            yield Label("", id="audit-status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.action_back()
        elif event.button.id == "run":
            self._run_audit()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "target":
            self._run_audit()

    def _run_audit(self) -> None:
        target = self.query_one("#target", Input).value.strip()
        if not target:
            self.status("Enter a target.")
            return

        breakpoints = self.query_one("#breakpoints", Select).value or None
        args = argparse.Namespace(
            target=target,
            url=False,
            depth=int(self.query_one("#depth", Select).value or 0),
            max_pages=30,
            max_files=5000,
            render=None,
            exclude=None,
            use_default_excludes=True,
            ext=None,
            scope="content",
            category=None,
            language=self.query_one("#language", Select).value,
            no_ignore=False,
            no_typography=False,
            categories=None,
            json=True,
            check=False,
            ai=self.query_one("#ai", Checkbox).value,
            provider=None,
            fix=self.query_one("#fix", Checkbox).value,
            report=None,
            browser=self.query_one("#browser", Checkbox).value,
            breakpoints=breakpoints,
            styled_report=None,
        )
        self.start_run(cmd_audit, args, title=f"Audit of {target}")
