"""Background thread that runs the crawl + detection pipeline so the UI
never freezes while a scan is in progress.
"""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal

import suppression
from crawler import CrawlConfig, crawl
from detectors.base import DetectorUnavailable
from detectors.factory import DetectorFactory
from models import AnalysisResult, CodeBlock, FileResult, PageResult, RepoAnalysisResult, TextBlock, TextSpan
from repo_scanner import ScanConfig, scan_repo


def _apply_suppressions(result, settings, root):
    """Drop findings the user has already decided about.

    Applied once, at the end of a scan, rather than inside each detector:
    the suppression list is a statement about findings, and a detector that
    knew about it would have to be handed it by every caller.
    """
    if settings is None:
        return result.spans
    suppressions = suppression.Suppressions.load(settings, root)
    blocks_by_id = {b.block_id: b for b in result.blocks()}
    return suppression.filter_spans(result.spans, blocks_by_id, suppressions)


def run_unicode_pass(blocks, categories, selected_detector: str = "") -> list:
    """Run the non-keyboard-character pass on top of the selected detector.

    It answers a different question from any content detector (exact
    character defects vs. probabilistic style) and costs nothing, so it is
    worth running whichever paid backend the user picked.

    It is skipped when the selected detector is the offline one, which
    already contains this pass — running it again there produced every
    character finding twice. `categories` falsy disables it entirely.
    """
    if not categories:
        return []
    if DetectorFactory.resolve(selected_detector) == "offline":
        return []
    detector = DetectorFactory.create(
        "offline", categories=tuple(categories), include_style=False
    )
    return detector.analyze_blocks(blocks)


