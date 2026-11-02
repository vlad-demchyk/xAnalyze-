"""Captured HTML reaches the preview whatever its size (P-17).

`setHtml` silently drops a document whose percent-encoded form is over 2 MB.
The window guessed that size from UTF-8 bytes and the findings panel did not
check it at all, so a large page - and a Cyrillic one of under 1 MB - left
the preview showing whatever was there before, beside findings about a
different page.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QEventLoop, QTimer, QUrl
    from PySide6.QtWidgets import QApplication
    from PySide6.QtWebEngineWidgets import QWebEngineView

    from ui.preview_loader import (
        SET_HTML_LIMIT, CapturedHtmlLoader, encoded_html_size, fits_set_html)
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None


def _page(body: str) -> str:
    return f"<!DOCTYPE html><html><head><title>t</title></head><body>{body}</body></html>"


@unittest.skipIf(QApplication is None, "PySide6 not available")
class Size(unittest.TestCase):
    def test_cyrillic_is_measured_as_qt_encodes_it_not_as_utf8(self):
        html = _page("ї" * 400_000)  # 800 KB of UTF-8
        self.assertLess(len(html.encode("utf-8")), 1_800_000)
        self.assertGreater(encoded_html_size(html), SET_HTML_LIMIT)
        self.assertFalse(fits_set_html(html))

    def test_a_small_page_fits(self):
        self.assertTrue(fits_set_html(_page("hello")))


@unittest.skipIf(QApplication is None, "PySide6 not available")
class Loading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.view = QWebEngineView()
        self.loader = CapturedHtmlLoader(self.view)
        self.results: list[tuple[bool, str]] = []
        self.loader.ready.connect(lambda ok, err: self.results.append((ok, err)))
        self.addCleanup(self._release)

    def _release(self):
        self.view.setPage(None)
        self.view.deleteLater()

    def _wait_ready(self, timeout_ms: int = 20000) -> None:
        loop = QEventLoop()
        self.loader.ready.connect(lambda *_: loop.quit())
        QTimer.singleShot(timeout_ms, loop.quit)
        loop.exec()

    def _eval(self, script: str):
        loop = QEventLoop()
        box = []
        self.view.page().runJavaScript(
            script, 0, lambda value: (box.append(value), loop.quit()))
        QTimer.singleShot(10000, loop.quit)
        loop.exec()
        return box[0] if box else None

    def test_a_page_over_the_limit_is_in_the_view_when_ready_fires(self):
        html = _page('<p id="mark">кінець</p>' + "ї" * 1_200_000)
        self.assertFalse(fits_set_html(html))
        self.loader.load(html, QUrl("https://example.test/page"))
        self._wait_ready()
        self.assertEqual(self.results, [(True, "")])
        self.assertEqual(self._eval("document.getElementById('mark').textContent"),
                         "кінець")
        # The site's own origin, as setHtml gives it - not a file:// copy,
        # which could read other local files.
        self.assertEqual(self._eval("location.origin"), "https://example.test")

    def test_a_small_page_is_given_to_set_html(self):
        self.loader.load(_page('<p id="mark">ok</p>'), QUrl("https://example.test/"))
        self._wait_ready()
        self.assertEqual(self.results, [(True, "")])
        self.assertEqual(self._eval("document.getElementById('mark').textContent"), "ok")

    def test_a_failed_navigation_is_reported(self):
        self.loader.navigate(QUrl("http://127.0.0.1:9/"))
        self._wait_ready()
        self.assertEqual(len(self.results), 1)
        self.assertFalse(self.results[0][0])


if __name__ == "__main__":
    unittest.main()
