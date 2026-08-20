"""Entry point: python main.py

Modern UI with sidebar, dark theme, and real analysis pipeline.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QMainWindow, QPushButton,
    QSplitter, QVBoxLayout, QWidget, QListWidget, QListWidgetItem,
    QLabel, QPlainTextEdit,
)

import config
import detectors  # noqa: F401 - registers detectors
from detectors.factory import DetectorFactory
from detectors.judges import judge_for_provider
from ui.design_system import TOKENS as T
from ui.modern_theme import build_modern_qss
from ui.sidebar import Sidebar
from ui.worker import AnalysisWorker, RepoAnalysisWorker


class SeverityBadge(QLabel):
    STYLES = {
        "critical": (T.critical, "#ffffff"),
        "high": (T.high, "#ffffff"),
        "medium": (T.medium, "#000000"),
        "low": (T.bg_active, T.text_secondary),
    }

    def __init__(self, severity: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(52, 20)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_severity(severity)

    def set_severity(self, severity: str):
        bg, fg = self.STYLES.get(severity, self.STYLES["low"])
        self.setText(severity.upper())
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border-radius: 3px;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
        """)


class FindingRow(QWidget):
    def __init__(self, severity: str, text: str, source: str = "", parent=None):
        super().__init__(parent)
        self.setMinimumHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(T.space_3, T.space_2, T.space_3, T.space_2)
        layout.setSpacing(T.space_3)

        self.badge = SeverityBadge(severity)
        layout.addWidget(self.badge, alignment=Qt.AlignmentFlag.AlignTop)

        # Parse text to extract [tag] parts
        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self._set_styled_text(text)
        layout.addWidget(self.text_label, stretch=1)

        self.setStyleSheet("""
            QWidget {
                background: transparent;
            }
            QWidget:hover {
                background-color: rgba(255, 255, 255, 0.03);
            }
        """)

    def _set_styled_text(self, text: str):
        """Style [tag] parts as inline badges."""
        import re
        # Find [tag] patterns and style them
        parts = re.split(r'(\[[\w-]+\])', text)
        styled = ""
        for part in parts:
            if part.startswith('[') and part.endswith(']'):
                tag = part[1:-1]
                styled += f'<span style="background-color: {T.bg_active}; color: {T.text_secondary}; border-radius: 3px; padding: 1px 4px; font-size: 10px; font-weight: 600;">{tag}</span> '
            else:
                styled += part
        self.text_label.setText(f'<span style="color: {T.text_primary}; font-size: {T.font_size_sm}px;">{styled}</span>')
        self.text_label.setTextFormat(Qt.TextFormat.RichText)


class FindingsList(QWidget):
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
        header_layout.setContentsMargins(T.space_4, T.space_3, T.space_4, T.space_3)

        self.title = QLabel("Findings")
        self.title.setStyleSheet(f"color: {T.text_primary}; font-size: {T.font_size_lg}px; font-weight: 600;")
        header_layout.addWidget(self.title)
        header_layout.addStretch(1)

        self.count_label = QLabel("0 items")
        self.count_label.setStyleSheet(f"""
            color: {T.text_secondary};
            font-size: {T.font_size_sm}px;
            background-color: {T.bg_active};
            border-radius: {T.radius_sm}px;
            padding: 2px {T.space_2}px;
        """)
        header_layout.addWidget(self.count_label)
        layout.addWidget(header)

        self.list = QListWidget()
        self.list.setStyleSheet(f"""
            QListWidget {{
                background-color: {T.bg_surface};
                border: none;
                outline: none;
                padding: {T.space_2}px {T.space_3}px;
            }}
            QListWidget::item {{
                padding: 0;
                margin: 0 0 {T.space_1}px 0;
                border: none;
                background: transparent;
            }}
            QListWidget::item:selected {{
                background-color: {T.accent_muted};
                border-radius: {T.radius_md}px;
            }}
            QListWidget::item:hover:!selected {{
                background-color: rgba(255, 255, 255, 0.03);
                border-radius: {T.radius_md}px;
            }}
        """)
        layout.addWidget(self.list)
        self._count = 0

    def add_finding(self, severity: str, text: str, source: str = ""):
        row = FindingRow(severity, text)
        item = QListWidgetItem()
        item.setSizeHint(row.sizeHint() + QSize(0, 8))
        item.setData(Qt.ItemDataRole.UserRole, (severity, text, source))
        self.list.addItem(item)
        self.list.setItemWidget(item, row)
        self._count += 1
        self.count_label.setText(f"{self._count} items")


