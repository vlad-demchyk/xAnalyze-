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
    profile_note_id = "audit-profile"

    #: Which control sets which run option. See `RunScreen.FIELD_OPTIONS`.
    FIELD_OPTIONS = {
        "depth": "depth",
        "breakpoints": "breakpoints",
        "category": "category",
        "confidence": "confidence",
        "within": "within",
        "no-session": "no_session",
        "unsettled": "unsettled",
        "site-controls": "site_controls",
        "browser": "no_browser",
        "ai": "ai",
        "fix": "fix",
    }

    def compose(self) -> ComposeResult:
        yield from self.compose_chrome()
        with Vertical(id="audit-form"):
            yield Label(self.tr("tui_audit_title"), classes="menu-title")
            yield Static("")

            yield Label(self.tr("tui_target_any"))
            # No scheme needed: `example.com` is accepted, the same as in the
            # CLI. See `cli_impl.auditpass.looks_like_url`.
            yield Input(placeholder=self.tr("tui_placeholder_any"), id="target")

            # Only for a checkout that ships web parts: an SPFx solution
            # knows it delivers into a SharePoint site and cannot know
            # which. Given one, this run audits that site with the checkout
            # paired to it (`--repo`) and confined to the parts it ships
            # (`--web-parts`) - which is the run the plain folder scan
            # could not be.
            yield Label(self.tr("tui_site_url"), classes="field-site-url")
            yield Input(placeholder=self.tr("tui_site_url_placeholder"),
                        id="site-url", classes="field-site-url")

            # What the target's own stack asked for, and why. Empty - and
            # invisible - until something asks.
            yield Label("", id="audit-profile", classes="hint")

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
                yield Static("·", classes="inline-sep field-depth")
                yield Static(self.tr("tui_label_depth"),
                             classes="inline-label field-depth")
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

            # Two of the five run parameters the CLI had and this screen did
            # not. `--within` is a field because it takes a selector,
            # `--no-session` is a switch.
            #
            # `--web-parts` is deliberately absent from both terminal forms:
            # it reads the part manifests out of a *checkout*, so without
            # `--repo` - a path field these forms have no room for - the flag
            # prints a refusal and audits the whole page anyway. A control
            # that reaches nothing is worse than no control, which is what
            # `tests/test_tui.py::NoDecorativeControls` exists to say.
            yield Static("")
            yield Label(self.tr("within_placeholder"))
            yield Input(placeholder=self.tr("tui_within_placeholder"), id="within")

            yield Static("")
            yield Checkbox(self.tr("tui_no_session"), id="no-session")
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
        from cli_impl.auditpass import unquote_target

        target = unquote_target(self.query_one("#target", Input).value)
        if not target:
            self.status(self.tr("tui_need_target"))
            return

        # An SPFx checkout plus the site it ships into is one run, not two:
        # the site is what gets audited, the checkout is what names the file
        # behind each finding, and `--web-parts` is what keeps the audit to
        # the parts this repository actually delivers. Without the address
        # the folder is scanned as a folder, exactly as before.
        site_url = unquote_target(self.query_one("#site-url", Input).value)
        repo = ""
        web_parts = False
        if site_url and self._plan is not None and self._plan.asks_for("site_url"):
            repo, target, web_parts = target, site_url, True
            # The plan was built for the folder; the run is now about the
            # site, and `settle` below reads the plan to decide which
            # options are in play. Left as it was, it would blank the very
            # `--repo` this branch just set.
            import run_profile
            self._plan = run_profile.build(target, repo=repo)

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
            repo=repo or None,
            web_parts=web_parts,
            # `no_browser`, not `browser`: the command reads the negative,
            # and the positive it was being sent under was read by nothing.
            # The checkbox was decorative - the browser pass ran either way,
            # which is also why an audit felt slow with it switched off.
            no_browser=not self.query_one("#browser", Checkbox).value,
            breakpoints=breakpoints,
            styled_report=None,
            within=self.query_one("#within", Input).value.strip(),
            no_session=self.query_one("#no-session", Checkbox).value,
            # The form already applied the profile, visibly, with the reason
            # under each control. Applying it a second time inside the
            # command would overwrite whatever the person changed after
            # seeing it.
            profile_defaults=False,
            _explicit=set(self._touched),
            no_hints=True,
        )
        self.start_run(cmd_audit, self.settle(args),
                       title=self.tr("tui_audit_of", target=target))
