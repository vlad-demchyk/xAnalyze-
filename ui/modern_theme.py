"""Modern QSS stylesheet builder.

Generates a complete dark-theme stylesheet from DesignTokens.
Every widget style is explicit - no reliance on Qt defaults.
"""
from __future__ import annotations

from ui.design_system import DesignTokens, TOKENS


def build_modern_qss(t: DesignTokens = TOKENS) -> str:
    """Build a complete dark-theme QSS stylesheet."""
    return f"""
/* ═══════════════════════════════════════════════════════════════════════
   XAnalyze Modern Design System
   Dark-first, inspired by Linear/Vercel/Sentry
   ═══════════════════════════════════════════════════════════════════════ */

/* ── Base ── */
QWidget {{
    background-color: {t.bg_base};
    color: {t.text_primary};
    font-family: {t.font_family};
    font-size: {t.font_size_base}px;
    selection-background-color: {t.accent_muted};
    selection-color: {t.text_primary};
}}

QMainWindow, QDialog {{
    background-color: {t.bg_base};
}}

QLabel {{
    background: transparent;
    padding: 0;
}}

/* ── Sidebar ── */
QWidget[class="sidebar"] {{
    background-color: {t.bg_surface};
    border-right: 1px solid {t.border_strong};
}}

QWidget[class="sidebar-section"] {{
    background: transparent;
    padding: {t.space_2}px 0;
}}

QLabel[class="sidebar-title"] {{
    color: {t.text_secondary};
    font-size: {t.font_size_xs}px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: {t.space_2}px {t.space_4}px;
}}

/* ── Source buttons (radio-like) ── */
QPushButton[class="source-btn"] {{
    background: transparent;
    border: none;
    border-radius: {t.radius_md}px;
    padding: {t.space_2}px {t.space_3}px;
    color: {t.text_secondary};
    font-size: {t.font_size_base}px;
    text-align: left;
}}

QPushButton[class="source-btn"]:hover {{
    background-color: {t.bg_hover};
    color: {t.text_primary};
}}

QPushButton[class="source-btn"]:checked,
QPushButton[class="source-btn"][active="true"] {{
    background-color: {t.accent_muted};
    color: {t.accent};
    font-weight: 500;
}}

/* ── Filter chips ── */
QPushButton[class="chip"] {{
    background-color: {t.bg_elevated};
    border: 1px solid {t.border_default};
    border-radius: {t.radius_sm}px;
    padding: {t.space_1}px {t.space_2}px;
    color: {t.text_secondary};
    font-size: {t.font_size_sm}px;
}}

QPushButton[class="chip"]:hover {{
    background-color: {t.bg_hover};
    border-color: {t.border_active};
    color: {t.text_primary};
}}

QPushButton[class="chip"]:checked {{
    background-color: {t.accent_muted};
    border-color: {t.accent};
    color: {t.accent};
}}

/* ── Primary action ── */
QPushButton[class="primary"] {{
    background-color: {t.accent_emphasis};
    border: none;
    border-radius: {t.radius_md}px;
    padding: {t.space_2}px {t.space_4}px;
    color: #ffffff;
    font-weight: 600;
    font-size: {t.font_size_base}px;
}}

QPushButton[class="primary"]:hover {{
    background-color: {t.accent};
}}

QPushButton[class="primary"]:disabled {{
    background-color: {t.bg_active};
    color: {t.text_disabled};
}}

/* ── Ghost button ── */
QPushButton[class="ghost"] {{
    background: transparent;
    border: 1px solid {t.border_default};
    border-radius: {t.radius_md}px;
    padding: {t.space_2}px {t.space_3}px;
    color: {t.text_secondary};
    font-size: {t.font_size_sm}px;
}}

QPushButton[class="ghost"]:hover {{
    background-color: {t.bg_hover};
    border-color: {t.text_secondary};
    color: {t.text_primary};
}}

/* ── Inputs ── */
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox {{
    background-color: {t.bg_input};
    border: 1px solid {t.border_default};
    border-radius: {t.radius_md}px;
    padding: {t.space_2}px {t.space_3}px;
    color: {t.text_primary};
    font-size: {t.font_size_base}px;
}}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QSpinBox:focus, QComboBox:focus {{
    border-color: {t.accent};
    outline: none;
}}

QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled,
QSpinBox:disabled, QComboBox:disabled {{
    color: {t.text_disabled};
    background-color: {t.bg_surface};
}}

QLineEdit[class="search"] {{
    background-color: {t.bg_elevated};
    border: 1px solid {t.border_default};
    border-radius: {t.radius_lg}px;
    padding: {t.space_2}px {t.space_3}px;
    padding-left: {t.space_8}px;
}}

QLineEdit[class="search"]:focus {{
    border-color: {t.accent};
    background-color: {t.bg_input};
}}

QLineEdit[class="field-error"] {{
    border-color: {t.error};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background-color: {t.bg_elevated};
    border: 1px solid {t.border_default};
    border-radius: {t.radius_md}px;
    padding: {t.space_1}px;
    color: {t.text_primary};
    outline: none;
}}

QComboBox QAbstractItemView::item {{
    padding: {t.space_2}px {t.space_3}px;
    border-radius: {t.radius_sm}px;
}}

QComboBox QAbstractItemView::item:selected {{
    background-color: {t.accent_muted};
    color: {t.accent};
}}

/* ── Panels ── */
QWidget[class="panel"] {{
    background-color: {t.bg_surface};
    border: 1px solid {t.border_default};
    border-radius: {t.radius_lg}px;
}}

QWidget[class="panel-header"] {{
    background-color: {t.bg_elevated};
    border-bottom: 1px solid {t.border_default};
    border-top-left-radius: {t.radius_lg}px;
    border-top-right-radius: {t.radius_lg}px;
    padding: {t.space_3}px {t.space_4}px;
}}

QLabel[class="panel-title"] {{
    color: {t.text_primary};
    font-size: {t.font_size_lg}px;
    font-weight: 600;
}}

/* ── Findings list ── */
QListWidget {{
    background-color: {t.bg_base};
    border: none;
    outline: none;
    padding: {t.space_1}px;
}}

QListWidget::item {{
    padding: {t.space_3}px {t.space_4}px;
    border-radius: {t.radius_md}px;
    margin: {t.space_1}px 0;
}}

QListWidget::item:hover {{
    background-color: {t.bg_hover};
}}

QListWidget::item:selected {{
    background-color: {t.accent_muted};
    color: {t.text_primary};
}}

/* ── Severity badges ── */
QLabel[class="badge-critical"] {{
    background-color: {t.critical};
    color: #ffffff;
    border-radius: {t.radius_sm}px;
    padding: 1px {t.space_2}px;
    font-size: {t.font_size_xs}px;
    font-weight: 600;
}}

QLabel[class="badge-high"] {{
    background-color: {t.high};
    color: #ffffff;
    border-radius: {t.radius_sm}px;
    padding: 1px {t.space_2}px;
    font-size: {t.font_size_xs}px;
    font-weight: 600;
}}

QLabel[class="badge-medium"] {{
    background-color: {t.medium};
    color: #000000;
    border-radius: {t.radius_sm}px;
    padding: 1px {t.space_2}px;
    font-size: {t.font_size_xs}px;
    font-weight: 600;
}}

QLabel[class="badge-low"] {{
    background-color: {t.bg_active};
    color: {t.text_secondary};
    border-radius: {t.radius_sm}px;
    padding: 1px {t.space_2}px;
    font-size: {t.font_size_xs}px;
    font-weight: 600;
}}

/* ── Status bar ── */
QStatusBar {{
    background-color: {t.bg_surface};
    border-top: 1px solid {t.border_default};
    color: {t.text_secondary};
    font-size: {t.font_size_sm}px;
    padding: {t.space_1}px {t.space_3}px;
}}

QStatusBar::item {{
    border: none;
}}

/* ── Scrollbar ── */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {t.border_default};
    border-radius: 4px;
    min-height: 32px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {t.text_disabled};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
    border: none;
    height: 0;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background-color: {t.border_default};
    border-radius: 4px;
    min-width: 32px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {t.text_disabled};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
    border: none;
    width: 0;
}}

/* ── Splitter ── */
QSplitter::handle {{
    background-color: {t.border_default};
}}

QSplitter::handle:horizontal {{
    width: 1px;
}}

QSplitter::handle:vertical {{
    height: 1px;
}}

/* ── Tab widget ── */
QTabWidget::pane {{
    background-color: {t.bg_surface};
    border: 1px solid {t.border_default};
    border-radius: {t.radius_md}px;
}}

QTabBar::tab {{
    background-color: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    padding: {t.space_2}px {t.space_4}px;
    color: {t.text_secondary};
    font-size: {t.font_size_base}px;
}}

QTabBar::tab:hover {{
    color: {t.text_primary};
    background-color: {t.bg_hover};
}}

QTabBar::tab:selected {{
    color: {t.text_primary};
    border-bottom-color: {t.accent};
    font-weight: 500;
}}

/* ── Tooltip ── */
QToolTip {{
    background-color: {t.bg_elevated};
    border: 1px solid {t.border_default};
    border-radius: {t.radius_md}px;
    padding: {t.space_2}px {t.space_3}px;
    color: {t.text_primary};
    font-size: {t.font_size_sm}px;
}}

/* ── Heading ── */
QLabel[class="heading"] {{
    font-size: {t.font_size_lg}px;
    font-weight: 600;
    color: {t.text_primary};
}}

QLabel[class="heading-lg"] {{
    font-size: {t.font_size_xxl}px;
    font-weight: 700;
    color: {t.text_primary};
}}

/* ── Muted text ── */
QLabel[class="muted"] {{
    color: {t.text_secondary};
    font-size: {t.font_size_sm}px;
}}

QLabel[class="muted-xs"] {{
    color: {t.text_disabled};
    font-size: {t.font_size_xs}px;
}}

/* ── Code ── */
QPlainTextEdit[class="code"] {{
    background-color: {t.bg_input};
    border: 1px solid {t.border_default};
    border-radius: {t.radius_md}px;
    padding: {t.space_3}px;
    font-family: {t.font_mono};
    font-size: {t.font_size_sm}px;
    color: {t.text_primary};
}}

/* ── Divider ── */
QFrame[class="divider"] {{
    background-color: {t.border_default};
    max-height: 1px;
    border: none;
}}

/* ── Empty state ── */
QWidget[class="empty-state"] {{
    background: transparent;
    padding: {t.space_8}px;
}}

QLabel[class="empty-title"] {{
    font-size: {t.font_size_xl}px;
    font-weight: 600;
    color: {t.text_primary};
}}

QLabel[class="empty-body"] {{
    font-size: {t.font_size_base}px;
    color: {t.text_secondary};
    line-height: 1.5;
}}

/* ── Toast notification ── */
QWidget[class="toast"] {{
    background-color: {t.bg_elevated};
    border: 1px solid {t.border_default};
    border-radius: {t.radius_lg}px;
    padding: {t.space_3}px {t.space_4}px;
}}

QWidget[class="toast-error"] {{
    border-color: {t.error};
}}

QWidget[class="toast-success"] {{
    border-color: {t.success};
}}

/* ── Score gauge ── */
QWidget[class="score-gauge"] {{
    background-color: {t.bg_elevated};
    border: 1px solid {t.border_default};
    border-radius: {t.radius_xl}px;
    padding: {t.space_4}px;
}}
"""
