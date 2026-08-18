"""Repo-mode counterpart to site_preview.py: column 1 shows the raw source
file (monospace, read-only) instead of a rendered web page, with the
selected CodeBlock's exact character range highlighted and scrolled into
view — the equivalent of the red outline used in the web preview.
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor

HIGHLIGHT_COLOR = QColor(255, 68, 68, 70)


def highlight_range(text_edit, start: int, end: int) -> None:
    # Clear any previous highlight first.
    clear_cursor = QTextCursor(text_edit.document())
    clear_cursor.select(QTextCursor.SelectionType.Document)
    clear_cursor.setCharFormat(QTextCharFormat())

    fmt = QTextCharFormat()
    fmt.setBackground(HIGHLIGHT_COLOR)
    cursor = QTextCursor(text_edit.document())
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    cursor.mergeCharFormat(fmt)

    text_edit.setTextCursor(cursor)
    text_edit.ensureCursorVisible()
