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

        # Repo config
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
        from repo_scanner import SCOPE_BOTH
        return SCOPE_BOTH

    # -- detector selection ------------------------------------------------
    def _detector_for_request(self) -> tuple[str, dict]:
        request = self._last_request or self.current_request()
        provider_key = self.state.provider or self.settings.llm_provider
        judge = judge_for_provider(provider_key)
        if request.wants_ai and request.wants_local:
            name = "hybrid"
        elif request.wants_ai:
            name = judge
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
            ignore_patterns=self.repo_ignore_patterns,
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

    def _start_audit(self):
        from i18n.translations import t
        lang = self.settings.ui_language

        if self.mode == "file":
            target = self.state.target
            if not target:
                self.error.emit(t("no_file_path", lang))
                return
        else:
            target = self.state.target
            if not target:
                self.error.emit(t("url_label_full", lang))
                return
            if not target.startswith(("http://", "https://")):
                target = "https://" + target

        self.audit_result = None
        self._worker = AuditWorker(
            pages=self._reusable_pages() if self.state.source == SOURCE_SITE else None,
            target=target,
            depth=self.state.depth,
            max_pages=self.settings.max_pages,
            is_page_file=self.mode == "file",
            settings=self.settings,
        )
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
        if isinstance(self.result, RepoAnalysisResult) and self.state.source == SOURCE_FILE:
            # Merge browser findings into the code analysis result
            self.result.spans.extend(result.spans)
            self.repo_result_ready.emit(self.result)
        else:
            self.result = result
            self._remember_extraction(self._last_request,
                                      pages=result.pages)
            self.web_result_ready.emit(result)

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
        self.audit_result = result
        self.audit_result_ready.emit(result)
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
        from unicode_rules import deterministic_fix
        fixes = deterministic_fix(spans)
        self.status_message.emit(f"Fixed {fixes} character(s)")

    def fix_on_disk(self):
        from audit import fix_ai, fixer
        if self.audit_result is None:
            return
        ready, pending, skipped = fixer.plan_fixes(self.audit_result.documents)
        # fill_locally needs page text
        page_text = ""
        if self.audit_result.documents:
            page_text = self.audit_result.documents[0].source
        filled, pending = fix_ai.fill_locally(pending, page_text)
        ready += filled
        outcome = fixer.apply_fixes(ready)
        outcome.skipped.extend(skipped)
        self.buttons_changed.emit()

    def undo_fix(self):
        from audit import fixer
        docs = self.audit_result.documents if self.audit_result else []
        paths = fixer.backups_for(docs)
        if not paths:
            return
        restored, problems = fixer.restore(paths)
        self.buttons_changed.emit()

    # -- suppression -------------------------------------------------------
    def ignore_span(self, span: TextSpan, block):
        root = self._ignore_scan_root()
        fingerprint = suppression.span_fingerprint(span, block)
        if root:
            suppression.add_fingerprint_to_ignore_file(root, fingerprint)
        else:
            fingerprints = list((self.settings.ignore or {}).get("fingerprints") or [])
            if fingerprint not in fingerprints:
                fingerprints.append(fingerprint)
                ignore = dict(self.settings.ignore or {})
                ignore["fingerprints"] = fingerprints
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
