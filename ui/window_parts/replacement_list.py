"""The replacement list: read it before anything is written (artboard 3l).

Writing to somebody's repository used to be a message box with a number in
it. The number was true and useless: it said how many passages would change
and not one of the things a person needs to know before saying yes - which
files, what the text is now, what it would become, and which of the changes
a model made up.

So the screen is a list, and the list is the confirmation. Four columns,
because those are the four questions: **where**, **was**, **becomes**,
**source**. The tick in front of every row is the answer, and the button
says how many ticks it is about to write, so the promise on the button and
the state of the list cannot drift apart.

What is selected when it opens is the argument of the whole screen.
Mechanical rows are ticked, because a derived correction does not need
review to be right. Model drafts are not, because a fluent sentence is not a
correct one. Decisions cannot be ticked at all: `alt=""` on a photograph
would satisfy the audit and hide the picture from everyone who cannot see
it, so the row shows what has to be decided instead of a replacement it does
not have.

`Save to file` writes the same list as Markdown. It is the export the old
flow ended with, kept because the review often happens somewhere else - a
pull request, a ticket, a colleague's screen - and now it can happen without
the window still being open.
"""
from __future__ import annotations

import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

import replacements
from i18n.translations import t
from ui import theme
from ui.widgets import muted

#: The source column's width. Fixed, because it is the answer to "did a
#: model write this" and the one column that must be readable in every row.
_SOURCE_WIDTH = 130

class Cell(QLabel):
    """One column of one row: plain text, elided to the width it is given.

    Both of these are load-bearing and both were wrong when the screen was
    first rendered. A `QLabel` guesses its format from the string, so
    `<img src="/icon.svg">` was drawn *as an image* - the markup rows, which
    are half the list, showed a broken-image icon where the element should
    be. And a label asks for the width of its whole text, so one rewritten
    paragraph pushed the source column off the right-hand edge of the screen
    and put a horizontal scrollbar under everything.

    The full text stays in the tooltip, which is where a passage too long
    for a column can still be read.
    """

    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self._full = ""
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored,
                           QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 - Qt's spelling
        self._full = text or ""
        self.setToolTip(self._full)
        self._elide()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        one_line = " ".join(self._full.split())
        QLabel.setText(self, self.fontMetrics().elidedText(
            one_line, Qt.TextElideMode.ElideRight, max(0, self.width() - 2)))


class ReplacementRow(QWidget):
    """One pending change, with the tick that decides whether it happens."""

    def __init__(self, item, lang: str = "en", parent=None):
        super().__init__(parent)
        self.item = item

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 5, 8, 5)
        row.setSpacing(8)

        self.check = QCheckBox()
        self.check.setChecked(item.selected)
        # A decision has no text to write, so the tick is not disabled as a
        # policy - there is literally nothing for it to mean.
        self.check.setEnabled(item.writable)
        row.addWidget(self.check)

        self.where = Cell(item.where)
        self.where.setProperty("class", theme.CLASS_CODE)
        row.addWidget(self.where, stretch=3)

        self.before = Cell(item.before)
        self.before.setProperty("class", theme.CLASS_CODE)
        row.addWidget(self.before, stretch=4)

        if item.source == replacements.DECISION:
            self.after = Cell(t("replacements_decision", lang,
                                reason=item.reason
                                or t("replacements_no_text", lang)))
            self.after.setProperty("class", theme.CLASS_MUTED)
        else:
            self.after = Cell(item.after)
            self.after.setProperty("class", theme.CLASS_CODE)
        row.addWidget(self.after, stretch=4)

        # Not a `Cell`: the source is three known words in three languages,
        # and it is the column that must never be the one that gives way.
        # The chip keeps its own width and the column keeps the chip, which
        # is why the label sits in a holder rather than being stretched to
        # the column - a chip as wide as its column reads as a text field.
        self.source = QLabel(t(f"replacements_source_{item.source}", lang))
        self.source.setProperty("class", theme.CLASS_CHIP)
        self.source.setTextFormat(Qt.TextFormat.PlainText)
        holder = QWidget()
        holder.setFixedWidth(_SOURCE_WIDTH)
        holder_row = QHBoxLayout(holder)
        holder_row.setContentsMargins(0, 0, 0, 0)
        holder_row.addWidget(self.source)
        holder_row.addStretch(1)
        row.addWidget(holder)


