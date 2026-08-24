"""Settings dialog: UI language, rewrite provider, and credentials.

This exists mainly to keep the main window's toolbar short. Everything you
set once and rarely change (language, which account pays for rewrites, API
keys, endpoint mapping) lives here; the toolbar keeps only what you touch
on every scan (source, target, detector, Analyze).
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit, QPushButton,
    QScrollArea, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

import cli_install
import config
import suppression
from i18n.translations import LANGUAGES, t
from llm import credentials
from llm.base import LLMAuthError, LLMProviderFactory, LLMUnavailable
from ui import theme

PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_XFORMAT = "xformat"

#: The five suppression levels, as translation keys rather than as English
#: strings. They were hardcoded English with a comment saying the
#: translations file belonged to someone else at the time - which left one
#: tab of a translated dialog in a language the user had not chosen.
_SUPPRESSION_LEVELS = (
    ("fingerprints", "suppression_fingerprints"),
    ("phrases", "suppression_phrases"),
    ("rules", "suppression_rules"),
    ("paths", "suppression_paths"),
    ("selectors", "suppression_selectors"),
)


def _select_data(combo, value) -> None:
    """Select the entry whose `userData` is `value`, if there is one.

    Falls back to leaving the current index alone rather than to index 0: a
    settings file holding a model this build does not offer should show as
    unrecognised, not be silently rewritten to the first item on save.
    """
    index = combo.findData(value)
    if index >= 0:
        combo.setCurrentIndex(index)


class SettingsDialog(QDialog):
    def __init__(self, settings: config.Settings, lang: str, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.lang = lang
        self._xformat_provider = None
        # Used for the handful of things QSS class selectors don't reach
        # here: the status colours (success/error are semantic, not literal
        # hex codes chosen to match one theme) and one indent.
        self._palette = theme.current_palette(settings.theme)

        self.setWindowTitle(t("settings_title", lang))
        self.resize(600, 520)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), t("settings_tab_general", lang))
        tabs.addTab(self._build_unicode_tab(), t("settings_tab_unicode", lang))
        tabs.addTab(self._build_provider_tab(), t("settings_tab_provider", lang))
        tabs.addTab(self._build_suppression_tab(), "Suppression")
        tabs.addTab(self._build_advanced_tab(), t("settings_tab_advanced", lang))
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._refresh_provider_ui()

    # ------------------------------------------------------------- tabs

    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.lang_combo = QComboBox()
        for code, name in LANGUAGES.items():
            self.lang_combo.addItem(name, userData=code)
        idx = self.lang_combo.findData(self.settings.ui_language)
        self.lang_combo.setCurrentIndex(max(idx, 0))
        form.addRow(t("ui_language_label_full", self.lang), self.lang_combo)

        self.theme_combo = QComboBox()
        for value in ("auto", "light", "dark"):
            self.theme_combo.addItem(t(f"theme_{value}", self.lang), userData=value)
        idx = self.theme_combo.findData(self.settings.theme)
        self.theme_combo.setCurrentIndex(max(idx, 0))
        # Applied as it changes rather than on OK: a colour scheme is judged
        # by looking at it, and a preview that needs a dialog round-trip is
        # not a preview.
        self.theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        form.addRow(t("theme_label", self.lang), self.theme_combo)

        self.max_pages_spin = QSpinBox()
        self.max_pages_spin.setRange(1, 500)
        self.max_pages_spin.setValue(self.settings.max_pages)
        form.addRow(t("settings_max_pages", self.lang), self.max_pages_spin)

        return w

    def _on_theme_changed(self) -> None:
        from PySide6.QtWidgets import QApplication
        from ui import theme

        app = QApplication.instance()
        if app is None:
            return
        palette = theme.apply_theme(app, self.theme_combo.currentData() or "auto")
        # The findings list is painted by a delegate holding its own copy of
        # the palette, so it has to be handed the new one — a style sheet
        # alone would leave the badges in the previous theme's colours.
        window = self.parent()
        if window is not None and hasattr(window, "apply_palette"):
            window.apply_palette(palette)

    def _build_unicode_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self.unicode_enabled_box = QCheckBox(t("settings_unicode_enabled", self.lang))
        self.unicode_enabled_box.setChecked(self.settings.unicode_check_enabled)
        layout.addWidget(self.unicode_enabled_box)

        note = QLabel(t("settings_unicode_note", self.lang))
        note.setWordWrap(True)
        note.setProperty("class", theme.CLASS_MUTED)
        layout.addWidget(note)

        active = set(self.settings.unicode_categories or [])
        self.category_boxes: dict[str, QCheckBox] = {}
        group = QGroupBox("")
        group_layout = QVBoxLayout(group)
        for key in ("invisible", "space", "homoglyph", "styled", "typography"):
            box = QCheckBox(t(f"settings_cat_{key}", self.lang))
            box.setChecked(key in active)
            self.category_boxes[key] = box
            group_layout.addWidget(box)
            if key == "typography":
                sub = QLabel(t("settings_cat_typography_note", self.lang))
                sub.setWordWrap(True)
                sub.setProperty("class", theme.CLASS_MUTED)
                sub.setStyleSheet(f"margin-left: {self._palette.space_lg + self._palette.space_sm}px;")
                group_layout.addWidget(sub)
        layout.addWidget(group)

        self.unicode_enabled_box.toggled.connect(group.setEnabled)
        group.setEnabled(self.unicode_enabled_box.isChecked())

        layout.addStretch(1)
        return w

    def _build_provider_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        self.provider_combo = QComboBox()
        for name in LLMProviderFactory.available():
            try:
                label = LLMProviderFactory.create(name).display_name
            except Exception:  # noqa: BLE001
                label = name
            self.provider_combo.addItem(label, userData=name)
        idx = self.provider_combo.findData(self.settings.llm_provider)
        self.provider_combo.setCurrentIndex(max(idx, 0))
        self.provider_combo.currentIndexChanged.connect(self._refresh_provider_ui)

        top_form = QFormLayout()
        top_form.addRow(t("settings_provider", self.lang), self.provider_combo)
        layout.addLayout(top_form)

        note = QLabel(t("settings_provider_note", self.lang))
        note.setWordWrap(True)
        note.setProperty("class", theme.CLASS_MUTED)
        layout.addWidget(note)

        # --- Anthropic group ---
        self.anthropic_group = QGroupBox("Anthropic")
        a_form = QFormLayout(self.anthropic_group)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        existing = config.get_anthropic_api_key()
        if existing:
            self.api_key_edit.setPlaceholderText("•••• " + existing[-4:])
        a_form.addRow(t("settings_api_key", self.lang), self.api_key_edit)
        self.model_edit = QLineEdit(self.settings.claude_model)
        a_form.addRow(t("settings_model", self.lang), self.model_edit)
        layout.addWidget(self.anthropic_group)

        # --- Claude Code group ---
        # Its own box, because it is a different account from the one above:
        # this is the session already signed in on this machine, and what it
        # costs is a setting rather than a detail - the AI pass runs over
        # every block on a site. `sonnet` at `low` effort is enough for the
        # job, which classifies short passages against a fixed rubric.
        self.claude_code_group = QGroupBox("Claude Code")
        cc_form = QFormLayout(self.claude_code_group)
        self.cc_model_combo = QComboBox()
        for label, value in (("—", ""), ("sonnet", "sonnet"),
                             ("opus", "opus"), ("haiku", "haiku")):
            self.cc_model_combo.addItem(label, userData=value)
        _select_data(self.cc_model_combo, self.settings.claude_code_model)
        cc_form.addRow(t("settings_cc_model", self.lang), self.cc_model_combo)
        self.cc_effort_combo = QComboBox()
        for label, value in (("—", ""), ("low", "low"),
                             ("medium", "medium"), ("high", "high")):
            self.cc_effort_combo.addItem(label, userData=value)
        _select_data(self.cc_effort_combo, self.settings.claude_code_effort)
        cc_form.addRow(t("settings_cc_effort", self.lang), self.cc_effort_combo)
        layout.addWidget(self.claude_code_group)

        # --- xformat group ---
        self.xformat_group = QGroupBox("app.xformat.net")
        x_layout = QVBoxLayout(self.xformat_group)
        x_form = QFormLayout()
        self.xformat_url_edit = QLineEdit(self.settings.xformat_base_url)
        x_form.addRow(t("settings_base_url", self.lang), self.xformat_url_edit)
        self.xformat_email_edit = QLineEdit(credentials.load_secret("xformat_account_email") or "")
        x_form.addRow(t("settings_email", self.lang), self.xformat_email_edit)
        self.xformat_password_edit = QLineEdit()
        self.xformat_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.xformat_password_edit.setPlaceholderText(t("settings_password_hint", self.lang))
        x_form.addRow(t("settings_password", self.lang), self.xformat_password_edit)
        x_layout.addLayout(x_form)

        btn_row = QHBoxLayout()
        self.sign_in_btn = QPushButton(t("settings_sign_in", self.lang))
        self.sign_in_btn.clicked.connect(self._on_sign_in)
        self.sign_out_btn = QPushButton(t("settings_sign_out", self.lang))
        self.sign_out_btn.clicked.connect(self._on_sign_out)
        self.check_btn = QPushButton(t("settings_check", self.lang))
        self.check_btn.clicked.connect(self._on_check_status)
        for b in (self.sign_in_btn, self.sign_out_btn, self.check_btn):
            btn_row.addWidget(b)
        x_layout.addLayout(btn_row)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        x_layout.addWidget(self.status_label)

        self.storage_label = QLabel(
            t("settings_storage_keyring", self.lang) if credentials.using_keyring()
            else t("settings_storage_file", self.lang)
        )
        self.storage_label.setWordWrap(True)
        self.storage_label.setProperty("class", theme.CLASS_MUTED)
        x_layout.addWidget(self.storage_label)

        layout.addWidget(self.xformat_group)
        layout.addStretch(1)
        return w

    def _build_suppression_tab(self) -> QWidget:
        """What is already being ignored, by level, with a way to undo it.

        Edits only the personal list (`Settings.ignore`) — the project's own
        `.xanalyze-ignore` is a file meant to be committed and reviewed like
        any other, not rewritten from a settings dialog on someone's machine.
        It is still shown, read-only, so "what is suppressed" is one honest
        answer instead of half of it.
        """
        # Five list-plus-add-row groups, one per level, add up to well over
        # this dialog's usual height - every other tab fits inside the
        # window's original 520px and this one blew straight past it, which
        # made switching to this tab visibly resize the whole dialog. Scrolled
        # rather than shrunk: every level is still worth seeing at a glance,
        # just not all five glued together outside a scroll area.
        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer_layout.addWidget(scroll)

        w = QWidget()
        scroll.setWidget(w)
        layout = QVBoxLayout(w)
        note = QLabel(t("suppression_note", self.lang))
        note.setWordWrap(True)
        note.setProperty("class", theme.CLASS_MUTED)
        layout.addWidget(note)

        own = suppression.Suppressions.from_dict(self.settings.ignore)
        self._suppression_lists: dict[str, QListWidget] = {}
        for key, label_key in _SUPPRESSION_LEVELS:
            group = QGroupBox(t(label_key, self.lang))
            group.setToolTip(t(f"{label_key}_hint", self.lang))
            group_layout = QVBoxLayout(group)

            listbox = QListWidget()
            listbox.addItems(getattr(own, key))
            listbox.setMaximumHeight(90)
            self._suppression_lists[key] = listbox
            group_layout.addWidget(listbox)

            row = QHBoxLayout()
            entry = QComboBox() if key == "rules" else QLineEdit()
            if isinstance(entry, QComboBox):
                entry.setEditable(True)
                for category, ids in suppression.known_rule_ids().items():
                    for rule_id in ids:
                        entry.addItem(f"{rule_id}  ({category})", userData=rule_id)
                entry.setCurrentIndex(-1)
                entry.lineEdit().setPlaceholderText(
                    t("suppression_rule_placeholder", self.lang))
            else:
                entry.setPlaceholderText(t("suppression_add_placeholder",
                                           self.lang))
            add_btn = QPushButton(t("suppression_add", self.lang))
            remove_btn = QPushButton(t("suppression_remove", self.lang))
            row.addWidget(entry, stretch=1)
            row.addWidget(add_btn)
            row.addWidget(remove_btn)
            group_layout.addLayout(row)

            def make_add(listbox=listbox, entry=entry):
                def add() -> None:
                    if isinstance(entry, QComboBox):
                        value = (entry.currentData() or entry.currentText()).strip()
                    else:
                        value = entry.text().strip()
                    if not value:
                        return
                    existing = [listbox.item(i).text() for i in range(listbox.count())]
                    if value not in existing:
                        listbox.addItem(value)
                    if isinstance(entry, QComboBox):
                        entry.setCurrentIndex(-1)
                        entry.clearEditText()
                    else:
                        entry.clear()
                return add

            def make_remove(listbox=listbox):
                def remove() -> None:
                    for item in listbox.selectedItems():
                        listbox.takeItem(listbox.row(item))
                return remove

            add_btn.clicked.connect(make_add())
            remove_btn.clicked.connect(make_remove())
            layout.addWidget(group)

        layout.addWidget(self._build_project_suppression_view())
        layout.addStretch(1)
        return outer

    def _project_ignore_root(self) -> str | None:
        """The folder whose `.xanalyze-ignore` is worth showing, if the
        window this dialog was opened from has one at the moment."""
        window = self.parent()
        for attr in ("repo_path_edit", "file_path_edit"):
            edit = getattr(window, attr, None)
            if edit is not None and edit.text().strip():
                return edit.text().strip()
        return None

    def _build_project_suppression_view(self) -> QWidget:
        from pathlib import Path

        group = QGroupBox("Project (.xanalyze-ignore) — read-only here")
        layout = QVBoxLayout(group)
        root = self._project_ignore_root()
        path = None
        if root:
            candidate = Path(root)
            if candidate.is_file():
                candidate = candidate.parent
            candidate = candidate / suppression.IGNORE_FILENAME
            if candidate.is_file():
                path = candidate

        if path is None:
            label = QLabel(
                "No .xanalyze-ignore file for the current source, or none "
                "chosen yet."
            )
            label.setWordWrap(True)
            label.setProperty("class", theme.CLASS_MUTED)
            layout.addWidget(label)
            return group

        project = suppression.Suppressions.parse(path.read_text(encoding="utf-8"))
        summary = ", ".join(
            f"{t(label_key, self.lang).lower()}: {len(getattr(project, key))}"
            for key, label_key in _SUPPRESSION_LEVELS
            if getattr(project, key)
        ) or t("suppression_empty", self.lang)
        label = QLabel(f"{path}\n{summary}")
        label.setWordWrap(True)
        layout.addWidget(label)
        return group

    def _build_advanced_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        note = QLabel(t("settings_endpoints_note", self.lang))
        note.setWordWrap(True)
        note.setProperty("class", theme.CLASS_MUTED)
        layout.addWidget(note)

        self.endpoints_edit = QPlainTextEdit()
        self.endpoints_edit.setPlainText(
            json.dumps(self.settings.xformat_endpoints or {}, indent=2, ensure_ascii=False)
        )
        mono = self.endpoints_edit.font()
        mono.setFamily("monospace")
        self.endpoints_edit.setFont(mono)
        layout.addWidget(self.endpoints_edit, stretch=1)

        defaults_btn = QPushButton(t("settings_show_defaults", self.lang))
        defaults_btn.clicked.connect(self._show_endpoint_defaults)
        layout.addWidget(defaults_btn)

        # Plain English, not routed through `i18n.translations.t()` — same
        # rule the Suppression tab follows above: this is a small, technical,
        # macOS-only action, not part of the shared vocabulary.
        cli_group = QGroupBox("Command line")
        cli_layout = QVBoxLayout(cli_group)
        self.cli_status_label = QLabel()
        self.cli_status_label.setWordWrap(True)
        self.cli_status_label.setProperty("class", theme.CLASS_MUTED)
        cli_layout.addWidget(self.cli_status_label)
        self.cli_install_btn = QPushButton()
        self.cli_install_btn.clicked.connect(self._on_cli_install_clicked)
        cli_layout.addWidget(self.cli_install_btn)
        layout.addWidget(cli_group)
        self._refresh_cli_status()

        return w

    # ---------------------------------------------------------- behaviour

    def _refresh_provider_ui(self) -> None:
        is_xformat = self.provider_combo.currentData() == PROVIDER_XFORMAT
        self.xformat_group.setEnabled(is_xformat)
        self.anthropic_group.setEnabled(not is_xformat)

    def _build_xformat_provider(self):
        endpoints = self._parse_endpoints(silent=True)
        return LLMProviderFactory.create(
            PROVIDER_XFORMAT,
            base_url=self.xformat_url_edit.text().strip() or self.settings.xformat_base_url,
            endpoints=endpoints,
        )

    def _on_sign_in(self) -> None:
        email = self.xformat_email_edit.text().strip()
        password = self.xformat_password_edit.text()
        if not email or not password:
            self._set_status(t("settings_need_credentials", self.lang), ok=False)
            return
        provider = self._build_xformat_provider()
        try:
            status = provider.sign_in(email, password)
        except (LLMAuthError, LLMUnavailable) as exc:
            self._set_status(str(exc), ok=False)
            return
        # The password is not kept anywhere — only the returned tokens are.
        self.xformat_password_edit.clear()
        self._report_status(status)

    def _on_sign_out(self) -> None:
        provider = self._build_xformat_provider()
        provider.sign_out()
        self._set_status(t("settings_signed_out", self.lang), ok=True)

    def _on_check_status(self) -> None:
        provider = self._build_xformat_provider()
        try:
            self._report_status(provider.auth_status())
        except (LLMAuthError, LLMUnavailable) as exc:
            self._set_status(str(exc), ok=False)

    def _report_status(self, status) -> None:
        if not status.signed_in:
            self._set_status(t("settings_not_signed_in", self.lang, detail=status.detail), ok=False)
            return
        text = t("settings_signed_in", self.lang, detail=status.detail)
        if status.quota_remaining is not None:
            text += " · " + t("settings_quota", self.lang, n=status.quota_remaining)
        self._set_status(text, ok=True)

    def _set_status(self, text: str, ok: bool) -> None:
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"color: {self._palette.success_text};" if ok
            else f"color: {self._palette.error_text};")

    def _parse_endpoints(self, silent: bool = False) -> dict:
        raw = self.endpoints_edit.toPlainText().strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("expected a JSON object")
            return data
        except (json.JSONDecodeError, ValueError) as exc:
            if not silent:
                QMessageBox.warning(self, "", t("settings_bad_json", self.lang, error=str(exc)))
            return {}

    def _show_endpoint_defaults(self) -> None:
        from dataclasses import asdict
        from llm.xformat_provider import XFormatEndpoints
        QMessageBox.information(
            self, "", json.dumps(asdict(XFormatEndpoints()), indent=2, ensure_ascii=False)
        )

    def _refresh_cli_status(self) -> None:
        """Reflects reality rather than assuming it: re-reads the actual
        symlink state every time, so a change made from a terminal (or a
        previous install this same session) is never shown stale."""
        bundled = cli_install.bundled_cli_path()
        if bundled is None:
            self.cli_status_label.setText(
                "Only available in the packaged macOS app, not this development run.")
            self.cli_install_btn.setEnabled(False)
            self.cli_install_btn.setText("Install 'xanalyze' command")
            return

        self.cli_install_btn.setEnabled(True)
        target = cli_install.installed_target()
        if target is None:
            self.cli_status_label.setText(
                "Not installed. Adds 'xanalyze' to your PATH, so you can run scans "
                "and audits from a terminal without opening this window.")
            self.cli_install_btn.setText("Install 'xanalyze' command")
            return

        path_note = "" if cli_install.is_dir_on_path(cli_install.USER_BIN_DIR) else (
            f" Note: {cli_install.USER_BIN_DIR} does not appear to be on your PATH — "
            "add it in your shell's startup file to use the command.")
        self.cli_status_label.setText(
            f"Installed at {cli_install.USER_BIN_DIR / cli_install.CLI_NAME}.{path_note}")
        self.cli_install_btn.setText("Remove 'xanalyze' command")

    def _on_cli_install_clicked(self) -> None:
        try:
            if cli_install.installed_target() is not None:
                cli_install.uninstall()
            else:
                cli_install.install()
        except cli_install.CliInstallError as exc:
            QMessageBox.warning(self, "", str(exc))
            return
        self._refresh_cli_status()

    def _on_accept(self) -> None:
        raw = self.endpoints_edit.toPlainText().strip()
        if raw:
            try:
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    raise ValueError("expected a JSON object")
            except (json.JSONDecodeError, ValueError) as exc:
                QMessageBox.warning(self, "", t("settings_bad_json", self.lang, error=str(exc)))
                return
            self.settings.xformat_endpoints = parsed
        else:
            self.settings.xformat_endpoints = {}

        self.settings.ui_language = self.lang_combo.currentData()
        self.settings.theme = self.theme_combo.currentData() or "auto"
        self.settings.max_pages = self.max_pages_spin.value()
        self.settings.unicode_check_enabled = self.unicode_enabled_box.isChecked()
        self.settings.unicode_categories = [
            key for key, box in self.category_boxes.items() if box.isChecked()
        ]
        self.settings.ignore = {
            key: [listbox.item(i).text() for i in range(listbox.count())]
            for key, listbox in self._suppression_lists.items()
        }

        self.settings.llm_provider = self.provider_combo.currentData()
        self.settings.claude_model = self.model_edit.text().strip() or self.settings.claude_model
        # Empty is a real answer here - "whatever the session is set to" -
        # so these are read straight rather than falling back to the old
        # value the way the free-text model field above has to.
        self.settings.claude_code_model = self.cc_model_combo.currentData() or ""
        self.settings.claude_code_effort = self.cc_effort_combo.currentData() or ""
        self.settings.xformat_base_url = self.xformat_url_edit.text().strip() or self.settings.xformat_base_url

        typed_key = self.api_key_edit.text().strip()
        if typed_key:
            config.set_anthropic_api_key(typed_key)

        self.settings.save()
        self.accept()
