"""Repo bulk actions: rewrite-all, auto-replace, and the review-list export."""
from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QMessageBox

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
            self._offer_export_list()

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

    def _offer_export_list(self) -> None:
        reply = QMessageBox.question(self, "", t("export_list_prompt", self.lang))
        if reply != QMessageBox.StandardButton.Yes:
            return
        path, _ = QFileDialog.getSaveFileName(self, "", "xanalyze-review.md", "Markdown (*.md)")
        if not path:
            return
        self._export_list_to_file(path)
        QMessageBox.information(self, "", t("export_list_saved", self.lang, path=path))

    def _export_list_to_file(self, path: str) -> None:
        if not self.result:
            return
        blocks_by_id = {b.block_id: b for b in self.result.blocks()}
        lines = ["# AI content review list", ""]
        for span in sorted(self.result.spans, key=lambda s: -s.score):
            if span.confidence == Confidence.LOW:
                continue
            block = blocks_by_id.get(span.block_id)
            if block is None:
                continue
            key = (block.block_id, span.start, span.end)
            original = block.text[span.start:span.end]
            draft = self.drafts.get(key, "")
            location = (
                f"{block.file_path}:{block.line_number}" if isinstance(block, CodeBlock)
                else block.page_url
            )
            lines.append(f"## {location} ({span.confidence.value}, {span.score:.2f})")
            lines.append("")
            lines.append(f"- original: {original}")
            lines.append(f"- suggested: {draft}")
            lines.append("")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
