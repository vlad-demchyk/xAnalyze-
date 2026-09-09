"""How many times a crawl's markup is parsed to answer the cross-page rules.

The cross-language rules ask two questions of the *other* page inside their
inner loop - what does it declare as an alternate, and what does it call
`x-default` - and each question re-ran BeautifulSoup over the whole document.
On a crawl of `n` pages declaring `k` languages that is a multiple of `n * k`
parses of markup that has not changed since the first one, which is invisible
in a unit test and the dominant cost on a real multilingual site.

This is a budget, not a benchmark: it counts constructions rather than
seconds, so it says the same thing on every machine.
"""
import unittest
from unittest.mock import patch

from audit import crosspage


class _Page:
    def __init__(self, url, html=""):
        self.url = url
        self.raw_html = html
        self.error = None
        self.diagnostics = None


def _site(count: int, languages=("it", "en", "de")) -> list:
    """`count` pages, each in every language, all cross-linked."""
    pages = []
    for index in range(count):
        slug = f"page-{index}"
        urls = {code: (f"https://example.com/{slug}/" if code == "it"
                       else f"https://example.com/{code}/{slug}/")
                for code in languages}
        links = "".join(
            f'<link rel="alternate" hreflang="{code}" href="{url}">'
            for code, url in urls.items())
        for code, url in urls.items():
            body = "".join(f"<p>{code} sentence number {n} here</p>"
                           for n in range(8))
            pages.append(_Page(url, f'<html lang="{code}"><head>{links}'
                                    f"<title>{code} {slug} title</title>"
                                    f"</head><body>{body}</body></html>"))
    return pages


class MarkupIsParsedOncePerPage(unittest.TestCase):

    def parses_for(self, pages) -> int:
        real = crosspage.BeautifulSoup
        calls = []

        def counting(markup, *args, **kwargs):
            calls.append(markup)
            return real(markup, *args, **kwargs)

        with patch.object(crosspage, "BeautifulSoup", counting):
            crosspage.issues_for(pages)
        return len(calls)

    def test_the_parse_count_does_not_grow_with_the_number_of_languages(self):
        two = self.parses_for(_site(4, ("it", "en")))
        four = self.parses_for(_site(4, ("it", "en", "de", "fr")))
        # Twice the pages, so at most twice the parses - and nothing like
        # the square that re-parsing each alternate produced.
        self.assertLessEqual(four, two * 2)

    def test_each_page_is_parsed_a_bounded_number_of_times(self):
        pages = _site(5, ("it", "en", "de"))
        # Three questions per page - alternates, `x-default`, comparable
        # strings - and none of them asked twice.
        self.assertLessEqual(self.parses_for(pages), 3 * len(pages))

    def test_the_answer_is_unchanged_by_the_caching(self):
        pages = _site(3, ("it", "en"))
        first = crosspage.issues_for(pages)
        second = crosspage.issues_for(pages)
        self.assertEqual([(i.rule_id, i.source) for i in first],
                         [(i.rule_id, i.source) for i in second])


if __name__ == "__main__":
    unittest.main()
