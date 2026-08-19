"""Repo-mode counterpart to site_preview.py: column 1 shows the raw source
file (monospace, read-only) instead of a rendered web page, with the
selected CodeBlock's exact character range highlighted and scrolled into
view — the equivalent of the red outline used in the web preview.
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor

HIGHLIGHT_COLOR = QColor(255, 68, 68, 70)


def highlight_line(text_edit, line: int) -> None:
    """Highlight one whole line, 1-based, and scroll it into view.

    An audit finding in a source file is located by line, not by character
    range: the rules read a parsed document and report where the element was,
    which is the number an editor also understands.
    """
    document = text_edit.document()
    block = document.findBlockByLineNumber(max(line - 1, 0))
    if not block.isValid():
        return
    highlight_range(text_edit, block.position(),
                    block.position() + block.length() - 1)


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
