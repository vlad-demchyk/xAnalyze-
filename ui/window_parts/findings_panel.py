"""The text-findings panel: flagged rows, previews, and the detail card."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidgetItem, QPushButton, QTextEdit, QVBoxLayout,
    QWidget,
)

import explanations
from i18n.translations import t
from models import (
    AnalysisResult, CodeBlock, Confidence, RepoAnalysisResult, TextBlock,
    TextSpan,
)
from repo_scanner import SCOPE_BOTH
from ui import theme
from ui.code_preview import highlight_range
from ui.site_preview import build_highlight_js
from ui.widgets import ROW_ROLE, RowData, diagnostics_message, muted
from ui.worker import SingleBlockWorker, SingleRewriteWorker
from ui.window_parts.shared import MODE_AUDIT, MODE_REPO, MODE_WEB, _SUPPRESSED_NOTE


class FindingsPanelMixin:
    """Everything the window shows about copy findings (not audit rows).

    Reads `self.result`, `self.lang`, `self.drafts`, `self.flagged_list`,
    `self.results_stack`, `self.empty_state`, the preview widgets and the
    layout-mode flags from the facade.
    """

    # ------------------------------------------------------------- column 2

    @staticmethod
    def _is_character_span(span: TextSpan) -> bool:
        return (span.details or {}).get("source") == "characters"

    @staticmethod
    def _copy_key(span: TextSpan, block) -> tuple:
        """What makes two findings in two files the same finding: the flagged
        text and what it becomes. Not the file, which is the thing that
        varies, and not the offsets, which differ between a source file and
        its compiled twin."""
        return (block.text[span.start:span.end], span.replacement,
                (span.details or {}).get("source", span.detector_name))

    def _copy_counts(self, spans, blocks_by_id) -> dict:
        counts: dict = {}
        for span in spans:
            block = blocks_by_id.get(span.block_id)
            if block is None:
                continue
            key = self._copy_key(span, block)
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _span_label(self, span: TextSpan, block) -> str:
        """One line describing a flagged span.

        A non-keyboard character often has no visible glyph at all — a
        zero-width joiner rendered as-is would leave the row looking blank —
        so those rows show what was found plus a little surrounding text
        instead of the raw characters. The surrounding text is what makes
        the row identifiable when the same invisible character occurs a
        dozen times on a page.
        """
        raw = block.text[span.start:span.end]
        if self._is_character_span(span):
            before = block.text[max(0, span.start - 20):span.start].replace("\n", " ")
            after = block.text[span.end:span.end + 20].replace("\n", " ")
            names = span.explanation.split("] ", 1)[-1]
            if len(names) > 70:
                names = names[:69] + "…"
            return f"{names}   ·   …{before}⟦{raw}⟧{after}…"
        snippet = raw.strip().replace("\n", " ")
        snippet = snippet[:89] + "…" if len(snippet) > 90 else snippet
        kind = getattr(block, "kind", None)
        # Only labelled when more than one kind can be on screen at once —
        # in a pure content scan every row is markup or an injected string
        # and the prefix would be noise on every line.
        if kind and self._repo_scope() == SCOPE_BOTH:
            return f"[{t('kind_' + kind, self.lang)}] {snippet}"
        return snippet

    def _populate_flagged_list(self) -> None:
        self.flagged_list.clear()
        self._expanded_item = None
        # A both-questions run put its audit findings here first; they are part
        # of the same result and must not disappear when the copy pass lands.
        audit_rows = (self._add_audit_rows()
                      if self._last_request is not None
                      and self._last_request.wants_accessibility else 0)
        if not self.result:
            if not audit_rows:
                self._show_empty_state()
            return
        flagged = [s for s in self.result.spans if s.confidence != Confidence.LOW]
        flagged.sort(key=lambda s: s.score, reverse=True)
        if not flagged:
            if not audit_rows:
                self._show_empty_state()
            return

        self.results_stack.setCurrentIndex(0)
        blocks_by_id = {b.block_id: b for b in self.result.blocks()}
        item_to_reselect = None
        # Copies of one file - source, compiled output, deployed folder -
        # produce the same defect once each. They stay in `self.result.spans`
        # because each is a real file a fix has to edit; what the list shows
        # is one row per distinct text, with the rest counted on it. See
        # `duplicates.py`.
        copies = self._copy_counts(flagged, blocks_by_id)
        shown_keys: set = set()
        for span in flagged:
            block = blocks_by_id.get(span.block_id)
            if block is None:
                continue
            copy_key = self._copy_key(span, block)
            if copy_key in shown_keys:
                continue
            shown_keys.add(copy_key)
            key = (span.block_id, span.start, span.end)
            item = QListWidgetItem()
            # The row is painted by FindingDelegate rather than rendered from
            # this string, so the confidence badge can be a real coloured
            # pill instead of "[high · 0.95]" typed into the label. The plain
            # text is still set, because that is what keyboard search,
            # accessibility tooling and a copied selection read.
            label = self._span_label(span, block)
            extra = copies.get(copy_key, 1) - 1
            if extra:
                label += "   ·   " + t("finding_copies", self.lang, n=extra)
            item.setText(label)
            item.setData(ROW_ROLE, RowData(
                badge=f"{t('confidence_' + span.confidence.value, self.lang)} {span.score:.2f}",
                confidence=span.confidence,
                score=span.score,
                text=item.text(),
                has_draft=key in self.drafts,
                is_character=self._is_character_span(span),
            ))
            item.setToolTip(span.explanation)
            item.setData(Qt.ItemDataRole.UserRole, (self._text_row_kind(), span, block))
            self.flagged_list.addItem(item)
            if self._last_selected_key and key[0] == self._last_selected_key[0]:
                item_to_reselect = (item, span, block)

        # Best-effort: if a passage was expanded (narrow layout) or shown in
        # the detail column (wide layout) and a re-analysis just rebuilt the
        # list, put the same block back in front of the user instead of
        # silently collapsing everything.
        if item_to_reselect and not self.wide_mode:
            self._expand_item(*item_to_reselect)
        elif item_to_reselect and self.wide_mode:
            self._populate_detail_column(item_to_reselect[1], item_to_reselect[2])

    def _show_empty_state(self) -> None:
        """Explain an empty findings list instead of leaving it blank.

        Three different situations produce no rows, and they need different
        answers. "Nothing scanned yet" is an instruction. "Scanned, nothing
        flagged" is a result, and has to say plainly that it is not proof of
        anything. "Scanned but the crawler got no text" is the one that is
        actually a problem, and it is the reason `PageDiagnostics` exists —
        without it, a JavaScript-rendered site is indistinguishable from a
        clean one.
        """
        self.results_stack.setCurrentIndex(1)
        if not self.result:
            self.empty_state.show_message(
                t("empty_no_scan_title", self.lang),
                t("empty_no_scan_body", self.lang),
            )
            return

        blocks = len(self.result.blocks())
        if blocks:
            units = (len(self.result.pages) if isinstance(self.result, AnalysisResult)
                     else len(self.result.files))
            body = t("empty_clean_body", self.lang, blocks=blocks, pages=units)
            # A clean result from a truncated walk is not a clean result. The
            # sentence goes here rather than only in the status bar because
            # this pane is what a reader is looking at when they conclude the
            # repository is fine.
            body += self._truncation_notice()
            self.empty_state.show_message(t("empty_clean_title", self.lang), body)
            return

        if isinstance(self.result, RepoAnalysisResult):
            self.empty_state.show_message(
                t("empty_repo_no_text_title", self.lang),
                t("empty_repo_no_text_body", self.lang, files=len(self.result.files)),
            )
            return

        self.empty_state.show_message(
            t("empty_no_text_title", self.lang),
            self._crawl_diagnosis(),
        )

    def _truncation_notice(self) -> str:
        """The sentence a partial walk owes the reader, or "" when it read
        everything. Empty string rather than None so it can be concatenated
        without a branch at every call site."""
        walk = getattr(self.result, "diagnostics", None)
        if walk is None or not getattr(walk, "truncated", False):
            return ""
        return "\n\n" + t("scan_truncated", self.lang, limit=walk.limit,
                          files=walk.files_read)

    def _crawl_diagnosis(self) -> str:
        """Per-page reasons the crawl produced no text.

        Only pages that actually yielded nothing are listed: on a multi-page
        crawl the interesting output is which pages failed and why, not a
        repetition of the ones that worked. The advice line is added only
        for the client-rendered case, because it is the only one with a
        concrete next step from inside this app.
        """
        lines = [t("empty_no_text_body", self.lang), ""]
        empty_pages = [p for p in self.result.pages if not p.blocks]
        for page in empty_pages[:5]:
            message = diagnostics_message(page, self.lang)
            lines.append(page.url)
            lines.append(message or t("crawl_reason_no_text", self.lang))
            lines.append("")
        if len(empty_pages) > 5:
            lines.append(t("pages_with_problems", self.lang, n=len(empty_pages)))
        if any("js-rendered" in (p.diagnostics.reasons or []) for p in empty_pages):
            lines.append(t("crawl_advice_js", self.lang))
        return "\n".join(lines).strip()

    def _on_flagged_item_clicked(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, span, block = data
        if kind == MODE_AUDIT:
            # For an audit row the second slot is the issue and the third is
            # the other places the same problem was found - see
            # `AuditPanelMixin._add_audit_rows`.
            self._on_audit_item_clicked(span, block or [])
            return
        self._last_selected_key = (span.block_id, span.start, span.end)
        if kind == MODE_WEB:
            self._load_preview_and_highlight(block)
        else:
            self._load_code_preview_and_highlight(block)
        if self.wide_mode:
            self._populate_detail_column(span, block)
        else:
            self._toggle_inline_detail(item, span, block)

    # ------------------------------------------------------------- column 1

    def _load_preview_and_highlight(self, block: TextBlock) -> None:
        if not self.result:
            return
        page = next((p for p in self.result.pages if p.url == block.page_url), None)
        if page is None or not page.raw_html:
            return
        self._pending_highlight_dom_path = block.dom_path
        self._pending_highlight_tag = ""
        if self.current_preview_url != block.page_url:
            self.current_preview_url = block.page_url
            self.site_view.setHtml(page.raw_html, QUrl(block.page_url))
        else:
            self._run_pending_highlight()

    def _on_preview_loaded(self, _ok: bool) -> None:
        self._run_pending_highlight()

    def _highlight_color(self) -> QColor:
        """The one red used everywhere something is pointed at: the HIGH
        confidence badge, the code preview's highlight, and the site
        preview's outline. Derived from the palette rather than each of the
        three carrying its own hard-coded hex, so a token change moves all
        three together instead of two of the three."""
        color = QColor(self.palette_tokens.error)
        color.setAlpha(70)
        return color

    def _run_pending_highlight(self) -> None:
        if self._pending_highlight_dom_path:
            self.site_view.page().runJavaScript(build_highlight_js(
                self._pending_highlight_dom_path,
                getattr(self, "_pending_highlight_tag", ""),
                color=self.palette_tokens.error))

    def _load_code_preview_and_highlight(self, block: CodeBlock) -> None:
        if not self.result:
            return
        file_result = next((f for f in self.result.files if f.path == block.file_path), None)
        if file_result is None or file_result.raw_text is None:
            return
        if self.current_preview_path != block.file_path:
            self.current_preview_path = block.file_path
            self.code_view.setPlainText(file_result.raw_text)
        highlight_range(self.code_view, block.start, block.end, self._highlight_color())

    # ------------------------------------------------------------- column 3

    def _reset_detail_panel(self) -> None:
        self._clear_layout(self.detail_layout)
        placeholder = muted(t("select_prompt", self.lang))
        self.detail_layout.addWidget(placeholder)

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            child = layout.takeAt(0)
            widget = child.widget()
            if widget:
                # Unparented before it is scheduled for deletion.
                # `takeAt` only removes the widget from the *layout* - it
                # keeps its parent and keeps painting until the event loop
                # gets around to the deletion, so clearing and refilling in
                # one turn showed both the old contents and the new.
                widget.setParent(None)
                widget.deleteLater()

    def _populate_detail_column(self, span: TextSpan, block) -> None:
        self._clear_layout(self.detail_layout)
        self.detail_layout.addWidget(self._build_detail_widget(span, block))

    def _collapse_inline_detail(self) -> None:
        if self._expanded_item is not None:
            self.flagged_list.setItemWidget(self._expanded_item, None)
            self._expanded_item.setSizeHint(QSize())
            self._expanded_item = None

    def _toggle_inline_detail(self, item: QListWidgetItem, span: TextSpan, block) -> None:
        if self._expanded_item is item:
            self._collapse_inline_detail()
            return
        self._expand_item(item, span, block)

    def _expand_item(self, item: QListWidgetItem, span: TextSpan, block) -> None:
        if self._expanded_item is not None and self._expanded_item is not item:
            self.flagged_list.setItemWidget(self._expanded_item, None)
            self._expanded_item.setSizeHint(QSize())

        header = QLabel(item.text())
        # The same class the panel titles use, not an ad-hoc bold: an inline
        # expansion is standing in for the third column's own title, and
        # inventing a second "this is a heading" style for it is exactly the
        # kind of small divergence that adds up to "nothing quite matches".
        header.setProperty("class", theme.CLASS_HEADING)
        header.setWordWrap(True)
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(6, 6, 6, 6)
        wrapper_layout.addWidget(header)
        wrapper_layout.addWidget(self._build_detail_widget(span, block))
        self.flagged_list.setItemWidget(item, wrapper)
        item.setSizeHint(wrapper.sizeHint())
        self._expanded_item = item

    def _build_detail_widget(self, span: TextSpan, block) -> QWidget:
        lang = self.lang
        key = (block.block_id, span.start, span.end)
        original = block.text[span.start:span.end]
        is_repo_block = isinstance(block, CodeBlock)

        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        if is_repo_block:
            source_label = QLabel(t("finding_file_line", lang, path=block.file_path, line=block.line_number))
        else:
            source_label = QLabel(t("source_page", lang, url=block.page_url))
        source_label.setWordWrap(True)
        layout.addWidget(source_label)

        original_caption = muted(t("detail_original_label", lang))
        layout.addWidget(original_caption)
        original_view = QLabel(original)
        original_view.setWordWrap(True)
        original_view.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(original_view)

        # --- why this was flagged, and what to replace it with --------------
        # The score alone tells the user nothing they can act on. This turns
        # the detector's structured record into sentences in their language,
        # and — when the correction follows a rule rather than taste — offers
        # the corrected text directly, with no model call and no cost.
        explanation = explanations.render(span, block.text, lang)
        layout.addWidget(muted(t("detail_why_header", lang)))
        why_label = QLabel(explanation.as_text())
        why_label.setWordWrap(True)
        why_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(why_label)

        # `suppression.py` already lowers the score and drops the reasons the
        # user ruled out before this panel ever sees the span
        # (`details["suppressed"]`); what was missing was saying so here -
        # otherwise a lowered score with no visible cause reads as the
        # detector being unsure, not as a decision the user already made.
        if (span.details or {}).get("suppressed"):
            note = muted(_SUPPRESSED_NOTE)
            note.setProperty("class", theme.CLASS_MUTED)
            layout.addWidget(note)

        edit_box = QTextEdit()
        edit_box.setPlainText(self.drafts.get(key, original))
        edit_box.setPlaceholderText(t("replace_placeholder", lang))
        edit_box.setMaximumHeight(120)
        layout.addWidget(edit_box)

        if explanation.suggestion is not None:
            layout.addWidget(muted(t("detail_suggestion_header", lang)))
            suggestion_view = QLabel(
                explanation.suggestion if explanation.suggestion
                else t("suggest_delete", lang)
            )
            suggestion_view.setWordWrap(True)
            suggestion_view.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            layout.addWidget(suggestion_view)
            use_btn = QPushButton(t("detail_use_suggestion", lang))
            # Fills the draft box rather than applying anything: the offline
            # suggestion is a starting point the user still edits and saves,
            # exactly like a model-generated one.
            use_btn.clicked.connect(
                lambda _=False, text=explanation.suggestion: edit_box.setPlainText(text)
            )
            layout.addWidget(use_btn)
        layout.addWidget(muted(explanation.suggestion_note))

        btn_row = QHBoxLayout()
        save_btn = QPushButton(t("replace_save", lang))
        save_btn.setProperty("class", theme.CLASS_PRIMARY)
        save_btn.setToolTip(t("replace_save", lang))
        analyze_btn = QPushButton(t("detail_analyze_button", lang))
        analyze_btn.setToolTip(t("detail_analyze_tooltip", lang))
        refactor_btn = QPushButton(t("detail_refactor_button", lang))
        refactor_btn.setToolTip(t("detail_refactor_tooltip", lang))
        ignore_btn = self._build_ignore_button(
            lambda: self._on_ignore_span_clicked(span, block))
        btn_row.addWidget(save_btn)
        btn_row.addWidget(analyze_btn)
        btn_row.addWidget(refactor_btn)
        btn_row.addWidget(ignore_btn)
        layout.addLayout(btn_row)

        note = muted(t("replace_note", lang) if not is_repo_block else "")
        layout.addWidget(note)

        save_btn.clicked.connect(lambda: self._save_draft(key, edit_box.toPlainText()))
        analyze_btn.clicked.connect(lambda: self._run_additional_analysis(block, span))
        refactor_btn.clicked.connect(lambda: self._run_refactor(edit_box.toPlainText(), block, edit_box))

        return w

    # ------------------------------------------------------------- actions

    def _save_draft(self, key: tuple, text: str) -> None:
        self.drafts[key] = text
        for i in range(self.flagged_list.count()):
            item = self.flagged_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if not data:
                continue
            _kind, span, block = data
            if (span.block_id, span.start, span.end) == key:
                current = item.text()
                if not current.startswith("✎ "):
                    item.setText("✎ " + current)

    def _run_additional_analysis(self, block, span: TextSpan) -> None:
        detector_name, detector_config = self._detector_for_request()
        self.status_bar.showMessage(t("detail_analyzing", self.lang))

        worker = SingleBlockWorker(block, detector_name, detector_config)
        worker.finished_ok.connect(lambda spans: self._on_additional_analysis_done(block, detector_name, spans))
        worker.failed.connect(self._on_failed)
        worker.finished.connect(lambda: self.status_bar.showMessage(t("status_idle", self.lang)))
        self._track_worker(worker)
        worker.start()

    def _on_additional_analysis_done(self, block, detector_name: str, spans: list[TextSpan]) -> None:
        if not self.result:
            return
        self.result.spans = [
            s for s in self.result.spans
            if not (s.block_id == block.block_id and s.detector_name == detector_name)
        ]
        self.result.spans.extend(spans)
        self._populate_flagged_list()
        self._update_repo_buttons_enabled()

    def _run_refactor(self, draft_text: str, block, edit_box=None) -> None:
        """Rewrite this one passage through the configured provider and drop
        the result straight into the edit box, so it can be reviewed and
        adjusted before anything is saved or written to disk."""
        source_text = draft_text.strip() or block.text
        self.status_bar.showMessage(t("detail_analyzing", self.lang))

        worker = SingleRewriteWorker(source_text, getattr(block, "language_hint", None), self.settings)

        def on_ok(result: str) -> None:
            if edit_box is not None:
                edit_box.setPlainText(result)
            self.status_bar.showMessage(t("status_idle", self.lang))

        worker.finished_ok.connect(on_ok)
        worker.failed.connect(self._on_failed)
        self._track_worker(worker)
        worker.start()
