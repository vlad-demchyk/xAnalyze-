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

    def close(self) -> None:
        # Order matters: Qt warns "Release of profile requested but
        # WebEnginePage still not deleted" and can crash if the profile outlives
        # its page only in Python's eyes.
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

        # One finding per problem, whoever found it: the same missing `alt`
        # reported by our rule, by axe and by HTML_CodeSniffer is one row that
        # names its corroboration, not three rows.
        result.issues = browser.deduplicate(issues)
        return result


def audit_urls(urls, options: browser.BrowserAuditOptions | None = None) -> list:
    """Convenience for the CLI: audit several pages with one browser.

    Creates a headless `QApplication` when there is none, so a script can call
    this without knowing that Qt is involved.
    """
    ensure_headless_application()
    runner = BrowserAuditRunner(options)
    try:
        return [runner.audit(url) for url in urls]
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
