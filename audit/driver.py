"""Driving a real browser over a page, off screen.

`browser.py` builds the JavaScript and normalises what comes back;
`states.py` builds the state pass. This is the missing third of that job: the
thing that actually loads the page, waits for it to settle, runs each script
and collects the answers.

It exists because QtWebEngine is already in the application — the same
Chromium that paints the page preview — so the industry-standard engines run
with no Node, no Puppeteer and no new dependency.

Three properties of `QWebEnginePage.runJavaScript` shape everything here:

**It cannot await a promise.** `axe.run()` and `HTMLCS.process()` both settle
asynchronously, and handing their Promise to `runJavaScript` returns the
Promise object, not the result. So every script is wrapped to park its answer
on a global slot, and the slot is then polled. Polling reads worse than
awaiting and is the only thing that works.

**It is a callback, not a return value.** The whole run is therefore a small
state machine over one nested `QEventLoop`, rather than a sequence of calls.

**It has to be on the main thread.** QtWebEngine is not usable from a worker
thread, so this blocks the thread it is called on and pumps events while it
waits. In the window that means the UI stays responsive but the audit cannot
be moved to `ui/worker.py`; in the CLI it means nothing at all.

Everything this returns is already an `Issue`, deduplicated against the rule
families in `browser.py`, so a caller never learns which engine found what
unless it looks at `Issue.engine`.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from . import browser, states

#: How often a parked result is checked for. Short enough that a fast page
#: does not wait on the poll, long enough that a slow one is not hammered.
POLL_INTERVAL_MS = 120

#: Ceiling for one script. axe on a large page is genuinely slow (seconds),
#: so this is not tight; it exists so a page that never settles fails with a
#: recorded reason instead of hanging the caller forever.
SCRIPT_TIMEOUT_MS = 60_000

#: Ceiling for the load itself, separate from the scripts: a page that never
#: fires `loadFinished` is a different failure from one that loaded and then
#: broke an engine, and the report should be able to say which.
LOAD_TIMEOUT_MS = 30_000

#: How long to let a viewport resize reach the renderer before asking the
#: page anything. Measured rather than guessed: below ~100ms the first probe
#: after a resize still reports the previous width.
VIEWPORT_SETTLE_MS = 200

#: Chromium flags for a headless run. Set before QtWebEngine initialises or
#: they are ignored, which is why `ensure_headless_application` exists rather
#: than the caller doing this by hand.
HEADLESS_CHROMIUM_FLAGS = "--disable-gpu --disable-software-rasterizer --no-sandbox"


@dataclass
class PageAudit:
    """One page, as the browser saw it."""
    url: str
    issues: list = field(default_factory=list)
    #: Raw measurement payload (timings, transfer size, request counts), kept
    #: alongside the issues because a report shows the numbers as well as the
    #: findings derived from them.
    measurements: dict = field(default_factory=dict)
    #: Why the page could not be audited, if it could not. An empty string
    #: means the pass ran; the issues list may still be empty and that is a
    #: different statement.
    error: str = ""
    #: Per-script failures that did not stop the rest of the pass.
    engine_errors: dict = field(default_factory=dict)
    #: The DOM as the browser built it, when `capture_html` asked for it. Empty
    #: otherwise - and empty is not the same as "the page had no content",
    #: which is why it is not None.
    html: str = ""


def ensure_headless_application():
    """A `QApplication` suitable for auditing with no screen.

    Returns the existing instance when the caller is the desktop app, so the
    window's own application is reused rather than a second one created (Qt
    permits exactly one).
    """
    # QtWebEngine must be imported before the QApplication exists: it sets the
    # shared-OpenGL-context attribute at import time, and creating the
    # application first makes the first page load hang instead of failing (cost
    # one debugging session to find).
    from PySide6 import QtWebEngineCore  # noqa: F401
    from PySide6.QtWidgets import QApplication

    existing = QApplication.instance()
    if existing is not None:
        return existing

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = f"{flags} {HEADLESS_CHROMIUM_FLAGS}".strip()
    return QApplication([])


def available() -> tuple:
    """`(usable, reason)` — whether a browser pass can run at all.

    Checked before a run rather than discovered during one: "QtWebEngine is
    not installed" and "this page has no problems" must never look the same
    in a report.
    """
    engines = browser.engines_available()
    if not engines["axe"] and not engines["htmlcs"]:
        return False, ("Neither axe-core nor HTML_CodeSniffer is present in "
                       "audit/vendor/ — reinstall or re-download them.")
    try:
        from PySide6.QtWebEngineCore import QWebEnginePage  # noqa: F401
    except ImportError as exc:
        return False, f"QtWebEngine is not available: {exc}"
    return True, ""


class _Slot:
    """One parked script result, and the polling around it."""

    def __init__(self, page, name: str, script: str, on_done):
        self.page = page
        self.name = name
        self.script = script
        self.on_done = on_done
        self.elapsed = 0

    def start(self) -> None:
        # `String(v)` because a script may resolve to something that is
        # already a string (measurements) or to a JSON string from a promise
        # (axe, HTMLCS); the Python side parses either the same way.
        wrapped = f"""
