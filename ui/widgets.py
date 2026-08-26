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

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QAbstractButton, QButtonGroup, QHBoxLayout, QLabel, QLayout, QPushButton,
    QSizePolicy, QStyle, QStyledItemDelegate, QVBoxLayout, QWidget,
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
            return QColor(p.error_strong), QColor(p.on_error)
        if confidence == Confidence.MEDIUM:
            return QColor(p.amber), QColor(p.on_amber)
        return QColor(p.bg_muted), QColor(p.text_muted)

    def sizeHint(self, option, index) -> QSize:  # noqa: N802 - Qt override
        row = index.data(ROW_ROLE)
        base = super().sizeHint(option, index)
        if row is None:
            return base
        # Width 0, not the text's width: `paint` already elides, so asking for
        # the full width only makes the list grow a horizontal scrollbar that
        # no one can usefully scroll. It showed up the moment findings started
        # arriving with long English sentences from axe.
        return QSize(0, max(base.height(), 34))

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


#: The three situations that produce no rows, as a mark and an ink. Drawn
#: rather than only written, because the difference between them is the
#: whole point: "nothing found" and "nothing was read" are opposite pieces
#: of news, and two grey paragraphs of the same weight hide that.
TONE_IDLE, TONE_CLEAN, TONE_PROBLEM = "idle", "clean", "problem"

_TONE_MARK = {TONE_IDLE: "\u25ce", TONE_CLEAN: "\u2713", TONE_PROBLEM: "!"}
_TONE_INK = {
    TONE_IDLE: "text_subtle",
    TONE_CLEAN: "success_text",
    TONE_PROBLEM: "amber_text",
}


