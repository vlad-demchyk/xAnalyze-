"""Settings screen — read the configuration, and change the useful parts.

Read-only before, which made it a screen that answered a question nobody had
asked: the values it showed were exactly the ones a person opens Settings to
change. The fields with a small, closed set of valid values are editable
here; anything needing a secret (an API key) deliberately is not - the
terminal is the wrong place to type one, and this tool does not store one.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Checkbox, DataTable, Label, Select, Static

import config

from tui.screens.base import XScreen

#: Editable settings: attribute, label, and the choices. Only closed sets -
#: a free-text field for a URL or a model name is one typo away from an app
#: that cannot reach its backend, and the desktop Settings dialog is where
#: that belongs.
CHOICES = (
    ("ui_language", "Interface language",
     (("Українська", "uk"), ("English", "en"), ("Italiano", "it"))),
    ("theme", "Theme",
     (("auto — follow the system", "auto"), ("light", "light"),
      ("dark", "dark"))),
    ("repo_scope", "Repository scope",
     (("content — copy that ships", "content"),
      ("technical — comments & docstrings", "technical"),
      ("both", "both"))),
    ("default_method", "Default method",
     (("local — offline only", "local"), ("ai — model only", "ai"),
      ("local+ai — hybrid", "local+ai"))),
    ("llm_provider", "AI account",
     (("anthropic — your own API key", "anthropic"),
      ("xformat — subscription", "xformat"),
      ("claude-code — the signed-in CLI", "claude-code"))),
    ("crawl_depth", "Crawl depth",
     (("0", "0"), ("1", "1"), ("2", "2"), ("3", "3"))),
    ("max_pages", "Max pages per crawl",
     (("10", "10"), ("30", "30"), ("100", "100"), ("unlimited", "0"))),
)

#: Editable booleans: attribute, label.
FLAGS = (
    ("unicode_check_enabled", "Check non-keyboard characters"),
    ("prefer_claude_code_in_cli", "Use Claude Code when run inside it"),
)

#: Shown but not editable here.
READ_ONLY = (
    ("Version", lambda s: config.APP_VERSION),
    ("Claude model", lambda s: s.claude_model),
    ("Unicode categories", lambda s: ", ".join(s.unicode_categories)),
    ("xFormat API", lambda s: s.xformat_base_url),
)

#: Attributes stored as integers, so a Select's string value is converted
#: back before it is saved.
_INTEGERS = {"crawl_depth", "max_pages"}


class SettingsScreen(XScreen):
    """View and change the configuration."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("s", "save", "Save"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.settings = config.Settings.load()

    def compose(self) -> ComposeResult:
        yield from self.compose_chrome()
        with Vertical(id="settings-view"):
            yield Label("Settings", classes="menu-title")
            with VerticalScroll():
                for attribute, label, options in CHOICES:
                    yield Label(f"{label}:")
                    yield Select(list(options), value=self._current(attribute),
                                 id=f"set-{attribute}", allow_blank=False)
                for attribute, label in FLAGS:
                    yield Checkbox(label, value=getattr(self.settings,
                                                        attribute, False),
                                   id=f"flag-{attribute}")
                yield Static("")
                yield DataTable(id="settings-table")
            yield Static("")
            with Horizontal():
                yield Button("Save", id="save", variant="primary")
                yield Button("Reload", id="reload")
                yield Button("Back", id="back")
            yield Label("", id="settings-status")
            yield Label(f"Config file: {config.CONFIG_FILE}", id="config-path")

    def _current(self, attribute: str) -> str:
        return str(getattr(self.settings, attribute, ""))

    def on_mount(self) -> None:
        table = self.query_one("#settings-table", DataTable)
        table.add_columns("Setting", "Value")
        self._fill_read_only()

    def _fill_read_only(self) -> None:
        table = self.query_one("#settings-table", DataTable)
        table.clear()
        for label, read in READ_ONLY:
            table.add_row(label, str(read(self.settings)))

    def action_save(self) -> None:
        changed = []
        for attribute, label, _options in CHOICES:
            value = self.query_one(f"#set-{attribute}", Select).value
            if attribute in _INTEGERS:
                value = int(value or 0)
            if getattr(self.settings, attribute, None) != value:
                setattr(self.settings, attribute, value)
                changed.append(label)
        for attribute, label in FLAGS:
            value = self.query_one(f"#flag-{attribute}", Checkbox).value
            if getattr(self.settings, attribute, None) != value:
                setattr(self.settings, attribute, value)
                changed.append(label)
        status = self.query_one("#settings-status", Label)
        if not changed:
            status.update("Nothing changed.")
            return
        try:
            self.settings.save()
        except OSError as exc:
            status.update(f"Could not save: {exc}")
            return
        status.update(f"Saved: {', '.join(changed)}.")
        status.set_class(True, "ok")
        self._fill_read_only()

    def action_reload(self) -> None:
        self.settings = config.Settings.load()
        for attribute, _label, _options in CHOICES:
            self.query_one(f"#set-{attribute}", Select).value = \
                self._current(attribute)
        for attribute, _label in FLAGS:
            self.query_one(f"#flag-{attribute}", Checkbox).value = \
                bool(getattr(self.settings, attribute, False))
        self._fill_read_only()
        status = self.query_one("#settings-status", Label)
        status.set_class(False, "ok")
        status.update("Reloaded from disk.")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.action_back()
        elif event.button.id == "save":
            self.action_save()
        elif event.button.id == "reload":
            self.action_reload()
