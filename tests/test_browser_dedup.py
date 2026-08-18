"""What happens when three engines report the same broken element.

The collapse is the whole reason both engines are worth running: together
they find more than either alone, but only if the overlap costs nothing.
An overlap that shows up as duplicate rows is worse than not running the
second engine at all, because the user learns the report is padded.

These tests pin the part that is easy to get wrong and impossible to notice:
each engine spells the same element differently, so anything keyed on the
selector silently never matches.
"""
import unittest

from audit import browser
from audit.base import ACCESSIBILITY, CRITICAL, MODERATE, SERIOUS, Issue


def issue(rule_id, engine, snippet="", selector="", severity=SERIOUS,
          source="http://example.test/"):
    return Issue(rule_id=rule_id, severity=severity, category=ACCESSIBILITY,
                 source=source, engine=engine, snippet=snippet,
                 selector=selector)


class ElementKeyTests(unittest.TestCase):

    def test_self_closing_and_open_serialisation_are_the_same_element(self):
        """Our parser writes `<img/>`, the browser writes `<img>`."""
        ours = browser._element_key(issue("image-alt", "static",
                                          '<img src="missing.png"/>'))
        theirs = browser._element_key(issue("axe:image-alt", "axe",
                                            '<img src="missing.png">'))
        self.assertEqual(ours, theirs)
        self.assertTrue(ours)

    def test_attribute_order_does_not_change_the_key(self):
        a = browser._element_key(issue("x", "static", '<a href="/x" id="q">'))
        b = browser._element_key(issue("x", "axe", '<a id="q" href="/x"></a>'))
        self.assertEqual(a, b)

    def test_a_finding_with_no_element_has_no_key(self):
        """A missing canonical link is about the page, not about a node, and
        must not be matched against every other elementless finding."""
        self.assertEqual(browser._element_key(issue("seo-canonical", "static")), "")


class DeduplicateTests(unittest.TestCase):

    def test_three_engines_on_one_image_become_one_row(self):
        issues = [
            issue("image-alt", "static", '<img src="a.png"/>',
                  "html:nth-of-type(1) > body:nth-of-type(1) > img:nth-of-type(1)",
                  severity=MODERATE),
            issue("axe:image-alt", "axe", '<img src="a.png">', "img",
                  severity=CRITICAL),
            issue("htmlcs:1_1_1", "htmlcs", '<img src="a.png">', ""),
        ]
        kept = browser.deduplicate(issues)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].rule_id, "image-alt")
        self.assertEqual(kept[0].details["also_found_by"], ["axe", "htmlcs"])

    def test_the_most_severe_reading_survives(self):
        kept = browser.deduplicate([
            issue("image-alt", "static", '<img src="a.png"/>', severity=MODERATE),
            issue("axe:image-alt", "axe", '<img src="a.png">', severity=CRITICAL),
        ])
        self.assertEqual(kept[0].severity, CRITICAL)

    def test_two_findings_from_one_engine_are_never_merged(self):
        """Two identical-looking buttons are two buttons. Merging them would
        hide a real second problem, which is worse than a duplicate row."""
        kept = browser.deduplicate([
            issue("state:focus-not-visible", "browser", "<button></button>",
                  "html > body > button:nth-of-type(1)"),
            issue("state:focus-not-visible", "browser", "<button></button>",
                  "html > body > button:nth-of-type(2)"),
        ])
        self.assertEqual(len(kept), 2)

    def test_different_problems_on_one_element_stay_separate(self):
        """A missing alt and missing dimensions on the same image are two
        things to fix, not one finding with corroboration."""
        kept = browser.deduplicate([
            issue("image-alt", "static", '<img src="a.png"/>'),
            issue("seo-image-dimensions", "static", '<img src="a.png"/>'),
        ])
        self.assertEqual(len(kept), 2)

    def test_the_same_element_on_two_pages_is_two_findings(self):
        kept = browser.deduplicate([
            issue("image-alt", "static", '<img src="a.png"/>',
                  source="http://example.test/one"),
            issue("axe:image-alt", "axe", '<img src="a.png">',
                  source="http://example.test/two"),
        ])
        self.assertEqual(len(kept), 2)

    def test_elementless_findings_are_still_deduplicated_by_rule(self):
        kept = browser.deduplicate([
            issue("html-lang", "static"),
            issue("axe:html-has-lang", "axe"),
        ])
        self.assertEqual(len(kept), 1)


if __name__ == "__main__":
    unittest.main()


class SameEngineCorroborationTests(unittest.TestCase):
    """One engine reporting the same element twice is a duplicate row, not a
    second opinion. Seen live: HTML_CodeSniffer emits two messages under one
    criterion for the same heading."""

    def test_a_repeat_from_one_engine_is_collapsed_without_claiming_support(self):
        kept = browser.deduplicate([
            issue("htmlcs:1_3_1_A", "htmlcs", "<h2>Good evening</h2>"),
            issue("htmlcs:1_3_1_A", "htmlcs", "<h2>Good evening</h2>"),
        ])
        self.assertEqual(len(kept), 1)
        self.assertNotIn("also_found_by", kept[0].details)
