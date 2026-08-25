"""What a run is doing while it does it: its stages, and its log.

Until now the only answer to "what is it doing" was the status bar, which
holds one line and overwrites it. That is enough to know the run is alive
and not enough to know anything else: which stage it is in, how far through
that stage it is, or what it has already done. A crawl of a large site
spends minutes in one stage, and a single line that changes every few
seconds reads as activity rather than as progress.

The design (artboard 3g) answers it with two lists side by side. The stages
say where the run is in its own plan - what is finished, with what it found,
and what has not started. The log says what just happened, newest first,
which is the part someone watches when they suspect something is wrong.

The stages are declared up front rather than discovered as they happen, and
that is the point: a stage that has not started is still shown, so the list
says how much is left. Discovering them would make the panel grow as the run
progressed, which tells you nothing about what remains.
"""
from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QSizePolicy, QVBoxLayout, QWidget,
)

from i18n.translations import t
from ui import theme

#: A stage that has not begun, is running, or is finished. The three are
#: painted differently rather than labelled: the eye finds "where is it now"
#: on a list of five faster than it reads five words.
PENDING, RUNNING, DONE = "pending", "running", "done"

#: How many lines of log are kept. The log is for "what just happened", and
#: a run over a large site produces thousands of lines - keeping them all
#: would turn a glance into a scroll and hold every URL in memory for the
#: length of the run.
LOG_LIMIT = 200


class StageRow(QWidget):
    """One stage: a mark, its name, and whatever it has to report."""

    #: Drawn rather than written, so the state of five stages is one glance.
    #: A circle for what has not begun, a filled circle for what is running,
    #: a check for what is done.
    MARKS = {PENDING: "○", RUNNING: "●", DONE: "✓"}

    def __init__(self, label: str, palette, parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self.state = PENDING
        self.label = label
        #: When this stage went RUNNING, and how long it ran for once it is
        #: DONE. Measured rather than estimated, because it is what
        #: `timings.md` reports and what someone asking "why did this take an
        #: hour" is owed - a made-up number would answer the question wrongly
        #: and look exactly the same.
        self.began: float | None = None
        self.elapsed: float | None = None

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(8)

        self.mark = QLabel(self.MARKS[PENDING])
        self.mark.setFixedWidth(14)
        row.addWidget(self.mark)

        self.name = QLabel(label)
        row.addWidget(self.name)
        row.addStretch(1)

        self.detail = QLabel()
        self.detail.setProperty("class", theme.CLASS_MUTED)
        row.addWidget(self.detail)

        self.apply_palette(palette)

    def set_state(self, state: str, detail: str = "", now=None) -> None:
        previous = self.state
        if now is None:
            now = time.monotonic()
        if state == RUNNING and previous != RUNNING:
            self.began = now
            self.elapsed = None
        elif state == DONE and previous == RUNNING and self.began is not None:
            self.elapsed = now - self.began
        elif state == PENDING:
            self.began = self.elapsed = None
        self.state = state
        self.mark.setText(self.MARKS.get(state, self.MARKS[PENDING]))
        if detail:
            self.detail.setText(detail)
        self.apply_palette(self.palette_)

    def apply_palette(self, palette) -> None:
        """Ink follows state, not the other way round.

        A pending stage is quiet because it has not happened; a running one
        is at full strength because it is the answer to "what now"; a done
        one steps back again without disappearing, because the run's history
        is the reason to keep it on the list at all.
        """
        self.palette_ = palette
        ink = {
            PENDING: palette.text_subtle,
            RUNNING: palette.text,
            DONE: palette.text_muted,
        }[self.state]
        mark_ink = palette.accent if self.state == RUNNING else ink
        self.name.setStyleSheet(f"color: {ink};")
        self.mark.setStyleSheet(f"color: {mark_ink};")


class RunProgressPanel(QWidget):
    """The stages and the log, for the column that has no preview to show yet."""

    def __init__(self, palette, lang: str = "en", parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self.lang = lang
        self._rows: dict = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 12)
        outer.setSpacing(10)

        self.stages_title = QLabel()
        self.stages_title.setProperty("class", theme.CLASS_FIELD_LABEL)
        outer.addWidget(self.stages_title)

        self.stages_box = QWidget()
        self.stages_layout = QVBoxLayout(self.stages_box)
        self.stages_layout.setContentsMargins(0, 0, 0, 0)
        self.stages_layout.setSpacing(1)
        outer.addWidget(self.stages_box)

        self.log_title = QLabel()
        self.log_title.setProperty("class", theme.CLASS_FIELD_LABEL)
        outer.addWidget(self.log_title)

        self.log = QListWidget()
        self.log.setProperty("class", theme.CLASS_CODE)
        self.log.setSizePolicy(QSizePolicy.Policy.Expanding,
                               QSizePolicy.Policy.Expanding)
        # Nothing in the log is clickable: it is a record, not a list of
        # things to open, and a selectable row invites a click that does
        # nothing.
        self.log.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.log.setFocusPolicy(Qt.NoFocus)
        outer.addWidget(self.log, stretch=1)

        self.retranslate(lang)

    # -- content ---------------------------------------------------------

    def retranslate(self, lang: str) -> None:
        self.lang = lang
        self.stages_title.setText(t("progress_stages", lang))
        self.log_title.setText(t("progress_log", lang))

    def set_stages(self, stages) -> None:
        """`stages` is a sequence of (key, label). Replaces whatever is there.

        Called once at the start of a run, because which stages there are
        depends on what was asked for: a repository scan has no crawl, and a
        run without the accessibility question has no browser pass.
        """
        while self.stages_layout.count():
            item = self.stages_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Unparented before deleting: `deleteLater` only schedules
                # it, so the previous run's stage rows would otherwise stay
                # on screen under the new ones.
                widget.setParent(None)
                widget.deleteLater()
        self._rows = {}
        for key, label in stages:
            row = StageRow(label, self.palette_)
            self._rows[key] = row
            self.stages_layout.addWidget(row)

    def mark(self, key: str, state: str, detail: str = "", now=None) -> None:
        """Move one stage to a state. Unknown keys are ignored.

        Ignored rather than raised: the signals that drive this come from
        four different workers, and a run kind that emits one the panel did
        not list must not take the window down with it.
        """
        row = self._rows.get(key)
        if row is not None:
            row.set_state(state, detail, now)

    def stage_state(self, key: str) -> str:
        row = self._rows.get(key)
        return row.state if row is not None else PENDING

    def add_log(self, message: str, when=None) -> None:
        """One line, stamped, newest first - the order the design shows and
        the order someone watching actually reads."""
        stamp = (when or datetime.now()).strftime("%H:%M:%S")
        self.log.insertItem(0, f"{stamp}  {message}")
        while self.log.count() > LOG_LIMIT:
            self.log.takeItem(self.log.count() - 1)

    def durations(self) -> list:
        """`(label, seconds)` for every stage that actually ran.

        A stage that never started is left out rather than reported as zero:
        a run without the browser pass did not do it in no time, it did not
        do it at all, and a `0.0s` row says the opposite.
        """
        return [(row.label, row.elapsed) for row in self._rows.values()
                if row.elapsed is not None]

    def reset(self) -> None:
        self.log.clear()
        for row in self._rows.values():
            row.set_state(PENDING, "")

    def apply_palette(self, palette) -> None:
        self.palette_ = palette
        for row in self._rows.values():
            row.apply_palette(palette)
