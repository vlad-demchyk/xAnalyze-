"""What a run produced: one folder, and the documents inside it.

Before this the window had a report button and a save dialog behind it,
which asks the wrong question. A run does not produce *a file* - it produces
a set of documents that only mean something together, and where they go is
already decided: one folder per target, one sub-folder per run, the layout
`cli_impl.runfolder` describes and the CLI already writes. Asking where to
save each one is how the four documents of a run end up in four places.

So this panel (artboard 3h) does not offer to save anything. The documents
are already on disk by the time it appears; it says where, which of the four
are there, and what each of them is for. The only action left is opening the
folder.

The fourth document is the interesting one. `changes.md` is written only
when there is an earlier run of the same target to compare against, so a
first run legitimately has three documents and not four. It is listed anyway,
greyed, with the reason: a reader who knows there should be a comparison and
sees no mention of one cannot tell a first run from a broken comparison.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from i18n.translations import t
from ui import theme
from ui.widgets import FlowLayout

#: Why a document is not on disk. Each is a different piece of news, and the
#: one thing they must not do is look like each other.
NO_AUDIT, FIRST_RUN, NOT_COMPARABLE = "no_audit", "first_run", "not_comparable"

_REASON_STRING = {
    NO_AUDIT: "documents_absent_no_audit",
    FIRST_RUN: "documents_absent_first_run",
    NOT_COMPARABLE: "documents_absent_not_comparable",
}


def _duration(seconds: float) -> str:
    """`93.4` -> `1m 33s`, the same shape `timings.md` uses.

    Deliberately the same: the panel and the document are describing one set
    of numbers, and two spellings of "a minute and a half" beside each other
    read as two different measurements.
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, rest = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {rest:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m {rest:02d}s"


class TimingBar(QWidget):
    """One stage's share of the run, drawn to scale.

    Drawn rather than written as a percentage because the question is which
    stage the time went into, and four bars answer that before four numbers
    can be read. The number stays beside it: the bar says which, the number
    says how much.
    """

    HEIGHT = 6

    def __init__(self, palette, parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self._share = 0.0
        self.setFixedHeight(self.HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Fixed)

    def set_share(self, share: float) -> None:
        self._share = max(0.0, min(1.0, share))
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt's spelling
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        radius = self.HEIGHT / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.palette_.bg_muted))
        painter.drawRoundedRect(self.rect(), radius, radius)
        filled = int(self.width() * self._share)
        if filled > 0:
            painter.setBrush(QColor(self.palette_.accent))
            painter.drawRoundedRect(0, 0, max(filled, self.HEIGHT),
                                    self.HEIGHT, radius, radius)
        painter.end()

    def apply_palette(self, palette) -> None:
        self.palette_ = palette
        self.update()


class DocumentRow(QWidget):
    """One of the four documents: its name, and whether it is there."""

    def __init__(self, name: str, palette, lang: str = "en", parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self.lang = lang
        self.name = name
        self.path = None
        self.reason = None

        # Two lines, not one. The reason a document is absent is a
        # sentence, and a sentence beside a file name in one row hands this
        # widget's parent the sum of both - which, through the stacked
        # widget it lives in, becomes a floor under the whole window's
        # minimum width. The name is what is scanned; the reason is read
        # only when the name is not there.
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 1, 0, 1)
        column.setSpacing(0)

        top = QWidget()
        row = QHBoxLayout(top)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.mark = QLabel()
        self.mark.setFixedWidth(14)
        row.addWidget(self.mark)

        self.label = QLabel(name)
        row.addWidget(self.label)
        row.addStretch(1)
        column.addWidget(top)

        self.note = QLabel()
        self.note.setProperty("class", theme.CLASS_MUTED)
        self.note.setWordWrap(True)
        self.note.setContentsMargins(22, 0, 0, 0)
        column.addWidget(self.note)

        self.set_state(None, None)

    def set_state(self, path, reason) -> None:
        self.path, self.reason = path, reason
        self.mark.setText("✓" if path else "·")
        key = _REASON_STRING.get(reason)
        self.note.setText(t(key, self.lang) if key else "")
        self.note.setVisible(bool(key))
        self.apply_palette(self.palette_)

    def retranslate(self, lang: str) -> None:
        self.lang = lang
        self.set_state(self.path, self.reason)

    def apply_palette(self, palette) -> None:
        self.palette_ = palette
        ink = palette.text if self.path else palette.text_subtle
        self.label.setStyleSheet(f"color: {ink};")
        self.mark.setStyleSheet(f"color: {ink};")


