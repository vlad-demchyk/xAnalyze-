"""What went wrong, in words, with the evidence and what to do next.

Four different pieces of news used to arrive as one: a modal with
`str(exception)` in it and an empty title bar. Three of the four never
reached even that - a page the server refused was recorded in
`PageDiagnostics` and then never mentioned anywhere, so a run that read five
addresses out of twelve reported "done" and let a clean result stand for a
site nobody had read. That is the defect this whole file is about, and it is
the reason the assertions below are mostly about *what is said*, not about
widgets.

Two rules the diagnoses have to keep.

An unrecognised failure is not diagnosed. Matching an exception string
against a table of guesses is how a tool tells someone confidently that
their network is down when their certificate expired, and a wrong diagnosis
costs more than none: it sends them to fix the wrong thing.

And a count that is a floor says so. A truncated crawl knows how many pages
it read and how many it had queued; what it does not know is the size of the
site, because the pages it never fetched would have contributed links of
their own.
"""
from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import diagnosis as dx
from unittest.mock import patch

from crawler import CrawlConfig
from crawler import crawl as crawl_pages
from models import AnalysisResult, CrawlDiagnostics, PageDiagnostics, PageResult

try:
    from PySide6.QtWidgets import QApplication

    from ui.main_window import MainWindow
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None


def page(url: str, *, status=200, error="", render_error="") -> PageResult:
    diag = PageDiagnostics(status_code=status, render_error=render_error)
    return PageResult(url=url, depth=0, error=error, diagnostics=diag)


def result(pages, crawl_diag=None) -> AnalysisResult:
    return AnalysisResult(root_url="https://example.com", pages=pages,
                          spans=[], crawl=crawl_diag or CrawlDiagnostics())


class Refused(unittest.TestCase):
    def test_a_refused_page_is_reported_at_all(self):
        """It was recorded and never mentioned, which is how a run that read
        five of twelve addresses reported "done"."""
        items = dx.diagnose_result(result([page("https://example.com/a", status=429),
                                           page("https://example.com/b")]))
        self.assertEqual([item.kind for item in items], [dx.BLOCKED])

    def test_it_says_how_many_of_how_many(self):
        items = dx.diagnose_result(result([
            page("https://example.com/a", status=429),
            page("https://example.com/b", status=403),
            page("https://example.com/c")]))
        self.assertEqual(items[0].fields, {"refused": 2, "total": 3})

    def test_the_evidence_carries_the_codes_and_the_addresses(self):
        """The line a reader checks the diagnosis against, rather than
        having to trust it."""
        items = dx.diagnose_result(result([
            page("https://example.com/pricing", status=429)]))
        self.assertIn("429", items[0].evidence)
        self.assertIn("/pricing", items[0].evidence)

    def test_a_long_list_of_addresses_is_cut_and_counted(self):
        pages = [page(f"https://example.com/p{i}", status=429) for i in range(9)]
        items = dx.diagnose_result(result(pages))
        self.assertIn("+6", items[0].evidence)

    def test_an_ordinary_page_is_not_a_diagnosis(self):
        self.assertEqual(dx.diagnose_result(result([page("https://example.com/")])), [])

    def test_a_404_is_not_a_refusal(self):
        """Missing is not the same as refused, and only one of them means
        the rest of the crawl is in danger."""
        items = dx.diagnose_result(result([page("https://example.com/x", status=404)]))
        self.assertEqual([item.kind for item in items], [])


class Unreachable(unittest.TestCase):
    def test_a_page_that_would_not_load_is_reported(self):
        items = dx.diagnose_result(result([
            page("https://example.com/a", status=None,
                 error="Max retries exceeded"),
            page("https://example.com/b")]))
        self.assertEqual([item.kind for item in items], [dx.UNREACHABLE])
        self.assertIn("Max retries exceeded", items[0].evidence)

    def test_a_refusal_is_not_counted_twice(self):
        """429 arrives with an error string too; it is one piece of news."""
        items = dx.diagnose_result(result([
            page("https://example.com/a", status=429, error="429 Client Error")]))
        self.assertEqual([item.kind for item in items], [dx.BLOCKED])


