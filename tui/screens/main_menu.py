"""Main menu screen — navigation hub."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, Label, Static

import config


class MainMenuScreen(Screen):
    """Central menu with all major actions."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("1", "scan", "Scan"),
        ("2", "audit", "Audit"),
        ("3", "fullscan", "Full Scan"),
        ("4", "reports", "Reports"),
        ("5", "settings", "Settings"),
        ("6", "update", "Update"),
        ("7", "uninstall", "Uninstall"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="main-menu"):
            yield Label("XAnalyze", classes="menu-title")
            yield Label(f"v{config.APP_VERSION}", id="version-hint")
            yield Static("")
            yield Button("1  Scan — AI patterns & characters", id="scan", classes="menu-item")
            yield Button("2  Audit — accessibility, SEO, performance", id="audit", classes="menu-item")
            yield Button("3  Full Scan — everything in one run", id="fullscan", classes="menu-item")
            yield Static("")
            yield Button("4  Reports — view previous analyses", id="reports", classes="menu-item")
            yield Button("5  Settings — configuration", id="settings", classes="menu-item")
            yield Button("6  Update — check for new version", id="update", classes="menu-item")
            yield Button("7  Uninstall — remove from this machine", id="uninstall", classes="menu-item")
            yield Static("")
            yield Button("Q  Quit", id="quit", classes="menu-item")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        action = event.button.id
        if action == "scan":
            self.app.push_screen("scan")
        elif action == "audit":
            self.app.push_screen("audit")
        elif action == "fullscan":
            self.app.push_screen("fullscan")
        elif action == "reports":
            self.app.push_screen("reports")
        elif action == "settings":
            self.app.push_screen("settings")
        elif action == "update":
            self.app.push_screen("update")
        elif action == "uninstall":
            self.app.push_screen("uninstall")
        elif action == "quit":
            self.app.exit()

    def action_scan(self) -> None:
        self.app.push_screen("scan")

    def action_audit(self) -> None:
        self.app.push_screen("audit")

    def action_fullscan(self) -> None:
        self.app.push_screen("fullscan")

    def action_reports(self) -> None:
        self.app.push_screen("reports")

    def action_settings(self) -> None:
        self.app.push_screen("settings")

    def action_update(self) -> None:
        self.app.push_screen("update")

    def action_uninstall(self) -> None:
        self.app.push_screen("uninstall")
