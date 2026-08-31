"""Audit screen — configure and run accessibility/SEO/performance audit."""
from __future__ import annotations

import argparse

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from audit.base import CATEGORIES, CONFIDENCE_ORDER
from cli import cmd_audit
from tui.screens.base import RunScreen


class AuditScreen(RunScreen):
    """Form to configure and run an audit."""

    status_id = "audit-status"

    def compose(self) -> ComposeResult:
        yield from self.compose_chrome()
        with Vertical(id="audit-form"):
            yield Label(self.tr("tui_audit_title"), classes="menu-title")
            yield Static("")

            yield Label(self.tr("tui_target_any"))
            # No scheme needed: `example.com` is accepted, the same as in the
            # CLI. See `cli_impl.auditpass.looks_like_url`.
            yield Input(placeholder=self.tr("tui_placeholder_any"), id="target")

            # One sentence, not three labelled dropdowns - see
            # FullscanScreen.compose for why, and ui.widgets.InlineValue for
            # the Qt window's version of the same idea.
            with Horizontal(classes="sentence"):
                yield Static(self.tr("tui_label_language"), classes="inline-label")
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
                yield Static(self.tr("tui_label_depth"), classes="inline-label")
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
                yield Static(self.tr("tui_label_widths"), classes="inline-label")
                # Every breakpoint the audit knows, not a subset. `tablet`
                # and `reflow` existed in `responsive.BREAKPOINTS` and in the
                # CLI while this list offered neither, so the width that
                # finds WCAG 1.4.10 overflow was unreachable from the TUI.
                yield Select(
                    [
                        ("default", ""),
                        ("all", "all"),
                        ("desktop", "desktop"),
                        ("desktop + mobile", "desktop,mobile"),
                        ("tablet", "tablet"),
                        ("mobile", "mobile"),
                        ("reflow (320 px)", "reflow"),
                    ],
                    value="",
                    id="breakpoints",
                    compact=True,
                    classes="inline-select",
                )

            # The second sentence: what to show of what was found. Both
            # are a view over one pass - the rules are cheap and share the
            # parse - so narrowing here costs nothing and hides nothing that
            # a wider choice would not bring straight back.
            with Horizontal(classes="sentence"):
                yield Static(self.tr("tui_label_category"), classes="inline-label")
                yield Select(
                    [(self.tr("tui_all_categories"), "")]
                    + [(self.tr(f"audit_category_{value}"), value)
                       for value in CATEGORIES],
                    value="",
                    id="category",
                    compact=True,
                    classes="inline-select",
                )
                yield Static("·", classes="inline-sep")
                yield Static(self.tr("tui_label_certainty"), classes="inline-label")
                yield Select(
                    [(self.tr("certainty_any"), "")]
                    + [(self.tr(f"certainty_{value}"), value)
                       for value in CONFIDENCE_ORDER],
                    value="",
                    id="confidence",
                    compact=True,
                    classes="inline-select",
                )

            yield Static("")
            yield Checkbox(self.tr("tui_unsettled"), id="unsettled")
            yield Checkbox(self.tr("tui_site_controls"), id="site-controls")
            yield Checkbox(self.tr("tui_browser_pass"), id="browser")
            yield Checkbox(self.tr("tui_ai_pass"), id="ai")
            yield Checkbox(self.tr("tui_autofix"), id="fix")

            yield Static("")
            with Horizontal():
                yield Button(self.tr("tui_audit_run"), id="run", variant="primary")
                yield Button(self.tr("tui_back"), id="back")

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
            self.status(self.tr("tui_need_target"))
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
            # `--category` takes a list; one choice or none, from a screen
            # that has one line to spend on it. `None` is every category,
            # which is what the CLI means by the flag being absent.
            category=([self.query_one("#category", Select).value]
                      if self.query_one("#category", Select).value else None),
            confidence=self.query_one("#confidence", Select).value or None,
            unsettled=self.query_one("#unsettled", Checkbox).value,
            site_controls=self.query_one("#site-controls", Checkbox).value,
            medium=None,
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
            # `no_browser`, not `browser`: the command reads the negative,
            # and the positive it was being sent under was read by nothing.
            # The checkbox was decorative - the browser pass ran either way,
            # which is also why an audit felt slow with it switched off.
            no_browser=not self.query_one("#browser", Checkbox).value,
            breakpoints=breakpoints,
            styled_report=None,
        )
        self.start_run(cmd_audit, args, title=self.tr("tui_audit_of", target=target))
