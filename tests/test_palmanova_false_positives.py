"""False positives the final Palmanova audit found (T-1961).

Each test is the shape the 381-page crawl produced, checked against its HTML.
"""
from __future__ import annotations

import json
import unittest

from audit.base import ADVISORY, EXACT, MINOR
from audit.browser import issues_from_htmlcs

H30_2 = "WCAG2AA.Principle1.Guideline1_1.1_1_1.H30.2"


def _h30(html: str, label: str | None = None):
    message = {"type": 1, "code": H30_2, "html": html, "msg": "…", "tag": "a"}
    if label is not None:
        message["label"] = label
    return issues_from_htmlcs(json.dumps({"messages": [message]}),
                              "https://site/")[0]


class GalleryLinkNamedByAttribute(unittest.TestCase):
    def test_aria_label_reported_by_the_collector_makes_it_a_note(self):
        issue = _h30('<a href="/a.jpg"><img src="a.jpg"></a>',
                     label="Apri immagine 1")
        self.assertEqual(issue.severity, MINOR)
        self.assertEqual(issue.confidence, ADVISORY)
        self.assertEqual(issue.details["accessible_name_from_attributes"],
                         "Apri immagine 1")

    def test_a_cached_payload_without_label_reads_the_opening_tag(self):
        for tag in ('<a href="/a.jpg" aria-label="Piazza Grande"><img src="a.jpg"></a>',
                    "<a title='Piazza' href=/a.jpg><img></a>",
                    '<a aria-labelledby="cap1" href="#"><img></a>'):
            with self.subTest(tag=tag):
                self.assertEqual(_h30(tag).severity, MINOR)

    def test_an_unnamed_link_keeps_its_weight(self):
        """The rule's real finding must survive the fix."""
        for tag in ('<a href="/a.jpg"><img src="a.jpg"></a>',
                    '<a href="/a.jpg" aria-label=""><img src="a.jpg"></a>',
                    # A name on the image, not the link, is not read here.
                    '<a href="/a.jpg"><img src="a.jpg" title="x"></a>'):
            with self.subTest(tag=tag):
                issue = _h30(tag, label="")
                self.assertNotEqual(issue.severity, MINOR)
                self.assertEqual(issue.confidence, EXACT)

    def test_other_htmlcs_codes_are_not_touched(self):
        message = {"type": 1, "code": "WCAG2AA.Principle1.Guideline1_1.1_1_1.H37",
                   "html": '<img aria-label="x">', "msg": "…", "tag": "img",
                   "label": "x"}
        issue = issues_from_htmlcs(json.dumps({"messages": [message]}),
                                   "https://site/")[0]
        self.assertNotEqual(issue.severity, MINOR)


if __name__ == "__main__":
    unittest.main()
