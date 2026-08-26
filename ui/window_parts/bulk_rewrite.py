"""Repo bulk actions: rewrite-all, auto-replace, and the replacement list."""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

import replacements
from file_writer import apply_replacements, build_plans
from i18n.translations import t
from models import CodeBlock, Confidence, RepoAnalysisResult, TextSpan
from ui.worker import RewriteAllWorker
from ui.window_parts.shared import MODE_REPO


class BulkRewriteMixin:
    """Batch operations over every flagged passage in a repository scan."""

    def _repo_flagged_items(self) -> list[tuple[CodeBlock, TextSpan]]:
        if not self.result or self.mode != MODE_REPO:
            return []
        blocks_by_id = {b.block_id: b for b in self.result.blocks()}
        items = []
        for span in self.result.spans:
            if span.confidence == Confidence.LOW:
                continue
            block = blocks_by_id.get(span.block_id)
            if block is not None:
                items.append((block, span))
        return items

    def _on_fix_unicode_clicked(self) -> None:
        spans = self._unicode_spans()
        if not spans:
            return
        self.view_model.fix_unicode(spans)

    def _on_generate_list_clicked(self) -> None:
        self._run_bulk_rewrite(auto_replace=False)

    def _on_auto_replace_clicked(self) -> None:
        items = self._repo_flagged_items()
        if not items:
            return
        message = t("confirm_auto_replace", self.lang, n=len(items))
        # Rewriting a comment is a different decision from rewriting a
        # heading, so the confirmation says how many of each are in the batch
        # rather than presenting one undifferentiated count.
        comments = sum(1 for b, _ in items if getattr(b, "kind", "") == "technical")
        if comments:
            message += "\n\n" + t("confirm_auto_replace_technical", self.lang, n=comments)
        reply = QMessageBox.question(self, "", message)
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._run_bulk_rewrite(auto_replace=True)

    def _run_bulk_rewrite(self, auto_replace: bool) -> None:
        items = self._repo_flagged_items()
        if not items:
            # Nothing for the model to draft is not nothing to write: the
            # character pass and the audit both produce corrections of their
            # own, and the list is where they are read.
            if not auto_replace:
                self._open_replacement_list()
            return
        missing = [(b, s) for (b, s) in items if (b.block_id, s.start, s.end) not in self.drafts]

        if not missing:
            self._after_bulk_rewrite({}, auto_replace)
            return

        # Fail here, before spending anything, if the configured provider
        # can't actually be used — otherwise the first of N billable calls
        # is what tells the user they're not signed in.
        try:
            import rewriter
            provider = rewriter.build_provider(self.settings)
            status = provider.auth_status()
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "", str(exc))
            return
        if not status.signed_in:
            QMessageBox.warning(
                self, "",
                t("settings_not_signed_in", self.lang, detail=status.detail)
                + "\n\n" + t("settings_button", self.lang),
            )
            return

        self.generate_list_btn.setEnabled(False)
        self.auto_replace_btn.setEnabled(False)
        worker = RewriteAllWorker(missing, self.settings)
        worker.progress.connect(
            lambda done, total: self.status_bar.showMessage(t("rewriting_status", self.lang, done=done, total=total))
        )
        worker.finished_ok.connect(lambda results: self._after_bulk_rewrite(results, auto_replace))
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_rewrite_worker_finished)
        self._rewrite_worker = worker
        self._track_worker(worker)
        self.cancel_btn.setEnabled(True)
        worker.start()

    def _on_rewrite_worker_finished(self) -> None:
        self.generate_list_btn.setEnabled(True)
        self.auto_replace_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.status_bar.showMessage(t("status_idle", self.lang))

    def _after_bulk_rewrite(self, results: dict, auto_replace: bool) -> None:
        for key, text in results.items():
            self.drafts[key] = text
        self._populate_flagged_list()
        if auto_replace:
            self._do_auto_replace()
        else:
            self._open_replacement_list()

    def _do_auto_replace(self) -> None:
        if not self.result:
            return
        blocks_by_id = {b.block_id: b for b in self.result.blocks()}
        plans = build_plans(blocks_by_id, self.result.spans, self.drafts)
        result = apply_replacements(plans)
        QMessageBox.information(
            self, "",
            t("auto_replace_summary", self.lang,
              applied=result.passages_applied, files=len(result.files_changed),
              stale=len(result.passages_skipped_stale), errors=len(result.errors)),
        )
        self._refresh_repo_raw_text_after_write(result.files_changed)

    def _refresh_repo_raw_text_after_write(self, changed_files: list[str]) -> None:
        if not self.result or not isinstance(self.result, RepoAnalysisResult):
            return
        changed = set(changed_files)
        for f in self.result.files:
            if f.path in changed:
                try:
                    with open(f.path, "r", encoding="utf-8") as fh:
                        f.raw_text = fh.read()
                except OSError:
                    pass
        if self.current_preview_path in changed:
            f = next((f for f in self.result.files if f.path == self.current_preview_path), None)
            if f is not None and f.raw_text is not None:
                self.code_view.setPlainText(f.raw_text)

    # ------------------------------------------------------- the list (3l)

    def _open_replacement_list(self) -> None:
        """Show every pending change of this run before writing any of it.

        One screen for three passes. The character fixes, the model's drafts
        and the audit's markup corrections all end as an edit to a file on
        this machine, and the question asked before any of them is written is
        the same question - so it is asked once, in one list, rather than by
        three buttons each with a count in a message box.
        """
        from ui.window_parts.replacement_list import ReplacementListDialog

        root = self.repo_path_edit.text().strip() or None
        items, skipped = replacements.collect(
            result=self.result, drafts=self.drafts,
            audit_result=self.audit_result, root=root)
        dialog = ReplacementListDialog(
            items, skipped=skipped, lang=self.lang, root=root,
            palette=getattr(self, "palette_tokens", None),
            on_fill=self._fill_decisions_with_model, parent=self)
        dialog.exec()
        if dialog.outcome is None:
            return
        self._after_replacement_write(dialog.outcome)

    def _fill_decisions_with_model(self, items) -> int:
        """The provider side of *let the model answer*, kept in the window.

        Building the provider is where "you are not signed in" is discovered,
        and that is an answer about the account rather than about the list,
        so it is raised here and shown by the screen that asked.
        """
        import rewriter

        provider = rewriter.build_provider(self.settings)
        status = provider.auth_status()
        if not status.signed_in:
            raise RuntimeError(
                t("settings_not_signed_in", self.lang, detail=status.detail))
        return replacements.fill_decisions(items, provider,
                                           self._audited_text(), self.lang)

    def _after_replacement_write(self, outcome) -> None:
        """What the window does after the write; the screen already reported.

        No message box here any more: the outcome is its own screen (3j),
        with the four numbers and the undo, and repeating it in a modal is
        the same fact told twice.
        """
        self._refresh_repo_raw_text_after_write(outcome.files_changed)
        # Markup was written into the audited files, so the findings on
        # screen are now a claim about a version that no longer exists.
        if self.audit_result is not None:
            self._reaudit_after_fix()
