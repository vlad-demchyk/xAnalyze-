"""What a run found, shown here rather than deferred to the terminal.

Every form used to end with "See results in terminal", which was not true:
the interface owns the terminal while it runs, so the JSON either vanished
or drew over the screen. The result is captured (`tui.runner`) and laid out
here - a summary, the documents that were written, and the full log for
anything the summary does not cover.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Label, RichLog, Static

from i18n.translations import t

from tui.screens.base import XScreen

#: Severity name -> the theme variable painting its step of the four-level
#: ramp (`ui.theme.build_textual_theme`, itself the same four fields
#: `ui.widgets.SeverityBar` paints in the Qt window). Before this, every
#: severity in this table was the table's default foreground - "27 critical"
#: and "27 minor" read as the same colour, which is the defect the ramp
#: exists to fix, and it reached the summary table but not this one.
_SEVERITY_VARIABLE = {
    "critical": "sev-critical",
    "serious": "sev-high",
    "moderate": "sev-medium",
    "minor": "sev-none",
}


def open_in_os(path: str, lang: str = "uk") -> str:
    """Hand a file or folder to the desktop. Returns a message for the user.

    A report the tool just wrote is only useful if it can be opened, and the
    interface cannot render a PDF. Nothing is sent anywhere - this is the
    same double-click the person would do themselves.
    """
    target = Path(path)
    if not target.exists():
        return t("tui_open_gone", lang, path=path)
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        elif os.name == "nt":  # pragma: no cover - not the supported platform
            os.startfile(str(target))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(target)])
    except OSError as exc:
        return t("tui_open_failed", lang, error=exc)
    return t("tui_opened", lang, name=target.name)


def summary_rows(payload: dict | None) -> list:
    """`(label, value)` pairs for whichever command produced this payload.

    The three commands print three different documents. Rather than a branch
    per command, each known shape contributes the rows it has - a payload
    from a future command still renders, just with fewer rows.
    """
    if not payload:
        return []
    rows: list = []
    summary = payload.get("summary")
    if isinstance(summary, dict):
        # fullscan: one document covering both passes.
        for key in ("total_findings", "ai_patterns", "characters",
                    "accessibility", "seo", "performance", "best_practices"):
            if key in summary:
                rows.append((key.replace("_", " "), str(summary[key])))
    counts = payload.get("counts")
    if isinstance(counts, dict):
        # scan: findings by detector, plus the totals.
        for key in ("total", "distinct", "files"):
            if key in counts:
                rows.append((key, str(counts[key])))
        for key, value in counts.items():
            if key not in ("total", "distinct", "files"):
                rows.append((f"by {key}", str(value)))
        for severity in ("critical", "serious", "moderate", "minor"):
            if severity in counts:
                rows.append((severity, str(counts[severity])))
    audit = payload.get("audit")
    if isinstance(audit, dict) and isinstance(audit.get("counts"), dict):
        for severity, value in audit["counts"].items():
            rows.append((f"audit {severity}", str(value)))
    if "target" in payload:
        rows.insert(0, ("target", str(payload["target"])))
    return rows


class ResultsScreen(XScreen):
    """Summary, documents written, and the full log of one run."""

    BINDINGS = [
        ("escape", "back", "Back"),
        ("o", "open_first", "Open report"),
    ]

    def __init__(self, title: str, result) -> None:
        super().__init__()
        self._title = title
        self._result = result
        self._paths = result.report_paths()

    def compose(self) -> ComposeResult:
        yield from self.compose_chrome()
        with Vertical(id="results-view"):
            yield Label(self.tr("tui_result_title", title=self._title),
                        classes="menu-title")
            yield Label(self.tr("tui_exit_code", code=self._result.exit_code),
                        id="results-exit")
            yield DataTable(id="results-summary")
            yield Static("")
            yield Label("", id="results-paths")
            with Horizontal(id="results-actions"):
                yield Button(self.tr("tui_open_report"), id="open-report", variant="primary")
                yield Button(self.tr("tui_open_folder"), id="open-folder")
                yield Button(self.tr("tui_back"), id="back")
            yield Label("", id="report-status")
            yield RichLog(id="results-log", highlight=False, markup=False,
                          wrap=True)

    def on_mount(self) -> None:
        table = self.query_one("#results-summary", DataTable)
        table.add_columns(self.tr("tui_col_what"), self.tr("tui_col_count"))
        rows = summary_rows(self._result.payload())
        if rows:
            variables = self.app.get_css_variables()
            for label, value in rows:
                # The payload's keys are machine names; the table is read by
                # a person, so each one is said in their language and falls
                # back to the raw key when a command grows a new field.
                shown = self.tr(f"tui_sum_{label.replace(' ', '_')}")
                if shown.startswith("tui_sum_"):
                    shown = label
                table.add_row(self._severity_cell(label, variables, shown),
                              value)
        else:
            table.add_row(self.tr("tui_no_summary"), "-")

        paths = self.query_one("#results-paths", Label)
        if self._paths:
            paths.update(self.tr("tui_written") + "\n"
                         + "\n".join(f"  {p}" for p in self._paths))
        else:
            paths.update(self.tr("tui_nothing_written"))
        self.query_one("#open-report", Button).disabled = not self._file_paths()
        self.query_one("#open-folder", Button).disabled = not self._paths

        log = self.query_one("#results-log", RichLog)
        for line in (self._result.stderr.splitlines()
                     + self._result.stdout.splitlines()):
            log.write(line)

    @staticmethod
    def _severity_cell(label: str, variables: dict,
                       shown: str | None = None) -> Text | str:
        """`shown` painted in `label`'s step of the ramp, or left unpainted.

        The severity is matched on the payload's own key, not on the words
        the person reads: the label is translated by the time it reaches the
        table, and matching on a translated word would paint the ramp in one
        language and nothing in the other two.

        Matched on the last word rather than the whole key, because a row can
        read "critical" (scan) or "audit critical" (audit) for the same
        severity - see `summary_rows`, which reconciles the two shapes.
        """
        text = label if shown is None else shown
        last_word = label.rsplit(" ", 1)[-1]
        variable = _SEVERITY_VARIABLE.get(last_word)
        if variable is None or variable not in variables:
            return text
        return Text(text, style=variables[variable])

    def _file_paths(self) -> list:
        return [p for p in self._paths if Path(p).is_file()]

    def _folder(self) -> str:
        for path in self._paths:
            candidate = Path(path)
            if candidate.is_dir():
                return str(candidate)
        files = self._file_paths()
        return str(Path(files[0]).parent) if files else ""

    def action_open_first(self) -> None:
        files = self._file_paths()
        if files:
            self.query_one("#report-status", Label).update(open_in_os(files[0], self.lang))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            self.action_back()
        elif event.button.id == "open-report":
            self.action_open_first()
        elif event.button.id == "open-folder":
            folder = self._folder()
            if folder:
                self.query_one("#report-status", Label).update(
                    open_in_os(folder, self.lang))
