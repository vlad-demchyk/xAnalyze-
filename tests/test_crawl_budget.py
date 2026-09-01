"""What `--max-pages` counts, and what it must not.

Measured 2026-09-01 on a live 250-page WordPress site: 25 of the 250 slots
went to `/wp-content/uploads/...` - `.jpg`, `.webp`, `.pdf`. The crawler
fetches such an address, sees it is not HTML, and keeps the result as a
diagnostic, which is right; counting it against the page budget is not. The
person asked for 250 pages and got 225, with nothing in the report saying so.

The file is still fetched and still recorded - a link to a 404 PDF is worth
knowing about - and a ceiling on total fetches keeps a gallery from turning
a crawl into a download.
"""
import unittest
from unittest.mock import patch

from crawler import EMPTY_NOT_HTML, CrawlConfig, crawl
from models import CrawlDiagnostics

PAGE = ('<!DOCTYPE html><html lang="en"><head><title>P</title></head><body>'
        '<h1>A page with copy on it</h1>'
        '<a href="/a.jpg">photo</a><a href="/b.pdf">leaflet</a>'
        '<a href="/next">next page</a>'
        '</body></html>')


class _Response:
    def __init__(self, url, text, content_type):
        self.url = url
        self.text = text
        self.status_code = 200
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        return None


class _Session:
    """Every address is a page; `.jpg` and `.pdf` answer as files."""

    headers: dict = {}

    def __init__(self):
        self.fetched = []

    def update(self, *_a, **_kw):
        return None

    def get(self, url, timeout=None):
        self.fetched.append(url)
        if url.endswith((".jpg", ".pdf")):
            return _Response(url, "binary", "image/jpeg")
        # Each page links to the next one, so the walk never runs dry.
        depth = len(self.fetched)
        html = PAGE.replace('href="/next"', f'href="/page-{depth}"')
        html = html.replace('href="/a.jpg"', f'href="/a-{depth}.jpg"')
        html = html.replace('href="/b.pdf"', f'href="/b-{depth}.pdf"')
        return _Response(url, html, "text/html; charset=utf-8")


class TheBudgetCountsPages(unittest.TestCase):

    def _crawl(self, max_pages, max_depth=6):
        session = _Session()
        walk = CrawlDiagnostics()
        with patch("crawler.requests.Session", return_value=session):
            pages = crawl("https://example.test/",
                          CrawlConfig(max_depth=max_depth, max_pages=max_pages),
                          walk=walk)
        return pages, walk, session

    def test_files_do_not_eat_the_page_budget(self):
        pages, walk, _ = self._crawl(max_pages=5)
        html = [p for p in pages
                if EMPTY_NOT_HTML not in p.diagnostics.reasons]
        self.assertEqual(len(html), 5)
        self.assertEqual(walk.pages_read, 5)

    def test_the_files_are_still_fetched_and_still_recorded(self):
        """Skipping them silently is the other half of the same defect: a
        link to a file that 404s is worth reporting, and only a fetch knows."""
        pages, _, session = self._crawl(max_pages=5)
        files = [p for p in pages if EMPTY_NOT_HTML in p.diagnostics.reasons]
        self.assertTrue(files)
        self.assertTrue(any(u.endswith(".jpg") for u in session.fetched))

    def test_a_gallery_cannot_turn_the_crawl_into_a_download(self):
        """The ceiling: three fetches per page of budget, then it stops."""
        pages, _, session = self._crawl(max_pages=5)
        self.assertLessEqual(len(session.fetched), 15)
        self.assertLessEqual(len(pages), 15)


if __name__ == "__main__":
    unittest.main()
