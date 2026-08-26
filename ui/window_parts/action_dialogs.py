"""The three moments where the tool touches somebody's files (artboard 3j).

Each of these was a `QMessageBox` with a sentence in it, and a message box is
the wrong shape for all three. It can say *how many*, which is the one thing
nobody needs to be told, and it cannot say **which files**, **why this one is
different**, or **what to do about what just happened** - which are the three
questions actually being asked.

- `WriteConfirmDialog` is the last screen before a write. It lists the files
  and how many fragments each of them gets, because "12 fragments" is a
  number and "5 of them in uk.json" is what somebody checks.
- `DecisionDialog` is one row that cannot be written mechanically. It gives
  the rule's own reason and three ways out, one of which - *mark it
  decorative* - is a claim a person is allowed to make and the tool is not.
- `WriteOutcomeDialog` is what happened, in four numbers that are not the
  same number: applied, files changed, skipped because the file moved on,
  and errors. It offers the undo while the `.bak` copies are still there,
  which is the only moment that offer is worth anything.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

import replacements
from i18n.translations import t
from ui import theme
from ui.widgets import Switch, muted


def _title(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("class", theme.CLASS_HEADING)
    label.setWordWrap(True)
    return label


def _body(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label


class WriteConfirmDialog(QDialog):
    """Which files are about to change, and by how much."""

    def __init__(self, items, lang: str = "en", root: str | None = None,
                 palette=None, parent=None):
        super().__init__(parent)
        self.items = items
        self.lang = lang
        self.palette_ = palette or getattr(parent, "palette_tokens", None)
        self.setWindowTitle(t("write_confirm_title", lang))
        self.resize(520, 380)

        column = QVBoxLayout(self)
        column.setSpacing(8)
        column.addWidget(_title(t("write_confirm_title", lang)))
        chosen = replacements.selected(items)
        column.addWidget(muted_wrapped(t("write_confirm_body", lang,
                                         n=len(chosen))))

        files = replacements.by_file(items, root)
        host = QWidget()
        rows = QVBoxLayout(host)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(2)
        for path, count in files:
            line = QWidget()
            row = QHBoxLayout(line)
            row.setContentsMargins(8, 3, 8, 3)
            name = QLabel(path)
            name.setProperty("class", theme.CLASS_CODE)
            name.setTextFormat(Qt.TextFormat.PlainText)
            row.addWidget(name, stretch=1)
            number = QLabel(str(count))
            number.setProperty("class", theme.CLASS_CHIP)
            row.addWidget(number)
            rows.addWidget(line)
        rows.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(host)
        column.addWidget(scroll, stretch=1)

        backup_row = QHBoxLayout()
        self.backup_switch = Switch(self.palette_)
        self.backup_switch.setChecked(True)
        backup_row.addWidget(self.backup_switch)
        backup_row.addWidget(muted_wrapped(t("write_confirm_backup", lang)),
                             stretch=1)
        column.addLayout(backup_row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton(t("cancel_button", lang))
        cancel.setProperty("class", theme.CLASS_QUIET)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        self.write_btn = QPushButton(t("replacements_write", lang,
                                       n=len(chosen)))
        self.write_btn.setProperty("class", theme.CLASS_PRIMARY)
        self.write_btn.clicked.connect(self.accept)
        buttons.addWidget(self.write_btn)
        column.addLayout(buttons)

    @property
    def backup(self) -> bool:
        return self.backup_switch.isChecked()


class DecisionDialog(QDialog):
    """One row that has no mechanical answer, and the three ways out.

    The middle one is the point. *Mark it decorative* writes the rule's own
    correction - for an image, `alt=""` - which is a true statement about a
    picture that carries no meaning and a lie about one that does. The tool
    cannot tell those apart by looking, and a person can, so this is the one
    place the claim is allowed to be made.
    """

    #: What the person chose: write it themselves, accept the rule's own
    #: correction as-is, or hand it to a model.
    SELF, DECORATIVE, MODEL = "self", "decorative", "model"

    def __init__(self, item, lang: str = "en", palette=None, parent=None):
        super().__init__(parent)
        self.item = item
        self.lang = lang
        self.choice = ""
        self.setWindowTitle(t("decision_title", lang))
        self.resize(560, 300)

        column = QVBoxLayout(self)
        column.setSpacing(8)
        column.addWidget(_title(t("decision_title", lang)))
        column.addWidget(muted_wrapped(t("decision_where", lang,
                                         where=item.where)))
        column.addWidget(_body(item.reason or t("replacements_no_text", lang)))

        self.value_edit = QLineEdit()
        self.value_edit.setPlaceholderText(t("decision_placeholder", lang))
        self.value_edit.returnPressed.connect(self._on_self)
        column.addWidget(self.value_edit)
        column.addWidget(muted_wrapped(t("decision_backup_note", lang)))
        column.addStretch(1)

        buttons = QHBoxLayout()
        self.self_btn = QPushButton(t("decision_self", lang))
        self.self_btn.setProperty("class", theme.CLASS_PRIMARY)
        self.self_btn.clicked.connect(self._on_self)
        buttons.addWidget(self.self_btn)
        self.decorative_btn = QPushButton(t("decision_decorative", lang))
        self.decorative_btn.setProperty("class", theme.CLASS_QUIET)
        self.decorative_btn.clicked.connect(self._on_decorative)
        buttons.addWidget(self.decorative_btn)
        self.model_btn = QPushButton(t("decision_model", lang))
        self.model_btn.setProperty("class", theme.CLASS_QUIET)
        self.model_btn.clicked.connect(self._on_model)
        buttons.addWidget(self.model_btn)
        buttons.addStretch(1)
        cancel = QPushButton(t("cancel_button", lang))
        cancel.setProperty("class", theme.CLASS_QUIET)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        column.addLayout(buttons)

    def _on_self(self) -> None:
        text = self.value_edit.text().strip()
        if not text:
            # Nothing typed is not an answer, and accepting it would write
            # the placeholder the rule is still carrying.
            self.value_edit.setFocus()
            return
        self.choice = self.SELF
        replacements.answer_decision(self.item, text=text)
        self.accept()

    def _on_decorative(self) -> None:
        self.choice = self.DECORATIVE
        replacements.answer_decision(self.item, decorative=True)
        self.accept()

    def _on_model(self) -> None:
        self.choice = self.MODEL
        self.accept()


class WriteOutcomeDialog(QDialog):
    """What the write did, in the four numbers that differ.

    "10 applied" and "4 files changed" are not the same fact, and neither is
    "2 skipped because the fragment moved after the scan" - that one is the
    reason to run again rather than a failure. They are shown apart because
    the next action differs for each.
    """

    def __init__(self, outcome, lang: str = "en", palette=None, parent=None):
        super().__init__(parent)
        self.outcome = outcome
        self.lang = lang
        self.undo_requested = False
        self.setWindowTitle(t("write_done_title", lang))
        self.resize(520, 340)

        column = QVBoxLayout(self)
        column.setSpacing(8)
        column.addWidget(_title(t("write_done_title", lang)))

        numbers = QHBoxLayout()
        numbers.setSpacing(12)
        for value, label in (
            (outcome.written, t("write_done_applied", lang)),
            (len(outcome.files_changed), t("write_done_files", lang)),
            (len(outcome.skipped), t("write_done_skipped", lang)),
            (len(outcome.errors), t("write_done_errors", lang)),
        ):
            cell = QWidget()
            stack = QVBoxLayout(cell)
            stack.setContentsMargins(0, 0, 0, 0)
            stack.setSpacing(0)
            number = QLabel(str(value))
            number.setProperty("class", theme.CLASS_HEADING)
            stack.addWidget(number)
            caption = muted_wrapped(label)
            stack.addWidget(caption)
            numbers.addWidget(cell, stretch=1)
        column.addLayout(numbers)

        if outcome.backups:
            first = outcome.backups[0].split("/")[-1]
            column.addWidget(muted_wrapped(
                t("write_done_backups", lang, first=first,
                  rest=len(outcome.backups) - 1)))

        detail = "\n".join(list(outcome.skipped)[:8] + list(outcome.errors)[:8])
        if detail:
            self.detail_label = _body(detail)
            self.detail_label.setVisible(False)
            column.addWidget(self.detail_label)
        else:
            self.detail_label = None
        column.addStretch(1)

        buttons = QHBoxLayout()
        self.undo_btn = QPushButton(t("write_done_undo", lang))
        self.undo_btn.setProperty("class", theme.CLASS_QUIET)
        self.undo_btn.setEnabled(bool(outcome.backups))
        self.undo_btn.clicked.connect(self._on_undo)
        buttons.addWidget(self.undo_btn)
        if self.detail_label is not None:
            self.show_btn = QPushButton(t("write_done_show", lang,
                                          n=len(outcome.skipped)))
            self.show_btn.setProperty("class", theme.CLASS_QUIET)
            self.show_btn.clicked.connect(
                lambda: self.detail_label.setVisible(True))
            buttons.addWidget(self.show_btn)
        buttons.addStretch(1)
        done = QPushButton(t("write_done_ok", lang))
        done.setProperty("class", theme.CLASS_PRIMARY)
        done.clicked.connect(self.accept)
        buttons.addWidget(done)
        column.addLayout(buttons)

    def _on_undo(self) -> None:
        """Put every file back, out of the copies taken before the write."""
        import backups

        restored, problems = backups.restore(self.outcome.backups)
        self.undo_requested = True
        self.undo_btn.setEnabled(False)
        message = t("write_done_undone", self.lang, n=len(restored))
        if problems:
            message += " · " + "; ".join(problems)
        if self.detail_label is None:
            self.detail_label = _body(message)
            self.layout().insertWidget(self.layout().count() - 1,
                                       self.detail_label)
        else:
            self.detail_label.setText(message)
        self.detail_label.setVisible(True)


def muted_wrapped(text: str) -> QLabel:
    label = muted(text)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.PlainText)
    return label
