"""Rendering during a crawl, with a stub browser.

No Qt here on purpose: the crawler takes `render` as a callable precisely so
the decision of *when* to render can be tested without starting one.
"""
import unittest
from unittest.mock import patch

from crawler import (
    EMPTY_JS_RENDERED, RENDER_ALWAYS, RENDER_AUTO, RENDER_NEVER, RENDERED,
    CrawlConfig, _should_render, crawl,
)
from models import PageDiagnostics

SHELL = ('<!DOCTYPE html><html lang="en"><head><title>App</title></head>'
         '<body><div id="root"></div>'
         '<script src="/assets/index-a1b2c3.js" type="module"></script>'
         '</body></html>')

RENDERED_HTML = (
    '<!DOCTYPE html><html lang="en"><head><title>App</title></head><body>'
    '<h1>Every document, one place</h1>'
    '<p>Convert, translate and read files without uploading them anywhere.</p>'
    '<a href="/pricing/">Pricing</a>'
    '</body></html>'
)


class WhenToRender(unittest.TestCase):
    def _diag(self, reasons=(), blocks_kept=0):
        diagnostics = PageDiagnostics()
        diagnostics.reasons = list(reasons)
        diagnostics.blocks_kept = blocks_kept
        return diagnostics

    def test_never_means_never(self):
        self.assertFalse(_should_render(RENDER_NEVER,
                                       self._diag([EMPTY_JS_RENDERED])))

    def test_always_means_always(self):
        self.assertTrue(_should_render(RENDER_ALWAYS,
                                       self._diag(blocks_kept=40)))

    def test_auto_renders_a_shell(self):
        self.assertTrue(_should_render(RENDER_AUTO,
                                       self._diag([EMPTY_JS_RENDERED])))

    def test_auto_renders_a_page_that_read_as_empty(self):
        self.assertTrue(_should_render(RENDER_AUTO, self._diag()))

    def test_auto_leaves_a_page_that_already_had_copy(self):
        # Rendering it would cost seconds per page to confirm what is known.
        self.assertFalse(_should_render(RENDER_AUTO, self._diag(blocks_kept=40)))


class _Response:
    status_code = 200
    headers = {"Content-Type": "text/html; charset=utf-8"}

    def __init__(self, url, text):
        self.url = url
        self.text = text

    def raise_for_status(self):
        return None


class _Session:
    headers: dict = {}

    def __init__(self, text):
        self.text = text
        self.fetched = []

    def update(self, *_a, **_kw):
        return None

    def get(self, url, timeout=None):
        self.fetched.append(url)
        return _Response(url, self.text)


class RenderingACrawl(unittest.TestCase):
    def _crawl(self, render=None, mode=RENDER_AUTO, depth=0):
        session = _Session(SHELL)
        with patch("crawler.requests.Session", return_value=session):
            pages = crawl("https://example.com",
                          CrawlConfig(max_depth=depth, max_pages=4,
                                      render_mode=mode),
                          render=render)
        return pages, session

    def test_a_shell_read_without_a_browser_has_nothing_in_it(self):
        pages, _ = self._crawl(mode=RENDER_NEVER)
        self.assertEqual(len(pages[0].blocks or []), 0)
        self.assertIn(EMPTY_JS_RENDERED, pages[0].diagnostics.reasons)

    def test_the_rendered_page_is_what_gets_read(self):
        pages, _ = self._crawl(render=lambda url: RENDERED_HTML)
        page = pages[0]
        self.assertTrue(page.blocks)
        texts = " ".join(b.text for b in page.blocks)
        self.assertIn("Every document, one place", texts)
        # The old diagnosis described the shell and is no longer true of what
        # was read, so it must not survive alongside the new reading.
        self.assertNotIn(EMPTY_JS_RENDERED, page.diagnostics.reasons)
        self.assertIn(RENDERED, page.diagnostics.reasons)

    def test_links_come_from_the_rendered_page_so_depth_works(self):
        pages, session = self._crawl(render=lambda url: RENDERED_HTML, depth=1)
        self.assertGreater(len(pages), 1)
        # The trailing slash is normalized away, so `/pricing/` and `/pricing`
        # are fetched once, under one name.
        self.assertIn("https://example.com/pricing", session.fetched)

    def test_a_trailing_slash_does_not_make_a_second_page(self):
        pages, session = self._crawl(
            render=lambda url: RENDERED_HTML.replace(
                "/pricing", "/pricing/"), depth=1)
        fetched_roots = [u for u in session.fetched
                         if u in ("https://example.com",
                                  "https://example.com/")]
        self.assertEqual(len(fetched_roots), 1,
                         "root crawled twice under two spellings")

    def test_a_failed_render_leaves_the_fetched_reading_and_says_why(self):
        def render(_url):
            raise RuntimeError("the page did not load")

        pages, _ = self._crawl(render=render)
        page = pages[0]
        self.assertEqual(page.diagnostics.render_error, "the page did not load")
        self.assertEqual(page.raw_html, SHELL)
        self.assertIn(EMPTY_JS_RENDERED, page.diagnostics.reasons)

    def test_an_empty_render_is_not_mistaken_for_a_rendered_page(self):
        pages, _ = self._crawl(render=lambda url: "")
        self.assertNotIn(RENDERED, pages[0].diagnostics.reasons)


if __name__ == "__main__":
    unittest.main()
