"""Settings screen — view current configuration."""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Label, Static

import config


class SettingsScreen(Screen):
    """Read-only view of current settings."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("q", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-view"):
            yield Label("Settings", classes="menu-title")
            yield Static("")
            yield DataTable(id="settings-table")
            yield Static("")
            yield Label(f"Config file: {config.CONFIG_FILE}", id="config-path")
            yield Static("")
            yield Button("Back", id="back")

    def on_mount(self) -> None:
        table = self.query_one("#settings-table", DataTable)
        table.add_columns("Setting", "Value")
        settings = config.Settings.load()
        data = {
            "Version": config.APP_VERSION,
            "UI Language": settings.ui_language,
            "Default Method": settings.default_method,
            "LLM Provider": settings.llm_provider,
            "Claude Model": settings.claude_model,
            "Theme": settings.theme,
            "Repo Scope": settings.repo_scope,
            "Unicode Check": "enabled" if settings.unicode_check_enabled else "disabled",
            "Unicode Categories": ", ".join(settings.unicode_categories),
            "Crawl Depth": str(settings.crawl_depth),
            "Max Pages": str(settings.max_pages),
            "xFormat URL": settings.xformat_base_url,
            "Claude Code in CLI": "yes" if settings.prefer_claude_code_in_cli else "no",
        }
        for key, value in data.items():
            table.add_row(key, value)

    def action_back(self) -> None:
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.app.pop_screen()
