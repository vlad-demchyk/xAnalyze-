"""Update screen — check for and install updates."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, Static

import config


class UpdateScreen(Screen):
    """Check for updates and install them."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("q", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="update-view"):
            yield Label("Update", classes="menu-title")
            yield Static("")
            yield Label(f"Current version: {config.APP_VERSION}")
            yield Static("")
            yield Button("Check for updates", id="check", variant="primary")
            yield Static("")
            yield Label("", id="update-status")
            yield Static("")
            yield Button("Back", id="back")

    def action_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
        elif event.button.id == "check":
            self._check_update()

    def _check_update(self) -> None:
        import updater

        status = self.query_one("#update-status", Label)
        status.update("Checking GitHub Releases...")

        try:
            release = updater.fetch_latest()
            if updater.newer(release.version, config.APP_VERSION):
                status.update(
                    f"New version available: {release.version}\n"
                    f"Run `xanalyze update` in terminal to install.\n"
                    f"Download: {release.html_url}"
                )
            else:
                status.update(f"Already up to date ({config.APP_VERSION}).")
        except Exception as exc:
            status.update(f"Check failed: {exc}")