(function() {{
  window.__xanalyze = window.__xanalyze || {{}};
  window.__xanalyze[{_js(self.name)}] = null;
  try {{
    Promise.resolve({self.script}).then(
      function(value) {{ window.__xanalyze[{_js(self.name)}] = String(value); }},
      function(err) {{ window.__xanalyze[{_js(self.name)}] = JSON.stringify({{error: String(err)}}); }}
    );
  }} catch (err) {{
    window.__xanalyze[{_js(self.name)}] = JSON.stringify({{error: String(err)}});
  }}
  return true;
}})()
"""
        self.page.runJavaScript(wrapped, 0, lambda _result: self._poll())

    def _poll(self) -> None:
        from PySide6.QtCore import QTimer

        def read(value):
            if value:
                self.on_done(self.name, value)
                return
            self.elapsed += POLL_INTERVAL_MS
            if self.elapsed >= SCRIPT_TIMEOUT_MS:
                self.on_done(self.name, None)
                return
            QTimer.singleShot(POLL_INTERVAL_MS, self._poll)

        self.page.runJavaScript(f"window.__xanalyze && window.__xanalyze[{_js(self.name)}]", 0, read)


class BrowserAuditRunner:
    """Runs the browser pass over pages, one at a time, reusing one page.

    One page rather than one per URL: creating a `QWebEnginePage` spins up a
    renderer process, and a crawl of thirty pages would spend most of its time
    starting and stopping Chromium.
    """

    def __init__(self, options: browser.BrowserAuditOptions | None = None,
                 profile=None):
        self.options = options or browser.BrowserAuditOptions()
        self._profile = profile
        self._page = None
        #: The widget that gives the page a size, when one was asked for.
        #: A page with no view has a viewport of 0x0, and a page that
        #: believes it is 0 pixels wide matches every `max-width` media
        #: query there is - which is how a "responsive" audit can produce
        #: three identical mobile-shaped answers and look like it worked.
        self._view = None
        self._viewport = self.options.viewport

    # ------------------------------------------------------------- lifecycle

    def _get_page(self):
        if self._page is not None:
            return self._page
        from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile, QWebEngineSettings

        profile = self._profile
        if profile is None:
            # An off-the-record profile: auditing someone's site must not leave
            # its cookies and cache in the user's own browsing profile.
            profile = QWebEngineProfile(None)
            self._profile = profile
        page = QWebEnginePage(profile, None)
        if self._viewport:
            page = self._attach_view(page)
        settings = page.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        # The point of this pass is to see what a visitor sees, which includes
        # what JavaScript writes; but nothing here should be able to open a
        # window, and a page off the network must never reach the local disk.
        # `allow_local_files` is the one exception, and only for a file the
        # user picked themselves - see `BrowserAuditOptions`.
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls,
                              bool(self.options.allow_local_files))
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)
        self._page = page
        return page

    def _attach_view(self, page):
        """Give the page a real, sized viewport without putting a window on
        anyone's screen.

        `WA_DontShowOnScreen` is the whole trick: the widget goes through
        show(), so it acquires a size, a layout and a compositor - which is
        what `window.innerWidth` and every media query read - but the window
        system never maps it. Without `show()` the size stays 0x0 no matter
        what `resize()` was called with; without the attribute, running an
        audit from the desktop app would flash a second window in the user's
        face for every page.
        """
        from PySide6.QtCore import Qt
        from PySide6.QtWebEngineWidgets import QWebEngineView

        view = QWebEngineView()
        view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        view.setPage(page)
        width, height = self._viewport
        view.resize(int(width), int(height))
        view.show()
        self._view = view
        return page

    def set_viewport(self, width: int, height: int) -> None:
        """Resize the page's viewport, for the next `audit()` call.

        The resize has to reach the renderer process before the page is asked
        anything, and that happens on the event loop rather than on this
        line - hence the short pump. Cheap: it is once per breakpoint, not
        once per page.
        """
        self._viewport = (int(width), int(height))
        if self._page is None:
            return
        if self._view is None:
            self._page = self._attach_view(self._page)
        else:
            self._view.resize(int(width), int(height))
        _pump(VIEWPORT_SETTLE_MS)

    def close(self) -> None:
        # Order matters: Qt warns "Release of profile requested but
        # WebEnginePage still not deleted" and can crash if the profile outlives
        # its page only in Python's eyes.
        view, self._view = self._view, None
        if view is not None:
            # The view before the page it shows: a view left holding a
            # deleted page is the same class of crash as a profile left
            # holding a deleted page.
            view.setPage(None)
            view.deleteLater()
        page, self._page = self._page, None
        if page is not None:
            page.deleteLater()
            # `deleteLater` only queues the deletion; dropping the profile in
            # the same breath drops it while the page is still alive on the
            # C++ side, which Qt warns about and can crash on. One turn of the
            # event loop is enough for the queued deletion to happen.
            from PySide6.QtCore import QCoreApplication, QEvent
            app = QCoreApplication.instance()
            if app is not None:
                # `DeferredDelete` explicitly: a plain `processEvents` does
                # not run deferred deletions outside the event loop level that
                # posted them, so the page would still be alive here.
                app.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        self._profile = None

    # ----------------------------------------------------------------- audit

    def audit(self, url: str) -> PageAudit:
        """Load one page, run every enabled pass, and return the findings."""
        from PySide6.QtCore import QEventLoop, QTimer, QUrl

        usable, reason = available()
        if not usable:
            return PageAudit(url=url, error=reason)

        page = self._get_page()
        result = PageAudit(url=url)
        loop = QEventLoop()
        state = {"loaded": None, "finished": False}

        def finish():
            if not state["finished"]:
                state["finished"] = True
                loop.quit()

        def on_load(ok: bool):
            state["loaded"] = bool(ok)
            if not ok:
                result.error = "the page did not load"
                finish()
                return
            # The settle wait is the difference between auditing the site and
            # auditing its loading skeleton.
            QTimer.singleShot(self.options.settle_ms, run_scripts)

        payloads: dict = {}
        #: Active `_Slot`s, kept alive against garbage collection. See
        #: `next_script` below for why this cannot be a local in the loop.
        live: list = []
        pending = [name for name, enabled in (
            ("axe", self.options.run_axe and browser.engines_available()["axe"]),
            ("htmlcs", self.options.run_htmlcs and browser.engines_available()["htmlcs"]),
            ("measurements", self.options.run_measurements),
            ("states", self.options.run_states),
            ("html", self.options.capture_html),
        ) if enabled]

        def on_script_done(name: str, value):
            if value is None:
                result.engine_errors[name] = f"timed out after {SCRIPT_TIMEOUT_MS // 1000}s"
            else:
                payloads[name] = value
            if name in pending:
                pending.remove(name)
            if not pending:
                finish()

        def run_scripts():
            if not pending:
                finish()
                return
            scripts = {
                "axe": lambda: browser.axe_script(self.options),
                "htmlcs": browser.htmlcs_script,
                "measurements": lambda: browser.MEASUREMENT_SCRIPT,
                "states": states.state_script,
                "html": lambda: browser.HTML_SCRIPT,
            }
            # Sequentially, not in parallel: axe and the state pass both walk
            # the whole DOM, and the state pass moves focus around. Running
            # them at once would have each measuring the other's side effects.
            queue = list(pending)

            def next_script(*_args):
                if not queue:
                    return
                name = queue.pop(0)
                slot = _Slot(page, name, scripts[name](),
                             lambda n, v: (on_script_done(n, v), next_script()))
                # Held for the length of the run. Without this the only
                # reference to the slot is the callback Qt is holding, and Qt
                # drops that as soon as it fires: the slot is then collected
                # between one poll and the next, the next poll is never
                # scheduled, and the pass hangs until its timeout with no
                # error to show for it (cost one debugging session to find).
                live.append(slot)
                slot.start()

            next_script()

        page.loadFinished.connect(on_load)
        QTimer.singleShot(LOAD_TIMEOUT_MS, lambda: (
            result.error or setattr(result, "error", "the page did not finish loading in time"),
            finish(),
        ) if state["loaded"] is None else None)

        page.setUrl(QUrl(url))
        loop.exec()
        try:
            page.loadFinished.disconnect(on_load)
        except (RuntimeError, TypeError):
            pass

        if result.error:
            return result

        issues = []
        if "axe" in payloads:
            issues += browser.issues_from_axe(payloads["axe"], url, self.options.disabled_rules)
        if "htmlcs" in payloads:
            issues += browser.issues_from_htmlcs(payloads["htmlcs"], url)
        if "measurements" in payloads:
            issues += browser.issues_from_measurements(payloads["measurements"], url)
            result.measurements = _parse(payloads["measurements"])
        if "states" in payloads:
            issues += states.issues_from_states(payloads["states"], url)
        if "html" in payloads:
            # A string, not JSON: the other scripts return structures, this one
            # returns the document, and putting it through the same parser
            # would only be a way to lose it.
            result.html = payloads["html"] if isinstance(payloads["html"], str) else ""

        # One finding per problem, whoever found it: the same missing `alt`
        # reported by our rule, by axe and by HTML_CodeSniffer is one row that
        # names its corroboration, not three rows.
        # The rendered document goes with them: whether two findings are about
        # one element or two is a question only the page can answer.
        result.issues = browser.deduplicate(issues, markup=result.html)
        return result


class html_renderer:
    """A `render(url) -> html` callable backed by one browser, as a context.

    A context manager because the browser is expensive to start and must be
    shut down deliberately: one profile for the whole crawl rather than one per
    page, and the profile released before the process exits (Qt warns, loudly
    and correctly, about a profile still in use).

    Must be used from the thread that owns the Qt application - QtWebEngine
    has no other mode - so a caller on a worker thread renders before or after
    its own work, not inside it.
    """

    def __init__(self, settle_ms: int = 1200, allow_local_files: bool = False):
        self.options = browser.BrowserAuditOptions(
            run_axe=False, run_htmlcs=False, run_measurements=False,
            run_states=False, capture_html=True, settle_ms=settle_ms,
            allow_local_files=allow_local_files,
        )
        self.runner = None

    def __enter__(self):
        ensure_headless_application()
        self.runner = BrowserAuditRunner(self.options)
        return self

    def __exit__(self, *_exc):
        if self.runner is not None:
            self.runner.close()
            self.runner = None
        return False

    def __call__(self, url: str) -> str:
        if self.runner is None:
            raise RuntimeError("html_renderer used outside its context")
        result = self.runner.audit(url)
        if result.error:
            # Raised rather than returned empty: the crawler records the reason
            # against the page, and "" would be indistinguishable from a page
            # that rendered to nothing.
            raise RuntimeError(result.error)
        return result.html


def _pump(milliseconds: int) -> None:
    """Run the event loop for a fixed time, on the caller's thread."""
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def audit_urls(urls, options: browser.BrowserAuditOptions | None = None,
               progress=None) -> list:
    """Convenience for the CLI: audit several pages with one browser.

    Creates a headless `QApplication` when there is none, so a script can call
    this without knowing that Qt is involved. progress, if given, is called as
    progress(page_number, url) before each page so a long run can show life.
    """
    ensure_headless_application()
    runner = BrowserAuditRunner(options)
    try:
        results = []
        for i, url in enumerate(urls, 1):
            if progress:
                progress(i, url)
            results.append(runner.audit(url))
        return results
    finally:
        runner.close()


def _js(value: str) -> str:
    import json
    return json.dumps(value)


def _parse(payload: str) -> dict:
    import json
    try:
        data = json.loads(payload)
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}
