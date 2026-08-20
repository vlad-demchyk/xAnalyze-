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
    QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from analysis_modes import (
    CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS, SOURCE_FILE,
    SOURCE_REPO, SOURCE_SITE,
)
from i18n.translations import t
from ui.design_system import TOKENS as T


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

    def __init__(self, lang: str = "uk", parent=None):
        super().__init__(parent)
        self.lang = lang
        self.setProperty("class", "sidebar")
        self.setFixedWidth(T.sidebar_width)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(T.space_3, T.space_4, T.space_3, T.space_4)
        layout.setSpacing(T.space_2)

        # -- Logo area --
        self._add_header(layout)

        # -- Source selection --
        self._add_section_title(layout, t("mode_label", lang))
        self._add_source_buttons(layout)

        layout.addSpacing(T.space_4)

        # -- Target input --
        self._add_target_input(layout)

        layout.addSpacing(T.space_4)

        # -- Filters --
        self._add_section_title(layout, t("checks_label", lang))
        self._add_check_filters(layout)

        layout.addSpacing(T.space_2)

        # -- Depth (for web) --
        self._add_depth_control(layout)

        layout.addStretch(1)

        # -- Analyze button --
        self._add_analyze_button(layout)

    def _add_header(self, layout: QVBoxLayout):
        """App title."""
        title = QLabel("XAnalyze")
        title.setProperty("class", "heading-lg")
        layout.addWidget(title)
        layout.addSpacing(T.space_4)

    def _add_section_title(self, layout: QVBoxLayout, text: str):
        label = QLabel(text)
        label.setProperty("class", "sidebar-title")
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
            btn.clicked.connect(lambda checked, s=source: self._on_source_clicked(s))
            self.source_buttons[source] = btn
            layout.addWidget(btn)
        self.source_buttons[SOURCE_SITE].setChecked(True)

    def _add_target_input(self, layout: QVBoxLayout):
        # URL input (for site)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(t("url_placeholder", self.lang))
        self.url_input.setProperty("class", "search")
        self.url_input.returnPressed.connect(self.analyze_clicked)
        layout.addWidget(self.url_input)

        # Repo path input (for repo) - with browse button
        self.repo_container = QWidget()
        repo_layout = QHBoxLayout(self.repo_container)
        repo_layout.setContentsMargins(0, 0, 0, 0)
        repo_layout.setSpacing(T.space_2)
        self.repo_input = QLineEdit()
        self.repo_input.setPlaceholderText(t("repo_path_placeholder", self.lang))
        self.repo_input.setProperty("class", "search")
        repo_layout.addWidget(self.repo_input, stretch=1)
        self.repo_browse = QPushButton("...")
        self.repo_browse.setFixedSize(36, 36)
        self.repo_browse.setToolTip("Browse for folder")
        self.repo_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.repo_browse.clicked.connect(self._browse_folder)
        repo_layout.addWidget(self.repo_browse)
        self.repo_container.setVisible(False)
        layout.addWidget(self.repo_container)

        # File path input (for file) - with browse button
        self.file_container = QWidget()
        file_layout = QHBoxLayout(self.file_container)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_layout.setSpacing(T.space_2)
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText(t("file_path_placeholder", self.lang))
        self.file_input.setProperty("class", "search")
        file_layout.addWidget(self.file_input, stretch=1)
        self.file_browse = QPushButton("...")
        self.file_browse.setFixedSize(36, 36)
        self.file_browse.setToolTip("Browse for HTML file")
        self.file_browse.setCursor(Qt.CursorShape.PointingHandCursor)
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
        label.setProperty("class", "muted")
        depth_layout.addWidget(label)

        self.depth_spin = QSpinBox()
        self.depth_spin.setRange(0, 5)
        self.depth_spin.setValue(1)
        self.depth_spin.setFixedWidth(60)
        depth_layout.addWidget(self.depth_spin)
        depth_layout.addStretch(1)

        layout.addWidget(self.depth_container)

    def _add_analyze_button(self, layout: QVBoxLayout):
        self.analyze_btn = QPushButton(t("analyze_button", self.lang))
        self.analyze_btn.setProperty("class", "primary")
        self.analyze_btn.setDefault(True)
        self.analyze_btn.clicked.connect(self.analyze_clicked)
        self.analyze_btn.setFixedHeight(40)
        layout.addWidget(self.analyze_btn)

        self.cancel_btn = QPushButton(t("cancel_button", self.lang))
        self.cancel_btn.setProperty("class", "ghost")
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

    def set_busy(self, busy: bool):
        self.analyze_btn.setVisible(not busy)
        self.cancel_btn.setVisible(busy)
        self.analyze_btn.setEnabled(not busy)

    def retranslate(self, lang: str):
        self.lang = lang
        self.analyze_btn.setText(t("analyze_button", lang))
        self.cancel_btn.setText(t("cancel_button", lang))
