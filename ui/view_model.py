"""ViewModel: business logic separated from UI.

MainViewModel owns the workers, caching, and action handlers that used
to live directly on MainWindow. The window forwards user actions here
and subscribes to signals for results, progress, and errors.

Design:
- AppState owns the user's choices (source, reader, check, method).
- ViewModel owns what happens when the user acts (analyze, rewrite, fix).
- MainWindow owns the widgets and layout.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

import config
import suppression
from analysis_modes import (
    CHECK_ACCESSIBILITY,
    CHECK_AI_PATTERNS,
    METHOD_AI,
    METHOD_EMBEDDING,
    METHOD_LOCAL,
    READER_BROWSER,
    READER_CODE,
    SOURCE_FILE,
    SOURCE_REPO,
    SOURCE_SITE,
    AnalysisRequest,
)
from detectors.factory import DetectorFactory
from detectors.judges import judge_for_provider
from models import AnalysisResult, RepoAnalysisResult, TextSpan
from ui.app_state import AppState
from ui.worker import (
    AnalysisWorker,
    AuditWorker,
    RepoAnalysisWorker,
    RewriteAllWorker,
    SingleBlockWorker,
    SingleRewriteWorker,
)


def _browser_url(source: str) -> str:
    if source.startswith(("http://", "https://", "file://")):
        return source
    return Path(source).resolve().as_uri()


class MainViewModel(QObject):
    """Business logic for the main window.

    Signals carry results and status to the UI layer. The UI never
    accesses workers, caches, or settings directly - it goes through
    this object.
    """

    # -- result signals ----------------------------------------------------
    web_result_ready = Signal(object)       # AnalysisResult
    repo_result_ready = Signal(object)      # RepoAnalysisResult
    audit_result_ready = Signal(object)     # AuditResult
    rewrite_ready = Signal(object)          # dict[tuple, str]
    single_rewrite_ready = Signal(object, object)  # (key, draft)

    # -- progress signals --------------------------------------------------
    status_message = Signal(str)            # status bar text
    crawling = Signal(str, int)             # (url, depth)
    scanning = Signal(str)                  # repo file path
    detecting = Signal(str)                 # detector phase
    auditing = Signal(str)                  # audit target

    # -- error signal ------------------------------------------------------
    error = Signal(str)                     # error message

    # -- browser pass signal -----------------------------------------------
    browser_pass_needed = Signal()          # audit done, browser pass needed

    # -- UI dialog signals -------------------------------------------------
    undo_outcome = Signal(str)              # message
    download_choice_needed = Signal(bool, bool)  # (has_audit, has_text)
    unicode_fixed = Signal(int)             # filled count

    # -- state signals -----------------------------------------------------
    busy_changed = Signal(bool)             # analysis running or not
    buttons_changed = Signal()              # recompute button enabled state

    def __init__(self, app_state: AppState, settings: config.Settings,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.state = app_state
        self.settings = settings

        # Results
        self.result: AnalysisResult | RepoAnalysisResult | None = None
        self.audit_result: Any | None = None
        self.drafts: dict[tuple, str] = {}

        # Workers
        self._worker = None
        self._rewrite_worker: RewriteAllWorker | None = None
        self._active_workers: list = []

        # Extraction cache
        self._last_request: AnalysisRequest | None = None
        self._extraction_request: AnalysisRequest | None = None
        self._cached_pages = None
        self._cached_files = None
        self._cached_scope = None

        # Repo config. The person's own list; what the *run* uses is
        # `effective_ignore_patterns`, which adds what the detected stack
        # says is not theirs. Two names because they are two facts, and
        # storing the sum would make the person's own list unrecoverable the
        # moment a profile was detected.
        self.repo_ignore_patterns: list[str] = []

        # Pending copy pass (for both-questions runs)
        self._pending_copy_pass = False
        # File mode: run code analysis then browser analysis
        self._file_both_passes = False

    # -- public properties -------------------------------------------------
    @property
    def is_busy(self) -> bool:
        return self._worker is not None

    @property
    def mode(self) -> str:
        return self.state.mode

    # -- request building --------------------------------------------------
    def current_request(self) -> AnalysisRequest:
        """Build a normalised request from the current state."""
        return AnalysisRequest(
            source=self.state.source,
            target=self.state.target,
            depth=self.state.depth,
            readers=self.state.readers,
            checks=self.state.checks,
            methods=self.state.methods,
            ai_available=self.state.ai_available,
        ).normalised()

    def _ai_available(self) -> bool:
        try:
            import rewriter
            from llm.base import LLMUnavailable
            provider = rewriter.build_provider(self.settings, allow_auto=True)
            try:
                return bool(provider.auth_status().signed_in)
            except LLMUnavailable:
                return False
        except Exception:
            return False

    def refresh_ai_available(self) -> None:
        self.state.set_ai_available(self._ai_available())

    # -- extraction cache --------------------------------------------------
    def _reusable_pages(self):
        request = self.current_request()
        if self._cached_pages and request.reuses_extraction(self._extraction_request):
            return self._cached_pages
        return None

    def _reusable_files(self):
        request = self.current_request()
        scope = self._repo_scope()
        if (self._cached_files
                and self._cached_scope == scope
                and request.reuses_extraction(self._extraction_request)):
            return self._cached_files
        return None

    def _remember_extraction(self, request, *, pages=None, files=None, scope=None):
        self._extraction_request = request
        if pages is not None:
            self._cached_pages = pages
        if files is not None:
            self._cached_files = files
            self._cached_scope = scope

    def forget_extraction(self):
        self._extraction_request = None
        self._cached_pages = None
        self._cached_files = None
        self._cached_scope = None

    def _repo_scope(self) -> str:
        return self.state.scope

    # -- detector selection ------------------------------------------------
    def _detector_for_request(self) -> tuple[str, dict]:
        request = self._last_request or self.current_request()
        provider_key = self.state.provider or self.settings.llm_provider
        judge = judge_for_provider(provider_key)
        if request.wants_ai and request.wants_local:
            name = "hybrid"
        elif request.wants_ai:
            name = judge
        elif request.wants_embedding:
            name = "embedding"
        else:
            name = "offline"
        return name, self._detector_config_for(name, judge)

    def _detector_config_for(self, detector_name: str, judge_name: str = "") -> dict:
        resolved = DetectorFactory.resolve(detector_name)
        if resolved == "hybrid":
            judge = judge_name or judge_for_provider(self.settings.llm_provider)
            return {
                "categories": self._active_unicode_categories() or (),
                "judge_name": judge,
                "judge_config": self._detector_config_for(judge),
            }
        if resolved in ("claude-llm-judge", "claude-official-watermark"):
            return {
                "api_key": config.get_anthropic_api_key(),
                "model": self.settings.claude_model,
            }
        if resolved == "xformat-llm-judge":
            return {
                "base_url": self.settings.xformat_base_url,
                "endpoints": self.settings.xformat_endpoints,
            }
        if resolved == "offline":
            return {"categories": self._active_unicode_categories() or ()}
        return {}

    def _active_unicode_categories(self):
        if not self.settings.unicode_check_enabled:
            return None
        return tuple(self.settings.unicode_categories or ())

    # -- analysis actions --------------------------------------------------
    def analyze(self) -> str | None:
        """Start analysis. Returns error message or None on success."""
        request = self.current_request()
        if not request.target:
            return self._missing_target_message()

        for note in request.notes:
            self.status_message.emit(self._note_message(note))

        self._last_request = request

        # Browser reading must happen on the main thread
        if request.wants_browser and self._reusable_pages() is None:
            pages = self._render_for_request(request)
            if request.source in (SOURCE_SITE, SOURCE_FILE):
                if pages is None:
                    return "browser_failed"
                self._remember_extraction(request, pages=pages)

        self._pending_copy_pass = (request.wants_accessibility
                                   and request.wants_ai_patterns)
        if request.wants_accessibility:
            self._start_audit()
        else:
            self._start_copy_pass()
        return None

    def _missing_target_message(self) -> str:
        from i18n.translations import t
        lang = self.settings.ui_language
        if self.state.source == SOURCE_REPO:
            return t("no_repo_path", lang)
        if self.state.source == SOURCE_FILE:
            return t("no_file_path", lang)
        return t("url_label_full", lang)

    def _note_message(self, note: str) -> str:
        from i18n.translations import t
        lang = self.settings.ui_language
        if "browser" in note:
            return t("reader_browser_unavailable", lang)
        if "AI pass" in note or "account or key" in note:
            return t("method_ai_unavailable", lang)
        return note

    def _render_for_request(self, request: AnalysisRequest):
        """Browser rendering - must be called from the main thread."""
        from audit import driver
        from crawler import RENDER_AUTO, CrawlConfig, crawl, page_from_html

        usable, reason = driver.available()
        if not usable:
            self.error.emit(reason)
            return None

        if request.source == SOURCE_FILE:
            return self._render_single_file(request.target)
        elif request.source == SOURCE_SITE:
            return self._render_crawl(request.target)
        return None

    def _render_crawl(self, url: str):
        from audit import driver
        from crawler import RENDER_AUTO, CrawlConfig, crawl

        usable, reason = driver.available()
        if not usable:
            self.error.emit(reason)
            return None

        cfg = CrawlConfig(max_depth=self.state.depth,
                          max_pages=self.settings.max_pages,
                          render_mode=RENDER_AUTO)

        def progress(page_url: str, _depth: int) -> None:
            from i18n.translations import t
            self.status_message.emit(
                t("status_browser_pass", self.settings.ui_language, url=page_url))

        try:
            with driver.html_renderer() as render:
                return crawl(url, cfg, progress_cb=progress, render=render)
        except Exception as exc:
            self.error.emit(str(exc))
            return None

    def _render_single_file(self, path: str):
        from audit import driver
        from crawler import page_from_html

        if not path:
            from i18n.translations import t
            self.error.emit(t("no_file_path", self.settings.ui_language))
            return None
        usable, reason = driver.available()
        if not usable:
            self.error.emit(reason)
            return None
        address = _browser_url(path)
        from i18n.translations import t
        self.status_message.emit(
            t("status_browser_pass", self.settings.ui_language, url=address))
        try:
            with driver.html_renderer() as render:
                html = render(address) or ""
        except Exception as exc:
            self.error.emit(str(exc))
            return None
        if not html:
            from i18n.translations import t
            self.error.emit(t("reader_browser_empty", self.settings.ui_language))
            return None
        return [page_from_html(html, address)]

    def _start_copy_pass(self):
        if self.state.source == SOURCE_REPO:
            self._start_repo_analysis()
        elif self.state.source == SOURCE_FILE:
            # File: always run code analysis first, then browser if available.
            # The raw file and the rendered DOM show different things.
            self._file_both_passes = self._reusable_pages() is not None
            self._start_file_copy_analysis()
        else:
            self._start_web_analysis()

    def _start_web_analysis(self, root: str = ""):
        url = root or self.state.target
        if not url:
            from i18n.translations import t
            self.error.emit(t("url_label_full", self.settings.ui_language))
            return
        if not url.startswith(("http://", "https://", "file://")):
            url = "https://" + url

        detector_name, detector_config = self._detector_for_request()
        reused = self._reusable_pages()
        if reused is not None:
            from i18n.translations import t
            self.status_message.emit(
                t("status_reusing_pages", self.settings.ui_language, count=len(reused)))

        self._worker = AnalysisWorker(
            pages=reused,
            root_url=url,
            depth=self.state.depth,
            detector_name=detector_name,
            detector_config=detector_config,
            max_pages=self.settings.max_pages,
            unicode_categories=self._active_unicode_categories(),
            settings=self.settings,
            # The checkout behind this site, when one was named. Findings
            # then carry the file and the line that wrote the passage; see
            # `repo_pairing`.
            paired_repo=self.state.paired_repo,
            paired_ignore=self.effective_ignore_patterns,
        )
        self._wire_worker(self._worker,
                          on_finished=self._on_web_finished)
        self._worker.start()
        self.busy_changed.emit(True)

    def _start_file_copy_analysis(self):
        self._start_repo_analysis(self.state.target)

    def _start_repo_analysis(self, path: str | None = None):
        path = path if path is not None else self.state.target
        if not path:
            from i18n.translations import t
            self.error.emit(t("no_repo_path", self.settings.ui_language))
            return

        detector_name, detector_config = self._detector_for_request()
        self._worker = RepoAnalysisWorker(
            files=self._reusable_files(),
            root_dir=path,
            ignore_patterns=self.effective_ignore_patterns,
            detector_name=detector_name,
            detector_config=detector_config,
            unicode_categories=self._active_unicode_categories(),
            scope=self._repo_scope(),
            settings=self.settings,
        )
        self._wire_worker(self._worker,
                          on_finished=self._on_repo_finished)
        self._worker.start()
        self.busy_changed.emit(True)

    @property
    def effective_ignore_patterns(self) -> list:
        """What a folder run actually skips: the person's list plus the
        detected stack's, unless they have lifted the latter."""
        return self.state.ignore_patterns_with_project(self.repo_ignore_patterns)

    def _start_audit(self):
        """Audit whatever the source is: a site, one page file, or a folder.

        A folder used to end up here with `https://` glued onto its path -
        see `ui.worker.audit_worker_for`, which now decides this once for
        both callers.
        """
        from i18n.translations import t
        from ui.worker import audit_worker_for

        lang = self.settings.ui_language
        worker, refusal = audit_worker_for(
            self.state.source,
            target=self.state.target,
            depth=self.state.depth,
            max_pages=self.settings.max_pages,
            pages=(self._reusable_pages()
                   if self.state.source == SOURCE_SITE else None),
            ignore_patterns=self.effective_ignore_patterns,
            max_files=self.settings.max_files,
            settings=self.settings,
            site_controls=self.state.site_controls,
            medium=self.state.medium,
            within=self.state.within,
        )
        if worker is None:
            self.error.emit(self._missing_target_message() if refusal == "no_target"
                            else t("url_label_full", lang))
            return

        self.audit_result = None
        self._worker = worker
        self._wire_worker(self._worker,
                          on_finished=self._on_audit_finished)
        self._worker.start()
        self.busy_changed.emit(True)

    def cancel(self):
        if self._worker is not None:
            self._worker.requestInterruption()

    # -- worker management -------------------------------------------------
    def _wire_worker(self, worker, *, on_finished):
        if hasattr(worker, 'crawling'):
            worker.crawling.connect(self.crawling)
        if hasattr(worker, 'scanning'):
            worker.scanning.connect(self.scanning)
        if hasattr(worker, 'detecting'):
            worker.detecting.connect(self.detecting)
        if hasattr(worker, 'auditing'):
            worker.auditing.connect(self.auditing)
        worker.finished_ok.connect(on_finished)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._on_worker_finished)
        self._active_workers.append(worker)

    def _on_worker_finished(self):
        self._worker = None
        self.busy_changed.emit(False)
        self.buttons_changed.emit()

    def _on_failed(self, message: str):
        self.error.emit(message)

    def _on_web_finished(self, result: AnalysisResult):
        self._report_session()
        self._report_pairing()
        if isinstance(self.result, RepoAnalysisResult) and self.state.source == SOURCE_FILE:
            # Merge browser findings into the code analysis result
            self.result.spans.extend(result.spans)
            self.repo_result_ready.emit(self.result)
        else:
            self.result = result
            self._remember_extraction(self._last_request,
                                      pages=result.pages)
            self.web_result_ready.emit(result)

    def _report_session(self, worker=None) -> None:
        """Say when a run read the site as a signed-in person.

        The host and nothing else. A run that was authenticated is a
        different run - what it found is what *that account* sees - and a
        report of it that does not say so is a report about the wrong
        visitor.
        """
        from i18n.translations import t

        worker = worker if worker is not None else self._worker
        host = getattr(worker, "session_host", "")
        if host:
            self.status_message.emit(
                t("sign_in_site_active", self.settings.ui_language, host=host))

    def _report_pairing(self) -> None:
        """Say how much of the site the paired checkout actually explained.

        The number is the honest half of pairing. Three matches out of forty
        means the wrong folder - or copy that arrives from a CMS - and a
        window that showed only the three files it did find would let a
        person believe the other thirty-seven passages are not in the code.
        """
        from i18n.translations import t

        worker = self._worker
        if not getattr(worker, "paired_repo", ""):
            return
        total = getattr(worker, "paired_total", 0)
        matched = getattr(worker, "paired_matched", 0)
        if not total:
            return
        key = "paired_repo_matched" if matched else "paired_repo_none"
        self.status_message.emit(t(key, self.settings.ui_language,
                                   matched=matched, total=total))

    def _on_repo_finished(self, result: RepoAnalysisResult):
        self.result = result
        self._remember_extraction(self._last_request,
                                  files=result.files,
                                  scope=self._repo_scope())
        if self._file_both_passes:
            # Code analysis done, now run browser analysis on the rendered DOM
            self._file_both_passes = False
            self._start_web_analysis(root=_browser_url(self.state.target))
        else:
            self.repo_result_ready.emit(result)

    def _on_audit_finished(self, result):
        self._report_session()
        self.audit_result = result
        self.audit_result_ready.emit(result)
        if self._last_request and self._last_request.wants_browser:
            self.browser_pass_needed.emit()
        if self._pending_copy_pass:
            self._pending_copy_pass = False
            self._start_copy_pass()

    # -- rewrite actions ---------------------------------------------------
    def rewrite_all(self):
        if not self.result or not self.result.spans:
            return
        self._rewrite_worker = RewriteAllWorker(
            self.result.spans, self.settings)
        self._rewrite_worker.finished_ok.connect(self._on_rewrite_finished)
        self._rewrite_worker.failed.connect(self._on_failed)
        self._rewrite_worker.finished.connect(
            lambda: setattr(self, '_rewrite_worker', None))
        self._active_workers.append(self._rewrite_worker)
        self._rewrite_worker.start()
        self.busy_changed.emit(True)

    def _on_rewrite_finished(self, drafts: dict):
        self.drafts = drafts
        self.rewrite_ready.emit(drafts)

    def rewrite_single(self, span: TextSpan, block):
        worker = SingleRewriteWorker(span, block, self.settings)
        worker.finished_ok.connect(
            lambda key, draft: self._on_single_rewrite(key, draft))
        worker.failed.connect(self._on_failed)
        worker.finished.connect(
            lambda: self._active_workers.remove(worker)
            if worker in self._active_workers else None)
        self._active_workers.append(worker)
        worker.start()

    def _on_single_rewrite(self, key, draft):
        self.drafts[key] = draft
        self.single_rewrite_ready.emit(key, draft)

    # -- fix actions -------------------------------------------------------
    def fix_unicode(self, spans):
        if not spans or not self.result:
            return
        blocks_by_id = {b.block_id: b for b in self.result.blocks()}
        filled = 0
        for span in spans:
            block = blocks_by_id.get(span.block_id)
            if block is None or span.replacement is None:
                continue
            original = block.text[span.start:span.end]
            if span.replacement != original:
                self.drafts[(block.block_id, span.start, span.end)] = span.replacement
                filled += 1
        self.unicode_fixed.emit(filled)
        self.buttons_changed.emit()

    # `fix_on_disk` and `apply_fix_with_ai` lived here and wrote the audit's
    # corrections straight to disk after a message box with two counts in it.
    # They are gone: the same corrections are rows in the replacement list
    # now, read before they are written, and a second path to the same write
    # is a second answer to "what changed in my repository". What the model
    # can answer is `replacements.fill_decisions`.

    def undo_fix(self):
        from audit import fixer
        from i18n.translations import t
        lang = self.settings.ui_language
        docs = self.audit_result.documents if self.audit_result else []
        paths = fixer.backups_for(docs)
        if not paths:
            return
        restored, problems = fixer.restore(paths)
        message = t("undo_done", lang, files=len(restored))
        if problems:
            message += "\n\n" + "\n".join(problems)
        self.undo_outcome.emit(message)
        self.buttons_changed.emit()

    # -- download actions --------------------------------------------------
    def download(self):
        has_audit = bool(self.audit_result and self.audit_result.documents)
        has_text = bool(self.result and self.result.spans)
        if not has_audit and not has_text:
            return
        self.download_choice_needed.emit(has_audit, has_text)

    def _report_model(self):
        """The findings of this run as one report model, or None.

        An audit and a copy scan can both be asked for in the same run, and
        the report is of the run, not of one of its halves - so the two sets
        of findings go into one model rather than producing two documents
        that each omit half of what was found.
        """
        from report.model import from_accessibility, from_text_analysis
        lang = self.settings.ui_language
        has_text = bool(self.result and self.result.spans)
        has_audit = bool(self.audit_result and self.audit_result.documents)
        # Exported through the same view the window is showing. A report
        # that carries findings the list on screen is hiding would make the
        # two disagree about one run, and the reader has no way to tell which
        # of them is the audit.
        audited = (self.audit_result.narrowed(self.state.categories,
                                              self.state.confidence_floor,
                                              unsettled=self.state.unsettled)
                   if has_audit else None)
        model = from_accessibility(audited, lang=lang) if has_audit else None
        if has_text:
            # No `lang`: the copy adapter does not take one - it was being
            # passed one anyway, which raised `TypeError` the moment a run
            # with copy findings reached this line.
            text_model = from_text_analysis(self.result)
            if model:
                model.findings.extend(text_model.findings)
            else:
                model = text_model
        return model

    def export_styled_report(self, path: str):
        from report.export import write_styled_report
        model = self._report_model()
        if model is None:
            return
        # `path` first, then the model: they were the other way round here,
        # which meant `Path(model)` and a TypeError every time the button was
        # pressed. The language was missing too, so an Italian window would
        # have printed an English report if it had printed one at all.
        write_styled_report(path, model, self.settings.ui_language)
        from i18n.translations import t

        self.status_message.emit(t("status_report_saved",
                                   self.settings.ui_language, path=path))

    def export_agent_report(self, path: str):
        import cli
        if self.audit_result is None:
            return
        class _Args:
            report = path
        cli._write_report(self.audit_result, _Args(), self.settings.ui_language, None)
        from i18n.translations import t

        self.status_message.emit(t("status_report_saved",
                                   self.settings.ui_language, path=path))

    def save_run_documents(self, stage_timings=None, run_began=None):
        """Write this run's folder, and say what ended up in it.

        The window used to have one report button and a save dialog behind
        it, which asks the wrong question: a run does not produce *a file*,
        it produces a set of documents that only make sense together, and
        where they go is already decided - one folder per target, one
        sub-folder per run (`cli_impl.runfolder`). Asking where to put each
        one is how the four documents of a run end up in four places.

        The same folder layout the CLI writes, through the same functions:
        `report.md` and its history come from `cli_impl.reports`, so a run
        started from the window and a run started from `xanalyze fullscan`
        share one history and each can be the previous run of the other.

        Returns a `RunDocuments`. `changes.md` is absent on a first run,
        deliberately: an empty comparison reads as a broken comparison.
        """
        from cli_impl import runfolder
        from cli_impl.runfolder import RunDocuments
        from report.export import write_styled_report

        model = self._report_model()
        if model is None:
            return None
        lang = self.settings.ui_language
        target = self.state.target or (
            getattr(self.result, "root_url", None) or "scan")
        folder = runfolder.prepare(target)
        written, absent = {}, {}

        payload = None
        if self.audit_result is not None:
            import cli

            class _Args:
                report = str(folder.report)

            payload = cli._write_report(self.audit_result, _Args(), lang, None)
            written["report.md"] = folder.report
        else:
            # A copy scan has no rule-by-rule briefing to write. Named as
            # absent with its reason rather than left off the list: a
            # document that is missing for a knowable reason is information,
            # a document that is silently not mentioned is not.
            absent["report.md"] = "no_audit"

        write_styled_report(str(folder.styled_report), model, lang,
                            markdown_path=str(folder.report) if payload else None)
        written["report.pdf"] = folder.styled_report

        timings = runfolder.Timings(started=run_began)
        for label, seconds in (stage_timings or []):
            timings.note(label, seconds)
        timings.write(folder.timings, target, extra={
            "findings": len(model.findings),
            "run folder": str(folder.run),
        })
        written["timings.md"] = folder.timings

        comparison = None
        if payload is not None:
            from cli_impl.reports import comparison_view, write_comparison_document
            if write_comparison_document(folder.changes, payload):
                written["changes.md"] = folder.changes
                # Built from the same payload that produced the document, so
                # the panel and the file are two renderings of one comparison
                # rather than two comparisons that can drift apart.
                comparison = comparison_view(payload)
            else:
                absent["changes.md"] = (
                    "first_run" if not folder.previous_runs() else "not_comparable")
        else:
            absent["changes.md"] = "no_audit"

        documents = RunDocuments(folder=folder, target=target,
                                 written=written, absent=absent,
                                 comparison=comparison)
        from i18n.translations import t

        self.status_message.emit(t("status_run_documents",
                                   self.settings.ui_language, path=folder.run))
        return documents

    # -- suppression -------------------------------------------------------
    def ignore_span(self, span: TextSpan, block):
        root = self._ignore_scan_root()
        fingerprint = suppression.span_fingerprint(span, block)
        label = suppression.span_label(span, block)
        if root:
            suppression.add_fingerprint_to_ignore_file(root, fingerprint, label)
        else:
            fingerprints = list((self.settings.ignore or {}).get("fingerprints") or [])
            if fingerprint not in fingerprints:
                fingerprints.append(fingerprint)
                ignore = dict(self.settings.ignore or {})
                ignore["fingerprints"] = fingerprints
                labels = dict(ignore.get("labels") or {})
                labels[fingerprint] = label
                ignore["labels"] = labels
                self.settings.ignore = ignore
                self.settings.save()
        if self.result is not None:
            self.result.spans = [s for s in self.result.spans if s is not span]
        self.buttons_changed.emit()

    def _ignore_scan_root(self) -> str | None:
        if self.state.source == SOURCE_REPO:
            return self.state.target or None
        if self.state.source == SOURCE_FILE:
            path = self.state.target
            return str(Path(path).parent) if path else None
        return None

    # -- shutdown ----------------------------------------------------------
    def shutdown(self):
        for w in self._active_workers:
            if w.isRunning():
                w.requestInterruption()
                w.wait(2000)
