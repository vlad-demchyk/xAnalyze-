"""The markup-provenance rule: what it must catch, and what it must not.

Half of these tests are about restraint. The rule matches vendor names, and
vendor names are ordinary words that appear in ordinary code - a class called
`claudette-card`, a field called `data-updated-by-gpt`. A provenance check
that cries wolf on someone's own CSS is worse than no provenance check, so
the negatives here are as load-bearing as the positives.
"""
import unittest

import audit
from audit import analyze_document

RULE_ID = "bp-ai-markup-artifact"


def findings(markup: str) -> list:
    """This rule's findings for one snippet, through the real engine.

    Driven end to end rather than by calling `check()` directly: the engine
    is what dedupes findings per element, and "one row per element" is one of
    the things asserted here.
    """
    found = analyze_document(markup, "test.html", line_numbers=True).issues
    return [i for i in found if i.rule_id == RULE_ID]


class Catches(unittest.TestCase):
    def test_a_vendor_class_left_on_a_pasted_block(self):
        found = findings('<div class="prose claude-artifact-body">text</div>')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].severity, audit.MINOR)
        self.assertIn('class="claude-artifact-body"', found[0].details["names"])

    def test_a_vendor_data_attribute(self):
        found = findings('<p data-claude-artifact="msg_01">text</p>')
        self.assertEqual(len(found), 1)
        self.assertIn("data-claude-artifact", found[0].details["names"])

    def test_other_vendors_too(self):
        for markup, vendor in (
            ('<div class="chatgpt-response">t</div>', "chatgpt"),
            ('<div data-gemini-id="1">t</div>', "gemini"),
            ('<div data-gpt-run="1">t</div>', "gpt"),
        ):
            with self.subTest(markup=markup):
                found = findings(markup)
                self.assertEqual(len(found), 1, markup)
                self.assertIn(vendor, found[0].details["vendor"])

    def test_one_finding_per_element_even_with_several_artifacts(self):
        """Two rows for one element would each offer a fix that leaves the
        other artifact in place - and the audit engine dedupes by element
        anyway, so the second row would be dropped with its half of the fix."""
        found = findings(
            '<div class="prose claude-artifact-body" data-claude-artifact="1">t</div>')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].details["count"], 2)

    def test_the_fix_removes_every_artifact_and_keeps_the_element(self):
        found = findings(
            '<div class="prose claude-artifact-body" data-claude-artifact="1">t</div>')
        fix = found[0].fix_snippet
        self.assertIn("prose", fix)
        self.assertNotIn("claude", fix)
        self.assertTrue(fix.startswith("<div"))

    def test_the_class_attribute_goes_when_nothing_is_left_of_it(self):
        found = findings('<div class="claude-artifact-body">t</div>')
        self.assertEqual(found[0].fix_snippet, "<div>")


class LeavesAlone(unittest.TestCase):
    def test_a_word_that_merely_contains_a_vendor_name(self):
        self.assertEqual(findings('<p class="claudette-note">t</p>'), [])

    def test_someones_own_data_field(self):
        self.assertEqual(findings('<p data-updated-by-gpt="yes">t</p>'), [])

    def test_ordinary_markup(self):
        self.assertEqual(
            findings('<div class="card card--wide" data-id="7">t</div>'), [])


if __name__ == "__main__":
    unittest.main()