class EmptyState(QWidget):
    """A mark, a heading, an explanation, and what to do next.

    Used for the three "nothing to show" situations, which need to look
    different from each other: nothing scanned yet, scanned and clean, and
    scanned but the crawler got no text - the last one being the case that
    actually needs explaining.

    The actions are the part that took longest to arrive (artboard 3i). A
    state that explains and stops leaves the reader holding a diagnosis and
    no way to act on it: "the markup is drawn by JavaScript" is only useful
    next to the button that re-reads the page in a browser. So each state
    carries the move that follows from it, and only moves that are real -
    a button offering something this run cannot do is worse than no button.
    """

    def __init__(self, palette=None, parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self.setProperty("class", theme.CLASS_CARD)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(8)

        self.mark = QLabel()
        self.mark.setVisible(False)

        self.title = QLabel()
        self.title.setProperty("class", theme.CLASS_HEADING)
        self.title.setWordWrap(True)

        self.body = QLabel()
        self.body.setProperty("class", theme.CLASS_EMPTY)
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.body.setOpenExternalLinks(False)

        self.actions = QWidget()
        # Wrapping, not a row: this pane narrows with the window, and a
        # `QHBoxLayout` would answer that by putting a floor under the
        # column rather than by using a second line.
        self.actions_layout = FlowLayout(self.actions, margin=0, spacing=6)

        layout.addWidget(self.mark)
        layout.addWidget(self.title)
        layout.addWidget(self.body)
        layout.addWidget(self.actions)
        layout.addStretch(1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def show_message(self, title: str, body: str, tone: str = "",
                     actions=()) -> None:
        """`actions` is a sequence of `(label, callback)`, left to right."""
        self.title.setText(title)
        self.body.setText(body)
        self._set_tone(tone)
        self._set_actions(actions)

    def _set_tone(self, tone: str) -> None:
        self.tone = tone
        mark = _TONE_MARK.get(tone, "")
        self.mark.setText(mark)
        self.mark.setVisible(bool(mark))
        self._paint_mark()

    def _paint_mark(self) -> None:
        if self.palette_ is None or not self.mark.text():
            return
        ink = getattr(self.palette_, _TONE_INK.get(getattr(self, "tone", ""), ""),
                      self.palette_.text_subtle)
        self.mark.setStyleSheet(f"color: {ink}; font-size: 22px;")

    def _set_actions(self, actions) -> None:
        while self.actions_layout.count():
            item = self.actions_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Unparented *before* `deleteLater`, which only schedules the
                # deletion: until the event loop gets round to it the widget
                # is still a visible child at its old geometry, so the
                # previous state's buttons stay on screen underneath the
                # current state's. The layout's count says one; the window
                # shows two.
                widget.setParent(None)
                widget.deleteLater()
        for label, callback in actions:
            from PySide6.QtWidgets import QPushButton
            button = QPushButton(label)
            button.clicked.connect(callback)
            self.actions_layout.addWidget(button)
        self.actions.setVisible(bool(actions))

    def apply_palette(self, palette) -> None:
        self.palette_ = palette
        self._paint_mark()


def card(widget: QWidget) -> QWidget:
    widget.setProperty("class", theme.CLASS_CARD)
    return widget


def heading(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setProperty("class", theme.CLASS_HEADING)
    # A finding's title can be the flagged markup itself.
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


def muted(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setProperty("class", theme.CLASS_MUTED)
    label.setWordWrap(True)
    # Same reason as in `field`: these carry rule text and file paths, and a
    # `<tag>` in either must be read, not rendered.
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


def panel(title: str = "", trailing=None) -> tuple:
    """A zone of the window: a surface, a titled head, and a body to fill.

    Returns `(panel, body_layout, title_label)`. The head is a strip with its
    own fill and a hairline under it rather than a bold label floating above
    whitespace: the window has four zones that mean different things, and the
    eye should find the boundary between them without reading anything.
    """
    from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

    container = QWidget()
    container.setProperty("class", theme.CLASS_PANEL)
    # Without this a plain QWidget ignores the background and border from the
    # style sheet entirely - it paints its parent's fill and nothing else.
    # Every zone in the window depends on it, and its absence is invisible in
    # code and obvious on screen.
    container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    outer = QVBoxLayout(container)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    head = QWidget()
    head.setProperty("class", theme.CLASS_PANEL_HEAD)
    head.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    head_layout = QHBoxLayout(head)
    head_layout.setContentsMargins(14, 9, 14, 9)
    head_layout.setSpacing(8)
    label = QLabel(title)
    label.setProperty("class", theme.CLASS_HEADING)
    head_layout.addWidget(label)
    head_layout.addStretch(1)
    if trailing is not None:
        head_layout.addWidget(trailing)
    outer.addWidget(head)

    body = QWidget()
    body.setProperty("class", theme.CLASS_PANEL_BODY)
    body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    body_layout = QVBoxLayout(body)
    body_layout.setContentsMargins(0, 0, 0, 0)
    body_layout.setSpacing(0)
    outer.addWidget(body, stretch=1)
    return container, body_layout, label


class SeverityBar(QWidget):
    """One bar showing how a run's findings divide between severities.

    The design puts this beside the finding count, and it answers a question
    the count alone cannot: 27 findings that are all minor and 27 that are
    all critical are the same number and a different afternoon.

    Painted rather than built from four child widgets. The segments have to
    share a rounded outline - the ends of the bar are round, the joins
    between segments are square - which four rounded rectangles cannot do,
    and a run with no findings of a given severity must contribute no sliver
    at all rather than a 1px one.

    The order is fixed and is the order of consequence, worst first. It is
    not sorted by size: a bar whose colours moved between runs would say
    nothing about whether things got better.
    """
    #: Severity key -> the palette field that paints it. The audit's four
    #: levels (`audit/base.py`) and the design's four-step ramp are the same
    #: four, in the same order, which is why neither needed adjusting.
    LEVELS = (
        ("critical", "sev_critical"),
        ("serious", "sev_high"),
        ("moderate", "sev_medium"),
        ("minor", "sev_none"),
    )

    HEIGHT = 6
    WIDTH = 190

    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self._counts: dict = {}
        self.setFixedSize(QSize(self.WIDTH, self.HEIGHT))

    def set_palette(self, palette) -> None:
        self.palette_ = palette
        self.update()

    def set_counts(self, counts: dict) -> None:
        """`counts` maps a severity key to how many findings carry it."""
        self._counts = {key: int(counts.get(key, 0)) for key, _field in self.LEVELS}
        self.setToolTip(", ".join(f"{key}: {value}"
                                  for key, value in self._counts.items() if value))
        self.update()

    def total(self) -> int:
        return sum(self._counts.values())

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        radius = self.height() / 2

        track = QPainterPath()
        track.addRoundedRect(QRectF(self.rect()), radius, radius)
        painter.fillPath(track, QColor(self.palette_.bg_muted))

        total = self.total()
        if total <= 0:
            painter.end()
            return

        # Clip to the rounded track, then fill flat rectangles inside it, so
        # the bar keeps one outline instead of four.
        painter.setClipPath(track)
        x = 0.0
        width = float(self.width())
        for key, field in self.LEVELS:
            count = self._counts.get(key, 0)
            if not count:
                continue
            span = width * count / total
            painter.fillRect(QRectF(x, 0, span, float(self.height())),
                             QColor(getattr(self.palette_, field)))
            x += span
        painter.end()


def hairline(height: int = 13):
    """The 1px rule that stands between two inline values.

    Its own helper rather than a reuse of `divider()` below: that one is the
    full-width horizontal rule between sections, this one is a short vertical
    tick inside a filled strip, and they take their colour from different
    tokens (`--divider` against `--border`) because the design separates the
    two ideas.
    """
    from PySide6.QtWidgets import QFrame

    line = QFrame()
    line.setProperty("class", theme.CLASS_HAIRLINE)
    line.setFixedWidth(1)
    line.setFixedHeight(height)
    return line


class InlineValue(QWidget):
    """A selector drawn as part of a sentence instead of as a combo box.

    The design's top row reads "аналізувати Сайт · xformat.net · глибина 2",
    where every emphasised word is actually a control. So this paints three
    inks - the label muted, the value at full strength, a subtle caret - and
    opens a menu when activated.

    Why not a restyled `QComboBox`: a combo box insists on a frame, a fixed
    popup geometry and a size hint built from its longest item, and the three
    are exactly what this must not have. What it *does* keep from one is the
    behaviour - focusable, arrow keys and Space/Enter open the menu - because
    an app that reports missing keyboard access on other people's pages
    cannot ship a control reachable only by mouse.
    """
    #: The index the user picked. Named like `QComboBox.currentIndexChanged`
    #: so the wiring in `main_window` reads the same for both.
    currentIndexChanged = Signal(int)  # noqa: N815 - matches Qt's spelling

    def __init__(self, label: str = "", parent=None):
        super().__init__(parent)
        self.setProperty("class", theme.CLASS_INLINE_FIELD)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self._items: list = []
        #: Per-item tooltips, index-aligned with `_items`. A parallel list
        #: rather than a third element in the tuple: only one selector in
        #: the window sets them, and every other read of `_items` unpacks
        #: exactly two values.
        self._tips: list = []
        self._index = -1

        row = QHBoxLayout(self)
        row.setContentsMargins(2, 1, 2, 1)
        row.setSpacing(3)

        self._label = QLabel(label)
        self._label.setProperty("class", theme.CLASS_INLINE_LABEL)
        row.addWidget(self._label)
        self._label.setVisible(bool(label))

        self._value = QLabel()
        self._value.setProperty("class", theme.CLASS_INLINE_VALUE)
        row.addWidget(self._value)

        # A down-pointing triangle rather than an icon: it has to sit on the
        # text baseline at 9px, which an SVG at that size renders as mush.
        self._caret = QLabel("▾")
        self._caret.setProperty("class", theme.CLASS_INLINE_CARET)
        row.addWidget(self._caret)

    # -- content ---------------------------------------------------------

    def set_label(self, text: str) -> None:
        self._label.setText(text)
        self._label.setVisible(bool(text))

    def set_items(self, items, index: int = 0) -> None:
        """`items` is a sequence of (text, data) pairs or plain strings."""
        self._items = [(item, item) if isinstance(item, str) else tuple(item)
                       for item in items]
        self._tips = [""] * len(self._items)
        self._index = -1
        self.set_index(index if self._items else -1, notify=False)

    def set_index(self, index: int, notify: bool = True) -> None:
        if not self._items:
            self._index = -1
            self._value.setText("")
            self._caret.setVisible(False)
            return
        index = max(0, min(len(self._items) - 1, index))
        self._caret.setVisible(len(self._items) > 1)
        if index == self._index:
            return
        self._index = index
        self._value.setText(self._items[index][0])
        self.setAccessibleName(f"{self._label.text()} {self._items[index][0]}".strip())
        if notify:
            self.currentIndexChanged.emit(index)

    def current_index(self) -> int:
        return self._index

    def current_data(self):
        return self._items[self._index][1] if 0 <= self._index < len(self._items) else None

    def set_value_text(self, text: str) -> None:
        """Show a value that is not one of the items - the scanned URL, say.

        Kept separate from `set_items` so a free-text value cannot be
        mistaken for a choice: with no items there is no caret and no menu,
        and the widget is a label that happens to live in the same strip.
        """
        self._items = []
        self._tips = []
        self._index = -1
        self._value.setText(text)
        self._caret.setVisible(False)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.ArrowCursor)

    # -- QComboBox compatibility -----------------------------------------
    #
    # The window addresses its selectors by name (`self.mode_combo`,
    # `self.method_combo`, ...) and so do the mixins, the panels and four
    # test files. Giving this widget the same handful of methods a combo box
    # is actually asked for lets it be swapped in without renaming any of
    # them - the alternative was a hidden combo box shadowing every visible
    # selector, kept in sync by hand, which is two sources of truth for one
    # value. The Qt spelling is kept deliberately, including the camelCase.

    def addItem(self, text: str, userData=None) -> None:  # noqa: N802,N803 - Qt's spelling
        # `userData`, not `data`: call sites pass it by keyword, in Qt's
        # spelling, and a parameter named anything else fails only at the
        # ones that do - which is a handful of lines in the whole window.
        self._items.append((text, text if userData is None else userData))
        self._tips.append("")
        if self._index < 0:
            self.set_index(0, notify=False)
        else:
            # A second item turns a fixed value into a choice.
            self._caret.setVisible(len(self._items) > 1)

    def clear(self) -> None:
        self._items = []
        self._tips = []
        self._index = -1
        self._value.setText("")
        self._caret.setVisible(False)

    def count(self) -> int:
        return len(self._items)

    def itemData(self, index: int,  # noqa: N802 - Qt's spelling
                 role=Qt.ItemDataRole.UserRole):
        if not 0 <= index < len(self._items):
            return None
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._tips[index]
        return self._items[index][1]

    def itemText(self, index: int) -> str:  # noqa: N802 - Qt's spelling
        return self._items[index][0] if 0 <= index < len(self._items) else ""

    def setItemData(self, index: int, value,  # noqa: N802 - Qt's spelling
                    role=Qt.ItemDataRole.UserRole) -> None:
        """Repoint an existing row's payload, leaving its text alone.

        The `role` argument is Qt's, and both roles the window actually uses
        are honoured: `UserRole` is the value the row stands for, and
        `ToolTipRole` is the long form of a scope name, which the menu shows
        on hover. Any other role is accepted and dropped rather than stored
        under a key nothing will ever read.
        """
        if not 0 <= index < len(self._items):
            return
        if role == Qt.ItemDataRole.ToolTipRole:
            self._tips[index] = value
        elif role == Qt.ItemDataRole.UserRole:
            self._items[index] = (self._items[index][0], value)

    def setItemText(self, index: int, text: str) -> None:  # noqa: N802 - Qt's spelling
        if 0 <= index < len(self._items):
            self._items[index] = (text, self._items[index][1])
            if index == self._index:
                self._value.setText(text)
                self.setAccessibleName(f"{self._label.text()} {text}".strip())

    def findData(self, data) -> int:  # noqa: N802 - Qt's spelling
        """The index holding `data`, or -1. Same contract as Qt's, including
        the -1: callers already branch on it."""
        for position, (_text, value) in enumerate(self._items):
            if value == data:
                return position
        return -1

    def currentIndex(self) -> int:  # noqa: N802 - Qt's spelling
        return self._index

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802 - Qt's spelling
        self.set_index(index)

    def currentData(self):  # noqa: N802 - Qt's spelling
        return self.current_data()

    def currentText(self) -> str:  # noqa: N802 - Qt's spelling
        return self._value.text()

    def setSizeAdjustPolicy(self, _policy) -> None:  # noqa: N802 - Qt's spelling
        """Accepted and ignored. A combo box sizes itself from its longest
        item; an inline value is as wide as the value it is showing, which is
        the whole point of it. Kept so the call sites read the same for both
        and nobody has to remember which selector is which."""

    def setMinimumContentsLength(self, _chars: int) -> None:  # noqa: N802 - Qt's spelling
        """Accepted and ignored, for the same reason as above."""

    # -- interaction -----------------------------------------------------

    def _open_menu(self) -> None:
        if len(self._items) < 2:
            return
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        # Qt hides action tooltips in menus unless asked; the scope names are
        # abbreviations, and the long form is the only thing that says what
        # they mean.
        menu.setToolTipsVisible(True)
        for position, (text, _data) in enumerate(self._items):
            action = menu.addAction(text)
            action.setCheckable(True)
            action.setChecked(position == self._index)
            if self._tips[position]:
                action.setToolTip(self._tips[position])
            action.triggered.connect(
                lambda _checked=False, chosen=position: self.set_index(chosen))
        menu.exec(self.mapToGlobal(QPoint(0, self.height())))

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.LeftButton:
            self._open_menu()
            event.accept()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override
        key = event.key()
        if key in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Down):
            self._open_menu()
            event.accept()
            return
        # Left/right step through the choices without opening anything, the
        # way a native combo does when it has focus.
        if key == Qt.Key_Left and self._index > 0:
            self.set_index(self._index - 1)
            event.accept()
            return
        if key == Qt.Key_Right and 0 <= self._index < len(self._items) - 1:
            self.set_index(self._index + 1)
            event.accept()
            return
        super().keyPressEvent(event)


def divider():
    """A hairline between two things inside one zone."""
    from PySide6.QtWidgets import QFrame

    line = QFrame()
    line.setProperty("class", theme.CLASS_DIVIDER)
    line.setFrameShape(QFrame.Shape.NoFrame)
    line.setFixedHeight(1)
    return line


def chip(text: str = "") -> QLabel:
    """A quiet pill: a rule id, an engine name, a position in a file."""
    label = QLabel(text)
    label.setProperty("class", theme.CLASS_CHIP)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


def field(label_text: str, body_text: str) -> QWidget:
    """One labelled block of an explanation.

    Four of these make the detail panel, and they are boxed rather than run
    together as paragraphs because they answer four different questions. A
    reader looking for "how do I fix this" should find it without reading the
    three above it.
    """
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    container = QWidget()
    container.setProperty("class", theme.CLASS_FIELD)
    container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(12, 10, 12, 12)
    layout.setSpacing(4)

    caption = QLabel(label_text.upper())
    caption.setProperty("class", theme.CLASS_FIELD_LABEL)
    layout.addWidget(caption)

    body = QLabel(body_text)
    body.setWordWrap(True)
    # Plain text, explicitly. Qt auto-detects rich text, and these
    # explanations are *about* markup: the fix for a missing language
    # attribute is the sentence «add <html lang="uk">», and Qt rendered that
    # as an HTML tag - so the one thing the reader needed vanished and the
    # sentence ended in a bare colon. Every explanation carrying an example
    # tag was silently truncated the same way.
    body.setTextFormat(Qt.TextFormat.PlainText)
    body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    layout.addWidget(body)
    return container


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


class FlowLayout(QLayout):
    """A row that wraps instead of squeezing.

    `QHBoxLayout` answers "not enough width" by shrinking its children, which
    for a toolbar means labels clipped to nothing and, for a row of chips, a
    column that cannot narrow past the sum of its pills. Neither is a layout
    decision anyone would make on purpose; they are what happens when a row has
    no way to become two rows.

    This is the standard flow layout: place items left to right, break when the
    next one would not fit, and report the height that width implies. The height
    depends on the width, which is the whole point and also the reason
    `hasHeightForWidth` has to say so - a parent that does not ask will hand out
    a single row's height and clip everything below it.
    """

    def __init__(self, parent=None, margin: int = 0, spacing: int = 6):
        super().__init__(parent)
        self._items: list = []
        self.setContentsMargins(margin, margin, margin, margin)
        self._spacing = spacing

    # --- QLayout plumbing. Qt owns the items once they are added.
    def addItem(self, item) -> None:  # noqa: N802 - Qt's spelling
        self._items.append(item)

    def insertWidget(self, index: int, widget) -> None:  # noqa: N802 - Qt's spelling
        """Put a widget back where it was.

        `QBoxLayout` has this and `QLayout` does not, so a widget lent to
        another layout and returned would always come back last. The toolbar
        lends its Analyze button to the setup screen, and Analyze arriving
        back after Cancel is a row nobody laid out.
        """
        self.addWidget(widget)          # reparents and appends, as Qt wants
        item = self._items.pop()
        self._items.insert(max(0, min(index, len(self._items))), item)
        self.invalidate()

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientations(Qt.Orientation(0))

    def setSpacing(self, spacing: int) -> None:  # noqa: N802
        self._spacing = spacing

    def spacing(self) -> int:
        return self._spacing

    # --- the part that matters
    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._layout(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._layout(rect, apply=True)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        # The widest single item, not the sum: a row that can wrap is only as
        # wide as the one thing that cannot be broken. A hidden item cannot
        # be "the one thing" - it contributes no pixels to any line, which is
        # exactly what `_layout` below already assumes; this skips it for the
        # same reason, so a collapsed "Advanced" section never sets a floor
        # under the row that shows it.
        size = QSize(0, 0)
        for item in self._items:
            widget = item.widget()
            if widget is not None and widget.isHidden():
                continue
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(),
                            margins.top() + margins.bottom())

    def _layout(self, rect, apply: bool) -> int:
        """Place the items and return the height the given width implies.

        Two passes per line, because the items on one line have different
        heights: a label is shorter than the combo it names, and placing both
        at the top of the line leaves the label floating above the field's
        centre. So a line is collected first, then placed centred in it.
        """
        margins = self.contentsMargins()
        left = rect.x() + margins.left()
        top = rect.y() + margins.top()
        right = rect.right() - margins.right()

        x, y = left, top
        line: list = []
        line_height = 0

        def flush() -> None:
            if not apply:
                return
            for item, item_x, hint in line:
                offset = (line_height - hint.height()) // 2
                item.setGeometry(QRect(QPoint(item_x, y + offset), hint))

        for item in self._items:
            widget = item.widget()
            if widget is not None and widget.isHidden():
                continue
            hint = item.sizeHint()
            if x > left and x + hint.width() > right:
                flush()
                line = []
                x = left
                y += line_height + self._spacing
                line_height = 0
            line.append((item, x, hint))
            x += hint.width() + self._spacing
            line_height = max(line_height, hint.height())

        flush()
        return y + line_height - rect.y() + margins.bottom()


class Switch(QAbstractButton):
    """A setting that is on or off, drawn as the design draws it (3d, 3q).

    A checkbox would carry the same value and read as a different kind of
    decision: a box in a list is one of several things you are choosing,
    while a switch at the end of a row is that row's state. The settings
    screen is rows, so it gets switches.

    Painted rather than styled: a QSS checkbox indicator is a fixed-size
    image slot, and the travelling knob would have to be two static images
    that cannot follow the palette.
    """

    #: The artboard's own numbers (3d, 3q): a 30x18 track with a 14px knob
    #: and 2px of padding. Not "about right" - the switch sits at the end of
    #: a row of text, and a taller one makes every row taller.
    WIDTH = 30
    HEIGHT = 18
    KNOB = 14

    def __init__(self, palette=None, parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(QSize(self.WIDTH, self.HEIGHT))

    def set_palette(self, palette) -> None:
        self.palette_ = palette
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        radius = self.height() / 2
        track = QRectF(0, 0, float(self.width()), float(self.height()))

        # Read from the palette, and the palette carries the artboard's
        # values: `accent` #4b46b8 on, `divider` #e2ded7 off, white knob.
        palette = self.palette_
        on = QColor(palette.accent if palette else "#4b46b8")
        off = QColor(palette.divider if palette else "#e2ded7")
        knob = QColor(palette.on_accent if palette else "#ffffff")
        if not self.isEnabled():
            on.setAlpha(90)
            off.setAlpha(90)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(on if self.isChecked() else off)
        painter.drawRoundedRect(track, radius, radius)

        inset = 2.0
        diameter = float(self.KNOB)
        x = (self.width() - diameter - inset) if self.isChecked() else inset
        painter.setBrush(knob)
        painter.drawEllipse(QRectF(x, inset, diameter, diameter))
        painter.end()


class Segmented(QWidget):
    """Two to four exclusive choices shown side by side, all of them visible.

    The design uses it where a dropdown would hide the alternatives behind a
    click even though there are only three of them - the theme, the effort a
    model spends. A combo box is right when the list is long or open-ended;
    this is right when seeing the options *is* the explanation.
    """

    changed = Signal(object)

    def __init__(self, options=(), parent=None):
        super().__init__(parent)
        self.setProperty("class", theme.CLASS_SEGMENTED)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 2, 2, 2)
        row.setSpacing(2)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self._buttons: list = []
        for index, (label, value) in enumerate(options):
            button = QPushButton(label)
            button.setProperty("class", theme.CLASS_SEGMENT)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setProperty("value", value)
            self.group.addButton(button, index)
            row.addWidget(button)
            self._buttons.append(button)
        self.group.idClicked.connect(self._on_clicked)

    def _on_clicked(self, index: int) -> None:
        self.changed.emit(self.current_data())

    def set_current_data(self, value) -> None:
        for button in self._buttons:
            if button.property("value") == value:
                button.setChecked(True)
                return
        if self._buttons:
            self._buttons[0].setChecked(True)

    def current_data(self):
        for button in self._buttons:
            if button.isChecked():
                return button.property("value")
        return None
