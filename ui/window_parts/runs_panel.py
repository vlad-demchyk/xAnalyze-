"""The catalogue of runs: what is on disk, and what can be continued.

A full scan of a large site is a three-quarter-hour job, and it can stop for
reasons that have nothing to do with the target - a wedged renderer, a laptop
closing, someone wanting their machine back. Before this the interface had no
idea any of that had happened: a stopped run was simply gone, and the only
evidence was a folder on the Desktop nobody was told about.

The list is built by walking the run folders, the same walk `xanalyze runs`
does, and not from a registry the interface keeps of its own. One fact, one
owner: a registry would be a second answer to "what runs exist", it would be
the one that went stale the moment a folder was moved by hand, and the CLI and
the GUI would then disagree about the same disk.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout,
    QWidget,
)

from i18n.translations import t
from ui.widgets import muted

#: How many runs the panel lists. The catalogue is for continuing recent work,
#: not for browsing history - that is what the folders on disk are.
_RUNS_SHOWN = 12


class RunsPanel:
    """The runs list in the control column, plus resume and pause.

    Reads `self.lang` and `self.status_bar` from the facade, exactly as the
    other window mixins do.
    """

    def _build_runs_panel(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(self.palette_tokens.space_1)

        self.runs_label = QLabel(t("runs_title", self.lang))
        self.runs_list = QListWidget()
        # Short: this sits in a column that already holds eleven controls, and
        # a list that grows with the disk would push Analyze off the bottom.
        self.runs_list.setMaximumHeight(120)
        self.runs_list.itemSelectionChanged.connect(self._on_run_selected)
        self.runs_list.itemDoubleClicked.connect(
            lambda _item: self._on_open_run_clicked())
        self.runs_empty = muted(t("runs_empty", self.lang))

        buttons = QWidget()
        button_layout = QHBoxLayout(buttons)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(self.palette_tokens.space_1)
        self.resume_run_btn = QPushButton(t("runs_resume", self.lang))
        self.resume_run_btn.clicked.connect(self._on_resume_run_clicked)
        self.pause_run_btn = QPushButton(t("runs_pause", self.lang))
        self.pause_run_btn.clicked.connect(self._on_pause_run_clicked)
        self.open_run_btn = QPushButton(t("runs_open", self.lang))
        self.open_run_btn.clicked.connect(self._on_open_run_clicked)
        for button in (self.resume_run_btn, self.pause_run_btn,
                       self.open_run_btn):
            button_layout.addWidget(button)

        for widget in (self.runs_label, self.runs_list, self.runs_empty,
                       buttons):
            layout.addWidget(widget)
        self.runs_buttons = buttons
        self.refresh_runs()
        return box

    # ------------------------------------------------------------ refreshing
    def refresh_runs(self) -> int:
        """Re-read the run folders. Returns how many rows are listed."""
        from cli_impl.runcmds import run_rows
        from cli_impl import runstate

        try:
            rows = run_rows(runstate.all_runs())[:_RUNS_SHOWN]
        except Exception:  # noqa: BLE001 - an unreadable disk is not a crash
            rows = []
        self.runs_list.clear()
        for row in rows:
            item = QListWidgetItem(self._run_label(row))
            # The whole row travels with the item: the buttons need the path
            # and the status, and re-deriving either from the label would mean
            # parsing a string this method formatted.
            item.setData(Qt.ItemDataRole.UserRole, row)
            self.runs_list.addItem(item)
        self.runs_list.setVisible(bool(rows))
        self.runs_empty.setVisible(not rows)
        self.runs_buttons.setVisible(bool(rows))
        self._on_run_selected()
        return len(rows)

    def _run_label(self, row: dict) -> str:
        target = row.get("target", "")
        if len(target) > 34:
            target = "…" + target[-33:]
        # `t` returns the key when it has no entry, so an unrecognised status
        # would print `runs_status_whatever` at the user. The raw word is a
        # worse label but a true one, so it is what an unknown status gets.
        key = f"runs_status_{row.get('status', '')}"
        status = t(key, self.lang)
        if status == key:
            status = row.get("status", "")
        stage = row.get("stage") or "-"
        if row.get("resumable") and stage != "-":
            status = f"{status} · {stage}"
        return f"{target}\n{status} · {row.get('age', '')}"

    def selected_run(self) -> dict | None:
        item = self.runs_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _on_run_selected(self) -> None:
        row = self.selected_run()
        # Resume is offered only where it would do something. A button that is
        # enabled for a finished run and then says "nothing to resume" teaches
        # people to distrust the buttons.
        self.resume_run_btn.setEnabled(bool(row and row.get("resumable")))
        self.pause_run_btn.setEnabled(bool(row and row.get("status") == "running"))
        self.open_run_btn.setEnabled(row is not None)

    # --------------------------------------------------------------- actions
    def _on_open_run_clicked(self) -> None:
        row = self.selected_run()
        if row is None:
            return
        _open_in_os(Path(row["run"]))

    def _on_pause_run_clicked(self) -> None:
        from cli_impl import runstate

        row = self.selected_run()
        if row is None:
            return
        state = runstate.RunState.load(Path(row["run"]))
        if state is None:
            return
        state.request_pause()
        self.status_bar.showMessage(t("runs_pause_requested", self.lang))
        self.refresh_runs()

    def _on_resume_run_clicked(self) -> None:
        """Continue the selected run, in a worker so the window stays alive.

        The resume re-enters the CLI's own `resume`, which re-enters
        `fullscan` with the recorded invocation. Deliberately the same path
        the terminal takes: a second implementation of "continue this run"
        would be a second set of phase decisions to keep in step.
        """
        row = self.selected_run()
        if row is None or not row.get("resumable"):
            return
        self.status_bar.showMessage(
            t("runs_resuming", self.lang, run=Path(row["run"]).name))
        self._run_resume_worker(row["run"])

    def _run_resume_worker(self, run: str) -> None:
        from PySide6.QtCore import QThread, Signal

        panel = self

        class _Resume(QThread):
            finished_with = Signal(int, str)

            def run(self) -> None:                     # noqa: D102
                try:
                    from cli_impl.runcmds import cmd_resume
                    import argparse

                    code = cmd_resume(argparse.Namespace(run=run, root=None))
                    self.finished_with.emit(int(code), "")
                except Exception as exc:  # noqa: BLE001 - reported, not lost
                    self.finished_with.emit(2, str(exc))

        worker = _Resume()
        worker.finished_with.connect(panel._on_resume_finished)
        # Kept on the window: a QThread that goes out of scope while running
        # is destroyed mid-run, which Qt warns about and which loses the work.
        self._resume_worker = worker
        worker.start()

    def _on_resume_finished(self, code: int, error: str) -> None:
        if error:
            self.status_bar.showMessage(
                t("runs_resume_failed", self.lang, reason=error))
        elif code == 0:
            self.status_bar.showMessage(t("runs_resume_done", self.lang))
        else:
            self.status_bar.showMessage(
                t("runs_resume_incomplete", self.lang))
        self.refresh_runs()

    def _retranslate_runs(self) -> None:
        self.runs_label.setText(t("runs_title", self.lang))
        self.runs_empty.setText(t("runs_empty", self.lang))
        self.resume_run_btn.setText(t("runs_resume", self.lang))
        self.pause_run_btn.setText(t("runs_pause", self.lang))
        self.open_run_btn.setText(t("runs_open", self.lang))
        self.refresh_runs()


def _open_in_os(path: Path) -> None:
    """Open a folder in Finder/Explorer/the desktop's file manager."""
    import subprocess

    if not path.exists():
        return
    if sys.platform == "darwin":
        command = ["open", str(path)]
    elif sys.platform.startswith("win"):
        command = ["explorer", str(path)]
    else:
        command = ["xdg-open", str(path)]
    try:
        subprocess.Popen(command, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except OSError:
        pass
