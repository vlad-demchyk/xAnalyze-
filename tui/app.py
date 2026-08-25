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
        width: 62;
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
    #version-hint, .hint {
        text-align: center;
        color: $text-muted;
        margin: 1 0 0 0;
    }
    #scan-form, #audit-form, #fullscan-form, #settings-view, #reports-view,
    #update-view, #uninstall-view {
        width: 74;
        height: auto;
        max-height: 90%;
        border: tall $accent;
        padding: 1 2;
    }
    #results-view, #report-detail {
        width: 96;
        height: 90%;
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
    #report-status, #scan-status, #audit-status, #fullscan-status,
    #update-status, #uninstall-status, #settings-status {
        color: $warning;
    }
    .ok {
        color: $success;
    }
    DataTable {
        height: auto;
        max-height: 22;
    }
    #results-summary {
        height: auto;
        max-height: 14;
    }
    #results-log, #report-body {
        height: 1fr;
        border: round $panel;
    }
    #confirm-modal {
        width: 60;
        height: auto;
        border: tall $warning;
        padding: 1 2;
        background: $surface;
    }
    #confirm-question {
        margin: 0 0 1 0;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        # Arrow keys move between controls, which is what the README has
        # always promised and what people try first. Textual binds only
        # `tab`/`shift+tab` by default, so without these a form could be
        # filled in exactly one order and the menu could not be walked at
        # all. Bindings are consulted after the focused widget has had the
        # key, so an Input still gets its own arrow handling.
        Binding("down", "focus_next", "Next", show=False),
        Binding("up", "focus_previous", "Previous", show=False),
    ]

    def on_mount(self) -> None:
        from tui.screens.main_menu import MainMenuScreen
        from tui.screens.scan import ScanScreen
        from tui.screens.audit import AuditScreen
        from tui.screens.fullscan import FullscanScreen
        from tui.screens.settings import SettingsScreen
        from tui.screens.reports import ReportsScreen
        from tui.screens.update import UpdateScreen
        from tui.screens.uninstall import UninstallScreen

        self.install_screen(MainMenuScreen(), name="main")
        self.install_screen(ScanScreen(), name="scan")
        self.install_screen(AuditScreen(), name="audit")
        self.install_screen(FullscanScreen(), name="fullscan")
        self.install_screen(SettingsScreen(), name="settings")
        self.install_screen(ReportsScreen(), name="reports")
        self.install_screen(UpdateScreen(), name="update")
        self.install_screen(UninstallScreen(), name="uninstall")
        self.push_screen("main")


def run_tui() -> int:
    """Entry point for the TUI."""
    app = XAnalyzeApp()
    app.run()
    return 0
