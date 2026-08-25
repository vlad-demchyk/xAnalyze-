"""Export actions: fix-on-disk plumbing, agent briefing, styled report."""
from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QMessageBox

from i18n.translations import t

#: This panel's own tiny trilingual vocabulary for the run-documents button,
#: kept local rather than added to `i18n/translations.py`: this feature's
#: task boundary deliberately excludes that module, and three short strings
#: do not need the shared table's machinery (pluralisation, `t()` lookup) to
#: stay correct in uk/it/en.
_STYLED_REPORT_STRINGS = {
    "uk": dict(button="Зберегти звіт", tooltip="Записати теку прогону: "
               "звіт для читання, звіт для агента і тривалість етапів",
               done="Документи прогону: {path}"),
    "it": dict(button="Salva il report", tooltip="Scrive la cartella "
               "dell'esecuzione: report da leggere, report per l'agente e "
               "durata delle fasi",
               done="Documenti dell'esecuzione: {path}"),
    "en": dict(button="Save report", tooltip="Write the run's folder: a "
               "report to read, a report for an agent, and where the time "
               "went",
               done="Run documents: {path}"),
}


def _styled_report_text(lang: str, key: str, **kwargs) -> str:
    strings = _STYLED_REPORT_STRINGS.get(lang, _STYLED_REPORT_STRINGS["en"])
    return strings[key].format(**kwargs)


class ReportExportMixin:
    """Toolbar actions that hand results to the reader or the disk."""

    def _on_fix_on_disk_clicked(self) -> None:
        self.view_model.fix_on_disk()

    def _on_undo_fix_clicked(self) -> None:
        self.view_model.undo_fix()

    def _on_download_clicked(self) -> None:
        self.view_model.download()

    def _on_export_report_clicked(self) -> None:
        if self.audit_result is None:
            return
        path, _filter = QFileDialog.getSaveFileName(
            self, t("export_report_button", self.lang), "audit-report.md",
            "Markdown (*.md);;JSON (*.json)")
        if not path:
            return
        try:
            self.view_model.export_agent_report(path)
        except OSError as exc:
            QMessageBox.warning(self, t("export_report_button", self.lang), str(exc))
            return
        QMessageBox.information(self, t("export_report_button", self.lang),
                                t("export_report_done", self.lang, path=path))

    def _on_styled_report_clicked(self) -> None:
        """Write the run's folder, then show what is in it.

        No save dialog. A run produces four documents that only mean
        something together, and their home is already decided - one folder
        per target, one sub-folder per run. Asking where to put each of them
        is how they end up in four places, and it asks the person to make a
        decision the tool has already made correctly.
        """
        has_text = bool(self.result and self.result.spans)
        has_audit = bool(self.audit_result and self.audit_result.documents)
        if not has_text and not has_audit:
            return
        title = _styled_report_text(self.lang, "button")
        try:
            documents = self.view_model.save_run_documents(
                stage_timings=self.run_progress.durations(),
                run_began=self._run_began)
        except (OSError, RuntimeError) as exc:
            QMessageBox.warning(self, title, str(exc))
            return
        if documents is None:
            return
        self._show_run_documents(documents)

    def _report_fix_outcome(self, outcome, written_by_model) -> None:
        lines = [t("fix_done", self.lang, applied=len(outcome.applied),
                   files=len(outcome.files_changed))]
        if written_by_model:
            lines.append(t("fix_done_by_model", self.lang,
                           rules=", ".join(sorted(set(written_by_model)))))
        if outcome.skipped:
            lines.append("")
            lines.append(t("fix_left_alone", self.lang, count=len(outcome.skipped)))
            for item in outcome.skipped[:6]:
                lines.append(f"  {item.rule_id}: {item.reason}")
        for error in outcome.errors:
            lines.append(error)
        QMessageBox.information(self, t("fix_on_disk_button", self.lang),
                                "\n".join(lines))

    def _audited_text(self) -> str:
        """The words of the audited files, for anything that has to read them."""
        import re

        parts = []
        for document in (self.audit_result.documents if self.audit_result else []):
            if document.source.startswith(("http://", "https://")):
                continue
            try:
                with open(document.source, encoding="utf-8", errors="replace") as handle:
                    parts.append(re.sub(r"<[^>]+>", " ", handle.read()))
            except OSError:
                continue
        return " ".join(parts)

    def _reaudit_after_fix(self) -> None:
        """Re-read the files so the list matches what is now on disk.

        Leaving the old findings on screen after writing to the file would
        show work as outstanding that has just been done, which is the one
        thing a fix button must not do.
        """
        if self.audit_result is None:
            return
        self._start_audit()
