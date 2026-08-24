"""What every screen shares: the key hints, going back, and running a scan.

The key hints matter more than they look. The bindings were always there,
but nothing displayed them, so the only way to learn that `Esc` goes back
was to try it - and the one key people do try, an arrow, did nothing. A
`Footer` turns the bindings into an interface.
"""
from __future__ import annotations

import argparse

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, Label


class XScreen(Screen):
    """Base screen: a header, a footer of key hints, and `Esc` to go back."""

    BINDINGS = [
        ("escape", "back", "Back"),
    ]

    def compose_chrome(self) -> ComposeResult:
        yield Header()
        yield Footer()

    def action_back(self) -> None:
        # The main menu is the bottom of the stack; popping it would leave
        # the app with no screen at all, so there it means "quit".
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        else:
            self.app.exit()


class RunScreen(XScreen):
    """A screen whose form starts a scan.

    Holds the one rule that keeps the captured-output trick safe: at most
    one command runs at a time (see `tui.runner.run_in_thread`). It also
    keeps the button and the status line honest while a run is in flight -
    a second press used to start a second, interleaved scan.
    """

    #: Set by the subclass: the id of the status label and of the run button.
    status_id = "status"
    run_button_id = "run"

    #: How often the worker is checked for new progress lines. A status line
    #: does not need sub-frame latency, and polling is what keeps the capture
    #: from re-entering the app - see `tui.runner`.
    poll_interval = 0.15

    def __init__(self) -> None:
        super().__init__()
        self._run = None
        self._timer = None
        self._title = ""

    # -- status ------------------------------------------------------------

    def status(self, text: str, *, ok: bool = False) -> None:
        label = self.query_one(f"#{self.status_id}", Label)
        label.update(text)
        label.set_class(ok, "ok")

    @property
    def busy(self) -> bool:
        return self._run is not None

    def _set_busy(self, busy: bool) -> None:
        try:
            button = self.query_one(f"#{self.run_button_id}")
        except Exception:  # noqa: BLE001 - a screen may have no run button
            return
        button.disabled = busy

    # -- running -----------------------------------------------------------

    def start_run(self, command, args: argparse.Namespace, *,
                  title: str) -> bool:
        """Run `command(args)` on a worker thread. False if one is already on.

        `title` is what the results screen is called, so a person who ran
        three things can tell which result they are looking at.

        One at a time, and that is not a nicety: the worker captures stdout
        and stderr by replacing them process-wide, so two overlapping runs
        would interleave into each other's output.
        """
        from tui import runner

        if self.busy:
            return False
        self._title = title
        self._run = runner.start(command, args)
        self._set_busy(True)
        self.status(f"{title}: starting…")
        self._timer = self.set_interval(self.poll_interval, self._poll)
        return True

    def _poll(self) -> None:
        """Drain progress, and finish once the worker has a result."""
        run = self._run
        if run is None:
            return
        for line in run.new_lines():
            # Only the tool's own progress lines: a library warning on
            # stderr is kept for the log but must not become the status.
            if line.startswith("#"):
                self.status(line.lstrip("# ").strip() or line)
        if run.running:
            return
        result = run.result
        self._run = None
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        self._set_busy(False)
        self.show_result(self._title, result)

    def show_result(self, title: str, result) -> None:
        """Show the finished run. Overridable; the default opens Results."""
        from tui.screens.results import ResultsScreen

        if result.error:
            self.status(f"Failed: {result.error}")
            return
        self.status("Done.", ok=True)
        self.app.push_screen(ResultsScreen(title, result))
