"""Sidebar widget for XAnalyze.

Replaces the top toolbar with a left sidebar containing:
- Source selection (Site/Repo/File)
- Target input (URL/path)
- Filters (checks, severity)
- Analyze button
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from analysis_modes import (
    CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS, METHOD_AI, METHOD_EMBEDDING, METHOD_LOCAL,
    SOURCE_FILE, SOURCE_REPO, SOURCE_SITE,
)
from repo_scanner import SCOPE_BOTH, SCOPE_CONTENT, SCOPE_TECHNICAL
from i18n.translations import t
from ui.tokens import Palette
from ui.theme import current_palette

# Default palette for inline styling. Updated when theme changes.
T: Palette = current_palette("dark")


class SourceButton(QPushButton):
    """A radio-like button for source selection."""

    def __init__(self, text: str, source: str, parent=None):
        super().__init__(text, parent)
        self.source = source
        self.setCheckable(True)
        self.setProperty("class", "source-btn")
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class FilterChip(QPushButton):
    """A toggle chip for filters."""

    def __init__(self, text: str, value: str, parent=None):
        super().__init__(text, parent)
        self.value = value
        self.setCheckable(True)
        self.setProperty("class", "chip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class Sidebar(QWidget):
    """Left sidebar with source selection, target input, and filters."""

    source_changed = Signal(str)
    analyze_clicked = Signal()
    cancel_clicked = Signal()
    target_changed = Signal(str)
    depth_changed = Signal(int)
    checks_changed = Signal(tuple)
    method_changed = Signal(tuple)
    scope_changed = Signal(str)
    settings_clicked = Signal()
    account_clicked = Signal()

    def __init__(self, lang: str = "uk", parent=None):
        super().__init__(parent)
        self.lang = lang
        self.setFixedWidth(T.sidebar_width)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {T.bg_surface};
                border-right: 1px solid {T.border_strong};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(T.space_4, T.space_4, T.space_4, T.space_4)
        layout.setSpacing(T.space_2)

        self._add_header(layout)
        layout.addSpacing(T.space_4)
        self._add_section_title(layout, t("mode_label", lang))
        self._add_source_buttons(layout)
        layout.addSpacing(T.space_3)
        self._add_target_input(layout)
        layout.addSpacing(T.space_4)
        self._add_section_title(layout, t("checks_label", lang))
        self._add_check_filters(layout)
        layout.addSpacing(T.space_3)
        self._add_section_title(layout, t("method_label", lang))
        self._add_method_selection(layout)
        layout.addSpacing(T.space_3)
        self._add_depth_control(layout)
        layout.addSpacing(T.space_3)
        self._add_scope_combo(layout)
        layout.addStretch(1)
        self._add_account_info(layout)
        layout.addSpacing(T.space_3)
        self._add_settings_button(layout)
        layout.addSpacing(T.space_3)
        self._add_analyze_button(layout)

    def _add_header(self, layout: QVBoxLayout):
        """App title."""
        title = QLabel("XAnalyze")
        title.setStyleSheet(f"""
            QLabel {{
                color: {T.text_primary};
                font-size: {T.font_size_xl}px;
                font-weight: 700;
                letter-spacing: -0.5px;
            }}
        """)
        layout.addWidget(title)

    def _add_section_title(self, layout: QVBoxLayout, text: str):
        label = QLabel(text)
        label.setStyleSheet(f"""
            QLabel {{
                color: {T.text_secondary};
                font-size: {T.font_size_xs}px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: {T.space_1}px 0;
            }}
        """)
        layout.addWidget(label)

    def _add_source_buttons(self, layout: QVBoxLayout):
        self.source_buttons: dict[str, SourceButton] = {}
        sources = [
            (SOURCE_SITE, t("source_site", self.lang)),
            (SOURCE_REPO, t("source_repo", self.lang)),
            (SOURCE_FILE, t("source_file", self.lang)),
        ]
        for source, label in sources:
            btn = SourceButton(label, source)
            btn.setFixedHeight(32)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: none;
                    border-radius: {T.radius_md}px;
                    padding: 0 {T.space_3}px;
                    color: {T.text_secondary};
                    font-size: {T.font_size_sm}px;
                    text-align: left;
                }}
                QPushButton:hover {{
                    background-color: {T.bg_hover};
                    color: {T.text_primary};
                }}
                QPushButton:checked {{
                    background-color: {T.accent_muted};
                    color: {T.accent};
                    font-weight: 500;
                }}
            """)
            btn.clicked.connect(lambda checked, s=source: self._on_source_clicked(s))
            self.source_buttons[source] = btn
            layout.addWidget(btn)
        self.source_buttons[SOURCE_SITE].setChecked(True)

    def _add_target_input(self, layout: QVBoxLayout):
        # URL input (for site)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(t("url_placeholder", self.lang))
        self.url_input.setFixedHeight(34)
        self.url_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {T.bg_input};
                border: 1px solid {T.border_default};
                border-radius: {T.radius_md}px;
                padding: 0 {T.space_3}px;
                color: {T.text_primary};
                font-size: {T.font_size_sm}px;
            }}
            QLineEdit:focus {{
                border-color: {T.accent};
            }}
        """)
        self.url_input.returnPressed.connect(self.analyze_clicked)
        layout.addWidget(self.url_input)

        # Repo path (for repo) - input + browse
        self.repo_container = QWidget()
        repo_layout = QHBoxLayout(self.repo_container)
        repo_layout.setContentsMargins(0, 0, 0, 0)
        repo_layout.setSpacing(T.space_2)
        self.repo_input = QLineEdit()
        self.repo_input.setPlaceholderText("Path to folder...")
        self.repo_input.setFixedHeight(34)
        self.repo_input.setStyleSheet(self.url_input.styleSheet())
        repo_layout.addWidget(self.repo_input, stretch=1)
        self.repo_browse = QPushButton("Browse")
        self.repo_browse.setFixedHeight(34)
        self.repo_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.repo_browse.setStyleSheet(f"""
            QPushButton {{
                background-color: {T.bg_elevated};
                border: 1px solid {T.border_default};
                border-radius: {T.radius_md}px;
                padding: 0 {T.space_3}px;
                color: {T.text_secondary};
                font-size: {T.font_size_sm}px;
            }}
            QPushButton:hover {{
                background-color: {T.bg_hover};
                border-color: {T.text_secondary};
                color: {T.text_primary};
            }}
        """)
        self.repo_browse.clicked.connect(self._browse_folder)
        repo_layout.addWidget(self.repo_browse)
        self.repo_container.setVisible(False)
        layout.addWidget(self.repo_container)

        # File path (for file) - input + browse
        self.file_container = QWidget()
        file_layout = QHBoxLayout(self.file_container)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(T.space_2)
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Path to HTML file...")
        self.file_input.setFixedHeight(34)
        self.file_input.setStyleSheet(self.url_input.styleSheet())
        file_layout.addWidget(self.file_input, stretch=1)
        self.file_browse = QPushButton("Browse")
        self.file_browse.setFixedHeight(34)
        self.file_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.file_browse.setStyleSheet(self.repo_browse.styleSheet())
        self.file_browse.clicked.connect(self._browse_file)
        file_layout.addWidget(self.file_browse)
        self.file_container.setVisible(False)
        layout.addWidget(self.file_container)

    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select folder")
        if path:
            self.repo_input.setText(path)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select HTML file", "",
            "HTML (*.html *.htm *.xhtml);;All files (*)")
        if path:
            self.file_input.setText(path)

    def _add_check_filters(self, layout: QVBoxLayout):
        self.check_chips: dict[str, FilterChip] = {}
        checks = [
            (CHECK_AI_PATTERNS, t("check_ai_patterns", self.lang)),
            (CHECK_ACCESSIBILITY, t("check_accessibility", self.lang)),
        ]
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(T.space_2)
        for check, label in checks:
            chip = FilterChip(label, check)
            chip.setChecked(True)
            chip.setFixedHeight(28)
            chip.setStyleSheet(f"""
                QPushButton {{
                    background-color: {T.bg_elevated};
                    border: 1px solid {T.border_default};
                    border-radius: {T.radius_sm}px;
                    padding: 0 {T.space_2}px;
                    color: {T.text_secondary};
                    font-size: {T.font_size_xs}px;
                }}
                QPushButton:hover {{
                    background-color: {T.bg_hover};
                    border-color: {T.text_secondary};
                    color: {T.text_primary};
                }}
                QPushButton:checked {{
                    background-color: {T.accent_muted};
                    border-color: {T.accent};
                    color: {T.accent};
                }}
            """)
            chip.toggled.connect(self._on_check_toggled)
            self.check_chips[check] = chip
            row_layout.addWidget(chip)
        row_layout.addStretch(1)
        layout.addWidget(row)

    def _add_depth_control(self, layout: QVBoxLayout):
        self.depth_container = QWidget()
        depth_layout = QHBoxLayout(self.depth_container)
        depth_layout.setContentsMargins(0, 0, 0, 0)
        depth_layout.setSpacing(T.space_2)

        label = QLabel(t("depth_label", self.lang))
        label.setStyleSheet(f"color: {T.text_secondary}; font-size: {T.font_size_sm}px;")
        depth_layout.addWidget(label)

        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(0, 5)
        self.depth_spin.setValue(1)
        self.depth_spin.setFixedSize(56, 28)
        self.depth_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {T.bg_input};
                border: 1px solid {T.border_default};
                border-radius: {T.radius_sm}px;
                padding: 0 {T.space_2}px;
                color: {T.text_primary};
                font-size: {T.font_size_sm}px;
            }}
            QSpinBox:focus {{
                border-color: {T.accent};
            }}
        """)
        depth_layout.addWidget(self.depth_spin)
        depth_layout.addStretch(1)

        layout.addWidget(self.depth_container)

    def _add_scope_combo(self, layout: QVBoxLayout):
        self.scope_container = QWidget()
        scope_layout = QHBoxLayout(self.scope_container)
        scope_layout.setContentsMargins(0, 0, 0, 0)
        scope_layout.setSpacing(T.space_2)

        label = QLabel(t("scope_label", self.lang))
        label.setStyleSheet(f"color: {T.text_secondary}; font-size: {T.font_size_sm}px;")
        scope_layout.addWidget(label)

        self.scope_combo = QComboBox()
        self.scope_combo.setFixedHeight(28)
        self.scope_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {T.bg_input};
                border: 1px solid {T.border_default};
                border-radius: {T.radius_sm}px;
                padding: 0 {T.space_2}px;
                color: {T.text_primary};
                font-size: {T.font_size_sm}px;
            }}
            QComboBox:focus {{
                border-color: {T.accent};
            }}
        """)
        for value in (SCOPE_CONTENT, SCOPE_TECHNICAL, SCOPE_BOTH):
            self.scope_combo.addItem(t(f"scope_{value}", self.lang), userData=value)
        self.scope_combo.currentIndexChanged.connect(
            lambda: self.scope_changed.emit(self.scope_combo.currentData()))
        scope_layout.addWidget(self.scope_combo)
        scope_layout.addStretch(1)

        layout.addWidget(self.scope_container)

    def _add_method_selection(self, layout: QVBoxLayout):
        self.method_chips: dict[str, FilterChip] = {}
        methods = [
            (METHOD_LOCAL, t("method_local", self.lang)),
            (METHOD_EMBEDDING, t("method_embedding", self.lang)),
            (METHOD_AI, t("method_ai", self.lang)),
        ]
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(T.space_2)
        for method, label in methods:
            chip = FilterChip(label, method)
            chip.setFixedHeight(28)
            chip.setStyleSheet(f"""
                QPushButton {{
                    background-color: {T.bg_elevated};
                    border: 1px solid {T.border_default};
                    border-radius: {T.radius_sm}px;
                    padding: 0 {T.space_2}px;
                    color: {T.text_secondary};
                    font-size: {T.font_size_xs}px;
                }}
                QPushButton:hover {{
                    background-color: {T.bg_hover};
                    border-color: {T.text_secondary};
                    color: {T.text_primary};
                }}
                QPushButton:checked {{
                    background-color: {T.accent_muted};
                    border-color: {T.accent};
                    color: {T.accent};
                }}
            """)
            chip.toggled.connect(self._on_method_toggled)
            self.method_chips[method] = chip
            row_layout.addWidget(chip)
        # Local is default
        self.method_chips[METHOD_LOCAL].setChecked(True)
        row_layout.addStretch(1)
        layout.addWidget(row)

    def _add_account_info(self, layout: QVBoxLayout):
        self.account_widget = QWidget()
        account_layout = QHBoxLayout(self.account_widget)
        account_layout.setContentsMargins(0, 0, 0, 0)
        account_layout.setSpacing(T.space_2)

        self.account_label = QLabel("Not signed in")
        self.account_label.setStyleSheet(f"""
            QLabel {{
                color: {T.text_disabled};
                font-size: {T.font_size_xs}px;
            }}
        """)
        account_layout.addWidget(self.account_label, stretch=1)

        self.account_btn = QPushButton("Sign in")
        self.account_btn.setFixedHeight(24)
        self.account_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.account_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {T.accent};
                font-size: {T.font_size_xs}px;
            }}
            QPushButton:hover {{
                text-decoration: underline;
            }}
        """)
        self.account_btn.clicked.connect(self.account_clicked)
        account_layout.addWidget(self.account_btn)
        layout.addWidget(self.account_widget)

    def _add_settings_button(self, layout: QVBoxLayout):
        self.settings_btn = QPushButton(t("settings_button", self.lang))
        self.settings_btn.setFixedHeight(32)
        self.settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {T.border_default};
                border-radius: {T.radius_md}px;
                color: {T.text_secondary};
                font-size: {T.font_size_sm}px;
            }}
            QPushButton:hover {{
                background-color: {T.bg_hover};
                border-color: {T.text_secondary};
                color: {T.text_primary};
            }}
        """)
        self.settings_btn.clicked.connect(self.settings_clicked)
        layout.addWidget(self.settings_btn)

    def _add_analyze_button(self, layout: QVBoxLayout):
        self.analyze_btn = QPushButton(t("analyze_button", self.lang))
        self.analyze_btn.setFixedHeight(36)
        self.analyze_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.analyze_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T.accent_emphasis};
                border: none;
                border-radius: {T.radius_md}px;
                color: #ffffff;
                font-weight: 600;
                font-size: {T.font_size_sm}px;
            }}
            QPushButton:hover {{
                background-color: {T.accent};
            }}
            QPushButton:disabled {{
                background-color: {T.bg_active};
                color: {T.text_disabled};
            }}
        """)
        self.analyze_btn.setDefault(True)
        self.analyze_btn.clicked.connect(self.analyze_clicked)
        layout.addWidget(self.analyze_btn)

        self.cancel_btn = QPushButton(t("cancel_button", self.lang))
        self.cancel_btn.setFixedHeight(36)
        self.cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {T.border_default};
                border-radius: {T.radius_md}px;
                color: {T.text_secondary};
                font-size: {T.font_size_sm}px;
            }}
            QPushButton:hover {{
                background-color: {T.bg_hover};
                border-color: {T.text_secondary};
                color: {T.text_primary};
            }}
        """)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self.cancel_clicked)
        layout.addWidget(self.cancel_btn)

    def _on_source_clicked(self, source: str):
        for s, btn in self.source_buttons.items():
            btn.setChecked(s == source)
        self._update_target_visibility(source)
        self.source_changed.emit(source)

    def _update_target_visibility(self, source: str):
        self.url_input.setVisible(source == SOURCE_SITE)
        self.repo_container.setVisible(source == SOURCE_REPO)
        self.file_container.setVisible(source == SOURCE_FILE)
        self.depth_container.setVisible(source == SOURCE_SITE)

    def _on_check_toggled(self, _checked: bool):
        checks = tuple(
            check for check, chip in self.check_chips.items() if chip.isChecked()
        )
        self.checks_changed.emit(checks)

    def _on_method_toggled(self, _checked: bool):
        methods = tuple(
            method for method, chip in self.method_chips.items() if chip.isChecked()
        )
        self.method_changed.emit(methods)

    def get_source(self) -> str:
        for source, btn in self.source_buttons.items():
            if btn.isChecked():
                return source
        return SOURCE_SITE

    def get_target(self) -> str:
        source = self.get_source()
        if source == SOURCE_REPO:
            return self.repo_input.text().strip()
        if source == SOURCE_FILE:
            return self.file_input.text().strip()
        return self.url_input.text().strip()

    def get_depth(self) -> int:
        return self.depth_spin.value()

    def get_checks(self) -> tuple[str, ...]:
        return tuple(
            check for check, chip in self.check_chips.items() if chip.isChecked()
        )

    def get_methods(self) -> tuple[str, ...]:
        return tuple(
            method for method, chip in self.method_chips.items() if chip.isChecked()
        )

    def set_busy(self, busy: bool):
        self.analyze_btn.setVisible(not busy)
        self.cancel_btn.setVisible(busy)
        self.analyze_btn.setEnabled(not busy)

    def retranslate(self, lang: str):
        self.lang = lang
        self.analyze_btn.setText(t("analyze_button", lang))
        self.cancel_btn.setText(t("cancel_button", lang))