class RenderFailed(unittest.TestCase):
    def test_a_page_the_browser_gave_up_on_is_reported(self):
        items = dx.diagnose_result(result([
            page("https://example.com/blog",
                 render_error="render timed out after 30s"),
            page("https://example.com/")]))
        self.assertEqual([item.kind for item in items], [dx.RENDER_FAILED])
        self.assertIn("30s", items[0].evidence)

    def test_the_page_still_counts_as_read(self):
        """The fetched reading stands; what is missing is the text
        JavaScript would have drawn."""
        items = dx.diagnose_result(result([
            page("https://example.com/blog", render_error="timeout")]))
        self.assertEqual(items[0].fields["total"], 1)


class Truncated(unittest.TestCase):
    def test_a_crawl_that_stopped_at_its_limit_says_so(self):
        items = dx.diagnose_result(result(
            [page("https://example.com/")],
            CrawlDiagnostics(pages_read=30, limit=30, queued_when_stopped=31)))
        self.assertEqual([item.kind for item in items], [dx.TRUNCATED])

    def test_the_number_it_reports_is_a_floor(self):
        """The pages it never fetched would have contributed links of their
        own, so the site is at least this big and probably bigger."""
        items = dx.diagnose_result(result(
            [page("https://example.com/")],
            CrawlDiagnostics(pages_read=30, limit=30, queued_when_stopped=31)))
        self.assertEqual(items[0].fields["read"], 30)
        self.assertEqual(items[0].fields["at_least"], 61)

    def test_a_crawl_that_finished_says_nothing(self):
        items = dx.diagnose_result(result(
            [page("https://example.com/")],
            CrawlDiagnostics(pages_read=4, limit=30, queued_when_stopped=0)))
        self.assertEqual(items, [])

    def test_it_offers_to_raise_the_limit(self):
        items = dx.diagnose_result(result(
            [page("https://example.com/")],
            CrawlDiagnostics(pages_read=30, limit=30, queued_when_stopped=31)))
        self.assertIn(dx.RAISE_LIMIT, items[0].actions)


class _Response:
    headers = {"Content-Type": "text/html; charset=utf-8"}

    def __init__(self, url, text):
        self.url = url
        self.text = text
        self.status_code = 200

    def raise_for_status(self):
        return None


class _Session:
    """The stub `crawler` tests already use, serving one body per address."""
    headers: dict = {}

    def __init__(self, pages: dict):
        self.pages = pages

    def update(self, *_a, **_kw):
        return None

    def get(self, url, timeout=None):
        return _Response(url, self.pages.get(url.rstrip("/") or url, ""))


class TheCrawlRecordsWhatItMissed(unittest.TestCase):
    """`crawler.crawl` fills the diagnostics it is handed."""

    def _site(self, n: int) -> dict:
        links = "".join(f'<a href="/p{i}">p{i}</a>' for i in range(n))
        pages = {"https://example.com":
                 "<html><body><p>Root page with enough words in it to be "
                 f"kept by the extractor.</p>{links}</body></html>"}
        for i in range(n):
            pages[f"https://example.com/p{i}"] = (
                "<html><body><p>A page with enough words in it to be kept "
                "by the extractor.</p></body></html>")
        return pages

    def crawl(self, pages: dict, limit: int) -> CrawlDiagnostics:
        walk = CrawlDiagnostics()
        with patch("crawler.requests.Session", return_value=_Session(pages)):
            crawl_pages("https://example.com/",
                        CrawlConfig(max_depth=3, max_pages=limit),
                        walk=walk)
        return walk

    def test_a_walk_that_finished_left_nothing_queued(self):
        walk = self.crawl(self._site(3), limit=30)
        self.assertFalse(walk.truncated)
        self.assertEqual(walk.pages_read, 4)

    def test_a_walk_that_hit_its_limit_says_what_was_left(self):
        walk = self.crawl(self._site(20), limit=5)
        self.assertTrue(walk.truncated)
        self.assertEqual(walk.pages_read, 5)
        self.assertGreater(walk.at_least, 5)

    def test_the_limit_it_ran_under_is_recorded(self):
        walk = self.crawl(self._site(20), limit=5)
        self.assertEqual(walk.limit, 5)

    def test_a_link_found_three_times_is_one_page_not_three(self):
        """The queue holds links as they were found, so counting its raw
        length would report a site several times larger than it is."""
        pages = {"https://example.com":
                 '<html><body><p>Root page with enough words in it to be kept '
                 'by the extractor.</p><a href="/x">x</a><a href="/x">x</a>'
                 '<a href="/x">x</a><a href="/y">y</a></body></html>'}
        walk = CrawlDiagnostics()
        with patch("crawler.requests.Session", return_value=_Session(pages)):
            crawl_pages("https://example.com/",
                        CrawlConfig(max_depth=2, max_pages=1), walk=walk)
        self.assertEqual(walk.queued_when_stopped, 2)


