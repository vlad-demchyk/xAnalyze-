"""Modern UI entry point for testing the redesign.

Usage: python main_modern.py
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QMainWindow, QPushButton,
    QSplitter, QVBoxLayout, QWidget, QListWidget, QListWidgetItem,
    QLabel, QPlainTextEdit, QSizePolicy, QStackedWidget,
)

import config
from ui.design_system import TOKENS as T
from ui.modern_theme import build_modern_qss
from ui.sidebar import Sidebar


class SeverityBadge(QLabel):
    """Styled severity badge - colored pill, not plain text."""

    STYLES = {
        "critical": (T.critical, "#ffffff"),
        "high": (T.high, "#ffffff"),
        "medium": (T.medium, "#000000"),
        "low": (T.bg_active, T.text_secondary),
    }

    def __init__(self, severity: str, parent=None):
        super().__init__(parent)
        self.set_severity(severity)

    def set_severity(self, severity: str):
        bg, fg = self.STYLES.get(severity, self.STYLES["low"])
        self.setText(severity.upper())
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border-radius: {T.radius_sm}px;
                padding: 2px {T.space_2}px;
                font-size: {T.font_size_xs}px;
                font-weight: 600;
                min-width: 40px;
                text-align: center;
            }}
        """)


class FindingRow(QWidget):
    """One finding row with badge + text + source."""

    def __init__(self, severity: str, text: str, source: str = "", parent=None):
        super().__init__(parent)
        self.setProperty("class", "finding-row")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(T.space_3, T.space_2, T.space_3, T.space_2)
        layout.setSpacing(T.space_3)

        # Severity badge
        self.badge = SeverityBadge(severity)
        layout.addWidget(self.badge)

        # Text
        self.text_label = QLabel(text)
        self.text_label.setProperty("class", "finding-text")
        self.text_label.setWordWrap(True)
        layout.addWidget(self.text_label, stretch=1)

        # Source (file:line)
        if source:
            self.source_label = QLabel(source)
            self.source_label.setProperty("class", "muted-xs")
            self.source_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            layout.addWidget(self.source_label)

        self.setStyleSheet(f"""
            QWidget[class="finding-row"] {{
                background: transparent;
                border-bottom: 1px solid {T.border_subtle};
                border-radius: 0;
                padding: {T.space_2}px 0;
            }}
            QWidget[class="finding-row"]:hover {{
                background-color: {T.bg_hover};
            }}
            QLabel[class="finding-text"] {{
                color: {T.text_primary};
                font-size: {T.font_size_base}px;
            }}
            QLabel[class="muted-xs"] {{
                color: {T.text_disabled};
                font-size: {T.font_size_xs}px;
                font-family: {T.font_mono};
            }}
        """)