class AnalysisWorker(QThread):
    crawling = Signal(str, int)          # url, depth
    detecting = Signal(str)              # detector display name
    finished_ok = Signal(object)         # AnalysisResult
    failed = Signal(str)                 # error message

    def __init__(self, root_url: str, depth: int, detector_name: str,
                 detector_config: dict, max_pages: int = 30,
                 unicode_categories: tuple | None = None, settings=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.ignore_root = None  # a URL has no folder to hold an ignore file
        self.root_url = root_url
        self.depth = depth
        self.detector_name = detector_name
        self.detector_config = detector_config
        self.max_pages = max_pages
        self.unicode_categories = unicode_categories
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            def progress_cb(url: str, depth: int) -> None:
                self.crawling.emit(url, depth)

            config = CrawlConfig(max_depth=self.depth, max_pages=self.max_pages)
            pages: list[PageResult] = crawl(self.root_url, config, progress_cb=progress_cb)
            if self._cancelled:
                return

            try:
                detector = DetectorFactory.create(self.detector_name, **self.detector_config)
            except KeyError as exc:
                self.failed.emit(str(exc))
                return

            self.detecting.emit(detector.display_name)

            result = AnalysisResult(root_url=self.root_url, pages=pages)
            all_blocks = result.blocks()
            try:
                result.spans = detector.analyze_blocks(all_blocks)
            except DetectorUnavailable as exc:
                self.failed.emit(str(exc))
                return
            result.spans.extend(
                run_unicode_pass(all_blocks, self.unicode_categories, self.detector_name)
            )
            result.spans = _apply_suppressions(result, self.settings, self.ignore_root)

            if self._cancelled:
                return
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001 - surface any unexpected failure to the UI
            self.failed.emit(str(exc))


class SingleBlockWorker(QThread):
    """Re-runs one detector on a single block — used by the "additional
    analysis" button in the detail panel, so a deeper (e.g. Claude-backed)
    pass on one flagged passage doesn't require rescanning the whole site.
    """
    finished_ok = Signal(list)   # list[TextSpan]
    failed = Signal(str)

    def __init__(self, block: TextBlock, detector_name: str, detector_config: dict, parent=None):
        super().__init__(parent)
        self.block = block
        self.detector_name = detector_name
        self.detector_config = detector_config

    def run(self) -> None:
        try:
            detector = DetectorFactory.create(self.detector_name, **self.detector_config)
            spans = detector.analyze_block(self.block)
            self.finished_ok.emit(spans)
        except DetectorUnavailable as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class RepoAnalysisWorker(QThread):
    """Repo-mode counterpart to AnalysisWorker: walks a local folder instead
    of crawling a URL, then runs the same Detector interface over whatever
    tag-embedded text it found.
    """
    scanning = Signal(str)                # relative file path
    detecting = Signal(str)               # detector display name
    finished_ok = Signal(object)          # RepoAnalysisResult
    failed = Signal(str)

    def __init__(self, root_dir: str, ignore_patterns: list[str], detector_name: str,
                 detector_config: dict, unicode_categories: tuple | None = None,
                 scope: str = "content", settings=None, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.ignore_root = root_dir
        self.root_dir = root_dir
        self.ignore_patterns = ignore_patterns
        self.scope = scope
        self.detector_name = detector_name
        self.detector_config = detector_config
        self.unicode_categories = unicode_categories
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            def progress_cb(rel_path: str) -> None:
                self.scanning.emit(rel_path)

            config = ScanConfig(ignore_patterns=self.ignore_patterns, scope=self.scope)
            files: list[FileResult] = scan_repo(self.root_dir, config, progress_cb=progress_cb)
            if self._cancelled:
                return

            try:
                detector = DetectorFactory.create(self.detector_name, **self.detector_config)
            except KeyError as exc:
                self.failed.emit(str(exc))
                return

            self.detecting.emit(detector.display_name)

            result = RepoAnalysisResult(root_dir=self.root_dir, files=files)
            all_blocks = result.blocks()
            try:
                result.spans = detector.analyze_blocks(all_blocks)
            except DetectorUnavailable as exc:
                self.failed.emit(str(exc))
                return
            result.spans.extend(
                run_unicode_pass(all_blocks, self.unicode_categories, self.detector_name)
            )
            result.spans = _apply_suppressions(result, self.settings, self.ignore_root)

            if self._cancelled:
                return
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class AuditWorker(QThread):
    """The accessibility/SEO/performance audit, off the UI thread.

    Separate from `AnalysisWorker` rather than a flag on it because the two
    answer different questions about the same page and produce different
    result types: one finds passages a person wrote, the other finds defects
    in the document. Sharing a worker would mean every caller unpacking a
    union.

    The browser pass is deliberately **not** here. QtWebEngine is only usable
    from the thread that owns the application, so it runs on the main thread
    after this worker finishes; see `MainWindow._run_browser_pass`.
    """
    crawling = Signal(str, int)     # url, depth
    auditing = Signal(str)          # what is being audited right now
    finished_ok = Signal(object)    # audit.AccessibilityResult
    failed = Signal(str)

    def __init__(self, target: str, depth: int, max_pages: int = 30,
                 is_repo: bool = False, is_page_file: bool = False,
                 ignore_patterns=None, max_files: int = 5000,
                 settings=None, parent=None):
        super().__init__(parent)
        self.target = target
        self.depth = depth
        self.max_pages = max_pages
        self.is_repo = is_repo
        self.is_page_file = is_page_file
        self.ignore_patterns = list(ignore_patterns or [])
        self.max_files = max_files
        self.settings = settings
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            import audit

            if self.is_page_file:
                # One file, read as a whole page. No crawl and no scan: the
                # user pointed at the document itself.
                self.auditing.emit(self.target)
                result = audit.analyze_page_file(self.target)
                ignore_root = None
            elif self.is_repo:
                files = scan_repo(self.target,
                                  ScanConfig(ignore_patterns=self.ignore_patterns,
                                             max_files=self.max_files))
                if self._cancelled:
                    return
                self.auditing.emit(self.target)
                result = audit.analyze_files(files, self.target)
                ignore_root = self.target
            else:
                def progress_cb(url: str, depth: int) -> None:
                    self.crawling.emit(url, depth)

                pages = crawl(self.target,
                              CrawlConfig(max_depth=self.depth, max_pages=self.max_pages),
                              progress_cb=progress_cb)
                if self._cancelled:
                    return
                self.auditing.emit(self.target)
                result = audit.analyze_pages(pages, self.target)
                ignore_root = None

            # The same list that governs the text scan: a user who said "not
            # this part of the page" meant it for the whole tool.
            if self.settings is not None:
                suppressions = suppression.Suppressions.load(self.settings, ignore_root)
                for document in result.documents:
                    document.issues = suppression.filter_issues(document.issues, suppressions)

            if self._cancelled:
                return
            self.finished_ok.emit(result)
        except Exception as exc:  # noqa: BLE001 - surface any unexpected failure to the UI
            self.failed.emit(str(exc))


class RewriteAllWorker(QThread):
    """Generates a human-sounding rewrite for every (block, span) passed in
    that doesn't already have a draft, through whichever LLM provider is
    configured (own Anthropic key or xformat.net subscription). Powers both
    repo-mode buttons — "generate replacement list" stops after this;
    "auto-replace in files" chains a file_writer.apply_replacements call
    onto the result.

    Partial results are kept: if a call fails or the user cancels halfway,
    whatever was already rewritten is still handed back rather than thrown
    away, since each one costs a billable request.
    """
    progress = Signal(int, int)   # done, total
    finished_ok = Signal(object)  # dict[(block_id, start, end)] -> rewritten text
    failed = Signal(str)

    def __init__(self, items: list[tuple[CodeBlock, TextSpan]], settings, parent=None):
        super().__init__(parent)
        self.items = items
        self.settings = settings
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        import rewriter
        from llm.base import LLMUnavailable

        results: dict[tuple, str] = {}
        try:
            # Built once and reused: one HTTP session / API client and one
            # auth token for the whole batch instead of per passage.
            provider = rewriter.build_provider(self.settings)
        except (LLMUnavailable, KeyError) as exc:
            self.failed.emit(str(exc))
            return

        total = len(self.items)
        for i, (block, span) in enumerate(self.items):
            if self._cancelled:
                self.finished_ok.emit(results)
                return
            try:
                original = block.text[span.start:span.end]
                rewritten = provider.rewrite(original, block.language_hint)
                results[(block.block_id, span.start, span.end)] = rewritten
            except Exception as exc:  # noqa: BLE001
                if results:
                    self.finished_ok.emit(results)
                self.failed.emit(str(exc))
                return
            self.progress.emit(i + 1, total)

        self.finished_ok.emit(results)


class SingleRewriteWorker(QThread):
    """Rewrites one passage through the configured provider — powers the
    detail panel's per-passage rewrite button, so a single fix doesn't
    require running the whole bulk job."""
    finished_ok = Signal(str)     # rewritten text
    failed = Signal(str)

    def __init__(self, text: str, language: str | None, settings, parent=None):
        super().__init__(parent)
        self.text = text
        self.language = language
        self.settings = settings
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        import rewriter
        try:
            provider = rewriter.build_provider(self.settings)
            result = provider.rewrite(self.text, self.language)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return
        if not self._cancelled:
            self.finished_ok.emit(result)