class AFailureIsNotGuessedAt(unittest.TestCase):
    def test_the_message_is_reported_verbatim(self):
        item = dx.diagnose_failure("SSLCertVerificationError: certificate has expired")
        self.assertEqual(item.kind, dx.UNKNOWN_FAILURE)
        self.assertIn("certificate has expired", item.evidence)

    def test_nothing_is_force_fitted_to_a_rule(self):
        """A confident wrong explanation sends someone to fix the wrong
        thing, which costs more than no explanation."""
        for message in ("connection refused", "429", "timed out", "boom"):
            with self.subTest(message=message):
                self.assertEqual(dx.diagnose_failure(message).kind,
                                 dx.UNKNOWN_FAILURE)

    def test_an_empty_message_is_still_a_diagnosis(self):
        self.assertEqual(dx.diagnose_failure("").kind, dx.UNKNOWN_FAILURE)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class InTheWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.addCleanup(self.window.deleteLater)
        self.addCleanup(self.window.close)

    def cards(self) -> list:
        layout = self.window.diagnosis_layout
        return [layout.itemAt(i).widget() for i in range(layout.count())]

    def test_the_strip_never_takes_more_than_its_share_of_the_window(self):
        """A run can legitimately produce three of these at once, and three
        cards stacked pushed the results off the bottom half of the window -
        which turns an explanation into an obstacle."""
        self.window.show_diagnoses(dx.diagnose_result(result(
            [page("https://example.com/a", status=429),
             page("https://example.com/b", render_error="timed out"),
             page("https://example.com/c", error="refused")],
            CrawlDiagnostics(pages_read=30, limit=30, queued_when_stopped=31))))
        self.assertEqual(len(self.cards()), 4)
        self.assertLessEqual(self.window.diagnosis_strip.height(),
                             self.window.DIAGNOSIS_MAX_HEIGHT)

    def test_one_card_does_not_leave_a_band_of_empty_surface(self):
        self.window._on_failed("boom")
        self.assertLess(self.window.diagnosis_strip.height(),
                        self.window.DIAGNOSIS_MAX_HEIGHT)

    def test_the_evidence_i_wrote_myself_is_translated(self):
        """A label of mine sitting in English in a Ukrainian window is not
        raw data, it is an untranslated string. Machine output - status
        codes, an exception's own words - stays as it came."""
        self.window.lang = "uk"
        self.window.show_diagnoses(dx.diagnose_result(result(
            [page("https://example.com/")],
            CrawlDiagnostics(pages_read=30, limit=30, queued_when_stopped=31))))
        self.assertNotIn("max pages", self.cards()[0].evidence.text())
        self.assertIn("30", self.cards()[0].evidence.text())

    def test_the_strip_is_not_there_before_there_is_anything_to_say(self):
        self.assertTrue(self.window.diagnosis_strip.isHidden())

    def test_a_run_that_could_not_read_the_site_says_so(self):
        self.window._on_web_finished(result([
            page("https://example.com/a", status=429),
            page("https://example.com/b")]))
        self.assertFalse(self.window.diagnosis_strip.isHidden())
        self.assertEqual(len(self.cards()), 1)

    def test_a_run_that_went_fine_says_nothing(self):
        self.window._on_web_finished(result([page("https://example.com/")]))
        self.assertTrue(self.window.diagnosis_strip.isHidden())

    def test_a_failure_lands_on_the_strip_rather_than_in_a_modal(self):
        """A modal is dismissed and then the explanation is gone, and the
        window looks exactly as it does after a run that went fine."""
        self.window._on_failed("something went wrong")
        self.assertFalse(self.window.diagnosis_strip.isHidden())
        self.assertIn("something went wrong", self.cards()[0].evidence.text())

    def test_a_card_can_be_put_away(self):
        self.window._on_failed("boom")
        self.cards()[0]._on_dismiss()
        self.assertTrue(self.window.diagnosis_strip.isHidden())

    def test_a_new_run_clears_the_last_one_s_diagnoses(self):
        """"The server refused seven addresses" read over a run that had no
        trouble at all is worse than saying nothing."""
        self.window._on_failed("boom")
        self.window._on_busy_changed(True)
        self.assertTrue(self.window.diagnosis_strip.isHidden())

    def test_raising_the_limit_raises_it_to_what_was_found(self):
        """Not to a larger round number: the point is to finish this site,
        and a number pulled out of the air is the same guess that produced
        the truncation."""
        before = self.window.settings.max_pages
        started = []
        self.window._on_analyze_clicked = lambda: started.append(1)
        item = dx.Diagnosis(dx.TRUNCATED, fields={"read": 30, "at_least": 61},
                            actions=(dx.RAISE_LIMIT,))
        self.window.run_action(dx.RAISE_LIMIT, item)
        self.assertEqual(self.window.settings.max_pages, 61)
        self.assertEqual(started, [1])
        self.window.settings.max_pages = before
        self.window.settings.save()

    def test_raising_the_limit_never_lowers_it(self):
        before = self.window.settings.max_pages
        self.window.settings.max_pages = 200
        self.window._on_analyze_clicked = lambda: None
        self.window.run_action(dx.RAISE_LIMIT,
                               dx.Diagnosis(dx.TRUNCATED,
                                            fields={"read": 30, "at_least": 61}))
        self.assertEqual(self.window.settings.max_pages, 200)
        self.window.settings.max_pages = before
        self.window.settings.save()

    def test_every_card_says_something_in_every_language(self):
        """`t` returns its key when it has no entry, and a user must never
        be shown `diagnosis_blocked_title`."""
        for lang in ("uk", "it", "en"):
            for kind in (dx.BLOCKED, dx.UNREACHABLE, dx.RENDER_FAILED,
                         dx.TRUNCATED, dx.UNKNOWN_FAILURE):
                with self.subTest(lang=lang, kind=kind):
                    from i18n.translations import t
                    fields = {"refused": 1, "total": 2, "count": 1,
                              "read": 30, "at_least": 61}
                    item = dx.Diagnosis(kind, fields=fields)
                    for key in (item.title_key, item.body_key):
                        self.assertNotIn("diagnosis_", t(key, lang, **fields))

    def test_a_second_set_of_cards_leaves_none_of_the_first_on_screen(self):
        from PySide6.QtWidgets import QWidget
        self.window.show_diagnoses([dx.diagnose_failure("a"),
                                    dx.diagnose_failure("b")])
        self.window.show_diagnoses([dx.diagnose_failure("c")])
        live = [child for child in self.window.diagnosis_cards.findChildren(QWidget)
                if child.parent() is self.window.diagnosis_cards]
        self.assertEqual(len(live), 1)


if __name__ == "__main__":
    unittest.main()