class ReplacementListDialog(QDialog):
    """Every pending change of this run, and the two things to do with them."""

    def __init__(self, items, skipped=None, lang: str = "en",
                 root: str | None = None, palette=None, parent=None):
        super().__init__(parent)
        self.items = list(items)
        self.skipped = list(skipped or [])
        self.lang = lang
        self.root = root
        self.palette_ = palette or getattr(parent, "palette_tokens", None)
        self.rows: list[ReplacementRow] = []
        self.outcome = None

        self.setWindowTitle(t("replacements_title", lang))
        self.resize(1080, 620)

        outer = QVBoxLayout(self)
        outer.setSpacing(8)
        outer.addWidget(self._build_header())
        outer.addWidget(self._build_table(), stretch=1)
        outer.addWidget(self._build_footer())
        self._refresh_counts()

    # ----------------------------------------------------------- building

    def _build_header(self) -> QWidget:
        head = QWidget()
        head.setProperty("class", theme.CLASS_PANEL_HEAD)
        row = QHBoxLayout(head)
        row.setSpacing(8)

        title = QLabel(t("replacements_title", self.lang))
        title.setProperty("class", theme.CLASS_HEADING)
        row.addWidget(title)

        self.summary = muted("")
        self.summary.setWordWrap(True)
        row.addWidget(self.summary, stretch=1)

        self.save_btn = QPushButton(t("replacements_save", self.lang))
        self.save_btn.setProperty("class", theme.CLASS_QUIET)
        self.save_btn.clicked.connect(self._on_save)
        row.addWidget(self.save_btn)

        self.write_btn = QPushButton("")
        self.write_btn.setProperty("class", theme.CLASS_PRIMARY)
        self.write_btn.clicked.connect(self._on_write)
        row.addWidget(self.write_btn)
        return head

    def _build_table(self) -> QWidget:
        pane = QWidget()
        pane.setProperty("class", theme.CLASS_PANEL)
        pane.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        column = QVBoxLayout(pane)
        column.setSpacing(4)

        heads = QHBoxLayout()
        heads.setContentsMargins(8, 0, 8, 0)
        heads.setSpacing(8)
        # An empty label of the tick's width, so every head sits over the
        # column it names rather than one to the left of it.
        self.tick_spacer = QLabel()
        self.tick_spacer.setFixedWidth(20)
        heads.addWidget(self.tick_spacer)
        for key, stretch in (("where", 3), ("before", 4), ("after", 4)):
            label = QLabel(t(f"replacements_column_{key}", self.lang))
            label.setProperty("class", theme.CLASS_FIELD_LABEL)
            heads.addWidget(label, stretch=stretch)
        source_head = QLabel(t("replacements_column_source", self.lang))
        source_head.setProperty("class", theme.CLASS_FIELD_LABEL)
        source_head.setFixedWidth(_SOURCE_WIDTH)
        heads.addWidget(source_head)
        column.addLayout(heads)

        host = QWidget()
        self.rows_layout = QVBoxLayout(host)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(0)
        for item in self.items:
            row = ReplacementRow(item, self.lang, self)
            row.check.toggled.connect(
                lambda checked, r=row: self._on_toggle(r, checked))
            self.rows_layout.addWidget(row)
            self.rows.append(row)
        if not self.rows:
            empty = QLabel(t("replacements_empty", self.lang))
            empty.setProperty("class", theme.CLASS_EMPTY)
            self.rows_layout.addWidget(empty)
        self.rows_layout.addStretch(1)

        self.scroll = scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        # Never sideways: a column that does not fit elides, because a row
        # scrolled off to the right is a row nobody reads before ticking it.
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(host)
        column.addWidget(scroll)
        return pane

    def _build_footer(self) -> QWidget:
        foot = QWidget()
        row = QHBoxLayout(foot)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.footer = muted("")
        self.footer.setWordWrap(True)
        row.addWidget(self.footer, stretch=1)
        self.filename = muted(replacements.default_filename())
        row.addWidget(self.filename)
        return foot

    # ------------------------------------------------------------ counting

    def _on_toggle(self, row: ReplacementRow, checked: bool) -> None:
        row.item.selected = checked
        self._refresh_counts()

    def _refresh_counts(self) -> None:
        totals = replacements.counts(self.items)
        self.summary.setText(t(
            "replacements_summary", self.lang,
            mechanical=totals[replacements.MECHANICAL],
            drafts=totals[replacements.DRAFT],
            decisions=totals[replacements.DECISION]))
        chosen = len(replacements.selected(self.items))
        self.write_btn.setText(t("replacements_write", self.lang, n=chosen))
        self.write_btn.setEnabled(bool(chosen))
        footer = t("replacements_footer", self.lang, n=chosen,
                   total=len(self.items))
        if self.skipped:
            # Named here, never dropped: a finding that could not be turned
            # into an edit is the one thing a review list must not make look
            # handled by leaving it out.
            footer += " · " + t("replacements_unplanned", self.lang,
                                n=len(self.skipped))
        self.footer.setText(footer)

    # ------------------------------------------------------------- actions

    def _on_save(self) -> None:
        suggested = replacements.default_filename(datetime.date.today())
        path, _filter = QFileDialog.getSaveFileName(
            self, t("replacements_save", self.lang), suggested,
            "Markdown (*.md)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(replacements.render_markdown(
                    self.items, root=self.root))
        except OSError as exc:
            QMessageBox.warning(self, t("replacements_title", self.lang), str(exc))
            return
        self.filename.setText(path)
        QMessageBox.information(self, t("replacements_title", self.lang),
                                t("export_list_saved", self.lang, path=path))

    def _on_write(self) -> None:
        chosen = replacements.selected(self.items)
        if not chosen:
            return
        self.outcome = replacements.write(self.items)
        self.accept()
