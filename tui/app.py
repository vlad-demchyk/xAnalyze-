"""XAnalyze TUI — interactive terminal interface.

Launch with no arguments: ``xanalyze`` or ``python cli.py``.
"""
from __future__ import annotations

from textual.app import App
from textual.binding import Binding

import config
from ui.theme import build_textual_themes

#: Registered in `on_mount` below and matched by name (`ui.theme.build_
#: textual_theme` names them `xanalyze-{light,dark}`), so the terminal
#: paints from the same `Palette` the Qt window's `build_qss` does instead
#: of Textual's stock design. `dark` is the default because a terminal's own
#: background is dark far more often than not, and there is no equivalent of
#: Qt's `QGuiApplication.styleHints().colorScheme()` to ask the terminal
#: instead - `light`/`dark` stay one setting away (`XAnalyzeApp().theme =
#: "xanalyze-light"`) for the person whose terminal is not.
DEFAULT_THEME = "xanalyze-dark"


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
    /* The inline sentence a form's stacked "Label: dropdown" rows became -
       see FullscanScreen.compose. `Select { margin }` above is for the
       stacked form and would space these out over two lines, so it is
       overridden back to zero here rather than left to fight the
       browser-style wrap a Horizontal gives a too-wide row. */
    .sentence {
        height: auto;
        align: left middle;
        margin: 0 0 1 0;
    }
    /* `width: auto` is not Static's default (a bare Static fills the row,
       which is right for a status line and wrong for a word in a sentence)
       - without it every label below claimed the row's full width and
       pushed everything after the first one off screen. */
    .sentence .inline-label {
        width: auto;
        color: $inline-label;
        margin: 0 1 0 0;
    }
    .sentence .inline-sep {
        width: auto;
        color: $inline-label;
        margin: 0 1 0 0;
    }
    /* `Select`'s own default CSS is `width: auto`, but the `SelectCurrent`
       it composes itself asks for `width: 1fr` - "fill whatever I am
       given" - which is right for a stand-alone dropdown and wrong for one
       word in a sentence. Both the box and the label inside it have to be
       told to size to content, or the widest option in the list keeps
       claiming the row's full width and pushing the selectors after it
       past the edge of the screen. */
    .sentence Select.inline-select {
        width: auto;
        margin: 0 0 0 0;
    }
    .sentence Select.inline-select SelectCurrent {
        width: auto;
    }
    .sentence Select.inline-select SelectCurrent Static#label {
        width: auto;
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

    def __init__(self) -> None:
        super().__init__()
        #: The interface language, read once and then owned here. Every
        #: screen asks the app rather than loading `Settings` itself: a
        #: screen that read the file would keep showing the old language
        #: after Settings changed it, which is exactly what "the option does
        #: nothing" looks like from the outside.
        self.lang = config.Settings.load().ui_language or "uk"
        self._translate_own_bindings()
        # Registered here rather than in `on_mount`: the CSS above already
        # references custom variables (`$inline-label` and friends), and the
        # first stylesheet parse - which resolves every `$name` against
        # whatever theme is current - happens while the widget tree is being
        # registered, before `on_mount` ever runs. A theme picked in
        # `on_mount` is a theme that arrives one parse too late, and the CSS
        # fails to load at all rather than falling back to something close.
        for theme in build_textual_themes().values():
            self.register_theme(theme)
        self.theme = DEFAULT_THEME

    def _translate_own_bindings(self) -> None:
        """The app's own footer hints, in the app's language.

        The same rewrite the screens do to their copy (`XScreen`), applied
        one level up. What is left in English after this belongs to Textual
        itself - the focus and clipboard hints a focused widget contributes -
        and translating those would mean patching the framework.
        """
        from dataclasses import replace

        from i18n.translations import t
        from tui.screens.base import BINDING_LABELS

        mapping = getattr(self._bindings, "key_to_bindings", None)
        if not mapping:
            return
        for key, bindings in list(mapping.items()):
            rewritten = []
            for binding in bindings:
                action = (binding.action or "").split("(")[0]
                label_key = BINDING_LABELS.get(action)
                if label_key and binding.description:
                    binding = replace(binding,
                                      description=t(label_key, self.lang))
                rewritten.append(binding)
            mapping[key] = rewritten

    #: Screen name -> the class that builds it. One list, because installing
    #: them and re-installing them after a language change must not drift.
    SCREENS_IN_ORDER = ("main", "scan", "audit", "fullscan", "settings",
                        "reports", "update", "uninstall")

    def _screen_classes(self) -> dict:
        from tui.screens.audit import AuditScreen
        from tui.screens.fullscan import FullscanScreen
        from tui.screens.main_menu import MainMenuScreen
        from tui.screens.reports import ReportsScreen
        from tui.screens.scan import ScanScreen
        from tui.screens.settings import SettingsScreen
        from tui.screens.uninstall import UninstallScreen
        from tui.screens.update import UpdateScreen

        return {"main": MainMenuScreen, "scan": ScanScreen,
                "audit": AuditScreen, "fullscan": FullscanScreen,
                "settings": SettingsScreen, "reports": ReportsScreen,
                "update": UpdateScreen, "uninstall": UninstallScreen}

    def install_all_screens(self) -> None:
        classes = self._screen_classes()
        for name in self.SCREENS_IN_ORDER:
            self.install_screen(classes[name](), name=name)

    def set_language(self, lang: str) -> None:
        """Change the language and rebuild the screens in it.

        A screen's labels are written when it is composed, so changing the
        setting is not enough: the screens are built once at startup and
        would keep the words they were built with. Rebuilding them is what
        makes the setting visibly do something, which is the whole point of
        an option.
        """
        if lang == self.lang:
            return
        self.lang = lang
        self._translate_own_bindings()
        while len(self.screen_stack) > 1:
            self.pop_screen()
        for name in self.SCREENS_IN_ORDER:
            self.uninstall_screen(name)
        self.install_all_screens()
        self.push_screen("settings")

    def on_mount(self) -> None:
        self.install_all_screens()
        self.push_screen("main")


def run_tui() -> int:
    """Entry point for the TUI."""
    app = XAnalyzeApp()
    app.run()
    return 0
