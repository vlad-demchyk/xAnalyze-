"""The same HTML `template.py` builds, turned into PDF bytes.

Uses `QWebEnginePage.printToPdf` rather than a separate PDF library:
QtWebEngine is already a dependency (the same Chromium that renders the
site preview and drives the accessibility audit's browser pass — see
`audit/driver.py`), so this needs no new one, and the page paginates and
prints exactly as "Print -> Save as PDF" would in a real browser.

Two properties shape this module, both already handled the same way for the
audit's browser pass in `audit/driver.py` (`BrowserAuditRunner.audit`):

* **`printToPdf` is a callback, not a return value.** It hands its bytes to
  a function you give it, asynchronously; there is no synchronous
  "render and return" call. So the public API here is a callable that
  blocks until that callback fires (via a nested `QEventLoop`) rather than
  a bare function pretending the bytes were available all along.
* **The page must have finished loading first.** Calling `printToPdf`
  before `loadFinished` fires produces an empty PDF with no error — so this
  waits on that signal exactly as the audit pass does, load -> `QEventLoop`
  + `QTimer` timeout -> callback -> disconnect.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from audit.driver import ensure_headless_application

#: An absolute ceiling on the whole render, in milliseconds. `0` - the
#: default - means there is none, and that is correct: printing a large
#: report legitimately takes minutes, and a fixed 30s ceiling once killed a
#: 158-page document that finishes in 108 seconds when left alone, taking a
#: 46-minute run's entire output with it.
#:
#: What replaces it is not "nothing". `report.activity.ActivityWatch` stops a
#: render that has stopped *making progress* - a dead render process, or no
#: output and no CPU time for `STALL_SECONDS` - which is the failure a ceiling
#: was a poor proxy for. Set this above 0 only to bound a render regardless of
#: progress, as the tests do.
RENDER_TIMEOUT_MS = 0

#: `QWebEnginePage.setHtml` funnels its argument through a `data:` URL
#: internally, which historically caps out around 2 MB. A styled report of
#: a genuinely large scan (hundreds of findings, each with a code snippet)
#: can cross that before the page limit in `template.py` would ever trim it
#: - hitting it needs to fail *loudly and correctly*, not silently truncate
#: the report. So anything past this threshold is instead written to a
#: temporary file and loaded by URL, which has no such limit; the API and
#: the output are identical either way.
_INLINE_HTML_LIMIT = 1_500_000


class PdfRenderer:
    """One offscreen `QWebEnginePage`, reused across renders.

    A context manager for the same reason as `audit.driver.html_renderer`:
    the page (and the off-the-record profile behind it) is expensive to
    start and must be torn down deliberately, in the right order, or Qt
    warns loudly and can crash - see `close()`.
    """

    def __init__(self, profile=None, stall_seconds: float | None = None):
        from report.activity import STALL_SECONDS

        self._profile = profile
        self._owns_profile = profile is None
        self._page = None
        #: How long this renderer tolerates no progress. A parameter rather
        #: than only a module constant so a caller that knows the report is
        #: enormous can be more patient without changing it for everyone.
        self.stall_seconds = (STALL_SECONDS if stall_seconds is None
                              else stall_seconds)

    def __enter__(self) -> "PdfRenderer":
        ensure_headless_application()
        return self

    def __exit__(self, *_exc) -> bool:
        self.close()
        return False

    def _get_page(self):
        if self._page is not None:
            return self._page
        from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile

        profile = self._profile
        if profile is None:
            # Off-the-record: nothing this renders (a data: logo, the
            # user's own findings) needs to persist between reports, and a
            # profile that never writes to disk cannot leave one report's
            # content lying around for the next.
            profile = QWebEngineProfile(None)
            self._profile = profile
        self._page = QWebEnginePage(profile, None)
        return self._page

    def close(self) -> None:
        # Same teardown order as `audit.driver.BrowserAuditRunner.close`,
        # for the same reason: dropping the profile before Qt has actually
        # deleted the page it backs is a documented crash risk.
        page, self._page = self._page, None
        if page is not None:
            page.deleteLater()
            from PySide6.QtCore import QCoreApplication, QEvent
            app = QCoreApplication.instance()
            if app is not None:
                app.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        if self._owns_profile:
            self._profile = None

    def render(self, html: str, base_url: str = "") -> bytes:
        """Render `html` to PDF bytes, blocking until it is ready.

        Raises `RuntimeError` when the page fails to load or times out, or
        when `printToPdf` produces no data - never returns an empty PDF
        silently, which is the one failure mode a report generator must
        not have (an empty file looks identical to "nothing was wrong").

        One retry, and only for one failure: a callback that never arrives.
        Reproduced at roughly one full test-suite run in three, on a document
        that renders in 0.3 seconds by itself and survived 30 consecutive
        renders in a process of its own - so it is not the document, and
        waiting longer on the same page is not the answer. Which callback
        goes missing varies: the timeout message names the phase, and both
        phases are retried once, against a fresh page.

        A load that *fails* (`loadFinished(False)`) is not retried. That is
        Qt answering rather than going silent, and the answer would be the
        same twice.
        """
        try:
            return self._render_once(html, base_url)
        except _CallbackLost:
            # Fresh page: whatever swallowed the callback belongs to the old
            # one, and keeping it would be retrying the same broken thing.
            self._drop_page()
            try:
                return self._render_once(html, base_url)
            except _CallbackLost as exc:
                raise RuntimeError(str(exc)) from exc

    def _drop_page(self) -> None:
        from PySide6.QtCore import QCoreApplication, QEvent

        page, self._page = self._page, None
        if page is not None:
            page.deleteLater()
            app = QCoreApplication.instance()
            if app is not None:
                app.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)

    def _render_once(self, html: str, base_url: str = "") -> bytes:
        from PySide6.QtCore import QEventLoop, QMarginsF, QTimer, QUrl
        from PySide6.QtGui import QPageLayout, QPageSize

        from report.activity import ActivityWatch, RenderProcessGone, Stalled

        page = self._get_page()
        loop = QEventLoop()
        # `phase` is what makes the timeout message worth reading: "the page
        # never loaded" and "the printer never answered" are different
        # failures with different causes, and one of them is worth retrying.
        state = {"finished": False, "error": None, "pdf": None,
                 "phase": "loading", "timed_out": False, "stalled": False,
                 "process_gone": False}

        def finish() -> None:
            if not state["finished"]:
                state["finished"] = True
                loop.quit()

        def on_pdf(data) -> None:
            state["pdf"] = bytes(data)
            finish()

        def on_load(ok: bool) -> None:
            if not ok:
                state["error"] = "the report page did not load"
                finish()
                return
            state["phase"] = "printing"
            # Printing is the phase with no progress signal of its own, so
            # the watch is told the phase changed: entering it is itself
            # progress, and the stall window starts again from here rather
            # than counting the load's quiet tail against the printer.
            watch.set_phase("printing")
            from report.template import PAGE_MARGIN_H_MM, PAGE_MARGIN_V_MM

            # Explicit, non-zero margins here, matching template.py's
            # `@page { margin: ... }`: printToPdf does not honour CSS
            # `@page` margins on its own - a QMarginsF() of all zeros is
            # Chromium's "None" print-margins setting, which prints flush to
            # the physical edge of the page regardless of what `@page` says.
            layout = QPageLayout(QPageSize(QPageSize.PageSizeId.A4),
                                 QPageLayout.Orientation.Portrait,
                                 QMarginsF(PAGE_MARGIN_H_MM, PAGE_MARGIN_V_MM,
                                           PAGE_MARGIN_H_MM, PAGE_MARGIN_V_MM),
                                 QPageLayout.Unit.Millimeter)
            page.printToPdf(on_pdf, layout)

        def on_no_progress(reason: Exception) -> None:
            if state["finished"]:
                return
            state["stalled"] = isinstance(reason, Stalled)
            state["process_gone"] = isinstance(reason, RenderProcessGone)
            state["error"] = str(reason)
            finish()

        watch = ActivityWatch(stall_seconds=self.stall_seconds)
        page.loadFinished.connect(on_load)
        watch.attach(page, on_no_progress)
        if RENDER_TIMEOUT_MS > 0:
            QTimer.singleShot(RENDER_TIMEOUT_MS, lambda: (
                state.__setitem__("timed_out", not state["error"]),
                state.__setitem__("error", state["error"] or _timeout_message(state)),
                finish(),
            ) if not state["finished"] else None)

        temp_path = None
        encoded_len = len(html.encode("utf-8"))
        if encoded_len > _INLINE_HTML_LIMIT and not base_url:
            handle = tempfile.NamedTemporaryFile(
                mode="w", suffix=".html", delete=False, encoding="utf-8")
            handle.write(html)
            handle.close()
            temp_path = handle.name
            page.setUrl(QUrl.fromLocalFile(temp_path))
        else:
            page.setHtml(html, QUrl(base_url) if base_url else QUrl())

        try:
            loop.exec()
            try:
                page.loadFinished.disconnect(on_load)
            except (RuntimeError, TypeError):
                pass
        finally:
            watch.detach()
            if temp_path is not None:
                Path(temp_path).unlink(missing_ok=True)

        if state["error"]:
            # A dead render process is Qt answering, and the answer will be
            # the same against a fresh page - so this one is never retried,
            # even though it arrived the same way a stall does.
            if state["process_gone"]:
                raise RuntimeError(state["error"])
            # `timed_out`/`stalled` rather than the phase: a load that
            # answered "no" sets the same error string in the loading phase,
            # and that one must not be retried.
            if state["timed_out"] or state["stalled"]:
                raise _CallbackLost(state["error"])
            raise RuntimeError(state["error"])
        if not state["pdf"]:
            raise RuntimeError("printToPdf produced no data")
        return state["pdf"]


class _CallbackLost(RuntimeError):
    """Qt took the job and never called back at all - neither
    `loadFinished` nor `printToPdf`'s completion arrived before the
    timeout. Internal: it reaches a caller only as a plain `RuntimeError`,
    after the retry.

    Deliberately not raised for `loadFinished(False)`. That is Qt answering
    "this document did not load", which is a fact about the document: it
    would be just as false the second time, and retrying it would only make
    a failed export take twice as long to fail."""


def _timeout_message(state: dict) -> str:
    seconds = RENDER_TIMEOUT_MS // 1000
    if state["phase"] == "printing":
        return (f"the report was laid out but the printer did not answer in "
                f"{seconds}s")
    return f"the report page did not finish loading in {seconds}s"


def render_pdf(html: str, base_url: str = "") -> bytes:
    """One-shot convenience: render `html` to PDF bytes with a fresh page.

    A caller producing several reports in the same process (a batch run, a
    test module) should keep one `PdfRenderer` open across them instead -
    the startup cost this spares them is exactly what
    `audit.driver.BrowserAuditRunner` spares a crawl by reusing one page.
    """
    with PdfRenderer() as renderer:
        return renderer.render(html, base_url)
