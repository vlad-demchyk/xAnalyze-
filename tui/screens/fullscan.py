"""Fullscan screen — combined AI patterns + accessibility in one run."""
from __future__ import annotations

import argparse

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from cli import cmd_fullscan
from tui.screens.base import RunScreen
from tui.screens.confirm import ConfirmModal


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

            # The design's toolbar (artboard 3a) reads "analyze Site ·
            # depth 2" - one sentence with the choices inline rather than a
            # label above every one of them. `Select(compact=True)` is
            # Textual's own version of that: no frame, sized to its current
            # value, opens the same way. Three selectors read as one
            # sentence this way where three stacked "Label: dropdown" rows
            # read as a form - which is the whole difference the redesign
            # was for.
            with Horizontal(classes="sentence"):
                yield Static("language", classes="inline-label")
                yield Select(
                    [
                        ("auto", ""),
                        ("English", "en"),
                        ("Українська", "uk"),
                        ("Italiano", "it"),
                    ],
                    value="",
                    id="language",
                    compact=True,
                    classes="inline-select",
                )
                yield Static("·", classes="inline-sep")
                yield Static("depth", classes="inline-label")
                yield Select(
                    [
                        ("1", "1"),
                        ("0 — this page only", "0"),
                        ("2", "2"),
                        ("3", "3"),
                    ],
                    value="1",
                    id="depth",
                    compact=True,
                    classes="inline-select",
                )
                yield Static("·", classes="inline-sep")
                yield Static("breakpoints", classes="inline-label")
                yield Select(
                    [
                        ("desktop", "desktop"),
                        ("all", "all"),
                        ("desktop + mobile", "desktop,mobile"),
                        ("mobile", "mobile"),
                    ],
                    value="desktop",
                    id="breakpoints",
                    compact=True,
                    classes="inline-select",
                )

            yield Static("")
            yield Checkbox("Agent mode (offline + agent judges)", id="agent")
            yield Checkbox("No browser (static fetch only, much faster)",
                           id="no-browser")
            # Off by default: a repo's dev server may already be running
            # elsewhere, and starting a second one on a different port is a
            # confusing outcome, not a helpful one. A repo scanned with this
            # unchecked is scanned statically, same as always.
            yield Checkbox("Start dev server if the repo has one "
                           "(package.json, manage.py, Gemfile+bin/rails)",
                           id="devserver")

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
            repo=None,
            devserver=self.query_one("#devserver", Checkbox).value,
            start_command=None,
            dev_server_port=None,
            yes=False,
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

        title = f"Full scan of {target}"
        if args.devserver:
            stack = self._devserver_stack_needing_confirm(target)
            if stack is not None:
                question = (f"{stack.name}: dependencies are missing for "
                           f"{target}. Install them and start the dev server?")
                self.app.push_screen(
                    ConfirmModal(question),
                    lambda confirmed: self._on_devserver_confirmed(confirmed, args, title))
                return
        # Not checked: scanned statically, same as always. If a stack exists,
        # `cmd_fullscan` says so itself (a "# [devserver] ..." stderr line),
        # which this screen already surfaces through the ordinary status-line
        # mechanism - no separate notice needed here.
        self.start_run(cmd_fullscan, args, title=title)

    def _devserver_stack_needing_confirm(self, target: str):
        """The detected stack, if it needs an install confirmed - else `None`.

        Cheap filesystem/`--version`-class checks only, run synchronously on
        the UI thread before anything starts: this is not the server itself,
        which is what `tui.runner`'s worker goes on to start once `start_run`
        is called below, exactly as it always has.
        """
        from pathlib import Path

        import devserver
        from cli_impl.auditpass import looks_like_url

        if looks_like_url(target):
            return None
        path = Path(target)
        if not path.is_dir():
            return None
        stack = devserver.detect_stack(path)
        if stack is None or stack.deps_satisfied(path):
            return None
        return stack

    def _on_devserver_confirmed(self, confirmed: bool, args: argparse.Namespace,
                                title: str) -> None:
        # A separate call, not a resumed one: the modal answers on its own
        # callback, on the UI thread, well after `_run_fullscan` already
        # returned - there is no suspended call frame to continue.
        args.yes = confirmed
        self.start_run(cmd_fullscan, args, title=title)