class DetailPanel(QWidget):
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
        layout.setSpacing(T.space_4)

        header = QLabel("Details")
        header.setStyleSheet(f"""
            QLabel {{
                color: {T.text_primary};
                font-size: {T.font_size_lg}px;
                font-weight: 600;
            }}
        """)
        layout.addWidget(header)

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

        self.detail_widget = QWidget()
        self.detail_widget.setStyleSheet("background: transparent;")
        detail_layout = QVBoxLayout(self.detail_widget)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(T.space_3)

        # Severity + source row
        meta_row = QWidget()
        meta_row.setStyleSheet("background: transparent;")
        meta_layout = QHBoxLayout(meta_row)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(T.space_2)

        self.severity_badge = SeverityBadge("high")
        meta_layout.addWidget(self.severity_badge)

        self.source_badge = QLabel()
        self.source_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {T.bg_active};
                border-radius: {T.radius_sm}px;
                padding: 2px {T.space_2}px;
                color: {T.text_secondary};
                font-size: {T.font_size_xs}px;
                font-family: {T.font_mono};
            }}
        """)
        meta_layout.addWidget(self.source_badge)
        meta_layout.addStretch(1)
        detail_layout.addWidget(meta_row)

        # Title
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

        # Description box
        desc_box = QWidget()
        desc_box.setStyleSheet(f"""
            QWidget {{
                background-color: {T.bg_elevated};
                border-radius: {T.radius_md}px;
            }}
        """)
        desc_layout = QVBoxLayout(desc_box)
        desc_layout.setContentsMargins(T.space_4, T.space_4, T.space_4, T.space_4)
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
        btn_layout.setSpacing(T.space_3)

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
            QPushButton:hover {{ background-color: {T.accent}; }}
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
        self.source_badge.setText(source or "No source")


class PreviewPanel(QWidget):
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
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

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
        header_layout.setContentsMargins(T.space_4, T.space_3, T.space_4, T.space_3)

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

        self.detach_btn = QPushButton("Detach")
        self.detach_btn.setFixedHeight(24)
        self.detach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.detach_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
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
        """)
        header_layout.addWidget(self.detach_btn)
        layout.addWidget(header)

        self.content = QPlainTextEdit()
        self.content.setReadOnly(True)
        self.content.setPlaceholderText("Page preview will appear here...")
        self.content.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {T.bg_surface};
                border: none;
                border-bottom-left-radius: {T.radius_lg}px;
                border-bottom-right-radius: {T.radius_lg}px;
                padding: {T.space_4}px;
                color: {T.text_primary};
                font-family: {T.font_mono};
                font-size: {T.font_size_sm}px;
            }}
        """)
        layout.addWidget(self.content)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XAnalyze")
        self.resize(1400, 900)
        self.settings = config.Settings.load()
        self.worker = None

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar(lang="uk")
        self.sidebar.analyze_clicked.connect(self._on_analyze)
        self.sidebar.cancel_clicked.connect(self._on_cancel)
        self.sidebar.settings_clicked.connect(self._on_settings)
        self.sidebar.account_clicked.connect(self._on_account)
        root.addWidget(self.sidebar)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f"background-color: {T.border_strong}; max-width: 1px;")
        root.addWidget(sep)

        content = QWidget()
        content.setStyleSheet(f"background-color: {T.bg_base};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(T.space_3, T.space_3, T.space_3, T.space_3)
        content_layout.setSpacing(T.space_3)

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

        self.findings = FindingsList()
        self.findings.list.itemClicked.connect(self._on_finding_clicked)
        self.splitter.addWidget(self.findings)

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

        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {T.text_secondary};
                font-size: {T.font_size_sm}px;
                padding: {T.space_1}px {T.space_3}px;
            }}
        """)
        self.statusBar().addWidget(self.status_label)
        self.statusBar().setStyleSheet(f"""
            QStatusBar {{
                background-color: {T.bg_surface};
                border-top: 1px solid {T.border_default};
            }}
        """)

    def _on_analyze(self):
        source = self.sidebar.get_source()
        target = self.sidebar.get_target()
        if not target:
            self.status_label.setText("Enter a URL or path")
            return

        self.findings.list.clear()
        self.findings._count = 0
        self.findings.count_label.setText("0 items")
        self.sidebar.set_busy(True)
        self.status_label.setText(f"Analyzing: {target}...")

        # Get checks and methods
        checks = self.sidebar.get_checks()
        methods = self.sidebar.get_methods()
        wants_copy = "ai-patterns" in checks
        wants_audit = "accessibility" in checks

        # Determine detector from method selection
        if "ai" in methods and "local" in methods:
            detector_name = "hybrid"
        elif "ai" in methods:
            provider = self.settings.llm_provider
            detector_name = judge_for_provider(provider)
        else:
            detector_name = "offline"

        detector_config = self._detector_config(detector_name)

        if source == "repo":
            self.worker = RepoAnalysisWorker(
                files=None, root_dir=target, ignore_patterns=[],
                detector_name=detector_name, detector_config=detector_config,
                unicode_categories=None, scope="both",
                settings=self.settings,
            )
            self.worker.finished_ok.connect(self._on_repo_finished)
        elif source == "file":
            self.worker = RepoAnalysisWorker(
                files=None, root_dir=target, ignore_patterns=[],
                detector_name=detector_name, detector_config=detector_config,
                unicode_categories=None, scope="both",
                settings=self.settings,
            )
            self.worker.finished_ok.connect(self._on_repo_finished)
        else:
            url = target
            if not url.startswith(("http://", "https://", "file://")):
                url = "https://" + url
            self.worker = AnalysisWorker(
                pages=None, root_url=url,
                depth=self.sidebar.get_depth(),
                detector_name=detector_name, detector_config=detector_config,
                max_pages=self.settings.max_pages,
                unicode_categories=None, settings=self.settings,
            )
            self.worker.finished_ok.connect(self._on_web_finished)

        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._on_worker_finished)
        if hasattr(self.worker, 'crawling'):
            self.worker.crawling.connect(
                lambda url, d: self.status_label.setText(f"Crawling: {url}"))
        if hasattr(self.worker, 'detecting'):
            self.worker.detecting.connect(
                lambda name: self.status_label.setText(f"Detecting: {name}"))
        self.worker.start()

    def _detector_config(self, detector_name: str) -> dict:
        resolved = DetectorFactory.resolve(detector_name)
        if resolved == "hybrid":
            judge = judge_for_provider(self.settings.llm_provider)
            return {
                "categories": (),
                "judge_name": judge,
                "judge_config": self._detector_config(judge),
            }
        if resolved in ("claude-llm-judge", "claude-official-watermark"):
            return {"api_key": config.get_anthropic_api_key(), "model": self.settings.claude_model}
        if resolved == "xformat-llm-judge":
            return {"base_url": self.settings.xformat_base_url, "endpoints": self.settings.xformat_endpoints}
        return {}

    def _on_cancel(self):
        if self.worker:
            self.worker.requestInterruption()

    def _on_settings(self):
        from PySide6.QtWidgets import QDialog
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self.settings, "uk", parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.settings = config.Settings.load()
            self.status_label.setText("Settings updated")

    def _on_account(self):
        from PySide6.QtWidgets import QDialog
        from ui.sign_in_dialog import SignInDialog
        from llm.base import LLMProviderFactory
        provider = LLMProviderFactory.create(
            "xformat",
            base_url=self.settings.xformat_base_url,
            endpoints=self.settings.xformat_endpoints or {},
        )
        dlg = SignInDialog(provider, "uk", parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.status:
            self.sidebar.account_label.setText(dlg.status.detail)
            self.sidebar.account_btn.setText("Sign out")
            self.status_label.setText(f"Signed in: {dlg.status.detail}")

    def _on_web_finished(self, result):
        for span in result.spans:
            sev = "high" if str(span.confidence) == "high" else "medium" if str(span.confidence) == "medium" else "low"
            text = (span.explanation or "Finding")[:80]
            source = ""
            for page in result.pages:
                for block in page.blocks:
                    if block.block_id == span.block_id:
                        source = page.url
                        break
            self.findings.add_finding(sev, text, source)
        self.status_label.setText(f"Done: {len(result.spans)} findings")

    def _on_repo_finished(self, result):
        for span in result.spans:
            sev = "high" if str(span.confidence) == "high" else "medium" if str(span.confidence) == "medium" else "low"
            text = (span.explanation or "Finding")[:80]
            source = ""
            for f in result.files:
                for block in f.blocks:
                    if block.block_id == span.block_id:
                        source = f"{f.path}:{block.line_number}"
                        break
            self.findings.add_finding(sev, text, source)
        self.status_label.setText(f"Done: {len(result.spans)} findings")

    def _on_failed(self, message):
        self.status_label.setText(f"Error: {message}")

    def _on_worker_finished(self):
        self.worker = None
        self.sidebar.set_busy(False)

    def _on_finding_clicked(self, item: QListWidgetItem):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            severity, text, source = data
            self.detail.show_finding(severity, text, source)

    def _on_detach_preview(self):
        self.status_label.setText("Detach preview - TODO")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("XAnalyze")
    app.setOrganizationName("xFormat")
    app.setStyleSheet(build_modern_qss())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
