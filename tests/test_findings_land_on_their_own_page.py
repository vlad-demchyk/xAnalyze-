"""A finding about a page is reported against that page.

The crawl-wide passes - `audit.crawlability` and `audit.crosspage` - answer
questions only a whole walk can answer: this URL returns 404, that one
carries `X-Robots-Tag: noindex`, these three share one title. Every one of
those findings is *about* a particular address, and each issue has always
carried it.

They were handed back as a single `DocumentReport` named after the **first**
issue's source, and every per-page view inherited that. Measured 2026-09-01
on a 250-page site served entirely `noindex`: the home page was reported
with 335 findings, 282 of them facts about other pages, and the page index
printed that number beside its address - so the one page a reader opens
first looked like the worst page on the site.
"""
import unittest

from audit import crawlability, crosspage


class _Diagnostics:
    def __init__(self, status=200, headers=None):
        self.status_code = status
        self.headers = headers or {}
        self.reasons = []


class _Page:
    def __init__(self, url, status=200, headers=None, html=""):
        self.url = url
        self.raw_html = html
        self.links = []
        self.diagnostics = _Diagnostics(status, headers)


NOINDEX = {"x-robots-tag": "noindex, nofollow"}


class CrawlFindingsGoToTheirOwnAddress(unittest.TestCase):

    def _documents(self, pages):
        return crawlability.as_documents(pages)

    def test_each_page_gets_its_own_document(self):
        pages = [_Page("https://x.test/", headers=NOINDEX),
                 _Page("https://x.test/a", headers=NOINDEX),
                 _Page("https://x.test/b", headers=NOINDEX)]
        documents = self._documents(pages)
        self.assertEqual(sorted(d.source for d in documents),
                         ["https://x.test/", "https://x.test/a",
                          "https://x.test/b"])
        for document in documents:
            with self.subTest(document.source):
                self.assertEqual(len(document.issues), 1)
                self.assertEqual(document.issues[0].source, document.source)

    def test_the_home_page_does_not_inherit_the_site(self):
        """The shape of the defect, pinned: three pages, one finding each,
        and the first page must not come back carrying three."""
        pages = [_Page("https://x.test/", headers=NOINDEX),
                 _Page("https://x.test/a", headers=NOINDEX),
                 _Page("https://x.test/b", headers=NOINDEX)]
        home = [d for d in self._documents(pages)
                if d.source == "https://x.test/"]
        self.assertEqual(len(home), 1)
        self.assertEqual(len(home[0].issues), 1)

    def test_nothing_found_is_no_document(self):
        self.assertEqual(self._documents([_Page("https://x.test/")]), [])


class CrossPageFindingsToo(unittest.TestCase):

    def _pages(self):
        html = ("<html lang='en'><head><title>The same title</title>"
                "<meta name='description' content='The same description'>"
                "</head><body><p>x</p></body></html>")
        return [_Page("https://x.test/", html=html),
                _Page("https://x.test/a", html=html),
                _Page("https://x.test/b", html=html)]

    def test_a_run_level_finding_is_one_row_naming_every_page(self):
        """Not the same defect, and worth pinning apart from it: "three
        pages share one title" is a single fact about a set, so it is one
        finding that *names* the three - not one finding per page, and not a
        count the first page has to carry."""
        documents = crosspage.as_documents(self._pages(),
                                           root_url="https://x.test/")
        issues = [i for d in documents for i in d.issues]
        rules = sorted(i.rule_id for i in issues)
        self.assertEqual(rules, ["seo-duplicate-description",
                                 "seo-duplicate-title"])
        for issue in issues:
            with self.subTest(issue.rule_id):
                self.assertEqual(issue.details["count"], 3)
                self.assertEqual(len(issue.details["pages"]), 3)

    def test_every_document_is_named_by_the_address_its_findings_are_about(self):
        for document in crosspage.as_documents(self._pages(),
                                               root_url="https://x.test/"):
            for issue in document.issues:
                with self.subTest(issue.rule_id):
                    self.assertEqual(issue.source or "https://x.test/",
                                     document.source)


if __name__ == "__main__":
    unittest.main()