class FindingsList(QWidget):
    """Findings list with severity grouping and styled rows."""

    item_selected = Signal = None  # will be set below

    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtCore import Signal as _Signal

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet(f"""
            QWidget {{
                background-color: {T.bg_elevated};
                border-bottom: 1px solid {T.border_strong};
                padding: {T.space_3}px {T.space_4}px;
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(T.space_4, T.space_3, T.space_4, T.space_3)

        self.title = QLabel("Findings")
        self.title.setStyleSheet(f"""
            QLabel {{
                color: {T.text_primary};
                font-size: {T.font_size_lg}px;
                font-weight: 600;
            }}
        """)
        header_layout.addWidget(self.title)
        header_layout.addStretch(1)

        self.count_label = QLabel("0 items")
        self.count_label.setStyleSheet(f"""
            QLabel {{
                color: {T.text_secondary};
                font-size: {T.font_size_sm}px;
                background-color: {T.bg_active};
                border-radius: {T.radius_sm}px;
                padding: 2px {T.space_2}px;
            }}
        """)
        header_layout.addWidget(self.count_label)
        layout.addWidget(header)

        # List widget
        self.list = QListWidget()
        self.list.setStyleSheet(f"""
            QListWidget {{
                background-color: {T.bg_base};
                border: none;
                outline: none;
            }}
            QListWidget::item {{
                padding: 0;
                margin: 0;
                border: none;
            }}
            QListWidget::item:selected {{
                background-color: {T.accent_muted};
            }}
            QListWidget::item:hover {{
                background-color: {T.bg_hover};
            }}
        """)
        layout.addWidget(self.list)

        self._count = 0

    def add_finding(self, severity: str, text: str, source: str = ""):
        row = FindingRow(severity, text, source)
        item = QListWidgetItem()
        item.setSizeHint(row.sizeHint() + QSize(0, 8))
        item.setData(Qt.ItemDataRole.UserRole, (severity, text, source))
        self.list.addItem(item)
        self.list.setItemWidget(item, row)
        self._count += 1
        self.count_label.setText(f"{self._count} items")


class DetailPanel(QWidget):
    """Detail panel for selected finding."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {T.bg_surface};
                border: 1px solid {T.border_strong};
                border-radius: {T.radius_lg}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(T.space_4, T.space_4, T.space_4, T.space_4)
        layout.setSpacing(T.space_3)

        # Header
        header = QLabel("Details")
        header.setStyleSheet(f"""
            QLabel {{
                color: {T.text_primary};
                font-size: {T.font_size_lg}px;
                font-weight: 600;
                padding-bottom: {T.space_2}px;
                border-bottom: 1px solid {T.border_default};
            }}
        """)
        layout.addWidget(header)

        # Placeholder
        self.placeholder = QLabel("Select a finding\nto see details")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet(f"""
            QLabel {{
                color: {T.text_disabled};
                font-size: {T.font_size_base}px;
                padding: {T.space_8}px;
            }}
        """)
        layout.addWidget(self.placeholder)

        # Detail content
        self.detail_widget = QWidget()
        self.detail_widget.setStyleSheet("background: transparent;")
        detail_layout = QVBoxLayout(self.detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(T.space_3)

        self.severity_badge = SeverityBadge("high")
        detail_layout.addWidget(self.severity_badge)

        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(f"""
            QLabel {{
                color: {T.text_primary};
                font-size: {T.font_size_lg}px;
                font-weight: 600;
            }}
        """)
        detail_layout.addWidget(self.title_label)

        self.source_label = QLabel()
        self.source_label.setStyleSheet(f"""
            QLabel {{
                color: {T.text_secondary};
                font-size: {T.font_size_sm}px;
                font-family: {T.font_mono};
            }}
        """)
        detail_layout.addWidget(self.source_label)

        # Description box
        desc_box = QWidget()
        desc_box.setStyleSheet(f"""
            QWidget {{
                background-color: {T.bg_elevated};
                border: 1px solid {T.border_default};
                border-radius: {T.radius_md}px;
                padding: {T.space_3}px;
            }}
        """)
        desc_layout = QVBoxLayout(desc_box)
        desc_layout.setContentsMargins(T.space_3, T.space_3, T.space_3, T.space_3)
        self.description = QLabel("Description of the issue will appear here.")
        self.description.setWordWrap(True)
        self.description.setStyleSheet(f"color: {T.text_primary}; background: transparent;")
        desc_layout.addWidget(self.description)
        detail_layout.addWidget(desc_box)

        # Action buttons
        btn_row = QWidget()
        btn_row.setStyleSheet("background: transparent;")
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(T.space_2)

        fix_btn = QPushButton("Fix")
        fix_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {T.accent_emphasis};
                border: none;
                border-radius: {T.radius_md}px;
                padding: {T.space_2}px {T.space_4}px;
                color: #ffffff;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {T.accent};
            }}
        """)
        btn_layout.addWidget(fix_btn)

        ignore_btn = QPushButton("Ignore")
        ignore_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {T.border_default};
                border-radius: {T.radius_md}px;
                padding: {T.space_2}px {T.space_4}px;
                color: {T.text_secondary};
            }}
            QPushButton:hover {{
                background-color: {T.bg_hover};
                border-color: {T.text_secondary};
                color: {T.text_primary};
            }}
        """)
        btn_layout.addWidget(ignore_btn)
        btn_layout.addStretch(1)
        detail_layout.addWidget(btn_row)

        detail_layout.addStretch(1)
        self.detail_widget.setVisible(False)
        layout.addWidget(self.detail_widget)

    def show_finding(self, severity: str, text: str, source: str = ""):
        self.placeholder.setVisible(False)
        self.detail_widget.setVisible(True)
        self.severity_badge.set_severity(severity)
        self.title_label.setText(text)
        self.source_label.setText(source or "")


