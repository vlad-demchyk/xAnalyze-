"""What went wrong, shown where the run's results are.

A modal was the wrong shape for this. It has one title bar for four
different kinds of news, it interrupts to say something the reader may
already know, and - the part that actually cost something - it is dismissed,
and then the explanation is gone. The window went back to looking exactly
as it does after a run that went fine.

So a diagnosis stays on screen, under the run summary, in the same place a
person is already looking at what the run produced (artboard 3m). Each card
says what happened in words, what it means for the result, the measurements
it was derived from, and the moves that follow.

The evidence line is not translated, on purpose. It is the line a reader
checks the diagnosis against - status codes, addresses, limits - and
translating `429 · /pricing, /docs, +5` would turn evidence into prose.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

import diagnosis as dx
from i18n.translations import t
from ui import theme
from ui.widgets import FlowLayout


class DiagnosisCard(QWidget):
    """One diagnosis: mark, title, what it means, evidence, what to do."""

    #: Drawn rather than written. Every card here is a warning, so the mark
    #: is not what tells them apart - it is what tells the strip apart from
    #: the summary above it at a glance.
    MARK = "!"

    def __init__(self, item, palette, lang: str, panel, parent=None):
        super().__init__(parent)
        self.item = item
        self.palette_ = palette
        self.lang = lang
        self.panel = panel
        self.setProperty("class", theme.CLASS_INSET)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 10)
        outer.setSpacing(3)

        self.title = QLabel(f"{self.MARK}  {t(item.title_key, lang)}")
        self.title.setWordWrap(True)
        outer.addWidget(self.title)

        self.body = QLabel(t(item.body_key, lang, **item.fields))
        self.body.setWordWrap(True)
        self.body.setProperty("class", theme.CLASS_MUTED)
        outer.addWidget(self.body)

        self.evidence = QLabel(t(item.evidence_key, lang, **item.fields)
                               if item.evidence_key else item.evidence)
        self.evidence.setWordWrap(True)
        self.evidence.setProperty("class", theme.CLASS_CODE)
        # Selectable: an address or a status code is the thing someone
        # pastes into a terminal to check for themselves.
        self.evidence.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self.evidence.setVisible(bool(self.evidence.text()))
        outer.addWidget(self.evidence)

        self.actions = QWidget()
        self.actions_layout = FlowLayout(self.actions, margin=0, spacing=6)
        for name in item.actions:
            button = QPushButton(self._action_text(name))
            button.clicked.connect(
                lambda _checked=False, chosen=name: self.panel.run_action(
                    chosen, self.item))
            self.actions_layout.addWidget(button)
        # Dismiss is always offered, and it is the only action every card
        # has: a diagnosis that cannot be put away is a diagnosis that takes
        # a strip of the window for the rest of the session.
        dismiss = QPushButton(t("diagnosis_dismiss", lang))
        dismiss.setProperty("class", theme.CLASS_QUIET)
        dismiss.clicked.connect(self._on_dismiss)
        self.actions_layout.addWidget(dismiss)
        outer.addWidget(self.actions)

        self.apply_palette(palette)

    def _action_text(self, name: str) -> str:
        if name == dx.RAISE_LIMIT:
            return t("diagnosis_raise_limit", self.lang,
                     n=self.item.fields.get("at_least", 0))
        return t(f"diagnosis_{name}", self.lang)

    def _on_dismiss(self) -> None:
        self.panel.dismiss(self.item)

    def apply_palette(self, palette) -> None:
        self.palette_ = palette
        self.title.setStyleSheet(f"color: {palette.amber_text};")


class DiagnosisStripMixin:
    """The strip of diagnoses under the run summary.

    Reads `self.lang`, `self.palette_tokens`, `self.settings` and the
    analyze action from the facade, as the other window mixins do.
    """

    #: How much of the window the strip may take before it scrolls. A run
    #: can legitimately produce three of these at once - refused addresses,
    #: a page that would not render, a crawl cut short - and three cards
    #: stacked pushed the results themselves off the bottom half of the
    #: window, which turns an explanation into an obstacle.
    DIAGNOSIS_MAX_HEIGHT = 230

    def _build_diagnosis_strip(self) -> QWidget:
        from PySide6.QtWidgets import QScrollArea

        self.diagnosis_cards = QWidget()
        self.diagnosis_layout = QVBoxLayout(self.diagnosis_cards)
        self.diagnosis_layout.setContentsMargins(0, 0, 0, 0)
        self.diagnosis_layout.setSpacing(6)

        self.diagnosis_strip = QScrollArea()
        self.diagnosis_strip.setWidgetResizable(True)
        self.diagnosis_strip.setFrameShape(QScrollArea.Shape.NoFrame)
        self.diagnosis_strip.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.diagnosis_strip.setWidget(self.diagnosis_cards)
        self.diagnosis_strip.setVisible(False)
        self._diagnoses = []
        return self.diagnosis_strip

    def show_diagnoses(self, items) -> None:
        """Replace whatever is on the strip with `items`."""
        self._diagnoses = list(items)
        while self.diagnosis_layout.count():
            entry = self.diagnosis_layout.takeAt(0)
            widget = entry.widget()
            if widget is not None:
                # Unparented before deleting: `deleteLater` only schedules
                # it, so the previous run's diagnoses would keep rendering
                # under this run's.
                widget.setParent(None)
                widget.deleteLater()
        for item in self._diagnoses:
            self.diagnosis_layout.addWidget(
                DiagnosisCard(item, self.palette_tokens, self.lang, self))
        # Sized to the cards, up to the cap. Fixed height would leave a band
        # of empty surface under a single card, which reads as something
        # missing.
        self.diagnosis_cards.adjustSize()
        self.diagnosis_strip.setFixedHeight(
            min(self.diagnosis_cards.sizeHint().height() + 6,
                self.DIAGNOSIS_MAX_HEIGHT))
        self.diagnosis_strip.setVisible(bool(self._diagnoses))

    def clear_diagnoses(self) -> None:
        self.show_diagnoses([])

    def dismiss(self, item) -> None:
        self.show_diagnoses([other for other in self._diagnoses
                             if other is not item])

    def run_action(self, name: str, item) -> None:
        """Perform one of a card's moves.

        The card names the move and the window performs it: which moves make
        sense is a property of what went wrong, and how to perform one is a
        property of this window.
        """
        if name == dx.RAISE_LIMIT:
            # Raised to what the crawl actually found, not to some larger
            # round number: the point is to finish this site, and a limit
            # pulled out of the air is the same guess that produced the
            # truncation.
            self.settings.max_pages = max(int(item.fields.get("at_least", 0)),
                                          self.settings.max_pages)
            self.settings.save()
        if name in (dx.RETRY, dx.RAISE_LIMIT):
            self.clear_diagnoses()
            self._on_analyze_clicked()

    def diagnose_finished_run(self, result=None) -> None:
        """After a run: everything worth saying about what it could not read.

        Both halves of a run, because a run can ask both questions: the
        crawl's own account of what it reached, and the audit's account of
        which images it managed to open. Called from either handler, so it
        reads whichever results the window is holding rather than only the
        one that just arrived.
        """
        items = []
        if getattr(self, "result", None) is not None:
            items.extend(dx.diagnose_result(self.result))
        if getattr(self, "audit_result", None) is not None:
            items.extend(dx.diagnose_audit(self.audit_result))
        self.show_diagnoses(items)
