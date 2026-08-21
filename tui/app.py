"""XAnalyze TUI — interactive terminal interface.

Launch with no arguments: ``xanalyze`` or ``python cli.py``.
"""
from __future__ import annotations

from textual.app import App
from textual.binding import Binding

import config


class XAnalyzeApp(App):
    """Interactive terminal interface for XAnalyze."""

    TITLE = "XAnalyze"
    SUB_TITLE = f"v{config.APP_VERSION} — AI text & accessibility analyzer"

    CSS = """
    Screen {
        align: center middle;
    }
    #main-menu {
        width: 60;
        height: auto;
        max-height: 90%;
        border: tall $accent;
        padding: 1 2;
    }
    .menu-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin: 1 0;
    }
    .menu-item {
        width: 100%;
        height: 3;
        margin: 0 0 1 0;
        text-align: left;
    }
    #version-hint {
        text-align: center;
        color: $text-muted;
        margin: 1 0 0 0;
    }
    #scan-form, #audit-form, #fullscan-form, #settings-view, #reports-view, #update-view {
        width: 70;
        height: auto;
        max-height: 90%;
        border: tall $accent;
        padding: 1 2;
    }
    Input {
        margin: 0 0 1 0;
    }
    Select {
        margin: 0 0 1 0;
    }
    Checkbox {
        margin: 0 0 0 0;
    }
    #config-path {
        color: $text-muted;
        text-style: italic;
    }
    #report-status, #scan-status, #audit-status, #fullscan-status, #update-status {
        color: $warning;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("escape", "quit", "Quit", show=False),
    ]

    SCREENS = {}

    def on_mount(self) -> None:
        from tui.screens.main_menu import MainMenuScreen
        from tui.screens.scan import ScanScreen
        from tui.screens.audit import AuditScreen
        from tui.screens.fullscan import FullscanScreen
        from tui.screens.settings import SettingsScreen
        from tui.screens.reports import ReportsScreen
        from tui.screens.update import UpdateScreen

        self.install_screen(MainMenuScreen(), name="main")
        self.install_screen(ScanScreen(), name="scan")
        self.install_screen(AuditScreen(), name="audit")
        self.install_screen(FullscanScreen(), name="fullscan")
        self.install_screen(SettingsScreen(), name="settings")
        self.install_screen(ReportsScreen(), name="reports")
        self.install_screen(UpdateScreen(), name="update")
        self.push_screen("main")


def run_tui() -> int:
    """Entry point for the TUI."""
    app = XAnalyzeApp()
    app.run()
    return 0
