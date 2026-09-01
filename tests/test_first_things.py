"""A run over a folder of deliverables has to say where to start.

`820 findings` is true and useless: the top of that list is the same six
page-level rules repeated across every document. What a person can act on is
the other shape of the same data - this is an email and these three things
break it in a mail client, this is a page and these three are worth an hour.
"""
from __future__ import annotations

import unittest

import audit
from audit.engine import AccessibilityResult
from report.model import from_accessibility
from report.template import render_html


def result_of(documents) -> AccessibilityResult:
    result = AccessibilityResult(root="/tmp/deliverables", mode="repo")
    result.documents = documents
    return result


PAGE = ("<html><head><title>Pricing</title></head><body>"
        "<img src='a.png'><button></button></body></html>")
EMAIL = ('<html xmlns:v="urn:schemas-microsoft-com:vml"><head></head><body>'
         '<p style="font-family: Brand Grotesk">hello</p>'
         '<a href="/x">Read</a></body></html>')
FRAGMENT = "<div onClick={go}>go</div>"


class KindIsRecorded(unittest.TestCase):
    def test_a_document_says_what_it_is(self):
        self.assertEqual(audit.analyze_document(PAGE, "index.html").kind, "page")
        self.assertEqual(audit.analyze_document(EMAIL, "mail.html").kind, "email")
        self.assertEqual(
            audit.analyze_document(FRAGMENT, "C.tsx", document_kind="fragment",
                                   syntax="jsx").kind,
            "fragment")

    def test_the_kind_reaches_every_finding_in_the_report(self):
        model = from_accessibility(result_of([
            audit.analyze_document(EMAIL, "mail.html")]), lang="en")
        self.assertTrue(model.findings)
        self.assertEqual({f.document_kind for f in model.findings}, {"email"})


class StartHere(unittest.TestCase):
    def model(self):
        return from_accessibility(result_of([
            audit.analyze_document(PAGE, "index.html"),
            audit.analyze_document(PAGE, "about.html"),
            audit.analyze_document(EMAIL, "march.html"),
            audit.analyze_document(FRAGMENT, "C.tsx", document_kind="fragment",
                                   syntax="jsx"),
        ]), lang="en")

    def test_each_kind_gets_its_own_short_list(self):
        groups = dict(self.model().first_things())
        self.assertEqual(set(groups), {"page", "email", "fragment"})
        for rows in groups.values():
            self.assertLessEqual(len(rows), 3)

    def test_a_problem_in_two_kinds_is_not_charged_to_one_of_them(self):
        """The bug this method was rewritten for: collapsing findings across
        the run first attributed the whole pile to whichever kind was seen
        first, and "no h1" turned up under Emails with a count of 34."""
        groups = dict(self.model().first_things())
        for kind, rows in groups.items():
            for _finding, places in rows:
                self.assertLessEqual(
                    places, {"page": 2, "email": 1, "fragment": 1}[kind],
                    f"{kind} counted more places than it has documents")

    def test_the_worst_kind_comes_first(self):
        order = [kind for kind, _rows in self.model().first_things()]
        self.assertEqual(order[0], "page")  # the only critical findings are there

    def test_a_run_that_recorded_no_kind_renders_nothing(self):
        model = self.model()
        for finding in model.findings:
            finding.document_kind = ""
        self.assertEqual(model.first_things(), [])
        self.assertNotIn('<section class="first-things">', render_html(model, "en"))

    def test_the_section_is_in_the_report_in_every_language(self):
        model = self.model()
        for lang, heading in (("en", "Start here"), ("uk", "З чого почати"),
                              ("it", "Da dove iniziare")):
            html = render_html(model, lang)
            self.assertIn('<section class="first-things">', html)
            self.assertIn(heading, html)


if __name__ == "__main__":
    unittest.main()