class PreviewPanel(QWidget):
    """Preview panel with detach button."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {T.bg_surface};
                border: 1px solid {T.border_strong};
                border-radius: {T.radius_lg}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with detach button
        header = QWidget()
        header.setStyleSheet(f"""
            QWidget {{
                background-color: {T.bg_elevated};
                border-bottom: 1px solid {T.border_strong};
                border-top-left-radius: {T.radius_lg}px;
                border-top-right-radius: {T.radius_lg}px;
            }}
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(T.space_4, T.space_3, T.space_3, T.space_3)

        title = QLabel("Preview")
        title.setStyleSheet(f"""
            QLabel {{
                color: {T.text_primary};
                font-size: {T.font_size_lg}px;
                font-weight: 600;
            }}
        """)
        header_layout.addWidget(title)
        header_layout.addStretch(1)

        # Detach button
        self.detach_btn = QPushButton("⧉")
        self.detach_btn.setToolTip("Detach preview to separate window")
        self.detach_btn.setFixedSize(28, 28)
        self.detach_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {T.border_default};
                border-radius: {T.radius_sm}px;
                color: {T.text_secondary};
                font-size: 16px;
            }}
            QPushButton:hover {{
                background-color: {T.bg_hover};
                border-color: {T.text_secondary};
                color: {T.text_primary};
            }}
        """)
        header_layout.addWidget(self.detach_btn)
        layout.addWidget(header)

        # Content
        self.content = QPlainTextEdit()
        self.content.setReadOnly(True)
        self.content.setPlaceholderText("Page preview will appear here...")
        self.content.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {T.bg_base};
                border: none;
                border-bottom-left-radius: {T.radius_lg}px;
                border-bottom-right-radius: {T.radius_lg}px;
                padding: {T.space_3}px;
                color: {T.text_primary};
                font-family: {T.font_mono};
                font-size: {T.font_size_sm}px;
            }}
        """)
        layout.addWidget(self.content)


class ThemeToggle(QPushButton):
    """Theme toggle button (dark/light)."""

    def __init__(self, parent=None):
        super().__init__("🌙", parent)
        self.setFixedSize(32, 32)
        self.setToolTip("Toggle theme")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.is_dark = True
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {T.border_default};
                border-radius: {T.radius_md}px;
                font-size: 16px;
            }}
            QPushButton:hover {{
                background-color: {T.bg_hover};
                border-color: {T.text_secondary};
            }}
        """)
        self.clicked.connect(self._toggle)

    def _toggle(self):
        self.is_dark = not self.is_dark
        self.setText("☀️" if self.is_dark else "🌙")


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

        # Add theme toggle to sidebar bottom
        self.sidebar.layout().addWidget(ThemeToggle())

        root.addWidget(self.sidebar)

        # Separator line between sidebar and content
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"background-color: {T.border_strong}; max-width: 1px;")
        root.addWidget(sep)

        # Main content area
        content = QWidget()
        content.setStyleSheet(f"background-color: {T.bg_base};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(T.space_3, T.space_3, T.space_3, T.space_3)
        content_layout.setSpacing(T.space_3)

        # Splitter: findings + detail/preview
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {T.border_strong};
                width: 2px;
            }}
            QSplitter::handle:hover {{
                background-color: {T.accent};
            }}
        """)

        # Findings list
        self.findings = FindingsList()
        self.findings.list.itemClicked.connect(self._on_finding_clicked)
        self.splitter.addWidget(self.findings)

        # Right side: detail + preview stacked
        right = QWidget()
        right.setStyleSheet("background: transparent;")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(T.space_3)

        self.detail = DetailPanel()
        right_layout.addWidget(self.detail)

        self.preview = PreviewPanel()
        self.preview.detach_btn.clicked.connect(self._on_detach_preview)
        right_layout.addWidget(self.preview)

        self.splitter.addWidget(right)
        self.splitter.setSizes([500, 500])

        content_layout.addWidget(self.splitter)
        root.addWidget(content)

        # Demo findings
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

    def _on_detach_preview(self):
        print("Detach preview - TODO: open in separate window")

    def _add_demo_findings(self):
        demos = [
            ("critical", "Missing lang attribute on <html>", "index.html:1"),
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
