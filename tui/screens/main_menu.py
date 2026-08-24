"""Main menu screen — navigation hub."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Label, Static

import config

from tui.screens.base import XScreen

#: Menu entries: shortcut key, screen name, label. One list rather than a
#: block of `elif`s plus a matching block of `action_*` methods, which had
#: already drifted once (the README documented shortcuts 1-6 while the menu
#: had seven).
MENU = (
    ("1", "scan", "Scan — AI patterns & characters"),
    ("2", "audit", "Audit — accessibility, SEO, performance"),
    ("3", "fullscan", "Full Scan — everything in one run"),
    ("4", "reports", "Reports — view previous analyses"),
    ("5", "settings", "Settings — configuration"),
    ("6", "update", "Update — check for new version"),
    ("7", "uninstall", "Uninstall — remove from this machine"),
)


class MainMenuScreen(XScreen):
    """Central menu with all major actions."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "quit", "Quit"),
    ] + [(key, f"go('{name}')", label.split(" —")[0])
         for key, name, label in MENU]

    def compose(self) -> ComposeResult:
        yield from self.compose_chrome()
        with Vertical(id="main-menu"):
            yield Label("XAnalyze", classes="menu-title")
            yield Label(f"v{config.APP_VERSION}", id="version-hint")
            yield Static("")
            for key, name, label in MENU:
                yield Button(f"{key}  {label}", id=name, classes="menu-item")
            yield Static("")
            yield Button("Q  Quit", id="quit", classes="menu-item")
            yield Label("Arrows or Tab to move, Enter to choose.",
                        classes="hint")

    def action_go(self, name: str) -> None:
        self.app.push_screen(name)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.app.exit()
        elif event.button.id in {name for _key, name, _label in MENU}:
            self.app.push_screen(event.button.id)
