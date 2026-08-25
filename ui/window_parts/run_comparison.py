"""Two runs against each other: fixed, appeared, still there.

The question a second run of the same target is actually asked is not "what
is wrong" - the report answers that - but "did the last round of work
help". Three answers, and they are three because they are acted on
differently: what was fixed is finished, what appeared is new work, and what
has not moved is the list that decides whether the current approach to it is
working at all.

The third one carries how many consecutive runs each rule has survived
(artboard 3n). That number is the difference between "this appeared last
week" and "this has outlived six rounds of work", and only the second is an
argument for changing how it is being approached rather than trying again.

Measurements are shown apart and counted into nothing. `perf-first-paint`
firing on ten pages in one run and none in the next is a warm cache, not
work done, and a comparison that adds it to "fixed" tells the one lie a
comparison must never tell.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from i18n.translations import t
from ui import theme
from ui.widgets import FlowLayout

#: The three sections, in the order they are read: what is finished, what is
#: new, what is still open. Each carries the palette field its mark is drawn
#: in - the sections are told apart at a glance or not at all.
FIXED, APPEARED, UNCHANGED = "fixed", "appeared", "unchanged"

_SECTION_INK = {
    FIXED: "success_text",
    APPEARED: "sev_high",
    UNCHANGED: "text_muted",
}
_SECTION_TITLE = {
    FIXED: "comparison_fixed",
    APPEARED: "comparison_appeared",
    UNCHANGED: "comparison_unchanged",
}


class Section(QWidget):
    """One of the three answers: a heading, a count, and its rules."""

    def __init__(self, kind: str, palette, lang: str = "en", parent=None):
        super().__init__(parent)
        self.kind = kind
        self.palette_ = palette
        self.lang = lang

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        head = QWidget()
        head_row = QHBoxLayout(head)
        head_row.setContentsMargins(0, 0, 0, 0)
        head_row.setSpacing(8)
        self.title = QLabel()
        self.title.setProperty("class", theme.CLASS_FIELD_LABEL)
        head_row.addWidget(self.title)
        head_row.addStretch(1)
        self.count = QLabel()
        self.count.setProperty("class", theme.CLASS_MUTED)
        head_row.addWidget(self.count)
        outer.addWidget(head)

        self.rows = QWidget()
        self.rows_layout = QVBoxLayout(self.rows)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(1)
        outer.addWidget(self.rows)

        self.note = QLabel()
        self.note.setProperty("class", theme.CLASS_MUTED)
        self.note.setWordWrap(True)
        self.note.setVisible(False)
        outer.addWidget(self.note)

        self.retranslate(lang)

    def retranslate(self, lang: str) -> None:
        self.lang = lang
        self.title.setText(t(_SECTION_TITLE[self.kind], lang))

    def set_rules(self, rules, count_text: str, note: str = "") -> None:
        self._clear()
        self.count.setText(count_text)
        for rule in rules:
            self.rows_layout.addWidget(self._row(rule))
        self.note.setText(note)
        self.note.setVisible(bool(note))
        # An empty section is still shown, with its count reading zero. The
        # three are read against each other - "nothing was fixed" is an
        # answer, and a section that vanishes when it is empty makes the
        # reader work out which one is missing.
        self.rows.setVisible(bool(rules))

    def _row(self, rule: dict) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(8)

        title = QLabel(rule.get("title") or rule["rule"])
        title.setWordWrap(True)
        layout.addWidget(title, stretch=1)

        detail = QLabel(self._detail(rule))
        detail.setProperty("class", theme.CLASS_MUTED)
        layout.addWidget(detail)

        value = QLabel(self._value(rule))
        value.setStyleSheet(
            f"color: {getattr(self.palette_, _SECTION_INK[self.kind])};")
        layout.addWidget(value)
        return row

    def _detail(self, rule: dict) -> str:
        if self.kind == UNCHANGED:
            runs = rule.get("runs", 0)
            return t("comparison_runs", self.lang, n=runs) if runs else ""
        # A rule that stopped firing entirely is not in this run, so it has
        # no title and falls back to its id - and printing the id twice on
        # one line reads as two facts when it is one.
        return "" if rule.get("title") == rule["rule"] else rule["rule"]

    def _value(self, rule: dict) -> str:
        if self.kind == UNCHANGED:
            return str(rule.get("count", 0))
        delta = rule.get("delta", 0)
        # Signed, always. "5" beside a rule says nothing about which way it
        # went, and this panel exists entirely to say which way things went.
        return f"{delta:+d}"

    def _clear(self) -> None:
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # Unparented before deleting: `deleteLater` only schedules
                # it, so the previous comparison's rows would stay on screen
                # underneath this one's.
                widget.setParent(None)
                widget.deleteLater()

    def apply_palette(self, palette) -> None:
        self.palette_ = palette


class RunComparisonPanel(QWidget):
    """The header, the three sections, and the document behind them."""

    def __init__(self, palette, lang: str = "en", parent=None):
        super().__init__(parent)
        self.palette_ = palette
        self.lang = lang
        self.view = None
        self.changes_path = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 12)
        outer.setSpacing(10)

        self.target_label = QLabel()
        self.target_label.setProperty("class", theme.CLASS_HEADING)
        self.target_label.setWordWrap(True)
        outer.addWidget(self.target_label)

        self.span_label = QLabel()
        self.span_label.setProperty("class", theme.CLASS_MUTED)
        self.span_label.setWordWrap(True)
        outer.addWidget(self.span_label)

        self.total_label = QLabel()
        self.total_label.setProperty("class", theme.CLASS_HEADING)
        outer.addWidget(self.total_label)

        buttons = QWidget()
        button_row = FlowLayout(buttons, margin=0, spacing=6)
        self.changes_btn = QPushButton()
        self.changes_btn.clicked.connect(self._on_open_changes)
        button_row.addWidget(self.changes_btn)
        self.back_btn = QPushButton()
        self.back_btn.setProperty("class", theme.CLASS_QUIET)
        button_row.addWidget(self.back_btn)
        outer.addWidget(buttons)

        # Scrolled: the unchanged list is as long as the target is old, and
        # it is the section most worth reading to the end.
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(12)
        self.sections = {}
        for kind in (FIXED, APPEARED, UNCHANGED):
            section = Section(kind, palette, lang)
            self.sections[kind] = section
            body_layout.addWidget(section)

        self.measurements = QLabel()
        self.measurements.setProperty("class", theme.CLASS_MUTED)
        self.measurements.setWordWrap(True)
        self.measurements.setVisible(False)
        body_layout.addWidget(self.measurements)
        body_layout.addStretch(1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidget(body)
        outer.addWidget(self.scroll, stretch=1)

        self.retranslate(lang)

    # -- content ---------------------------------------------------------

    def retranslate(self, lang: str) -> None:
        self.lang = lang
        self.changes_btn.setText(t("comparison_document", lang))
        self.back_btn.setText(t("documents_back", lang))
        for section in self.sections.values():
            section.retranslate(lang)
        if self.view is not None:
            self.show_comparison(self.view, self.changes_path)

    def show_comparison(self, view: dict, changes_path=None) -> None:
        """`view` is a `cli_impl.reports.comparison_view` result."""
        self.view = view
        self.changes_path = changes_path
        lang = self.lang
        self.target_label.setText(view["target"])
        self.span_label.setText(f"{view['before_at']}  →  {view['now_at']}")
        self.total_label.setText(
            f"{view['findings_before']}  →  {view['findings_now']}")
        self.changes_btn.setVisible(bool(changes_path))

        fixed, appeared, unchanged = (view["fixed"], view["appeared"],
                                      view["unchanged"])
        self.sections[FIXED].set_rules(
            fixed["rules"], t("comparison_places", lang, n=fixed["places"]),
            note=(t("comparison_solved", lang,
                    rules=", ".join(fixed["solved"])) if fixed["solved"] else ""))
        self.sections[APPEARED].set_rules(
            appeared["rules"], t("comparison_places", lang, n=appeared["places"]),
            note=(t("comparison_new_rules", lang,
                    rules=", ".join(appeared["new"])) if appeared["new"] else ""))
        self.sections[UNCHANGED].set_rules(
            unchanged["rules"],
            t("comparison_places", lang, n=unchanged["places"]),
            note=t("comparison_oldest_first", lang) if unchanged["rules"] else "")

        measured = view.get("measurements") or []
        self.measurements.setText(
            t("comparison_measurements", lang,
              rules=", ".join(row["rule"] for row in measured)) if measured else "")
        self.measurements.setVisible(bool(measured))

    # -- actions ---------------------------------------------------------

    def _on_open_changes(self) -> None:
        if self.changes_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.changes_path)))

    def apply_palette(self, palette) -> None:
        self.palette_ = palette
        for section in self.sections.values():
            section.apply_palette(palette)
        if self.view is not None:
            self.show_comparison(self.view, self.changes_path)
