"""One way to put captured HTML into a preview, whatever its size (P-17).

`QWebEngineView.setHtml` turns the document into a percent-encoded `data:`
URL, and Qt refuses one over 2 MB - without an error, the view simply stays
as it was. Three call sites fed it captured pages: one guessed the limit from
UTF-8 bytes (a Cyrillic page triples when percent-encoded, so a 900 KB page
already failed) and two did not check at all. None of them looked at whether
the load worked.

Every captured document now goes through `CapturedHtmlLoader.load`:

* a document that fits is given to `setHtml` with the page's own base URL;
* a larger one is written into an empty document loaded at that same base
  URL, so it keeps the origin `setHtml` would have given it. A temporary
  `file://` copy was the other option and was rejected: a file origin may
  read other local files, and this HTML came from someone else's site.

`ready(ok, error)` fires once the document is really in the view - after the
write for a large one - so a highlight runs against the page and not against
the empty bootstrap. A load that a newer one interrupted reports nothing:
that is not a failure the person should be told about.
"""
from __future__ import annotations

import json
from urllib.parse import quote

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtWebEngineCore import QWebEngineLoadingInfo

#: Qt's documented ceiling for `setHtml`/`setContent`.
SET_HTML_LIMIT = 2 * 1024 * 1024
_DATA_PREFIX = "data:text/html;charset=UTF-8,"
#: Headroom for whatever Qt adds that the prefix above does not account for.
_MARGIN = 16 * 1024

_BOOTSTRAP = "<!DOCTYPE html><html><head></head><body></body></html>"


def encoded_html_size(html: str) -> int:
    """The length of the `data:` URL `setHtml` would build from `html`.

    `quote(..., safe="")` leaves exactly the RFC 3986 unreserved characters
    alone, as `QUrl.toPercentEncoding` does.
    """
    return len(_DATA_PREFIX) + len(quote(html.encode("utf-8"), safe=""))


def fits_set_html(html: str) -> bool:
    return encoded_html_size(html) <= SET_HTML_LIMIT - _MARGIN


def document_write_js(html: str) -> str:
    """Replace the current document with `html`, scripts included."""
    return ("document.open();document.write(" + json.dumps(html)
            + ");document.close();")


class CapturedHtmlLoader(QObject):
    """Owns how one view is loaded and when it counts as loaded."""

    #: ok, error text (empty when ok).
    ready = Signal(bool, str)

    def __init__(self, view, parent=None) -> None:
        super().__init__(parent or view)
        self._view = view
        self._pending_html: str | None = None
        view.page().loadingChanged.connect(self._on_loading_changed)

    def load(self, html: str, base: QUrl | None = None) -> None:
        base = base or QUrl()
        if fits_set_html(html):
            self._pending_html = None
            self._view.setHtml(html, base)
            return
        self._pending_html = html
        self._view.setHtml(_BOOTSTRAP, base)

    def navigate(self, url: QUrl) -> None:
        """Load an address; the loader still reports when it is in."""
        self._pending_html = None
        self._view.setUrl(url)

    def _on_loading_changed(self, info) -> None:
        status = info.status()
        if status == QWebEngineLoadingInfo.LoadStatus.LoadStartedStatus:
            return
        if status == QWebEngineLoadingInfo.LoadStatus.LoadStoppedStatus:
            # Interrupted by a newer load, whose own result follows.
            return
        if status == QWebEngineLoadingInfo.LoadStatus.LoadFailedStatus:
            self._pending_html = None
            self.ready.emit(False, info.errorString() or "")
            return
        html, self._pending_html = self._pending_html, None
        if html is None:
            self.ready.emit(True, "")
            return
        page = self._view.page()
        if page is None:
            return
        page.runJavaScript(document_write_js(html), 0, self._written)

    def _written(self, _result) -> None:
        try:
            self.ready.emit(True, "")
        except RuntimeError:
            # The window closed while the write was in flight.
            pass
