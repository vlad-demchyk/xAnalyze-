"""Modern UI entry point for testing the redesign.

Usage: python main_modern.py

This is a standalone window that demonstrates the new design system
with sidebar navigation, dark theme, and modern layout.
It does NOT replace main.py yet - it's for visual testing.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QMainWindow, QSplitter,
    QVBoxLayout, QWidget, QListWidget, QListWidgetItem,
    QLabel, QPlainTextEdit, QSizePolicy,
)

import config
from ui.design_system import TOKENS as T
from ui.modern_theme import build_modern_qss
from ui.sidebar import Sidebar


class FindingsList(QWidget):
    """Findings list with severity grouping."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setProperty("class", "panel-header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(T.space_4, T.space_3, T.space_4, T.space_3)
        self.title = QLabel("Findings")
        self.title.setProperty("class", "panel-title")
        header_layout.addWidget(self.title)
        header_layout.addStretch(1)
        self.count_label = QLabel("0")
        self.count_label.setProperty("class", "muted")
        header_layout.addWidget(self.count_label)
        layout.addWidget(header)

        # List
        self.list = QListWidget()
        self.list.setProperty("class", "findings-list")
        layout.addWidget(self.list)

    def add_finding(self, severity: str, text: str, source: str = ""):
        item = QListWidgetItem()
        item.setText(f"[{severity.upper()}] {text}")
        item.setData(Qt.ItemDataRole.UserRole, (severity, text, source))
        self.list.addItem(item)
        self.count_label.setText(str(self.list.count()))


class DetailPanel(QWidget):
    """Detail panel for selected finding."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(T.space_4, T.space_4, T.space_4, T.space_4)
        layout.setSpacing(T.space_3)

        # Placeholder
        self.placeholder = QLabel("Select a finding to see details")
        self.placeholder.setProperty("class", "empty-body")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.placeholder)

        # Detail content (hidden initially)
        self.detail_widget = QWidget()
        detail_layout = QVBoxLayout(self.detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(T.space_3)

        self.severity_badge = QLabel()
        self.severity_badge.setProperty("class", "badge-high")
        detail_layout.addWidget(self.severity_badge)

        self.title_label = QLabel()
        self.title_label.setProperty("class", "heading")
        self.title_label.setWordWrap(True)
        detail_layout.addWidget(self.title_label)

        self.source_label = QLabel()
        self.source_label.setProperty("class", "muted")
        detail_layout.addWidget(self.source_label)

        self.description = QLabel()
        self.description.setWordWrap(True)
        self.description.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        detail_layout.addWidget(self.description)

        detail_layout.addStretch(1)
        self.detail_widget.setVisible(False)
        layout.addWidget(self.detail_widget)

    def show_finding(self, severity: str, text: str, source: str = ""):
        self.placeholder.setVisible(False)
        self.detail_widget.setVisible(True)
        self.severity_badge.setText(severity.upper())
        self.severity_badge.setProperty("class", f"badge-{severity}")
        self.severity_badge.style().unpolish(self.severity_badge)
        self.severity_badge.style().polish(self.severity_badge)
        self.title_label.setText(text)
        self.source_label.setText(source or "No source")


class PreviewPanel(QWidget):
    """Preview panel for page/code view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setProperty("class", "panel-header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(T.space_4, T.space_3, T.space_4, T.space_3)
        title = QLabel("Preview")
        title.setProperty("class", "panel-title")
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        layout.addWidget(header)

        # Content
        self.content = QPlainTextEdit()
        self.content.setReadOnly(True)
        self.content.setPlaceholderText("Page preview will appear here...")
        layout.addWidget(self.content)


class ModernMainWindow(QMainWindow):
    """Modern redesign of the main window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("XAnalyze")
        self.resize(1400, 900)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar(lang="uk")
        self.sidebar.analyze_clicked.connect(self._on_analyze)
        root.addWidget(self.sidebar)

        # Main content area
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(T.space_4, T.space_4, T.space_4, T.space_4)
        content_layout.setSpacing(T.space_3)

        # Splitter: findings + detail/preview
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Findings list
        self.findings = FindingsList()
        self.findings.list.itemClicked.connect(self._on_finding_clicked)
        self.splitter.addWidget(self.findings)

        # Right side: detail + preview stacked
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(T.space_3)

        self.detail = DetailPanel()
        right_layout.addWidget(self.detail)

        self.preview = PreviewPanel()
        right_layout.addWidget(self.preview)

        self.splitter.addWidget(right)
        self.splitter.setSizes([500, 500])

        content_layout.addWidget(self.splitter)
        root.addWidget(content)

        # Add some demo findings
        self._add_demo_findings()

    def _on_analyze(self):
        source = self.sidebar.get_source()
        target = self.sidebar.get_target()
        print(f"Analyzing: {source} -> {target}")

    def _on_finding_clicked(self, item: QListWidgetItem):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            severity, text, source = data
            self.detail.show_finding(severity, text, source)

    def _add_demo_findings(self):
        """Add demo findings to show the UI."""
        demos = [
            ("high", "Missing alt attribute on <img>", "index.html:42"),
            ("high", "Button has no accessible name", "index.html:108"),
            ("medium", "Heading order skipped (h1 -> h3)", "index.html:15"),
            ("medium", "Color contrast below 4.5:1", "style.css:89"),
            ("low", "Link text is vague ('click here')", "index.html:20"),
            ("low", "Positive tabindex value", "form.html:33"),
        ]
        for severity, text, source in demos:
            self.findings.add_finding(severity, text, source)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("XAnalyze")
    app.setStyleSheet(build_modern_qss())
    window = ModernMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
