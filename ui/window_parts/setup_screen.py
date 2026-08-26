"""The screen before the first run: four choices, in the order they are made.

Artboard 3b. The window used to open on its working layout - three columns
of results, all empty - with the run's settings folded into one line of
inline values above them. That line is right *during* work, where the
question is "what will the next run be" and the answer has to fit beside
the findings of the last one. It is wrong before any work, where the same
line is the entire task and is written in eight words across the top of a
window that is otherwise blank.

So: one screen while nothing has run, the working layout once something has.

The four cards are the four axes, and they are four because they are chosen
independently - what is looked at, how it is read, what is looked for, and
who judges. The screen writes every choice into `AppState`, which the top
row already reads, so the two surfaces cannot disagree: they are two
renderings of one object, not two copies of one decision.

**Card 2 states rather than asks.** How a source is read is derived
(`mode_rules.auto_readers`) - a site is read both ways because the
difference between the two readings is itself a finding. A selector here
would be a control nothing consults, which this window has had before and
removed on purpose. It says what will happen and why, and takes no clicks.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QHBoxLayout, QLabel, QPushButton, QRadioButton,
    QVBoxLayout, QWidget,
)

from analysis_modes import (
    CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS, METHOD_AI, METHOD_EMBEDDING,
    METHOD_LOCAL, READER_BROWSER, SOURCE_FILE, SOURCE_REPO, SOURCE_SITE,
)
from i18n.translations import t
from ui import theme

#: The three sources, with the sentence each one is described by.
SOURCES = (
    (SOURCE_SITE, "source_site", "setup_source_site_hint"),
    (SOURCE_REPO, "source_repo", "setup_source_repo_hint"),
    (SOURCE_FILE, "source_file", "setup_source_file_hint"),
)

#: The judges. `METHOD_AI` needs an account, which is why it carries a flag
#: rather than being filtered out of the list: a choice that is missing looks
#: like a choice that does not exist.
METHODS = (
    (METHOD_LOCAL, "method_local", "setup_method_local_hint", False),
    (METHOD_EMBEDDING, "method_embedding", "setup_method_embedding_hint", False),
    (METHOD_AI, "method_both", "setup_method_ai_hint", True),
)


def _under_home(path) -> str:
    """`~/Downloads/page.html` rather than the whole absolute path.

    The design writes it this way and it is not only shorter: the part that
    identifies the file is its tail, and a temporary directory's path can be
    sixty characters of nothing anybody typed.
    """
    from pathlib import Path

    try:
        return "~/" + str(Path(path).relative_to(Path.home()))
    except ValueError:
        return str(path)


def _human_size(size: int) -> str:
    """Bytes as somebody would say them. Two units are enough here: a saved
    page is kilobytes or a few megabytes, never gigabytes."""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def _two_line(title: str, hint: str) -> QWidget:
    """A name over the sentence that says what choosing it means."""
    holder = QWidget()
    column = QVBoxLayout(holder)
    column.setContentsMargins(0, 0, 0, 0)
    column.setSpacing(0)
    name = QLabel(title)
    column.addWidget(name)
    if hint:
        note = QLabel(hint)
        note.setProperty("class", theme.CLASS_MUTED)
        note.setWordWrap(True)
        column.addWidget(note)
    return holder


class SetupCard(QWidget):
    """One numbered card: a step label and whatever the step is choosing."""

    def __init__(self, step_key: str, lang: str = "en", parent=None):
        super().__init__(parent)
        self.step_key = step_key
        self.lang = lang
        self.setProperty("class", theme.CLASS_INSET)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.column = QVBoxLayout(self)
        self.column.setContentsMargins(12, 11, 12, 11)
        self.column.setSpacing(7)
        self.step = QLabel(t(step_key, lang))
        self.step.setProperty("class", theme.CLASS_FIELD_LABEL)
        self.column.addWidget(self.step)


class SetupScreen(QWidget):
    """Everything a run is, before it is one."""

    analyze_requested = Signal()
    #: The screen asks; the window owns the picker and the field it fills.
    choose_file_requested = Signal()

    def __init__(self, app_state, palette, lang: str = "en", parent=None):
        super().__init__(parent)
        self.app_state = app_state
        self.palette_ = palette
        self.lang = lang
        self.setProperty("class", theme.CLASS_PANEL)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QWidget()
        body.setProperty("class", theme.CLASS_PANEL_BODY)
        column = QVBoxLayout(body)
        column.setContentsMargins(44, 30, 44, 24)
        column.setSpacing(18)
        outer.addWidget(body, stretch=1)

        self.title = QLabel(t("setup_title", lang))
        self.title.setProperty("class", theme.CLASS_HEADING)
        self.subtitle = QLabel(t("setup_subtitle", lang))
        self.subtitle.setProperty("class", theme.CLASS_MUTED)
        self.subtitle.setWordWrap(True)
        heading = QWidget()
        heading_column = QVBoxLayout(heading)
        heading_column.setContentsMargins(0, 0, 0, 0)
        heading_column.setSpacing(2)
        heading_column.addWidget(self.title)
        heading_column.addWidget(self.subtitle)
        column.addWidget(heading)

        # The target row is filled by the window, which owns the fields: the
        # address, the folder and the file are three different widgets with
        # three different pickers, and copying them here would be a second
        # place for the same value to be wrong in.
        self.target_row = QWidget()
        self.target_row.setProperty("class", theme.CLASS_INSET)
        self.target_row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Capped, as the design caps it. A single address stretched across
        # 1300px reads as a form field in an empty room; the row is the one
        # thing on this screen that is typed into, and it should look like a
        # sentence rather than like the width of the window.
        self.target_row.setMaximumWidth(720)
        self.target_layout = QHBoxLayout(self.target_row)
        self.target_layout.setContentsMargins(10, 6, 6, 6)
        self.target_layout.setSpacing(8)
        column.addWidget(self.target_row)

        # The single-page source is the one target you can bring rather than
        # type, so it gets the area the design draws for it (artboard 3o).
        # It sits under the target row and takes the same drop the window
        # takes anywhere on itself.
        self.drop_zone = self._build_drop_zone()
        column.addWidget(self.drop_zone)

        cards = QHBoxLayout()
        cards.setSpacing(8)
        cards.addWidget(self._build_source_card(), stretch=1)
        cards.addWidget(self._build_reading_card(), stretch=1)
        cards.addWidget(self._build_question_card(), stretch=1)
        cards.addWidget(self._build_judge_card(), stretch=1)
        column.addLayout(cards)
        column.addStretch(1)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        self.summary = QLabel()
        self.summary.setProperty("class", theme.CLASS_MUTED)
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        bottom.addWidget(self.summary, stretch=1)
        self.analyze_btn = QPushButton()
        self.analyze_btn.setProperty("class", theme.CLASS_PRIMARY)
        self.analyze_btn.clicked.connect(self.analyze_requested)
        bottom.addWidget(self.analyze_btn)
        column.addLayout(bottom)

        # No footer strip. The design draws one ("Готово до роботи · ⌘K …")
        # and the window already has a status bar saying exactly that, at the
        # bottom of the same window. Two places for one sentence is how one
        # of them comes to be stale.

        self.app_state.any_changed.connect(self.refresh)
        self.retranslate(lang)

    def _build_drop_zone(self) -> QWidget:
        zone = QWidget()
        zone.setProperty("class", theme.CLASS_INSET)
        zone.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        zone.setMaximumWidth(720)
        column = QVBoxLayout(zone)
        column.setContentsMargins(16, 14, 16, 14)
        column.setSpacing(4)

        self.drop_arrow = QLabel("↓")
        self.drop_arrow.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        column.addWidget(self.drop_arrow)
        self.drop_title = QLabel()
        self.drop_title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        column.addWidget(self.drop_title)
        self.drop_note = QLabel()
        self.drop_note.setProperty("class", theme.CLASS_MUTED)
        self.drop_note.setWordWrap(True)
        self.drop_note.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        column.addWidget(self.drop_note)

        row = QHBoxLayout()
        row.addStretch(1)
        self.drop_choose_btn = QPushButton()
        self.drop_choose_btn.setProperty("class", theme.CLASS_QUIET)
        self.drop_choose_btn.clicked.connect(self.choose_file_requested)
        row.addWidget(self.drop_choose_btn)
        row.addStretch(1)
        column.addLayout(row)

        # What was chosen, once something is: the design puts the file's own
        # name and size here, because "412 KB" is how somebody notices they
        # dropped the wrong export.
        self.drop_chosen = QLabel()
        self.drop_chosen.setProperty("class", theme.CLASS_CODE)
        self.drop_chosen.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.drop_chosen.setVisible(False)
        column.addWidget(self.drop_chosen)
        return zone

    def refresh_target(self) -> None:
        """The two things that read the target: the drop zone and the sentence.

        `AppState.set_target` carries no signal - the target changes on every
        keystroke and a repaint per character is not worth it - so the window
        calls this when the value has actually settled.
        """
        self._refresh_drop_zone()
        self._refresh_summary()

    def _refresh_drop_zone(self) -> None:
        from pathlib import Path

        state = self.app_state
        self.drop_zone.setVisible(state.source == SOURCE_FILE)
        if state.source != SOURCE_FILE:
            return
        target = (state.target or "").strip()
        path = Path(target) if target else None
        if path is not None and path.is_file():
            size = path.stat().st_size
            self.drop_chosen.setText(t("setup_drop_chosen", self.lang,
                                       name=_under_home(path),
                                       size=_human_size(size)))
            self.drop_chosen.setVisible(True)
        else:
            self.drop_chosen.setVisible(False)

    # ------------------------------------------------------------- cards

    def _build_source_card(self) -> QWidget:
        card = SetupCard("setup_step_source", self.lang)
        self.source_buttons = {}
        self.source_group = QButtonGroup(self)
        self.source_group.setExclusive(True)
        for value, label_key, hint_key in SOURCES:
            row = QWidget()
            line = QHBoxLayout(row)
            line.setContentsMargins(0, 0, 0, 0)
            line.setSpacing(8)
            button = QRadioButton()
            button.toggled.connect(
                lambda checked, chosen=value: checked and self.app_state.set_source(chosen))
            self.source_group.addButton(button)
            line.addWidget(button)
            line.addWidget(_two_line(t(label_key, self.lang),
                                     t(hint_key, self.lang)), stretch=1)
            self.source_buttons[value] = (button, row)
            card.column.addWidget(row)
        # The depth belongs to the source: it is how far the crawl goes from
        # the page you name, and it means nothing for a folder or one file.
        self.depth_holder = QWidget()
        self.depth_layout = QHBoxLayout(self.depth_holder)
        self.depth_layout.setContentsMargins(0, 0, 0, 0)
        self.depth_layout.setSpacing(6)
        self.depth_note = QLabel()
        self.depth_note.setProperty("class", theme.CLASS_MUTED)
        self.depth_layout.addWidget(self.depth_note)
        card.column.addWidget(self.depth_holder)
        card.column.addStretch(1)
        self.source_card = card
        return card

    def _build_reading_card(self) -> QWidget:
        card = SetupCard("setup_step_reading", self.lang)
        self.reading_rows = {}
        for key, hint_key in (("setup_reading_code", "setup_reading_code_hint"),
                              ("setup_reading_browser", "setup_reading_browser_hint")):
            row = _two_line(t(key, self.lang), t(hint_key, self.lang))
            self.reading_rows[key] = row
            card.column.addWidget(row)
        self.reading_note = QLabel(t("setup_reading_note", self.lang))
        self.reading_note.setProperty("class", theme.CLASS_MUTED)
        self.reading_note.setWordWrap(True)
        card.column.addWidget(self.reading_note)
        card.column.addStretch(1)
        self.reading_card = card
        return card

    def _build_question_card(self) -> QWidget:
        card = SetupCard("setup_step_question", self.lang)
        self.check_boxes = {}
        for value, label_key, hint_key in (
                (CHECK_ACCESSIBILITY, "check_accessibility",
                 "setup_check_accessibility_hint"),
                (CHECK_AI_PATTERNS, "check_ai_patterns", "setup_check_ai_hint")):
            row = QWidget()
            line = QHBoxLayout(row)
            line.setContentsMargins(0, 0, 0, 0)
            line.setSpacing(8)
            box = QCheckBox()
            box.toggled.connect(self._on_checks_toggled)
            line.addWidget(box)
            line.addWidget(_two_line(t(label_key, self.lang), ""), stretch=1)
            self.check_boxes[value] = (box, row, hint_key, line)
            card.column.addWidget(row)
        self.checks_note = QLabel()
        self.checks_note.setProperty("class", theme.CLASS_MUTED)
        self.checks_note.setWordWrap(True)
        card.column.addWidget(self.checks_note)
        card.column.addStretch(1)
        self.question_card = card
        return card

    def _build_judge_card(self) -> QWidget:
        card = SetupCard("setup_step_judge", self.lang)
        self.method_buttons = {}
        self.method_group = QButtonGroup(self)
        self.method_group.setExclusive(True)
        for value, label_key, hint_key, needs_account in METHODS:
            row = QWidget()
            line = QHBoxLayout(row)
            line.setContentsMargins(0, 0, 0, 0)
            line.setSpacing(8)
            button = QRadioButton()
            button.toggled.connect(
                lambda checked, chosen=value:
                checked and self.app_state.set_methods((chosen,)))
            self.method_group.addButton(button)
            line.addWidget(button)
            line.addWidget(_two_line(t(label_key, self.lang),
                                     t(hint_key, self.lang)), stretch=1)
            self.method_buttons[value] = (button, row, needs_account)
            card.column.addWidget(row)
        self.account_note = QLabel()
        self.account_note.setProperty("class", theme.CLASS_MUTED)
        self.account_note.setWordWrap(True)
        card.column.addWidget(self.account_note)
        card.column.addStretch(1)
        self.judge_card = card
        return card

    # ------------------------------------------------------------ filling

    def _on_checks_toggled(self, _checked: bool) -> None:
        chosen = tuple(value for value, (box, *_rest) in self.check_boxes.items()
                       if box.isChecked())
        # Neither question asked is not a run, it is a walk over the pages
        # with nothing to say about them, so the state keeps the last one.
        if chosen:
            self.app_state.set_checks(chosen)
        self.refresh()

    def retranslate(self, lang: str) -> None:
        self.lang = lang
        self.title.setText(t("setup_title", lang))
        self.subtitle.setText(t("setup_subtitle", lang))
        self.reading_note.setText(t("setup_reading_note", lang))
        self.analyze_btn.setText(t("analyze_button", lang))
        self.drop_title.setText(t("setup_drop_title", lang))
        self.drop_note.setText(t("setup_drop_note", lang))
        self.drop_choose_btn.setText(t("setup_drop_choose", lang))
        self.refresh()

    def refresh(self) -> None:
        """Every control back from `AppState`, which is what actually holds
        the run. Written this way round so that a choice made in the top row
        shows here too, rather than the two drifting apart."""
        state = self.app_state
        for value, (button, _row) in self.source_buttons.items():
            button.blockSignals(True)
            button.setChecked(state.source == value)
            button.blockSignals(False)

        site = state.source == SOURCE_SITE
        self.depth_holder.setVisible(site)
        self.depth_note.setText(t("setup_depth_zero", self.lang))

        # Card 2 states what the chosen source means, and only the readings
        # that will actually happen.
        readers = state.readers
        self.reading_rows["setup_reading_browser"].setVisible(
            READER_BROWSER in readers)

        for value, (box, _row, hint_key, line) in self.check_boxes.items():
            box.blockSignals(True)
            box.setChecked(value in state.checks)
            box.blockSignals(False)
        self.checks_note.setText(
            t("setup_checks_note", self.lang) if len(state.checks) > 1
            else t("setup_checks_one_at_least", self.lang))

        ai_ready = state.ai_available
        for value, (button, row, needs_account) in self.method_buttons.items():
            button.blockSignals(True)
            button.setChecked(value in state.methods)
            button.blockSignals(False)
            if needs_account:
                button.setEnabled(ai_ready)
                row.setEnabled(ai_ready)
        self.account_note.setText("" if ai_ready
                                  else t("setup_method_needs_account", self.lang))
        self.account_note.setVisible(not ai_ready)
        self._refresh_drop_zone()
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        state = self.app_state
        source_key = {SOURCE_SITE: "source_site", SOURCE_REPO: "source_repo",
                      SOURCE_FILE: "source_file"}[state.source]
        readers = ", ".join(
            t("setup_reading_browser" if reader == READER_BROWSER
              else "setup_reading_code", self.lang).lower()
            for reader in state.readers)
        checks = (t("checks_both", self.lang) if len(state.checks) > 1
                  else t("check_accessibility" if CHECK_ACCESSIBILITY in state.checks
                         else "check_ai_patterns", self.lang))
        method_key = {METHOD_LOCAL: "method_local", METHOD_EMBEDDING: "method_embedding",
                      METHOD_AI: "method_both"}.get(
                          state.methods[0] if state.methods else METHOD_LOCAL,
                          "method_local")

        def strong(text: str) -> str:
            return f"<b>{text}</b>"

        self.summary.setText(t("setup_summary", self.lang).format(
            source=t(source_key, self.lang),
            target=strong(state.target or "…"),
            reading=strong(readers),
            # Not lowercased: "AI" is not a word that has a small form, and
            # the label already reads as a phrase in the middle of a sentence.
            checks=strong(checks),
            method=strong(t(method_key, self.lang).lower()),
        ))

