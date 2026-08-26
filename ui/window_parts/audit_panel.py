"""The audit findings panel: list rows, the detail card, one-issue fixes."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidgetItem, QMessageBox, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget,
)

import duplicates
from audit import explanations as audit_explanations
from audit import responsive
from i18n.translations import t
from models import Confidence
from ui import theme
from ui.widgets import (
    ROW_ROLE, FlowLayout, RowData, chip, divider, field, heading, muted,
    panel,
)
from ui.window_parts.shared import (
    MODE_AUDIT, _SEVERITY_BADGE, _SEVERITY_CONFIDENCE, _browser_url,
)


class AuditPanelMixin:
    """Everything the window shows about accessibility/SEO/performance rows.

    Reads `self.audit_result`, `self.lang`, `self.flagged_list`,
    `self.results_stack`, `self.empty_state`, `self.detail_layout`,
    `self.wide_mode` and the preview widgets from the facade.
    """

    def _populate_audit_list(self) -> None:
        self.flagged_list.clear()
        self._expanded_item = None
        if not self._add_audit_rows():
            self._show_audit_empty_state()
            return
        self.results_stack.setCurrentIndex(0)

    def _arrival_text(self, arrival) -> str:
        """When this line last changed, and in whose commit.

        "Last changed", said in those words, because that is what blame
        answers: a reformat, a rename or a moved block all take a line over,
        so a date here is not evidence of who introduced the problem. The
        sentence that follows it says so, and the caveat is not optional -
        an unqualified name-and-date beside a finding reads as an accusation.
        """
        from datetime import datetime

        when = ""
        if getattr(arrival, "when", ""):
            try:
                when = datetime.fromtimestamp(int(arrival.when)).strftime("%Y-%m-%d")
            except (ValueError, OSError, OverflowError):
                when = ""
        parts = [part for part in (when, arrival.author,
                                   f"{arrival.sha} {arrival.summary}".strip())
                 if part]
        text = " · ".join(parts)
        if getattr(arrival, "assistant", False):
            text += "\n" + t("audit_arrived_assistant", self.lang)
        return text + "\n" + t("audit_arrived_caveat", self.lang)

    #: How much of a distinguishing value a row carries. Long enough to
    #: recognise an address, short enough that it stays one line.
    _APART_CHARS = 42

    @staticmethod
    def _what_tells_it_apart(issue) -> str:
        """The one detail that makes this finding not the one above it.

        Taken from the fields the rule's own sentences interpolate, so it is
        the value the explanation would have shown anyway rather than a
        second vocabulary invented for the list. Falls back to the selector,
        which is what a rule with nothing to interpolate has instead.
        """
        from audit.explanations import template_fields_for

        details = getattr(issue, "details", None) or {}
        for name in template_fields_for(getattr(issue, "rule_id", "")):
            value = details.get(name)
            if value:
                text = " ".join(str(value).split())
                limit = AuditPanelMixin._APART_CHARS
                return text if len(text) <= limit else "…" + text[-(limit - 1):]
        return " ".join((getattr(issue, "selector", "") or "").split())

    def _add_audit_rows(self) -> int:
        """Append the audit findings to the list and say how many there were.

        Separate from clearing the list because a run can ask both questions,
        and then the copy pass finishes second and must add to these rows
        rather than replace them.
        """
        if self.audit_result is None:
            return 0
        issues = self.audit_result.issues()
        if not issues:
            return 0

        self.results_stack.setCurrentIndex(0)
        self.flagged_list.setItemDelegate(self.finding_delegate)
        # One row per distinct problem, with the number of places on it -
        # the same rule the copy findings already followed (`duplicates.py`).
        # A crawl of thirty pages sharing a header produced thirty identical
        # rows, and a list where every row repeats the previous one is a list
        # nobody reads to the bottom. Nothing is dropped: the grouped issues
        # travel with the row, so clicking it can still name every page.
        rows = 0
        grouped = list(duplicates.group_issues(issues))
        # Which titles are about to appear more than once. A page with twenty
        # images in an old format produced twenty rows reading "Image with no
        # dimensions set" and nothing else - the src that tells them apart is
        # in the finding, and was not on the row. Grouping is not the fix:
        # they are twenty different images, and merging them would lose which.
        # The row has to say what it is about.
        titles: dict = {}
        for issue, _others in grouped:
            title = audit_explanations.render(issue, self.lang).title
            titles[title] = titles.get(title, 0) + 1

        for issue, others in grouped:
            explanation = audit_explanations.render(issue, self.lang)
            places = duplicates.places_of(issue, others)
            label = explanation.title
            if titles.get(label, 0) > 1:
                # Only when it repeats. Adding it always would push the same
                # detail onto every row of every rule, which is how a list
                # stops being scannable in the other direction.
                distinguishing = self._what_tells_it_apart(issue)
                if distinguishing:
                    label += "   ·   " + distinguishing
            if len(places) > 1:
                label += "   ·   " + t("finding_copies", self.lang,
                                       n=len(places) - 1)
            item = QListWidgetItem()
            item.setText(label)
            item.setData(ROW_ROLE, RowData(
                badge=t(f"severity_{issue.severity}", self.lang),
                # The delegate colours a row by confidence, and severity is
                # the audit's word for the same axis. Mapped rather than
                # given the delegate a second vocabulary to paint.
                confidence=_SEVERITY_CONFIDENCE.get(issue.severity, Confidence.MEDIUM),
                score=0.0,
                text=label,
                has_draft=False,
                is_character=False,
            ))
            item.setToolTip(explanation.found if len(places) == 1
                            else explanation.found + "\n\n"
                            + "\n".join(places[:10]))
            # `others` rides along so the detail panel can list every place
            # without grouping the issues a second time.
            item.setData(Qt.ItemDataRole.UserRole, (MODE_AUDIT, issue, others))
            self.flagged_list.addItem(item)
            rows += 1
        return rows

    def _show_audit_empty_state(self) -> None:
        """An audit with no findings is a result, not a blank screen — and it
        is not a clean bill of health either, which the body text has to say
        rather than imply."""
        self.results_stack.setCurrentIndex(1)
        if self.audit_result is None:
            self.empty_state.show_message(
                t("empty_no_scan_title", self.lang),
                t("empty_no_scan_body", self.lang),
            )
            return
        checked = len(self.audit_result.documents)
        unreadable = [d for d in self.audit_result.documents if d.error]
        if checked and not unreadable:
            self.empty_state.show_message(
                t("empty_audit_clean_title", self.lang),
                t("empty_audit_clean_body", self.lang, documents=checked),
            )
            return
        lines = [t("empty_audit_unreadable_body", self.lang), ""]
        for document in unreadable[:5]:
            lines.append(document.source)
            lines.append(document.error)
            lines.append("")
        self.empty_state.show_message(
            t("empty_audit_unreadable_title", self.lang), "\n".join(lines).strip())

    def _on_audit_item_clicked(self, issue, others=None) -> None:
        """Show the finding in its document, and the explanation beside it.

        "Show" means the element, not the page: a list of findings next to a
        page scrolled to the top leaves the reader to hunt for the thing the
        row is about. Which preview does the showing depends on what the
        document is - a page gets outlined in the browser, a source file gets
        its line highlighted.
        """
        from analysis_modes import SOURCE_REPO

        if self.source == SOURCE_REPO:
            self._show_audit_issue_in_code(issue)
        else:
            self._show_audit_issue_in_page(issue)
        if self.wide_mode:
            self._clear_layout(self.detail_layout)
            self.detail_layout.addWidget(
                self._build_audit_detail_widget(issue, others))
        else:
            # In a narrow window there is no third column, so the explanation
            # expands under the row that was clicked - the same behaviour the
            # text scan has always had.
            self._toggle_audit_detail(self.flagged_list.currentItem(), issue,
                                      others)

    #: How many places the detail card lists before it stops. Enough to see
    #: whether this is the whole site or three pages; a card that is nothing
    #: but addresses has stopped being an explanation.
    _PLACES_IN_DETAIL = 25

    #: Elements a finding can name that cannot be pointed at on screen.
    #: `<head>` has no rendered box, and outlining `<html>` outlines
    #: everything, which points at nothing.
    _UNSHOWABLE_ELEMENTS = ("head", "html")

    @staticmethod
    def _element_of(snippet: str) -> str:
        """The element name a snippet opens with, or "".

        Findings about the document as a whole carry no selector - they are
        about an element that is missing, so there is nothing to select - but
        they do say which container they were raised against (`<body>…</body>`),
        and that is enough to point at.
        """
        import re
        match = re.match(r"\s*<([a-zA-Z][\w:-]*)", snippet or "")
        return match.group(1).lower() if match else ""

    def _audit_target(self, issue) -> str:
        """The CSS selector this finding can be shown at, or "" if none can.

        Written as its own function because the answer is not "issue.selector":
        five of the eight findings a plain page produces (no h1, no canonical,
        no meta description, no Open Graph, no structured data) have an empty
        selector and no line, since what they report is something *absent*.
        Clicking those used to do nothing at all - no highlight, no message,
        no reason given - which is what "some findings are not clickable"
        turned out to mean.
        """
        if issue.selector:
            return issue.selector
        element = self._element_of(issue.snippet)
        if not element or element in self._UNSHOWABLE_ELEMENTS:
            return ""
        return element

    def _show_audit_issue_in_page(self, issue) -> None:
        address = _browser_url(issue.source)
        target = self._audit_target(issue)
        # Held until the page reports itself loaded: highlighting a document
        # that is still arriving finds nothing and leaves no trace of trying.
        self._pending_highlight_dom_path = target
        self._pending_highlight_tag = issue.snippet or ""
        if not target:
            # Said rather than left silent: the finding is about the document,
            # and a click that quietly does nothing reads as a broken row.
            self.status_bar.showMessage(t("audit_document_level", self.lang))
        if self.current_preview_url != address:
            self.current_preview_url = address
            self.site_view.setUrl(QUrl(address))
        else:
            self._run_pending_highlight()

    def _show_audit_issue_in_code(self, issue) -> None:
        """A repository finding lives on a line of a file, so show that line -
        and when it has no line, show the file anyway.

        The early return that used to stand here made every document-level
        finding in repository mode do nothing when clicked, including the case
        where the file was not even open in the preview yet.
        """
        from ui.code_preview import highlight_line

        try:
            text = Path(issue.source).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            self.status_bar.showMessage(str(exc))
            return
        if self.current_preview_path != issue.source:
            self.current_preview_path = issue.source
            self.code_view.setPlainText(text)
        self.col1_stack.setCurrentIndex(1)
        if issue.line:
            highlight_line(self.code_view, issue.line, self._highlight_color())
        else:
            self.status_bar.showMessage(t("audit_document_level", self.lang))

    def _toggle_audit_detail(self, item, issue, others=None) -> None:
        """Expand the finding under its row, or collapse it if already open."""
        if item is None:
            return
        if self._expanded_item is item:
            self._collapse_inline_detail()
            return
        self._collapse_inline_detail()
        detail = self._build_audit_detail_widget(issue, others)
        # Bounded: an explanation with four blocks and two code samples is
        # taller than a list row has any business being, and a row that fills
        # the window hides the findings the user is comparing it against.
        detail.setMaximumHeight(460)
        self.flagged_list.setItemWidget(item, detail)
        item.setSizeHint(QSize(0, min(detail.sizeHint().height(), 460)))
        self._expanded_item = item

    def _build_audit_detail_widget(self, issue, others=None) -> QWidget:
        """One finding, laid out as the four questions it answers.

        What was found, why it matters, how to fix it, and - when the check
        cannot be certain - what would make it a false positive. Four boxed
        blocks rather than four paragraphs: someone who already believes the
        finding wants only the third one, and should not have to read the
        first two to reach it.

        Under them, where the rule knows the corrected markup, the correction
        itself and a button that writes exactly that one element. The button
        is here rather than only in the toolbar because this is the moment
        the user has decided about *this* finding, and making them then find
        it again in a batch is how a fix list stops being used.
        """
        from PySide6.QtWidgets import QScrollArea

        explanation = audit_explanations.render(issue, self.lang)
        container, body, _title = panel(t("detail_panel_title", self.lang))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(self.palette_tokens.space_sm)

        title = heading(explanation.title)
        title.setWordWrap(True)
        layout.addWidget(title)

        # The identity of the finding, as chips: severity, where it is, and
        # who found it. A row of small facts reads faster than a sentence
        # that has to be parsed to get at the same three things.
        # A flow, not a row: chips used to push the column's minimum width to
        # the sum of their own, so the third column could not be narrowed and a
        # long selector made the whole window unshrinkable.
        chips_host = QWidget()
        chips = FlowLayout(chips_host, spacing=6)
        severity_chip = QLabel(t(f"severity_{issue.severity}", self.lang))
        severity_chip.setProperty("class", _SEVERITY_BADGE[issue.severity])
        chips.addWidget(severity_chip)
        # The tail of the selector, short enough not to dictate how narrow the
        # column may become. The whole of it is on the chip as a tooltip: it is
        # worth having, just not worth 300 pixels of minimum width.
        if issue.line:
            where = f"{t('detail_line', self.lang)} {issue.line}"
            where_full = where
        else:
            where_full = issue.selector or Path(issue.source).name
            where = where_full[-28:]
            if len(where_full) > 28:
                where = "…" + where
        where_chip = chip(where)
        where_chip.setToolTip(where_full)
        chips.addWidget(where_chip)
        chips.addWidget(chip(issue.rule_id))
        if issue.engine and issue.engine != "static":
            chips.addWidget(chip(issue.engine))
        # A finding seen at one width out of the three the window always runs
        # is a different fact from one seen at all of them: the mobile menu's
        # unnamed button does not exist in the desktop DOM at all. The list
        # is recorded by `audit.responsive.merge`; a static finding has none
        # and gets no chip.
        only = responsive.only_at(issue)
        if only:
            width = dict((name, w) for name, w, _h in responsive.BREAKPOINTS)
            only_chip = chip(t("audit_only_at", self.lang,
                               width=width.get(only, only)))
            only_chip.setToolTip(t("audit_only_at_note", self.lang,
                                   name=t(f"breakpoint_{only}", self.lang)))
            chips.addWidget(only_chip)

        also = (issue.details or {}).get("also_found_by", [])
        if also:
            also_label = ", ".join(also)
            confirm_chip = chip(f"+ {also_label}")
            confirm_chip.setToolTip(t("audit_also_found_by", self.lang,
                                      engines=also_label))
            chips.addWidget(confirm_chip)
        layout.addWidget(chips_host)

        layout.addWidget(divider())

        for label_key, text_body in (("audit_found", explanation.found),
                                     ("audit_why", explanation.why),
                                     ("audit_fix", explanation.fix),
                                     ("audit_caveat", explanation.caveat)):
            if text_body:
                layout.addWidget(field(t(label_key, self.lang), text_body))

        if issue.snippet:
            layout.addWidget(self._evidence(t("detail_element", self.lang),
                                            issue.snippet))
        if issue.fix_snippet:
            layout.addWidget(self._evidence(t("detail_replacement", self.lang),
                                            issue.fix_snippet))

        arrival = (issue.details or {}).get("arrived")
        if arrival is not None and getattr(arrival, "sha", ""):
            layout.addWidget(field(t("audit_arrived", self.lang),
                                   self._arrival_text(arrival)))

        confirmations = (issue.details or {}).get("also_found_by")
        if confirmations:
            layout.addWidget(muted(t("audit_also_found_by", self.lang,
                                     engines=", ".join(confirmations))))

        # Every place this same problem was found. The row collapses them into
        # one line; the detail is where the full list belongs, because a fix
        # has to visit each of them.
        places = duplicates.places_of(issue, others or [])
        if len(places) > 1:
            layout.addWidget(field(
                t("audit_places", self.lang, count=len(places)),
                "\n".join(places[:self._PLACES_IN_DETAIL])
                + ("\n…" if len(places) > self._PLACES_IN_DETAIL else "")))

        layout.addStretch(1)
        scroll.setWidget(inner)
        body.addWidget(scroll, stretch=1)

        actions = self._detail_actions(issue)
        if actions is not None:
            body.addWidget(divider())
            body.addWidget(actions)

        body.addWidget(divider())
        ignore_row = QWidget()
        ignore_layout = QHBoxLayout(ignore_row)
        ignore_layout.setContentsMargins(14, 10, 14, 12)
        ignore_layout.addStretch(1)
        ignore_layout.addWidget(
            self._build_ignore_button(lambda: self._on_ignore_issue_clicked(issue)))
        body.addWidget(ignore_row)
        return container

    def _evidence(self, label_text: str, markup: str) -> QWidget:
        """Markup shown as evidence: readable, selectable, not editable."""
        holder = QWidget()
        holder.setProperty("class", theme.CLASS_FIELD)
        holder.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(4)
        caption = QLabel(label_text.upper())
        caption.setProperty("class", theme.CLASS_FIELD_LABEL)
        layout.addWidget(caption)
        view = QPlainTextEdit(markup)
        view.setProperty("class", theme.CLASS_CODE)
        view.setReadOnly(True)
        view.setMaximumHeight(84)
        layout.addWidget(view)
        return holder

    def _detail_actions(self, issue):
        """The row of things that can be done about this one finding.

        Absent entirely when there is nothing to do: a disabled button with a
        tooltip explaining why it is disabled is a worse answer than the
        sentence that replaces it here.
        """
        from audit import fixer

        if not issue.fix_snippet or issue.source.startswith(("http://", "https://")):
            return None

        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(self.palette_tokens.space_sm)

        held_back = fixer.DECISION_RULES.get(issue.rule_id, "")
        if held_back:
            note = muted(t("detail_needs_decision", self.lang))
            note.setWordWrap(True)
            layout.addWidget(note, stretch=1)
        else:
            layout.addStretch(1)

        button = QPushButton(t("detail_fix_this", self.lang))
        button.setProperty("class", theme.CLASS_ACCENT)
        button.setToolTip(t("detail_fix_this_tooltip", self.lang))
        button.clicked.connect(lambda: self._fix_single_issue(issue))
        layout.addWidget(button)
        return row

    def _fix_single_issue(self, issue) -> None:
        """Write one correction, for the finding in front of the user."""
        from audit import fix_ai, fixer
        from audit.engine import DocumentReport

        document = DocumentReport(source=issue.source)
        document.issues = [issue]
        ready, pending, skipped = fixer.plan_fixes([document])

        if pending:
            filled, pending = fix_ai.fill_locally(pending, self._audited_text())
            ready += filled

        if pending:
            plan = pending[0]
            answer = QMessageBox.question(
                self, t("detail_fix_this", self.lang),
                t("detail_decide_body", self.lang, reason=plan.needs_input),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            import rewriter

            try:
                provider = rewriter.build_provider(self.settings)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(self, t("detail_fix_this", self.lang), str(exc))
                return
            filled, pending = fix_ai.describe(pending, self._audited_text(),
                                              provider, self.lang)
            ready += filled

        if not ready:
            reason = (skipped[0].reason if skipped
                      else (pending[0].needs_input if pending else ""))
            QMessageBox.information(self, t("detail_fix_this", self.lang),
                                    reason or t("fix_nothing_ready", self.lang))
            return

        outcome = fixer.apply_fixes(ready)
        if outcome.errors:
            QMessageBox.warning(self, t("detail_fix_this", self.lang),
                                "\n".join(outcome.errors))
            return
        self.status_bar.showMessage(
            t("fix_done", self.lang, applied=len(outcome.applied),
              files=len(outcome.files_changed)))
        self._reaudit_after_fix()
