"""Update screen — check for and install updates."""
from __future__ import annotations

import threading

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, Static

import config

from tui.screens.base import XScreen


class UpdateScreen(XScreen):
    """Check for updates and install them."""

    BINDINGS = [
        ("escape", "back", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._release = None
        self._busy = False

    def compose(self) -> ComposeResult:
        yield from self.compose_chrome()
        with Vertical(id="update-view"):
            yield Label("Update", classes="menu-title")
            yield Static("")
            yield Label(f"Current version: {config.APP_VERSION}")
            yield Static("")
            with Horizontal():
                yield Button("Check for updates", id="check", variant="primary")
                yield Button("Install", id="install", disabled=True)
                yield Button("Back", id="back")
            yield Static("")
            yield Label("", id="update-status")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.action_back()
        elif event.button.id == "check":
            self._check_update()
        elif event.button.id == "install":
            self._install()

    def _status(self, text: str) -> None:
        self.query_one("#update-status", Label).update(text)

    def _check_update(self) -> None:
        """Ask GitHub, off the UI thread.

        A network call on the UI thread froze the whole interface until it
        answered - or until it timed out, which on a captive network is
        thirty seconds of a dead screen.
        """
        if self._busy:
            return
        self._busy = True
        self._status("Checking GitHub Releases…")

        def work() -> None:
            import updater

            try:
                release = updater.fetch_latest()
            except Exception as exc:  # noqa: BLE001 - shown to the user
                self.app.call_from_thread(self._checked, None, str(exc))
                return
            self.app.call_from_thread(self._checked, release, "")

        threading.Thread(target=work, daemon=True).start()

    def _checked(self, release, error: str) -> None:
        import updater

        self._busy = False
        if error:
            self._status(f"Check failed: {error}")
            return
        self._release = release
        if updater.newer(release.version, config.APP_VERSION):
            self.query_one("#install", Button).disabled = False
            self._status(f"New version available: {release.version}\n"
                         f"{release.html_url}\n"
                         f"Press Install to download and replace this "
                         f"installation.")
        else:
            self._status(f"Already up to date ({config.APP_VERSION}).")

    def _install(self) -> None:
        """Install the release found by the check.

        Two presses, not one: this replaces the installed program, and the
        `Install` button only becomes pressable after a check has actually
        found something newer.
        """
        if self._busy or self._release is None:
            return
        button = self.query_one("#install", Button)
        if str(button.label) != "Really install?":
            button.label = "Really install?"
            self._status("Press Install again to confirm.")
            return
        button.label = "Install"
        button.disabled = True
        self._busy = True
        self._status("Installing…")

        # `do_update` is the same flow `xanalyze update` runs: it checks,
        # downloads, and replaces the binary, reporting progress on stderr.
        # Driven through the shared runner so that progress reaches the
        # screen instead of the terminal underneath it.
        import argparse

        import updater

        from tui.runner import run_in_thread

        run_in_thread(self.app, lambda _args: updater.do_update(),
                      argparse.Namespace(),
                      on_progress=lambda line: self._status(
                          line.lstrip("# ").strip() or line),
                      on_done=self._installed)

    def _installed(self, result) -> None:
        self._busy = False
        if result.error:
            self._status(f"Install failed: {result.error}")
            return
        tail = [line for line in (result.stderr + "\n" + result.stdout)
                .splitlines() if line.strip()]
        summary = tail[-1] if tail else ""
        if result.exit_code == 0:
            self._status(f"{summary}\nRestart xanalyze to run the new version.")
        else:
            self._status(f"Install did not finish (exit {result.exit_code}).\n"
                         f"{summary}")
