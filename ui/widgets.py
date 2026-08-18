"""Small presentation pieces shared by the main window.

Kept out of `main_window.py` for one reason each:

* `FindingDelegate` paints the findings list. Every row shows a coloured
  confidence pill, and the obvious way to get one — a widget per row via
  `setItemWidget` — allocates a widget tree per finding, which a scan of a
  large site produces thousands of. A delegate paints the same thing with
  no per-row objects at all.
* `EmptyState` is the answer to "why did I get nothing?", which is a
  screenful of explanation rather than a label, and is reused by both
  source modes.
* The `card` / `heading` helpers exist so the class names the style sheet
  matches on are written in one place.
"""
from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QLabel, QSizePolicy, QStyle, QStyledItemDelegate, QVBoxLayout, QWidget,
)

from i18n.translations import t
from models import Confidence
from ui import theme

#: Item data role carrying the row's presentation record (see `RowData`).
ROW_ROLE = Qt.ItemDataRole.UserRole + 1


class RowData:
    """What the delegate needs to paint one finding, precomputed.

    Deliberately not the `TextSpan` itself: the delegate runs on every
    repaint, and formatting a score or looking up a translation there would
    put that work on the scroll path.
    """

    __slots__ = ("badge", "confidence", "score", "text", "has_draft", "is_character")

    def __init__(self, badge: str, confidence: Confidence, score: float,
                 text: str, has_draft: bool, is_character: bool):
        self.badge = badge
        self.confidence = confidence
        self.score = score
        self.text = text
        self.has_draft = has_draft
        self.is_character = is_character


class FindingDelegate(QStyledItemDelegate):
    """Draws: [ HIGH 0.95 ] flagged text …  ✎"""

    PADDING = 8
    BADGE_PADDING = 6
    GAP = 10

    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self.palette_ = palette

    def set_palette(self, palette) -> None:
        self.palette_ = palette

    def _badge_colors(self, confidence: Confidence) -> tuple:
        p = self.palette_
        if confidence == Confidence.HIGH:
            return QColor(p.error), QColor("#ffffff")
        if confidence == Confidence.MEDIUM:
            return QColor(p.amber), QColor("#141416")
        return QColor(p.bg_muted), QColor(p.text_muted)

    def sizeHint(self, option, index) -> QSize:  # noqa: N802 - Qt override
        row = index.data(ROW_ROLE)
        base = super().sizeHint(option, index)
        if row is None:
            return base
        return QSize(base.width(), max(base.height(), 34))

    def paint(self, painter: QPainter, option, index) -> None:  # noqa: N802 - Qt override
        row = index.data(ROW_ROLE)
        if row is None:
            # Placeholder rows ("nothing found") are plain text.
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        p = self.palette_
        rect = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected or hovered:
            background = QColor(p.bg_hover)
            path = QPainterPath()
            path.addRoundedRect(
                QRect(rect.x() + 2, rect.y() + 1, rect.width() - 4, rect.height() - 2),
                p.radius_md, p.radius_md,
            )
            painter.fillPath(path, background)

        badge_font = QFont(painter.font())
        badge_font.setPointSizeF(max(8.0, badge_font.pointSizeF() - 1))
        badge_font.setBold(True)
        painter.setFont(badge_font)
        badge_width = painter.fontMetrics().horizontalAdvance(row.badge) + 2 * self.BADGE_PADDING
        badge_height = painter.fontMetrics().height() + 2
        badge_rect = QRect(
            rect.x() + self.PADDING,
            rect.y() + (rect.height() - badge_height) // 2,
            badge_width, badge_height,
        )
        fill, ink = self._badge_colors(row.confidence)
        path = QPainterPath()
        path.addRoundedRect(badge_rect, p.radius_sm, p.radius_sm)
        painter.fillPath(path, fill)
        painter.setPen(ink)
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, row.badge)

        text_font = QFont(option.font)
        if row.is_character:
            # A non-keyboard character is about the exact glyphs, so the row
            # shows them in the monospaced face where they line up.
            text_font.setFamily(p.font_mono)
        painter.setFont(text_font)
        painter.setPen(QColor(p.text))

        draft_mark = "  ✎" if row.has_draft else ""
        text_rect = QRect(
            badge_rect.right() + self.GAP,
            rect.y(),
            rect.width() - badge_rect.width() - self.GAP - 2 * self.PADDING,
            rect.height(),
        )
        metrics = painter.fontMetrics()
        elided = metrics.elidedText(
            row.text, Qt.TextElideMode.ElideRight,
            max(0, text_rect.width() - metrics.horizontalAdvance(draft_mark)),
        )
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            elided + draft_mark,
        )
        painter.restore()


class EmptyState(QWidget):
    """A heading, an explanation and (optionally) a list of specifics.

    Used for the three "nothing to show" situations, which need to look
    different from each other: nothing scanned yet, scanned and clean, and
    scanned but the crawler got no text — the last one being the case that
    actually needs explaining.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", theme.CLASS_CARD)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        self.title = QLabel()
        self.title.setProperty("class", theme.CLASS_HEADING)
        self.title.setWordWrap(True)

        self.body = QLabel()
        self.body.setProperty("class", theme.CLASS_EMPTY)
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.body.setOpenExternalLinks(False)

        layout.addWidget(self.title)
        layout.addWidget(self.body)
        layout.addStretch(1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def show_message(self, title: str, body: str) -> None:
        self.title.setText(title)
        self.body.setText(body)


def card(widget: QWidget) -> QWidget:
    widget.setProperty("class", theme.CLASS_CARD)
    return widget


def heading(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setProperty("class", theme.CLASS_HEADING)
    return label


def muted(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setProperty("class", theme.CLASS_MUTED)
    label.setWordWrap(True)
    return label


def restyle(widget: QWidget) -> None:
    """Re-evaluate the style sheet for a widget whose `class` property was
    set after it was first shown. Qt only re-reads property selectors when
    it is told to."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def diagnostics_message(page, lang: str) -> str:
    """Turn a `PageDiagnostics` record into the reason a page yielded no
    text, in the user's language, with the measurements that back it up."""
    diagnostics = getattr(page, "diagnostics", None)
    if diagnostics is None:
        return ""

    lines = []
    for reason in diagnostics.reasons:
        key = f"crawl_reason_{reason.replace('-', '_')}"
        if reason == "js-rendered" and diagnostics.js_framework:
            lines.append(t(key, lang) + " " +
                         t("crawl_reason_framework", lang, framework=diagnostics.js_framework))
        elif reason == "not-html":
            lines.append(t(key, lang, content_type=diagnostics.content_type or "?"))
        elif reason == "blocked":
            lines.append(t(key, lang, status=diagnostics.status_code or "?"))
        elif reason == "too-short":
            lines.append(t(key, lang, dropped=diagnostics.dropped_too_short))
        elif reason == "redirected":
            lines.append(t(key, lang, final_url=diagnostics.final_url))
        elif reason == "error":
            lines.append(t(key, lang, error=page.error or "?"))
        else:
            lines.append(t(key, lang))

    if not lines:
        return ""

    measured = t(
        "crawl_measurements", lang,
        bytes=diagnostics.html_bytes,
        ratio=f"{diagnostics.text_ratio:.1%}",
        candidates=diagnostics.candidates_found,
        kept=diagnostics.blocks_kept,
    )
    return "\n".join("• " + line for line in lines) + "\n\n" + measured