class RunDocumentsPanel(QWidget):
    """The run's folder, its four documents, and where the time went."""

    def __init__(self, palette, lang: str = "en", parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self.lang = lang
        self.documents = None
        self._rows: dict = {}
        self._timing_widgets: list = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 12)
        outer.setSpacing(10)

        self.target_label = QLabel()
        self.target_label.setProperty("class", theme.CLASS_HEADING)
        self.target_label.setWordWrap(True)
        outer.addWidget(self.target_label)

        # No section label over the list: the column header above already
        # says "Run documents", and four file names with a tick beside them
        # read as a list of files without being told that they are one.
        self.documents_box = QWidget()
        documents_layout = QVBoxLayout(self.documents_box)
        documents_layout.setContentsMargins(0, 0, 0, 0)
        documents_layout.setSpacing(1)
        # Built once and refilled, not rebuilt per run: the four names are a
        # fixed set, and a list that is torn down and re-created is a list
        # that can come back in a different order.
        from cli_impl.runfolder import RunDocuments
        for name in RunDocuments.ORDER:
            row = DocumentRow(name, palette, lang)
            self._rows[name] = row
            documents_layout.addWidget(row)
        outer.addWidget(self.documents_box)

        self.folder_label = QLabel()
        self.folder_label.setProperty("class", theme.CLASS_CODE)
        self.folder_label.setWordWrap(True)
        # Selectable: the path is the thing someone wants to paste into a
        # terminal, and a label they cannot copy sends them back to the
        # file manager to find a folder the window is already showing them.
        self.folder_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        outer.addWidget(self.folder_label)

        buttons = QWidget()
        # Wrapping, not a row. A `QHBoxLayout` hands its parent the sum of
        # its children's minimum widths, and a stacked widget takes the
        # widest of all its pages - so two buttons side by side here put a
        # 268px floor under the whole window, which is the same defect the
        # top row had and the reason `FlowLayout` exists in this codebase.
        button_row = FlowLayout(buttons, margin=0, spacing=6)
        self.open_folder_btn = QPushButton()
        self.open_folder_btn.clicked.connect(self._on_open_folder)
        button_row.addWidget(self.open_folder_btn)
        # Not in the mockup, which is one screen with nowhere else to be.
        # In the window this panel takes over a column that has another job,
        # so there has to be a way to give it back.
        self.back_btn = QPushButton()
        self.back_btn.setProperty("class", theme.CLASS_QUIET)
        button_row.addWidget(self.back_btn)
        outer.addWidget(buttons)

        self.timings_title = QLabel()
        self.timings_title.setProperty("class", theme.CLASS_FIELD_LABEL)
        outer.addWidget(self.timings_title)

        self.timings_box = QWidget()
        self.timings_layout = QVBoxLayout(self.timings_box)
        self.timings_layout.setContentsMargins(0, 0, 0, 0)
        self.timings_layout.setSpacing(3)
        outer.addWidget(self.timings_box)

        self.handoff = QLabel()
        self.handoff.setProperty("class", theme.CLASS_MUTED)
        self.handoff.setWordWrap(True)
        outer.addWidget(self.handoff)

        outer.addStretch(1)
        self.retranslate(lang)

    # -- content ---------------------------------------------------------

    def retranslate(self, lang: str) -> None:
        self.lang = lang
        self.timings_title.setText(t("documents_timings", lang))
        self.open_folder_btn.setText(t("documents_open", lang))
        self.back_btn.setText(t("documents_back", lang))
        self.handoff.setText(t("documents_handoff", lang))
        for row in self._rows.values():
            row.retranslate(lang)
        if self.documents is not None:
            self.target_label.setText(self._title_for(self.documents))

    def show_documents(self, documents) -> None:
        """Take a `cli_impl.runfolder.RunDocuments` and say what is in it."""
        self.documents = documents
        self.target_label.setText(self._title_for(documents))
        self.folder_label.setText(str(documents.folder.run))
        for name, path, reason in documents.documents():
            row = self._rows.get(name)
            if row is not None:
                row.set_state(path, reason)

    @staticmethod
    def _title_for(documents) -> str:
        """The target and when the run happened.

        The stamp is read off the folder name rather than kept beside it:
        the folder name *is* the run's identity, and a second copy of the
        time is a second thing that can disagree with it.
        """
        stamp = documents.folder.run.name
        return f"{documents.target}  ·  {stamp}" if stamp else documents.target

    def set_timings(self, stages) -> None:
        """`stages` is a sequence of `(label, seconds)`, in run order.

        Shares are of the sum of the stages shown, not of the run's total.
        The bars sit beside each other and are read against each other, and
        against a total that includes time no bar accounts for they would
        never fill the row - which reads as "every stage was fast" on a run
        that took an hour.
        """
        while self.timings_layout.count():
            item = self.timings_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Unparented before deleting: `deleteLater` only schedules
                # it, and until then the previous run's rows are still
                # visible children at their old geometry.
                widget.setParent(None)
                widget.deleteLater()
        self._timing_widgets = []
        stages = [(label, seconds) for label, seconds in stages
                  if seconds is not None]
        total = sum(seconds for _label, seconds in stages)
        self.timings_box.setVisible(bool(stages))
        self.timings_title.setVisible(bool(stages))
        for label, seconds in stages:
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)
            name = QLabel(label)
            name.setProperty("class", theme.CLASS_MUTED)
            name.setFixedWidth(120)
            layout.addWidget(name)
            bar = TimingBar(self.palette_)
            bar.set_share(seconds / total if total else 0.0)
            layout.addWidget(bar, stretch=1)
            value = QLabel(_duration(seconds))
            value.setProperty("class", theme.CLASS_MUTED)
            layout.addWidget(value)
            self.timings_layout.addWidget(row)
            self._timing_widgets.append(bar)

    # -- actions ---------------------------------------------------------

    def _on_open_folder(self) -> None:
        if self.documents is None:
            return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self.documents.folder.run)))

    def apply_palette(self, palette) -> None:
        self.palette_ = palette
        for row in self._rows.values():
            row.apply_palette(palette)
        for bar in self._timing_widgets:
            bar.apply_palette(palette)
