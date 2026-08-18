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
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox,
    QTabWidget, QVBoxLayout, QWidget,
)

import config
from i18n.translations import LANGUAGES, t
from llm import credentials
from llm.base import LLMAuthError, LLMProviderFactory, LLMUnavailable

PROVIDER_ANTHROPIC = "anthropic"
PROVIDER_XFORMAT = "xformat"


class SettingsDialog(QDialog):
    def __init__(self, settings: config.Settings, lang: str, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.lang = lang
        self._xformat_provider = None

        self.setWindowTitle(t("settings_title", lang))
        self.resize(600, 520)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), t("settings_tab_general", lang))
        tabs.addTab(self._build_unicode_tab(), t("settings_tab_unicode", lang))
        tabs.addTab(self._build_provider_tab(), t("settings_tab_provider", lang))
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
        note.setStyleSheet("color:#888;")
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
                sub.setStyleSheet("color:#888; font-size: 11px; margin-left: 20px;")
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
        note.setStyleSheet("color:#888;")
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
        self.storage_label.setStyleSheet("color:#888; font-size: 11px;")
        x_layout.addWidget(self.storage_label)

        layout.addWidget(self.xformat_group)
        layout.addStretch(1)
        return w

    def _build_advanced_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        note = QLabel(t("settings_endpoints_note", self.lang))
        note.setWordWrap(True)
        note.setStyleSheet("color:#888;")
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
        self.status_label.setStyleSheet("color: #2e7d32;" if ok else "color: #c62828;")

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
        self.settings.llm_provider = self.provider_combo.currentData()
        self.settings.claude_model = self.model_edit.text().strip() or self.settings.claude_model
        self.settings.xformat_base_url = self.xformat_url_edit.text().strip() or self.settings.xformat_base_url

        typed_key = self.api_key_edit.text().strip()
        if typed_key:
            config.set_anthropic_api_key(typed_key)

        self.settings.save()
        self.accept()
