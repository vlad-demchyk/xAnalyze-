"""Ignoring findings: the five levels, and the re-scoring that has to follow.

The re-scoring cases matter most. Suppressing one reason out of three and
leaving the original score would show a "high confidence" finding whose
explanation no longer contains the thing that made it high — which is worse
than either reporting or hiding it.
"""
from __future__ import annotations

import unittest
import uuid

import detectors  # noqa: F401 - registers the detectors
import suppression
from detectors.factory import DetectorFactory
from models import Confidence, TextBlock

SAMPLE = ("In today's fast-paced world our comprehensive platform is robust and "
          "will unlock the potential of your team — every single day.")


def block(text: str = SAMPLE, url: str = "http://x/a", dom: str = "html > body > p") -> TextBlock:
    return TextBlock(block_id=str(uuid.uuid4()), page_url=url, dom_path=dom, text=text)


def analyse(b: TextBlock):
    spans = DetectorFactory.create("offline").analyze_block(b)
    return spans, {b.block_id: b}


def style_spans(spans):
    return [s for s in spans if (s.details or {}).get("source") == "style"]


class Parsing(unittest.TestCase):
    def test_sections_and_comments(self):
        parsed = suppression.Suppressions.parse(
            "# a comment\n[phrases]\nrobust\n\n[rules]\ndashes\n[paths]\nsrc/gen/\n")
        self.assertEqual(parsed.phrases, ["robust"])
        self.assertEqual(parsed.rules, ["dashes"])
        self.assertEqual(parsed.paths, ["src/gen/"])

    def test_a_bare_list_is_read_as_phrases(self):
        # What people write first, before reading any documentation.
        self.assertEqual(suppression.Suppressions.parse("robust\ndelve\n").phrases,
                         ["robust", "delve"])

    def test_round_trip_through_settings(self):
        original = suppression.Suppressions(phrases=["a"], rules=["dashes"])
        restored = suppression.Suppressions.from_dict(original.to_dict())
        self.assertEqual(restored.phrases, ["a"])
        self.assertEqual(restored.rules, ["dashes"])


class Matching(unittest.TestCase):
    def test_phrases_are_case_insensitive(self):
        s = suppression.Suppressions(phrases=["Robust"])
        self.assertTrue(s.ignores_phrase("robust"))
        self.assertTrue(s.ignores_phrase(" ROBUST "))

    def test_directory_pattern_matches_anywhere_in_the_path(self):
        s = suppression.Suppressions(paths=["src/generated/"])
        self.assertTrue(s.ignores_path("a/src/generated/page.html"))
        self.assertFalse(s.ignores_path("src/app.html"))

    def test_glob_matches_the_file_name(self):
        s = suppression.Suppressions(paths=["*.min.html"])
        self.assertTrue(s.ignores_path("/deep/path/page.min.html"))
        self.assertFalse(s.ignores_path("/deep/path/page.html"))

    def test_a_url_is_matched_by_the_same_list(self):
        s = suppression.Suppressions(paths=["https://staging.example.com/*"])
        self.assertTrue(s.ignores_path("https://staging.example.com/pricing"))
        self.assertFalse(s.ignores_path("https://example.com/pricing"))


class Fingerprints(unittest.TestCase):
    def test_same_text_in_the_same_place_gives_the_same_id(self):
        a = suppression.fingerprint("page.html", "Hello  there", "style")
        b = suppression.fingerprint("page.html", "Hello there", "style")
        # Whitespace is normalised, so reformatting the source does not
        # silently expire a dismissal.
        self.assertEqual(a, b)

    def test_different_documents_give_different_ids(self):
        self.assertNotEqual(
            suppression.fingerprint("a.html", "Hello", "style"),
            suppression.fingerprint("b.html", "Hello", "style"),
        )

    def test_dismissing_one_finding_leaves_the_others(self):
        b = block()
        spans, blocks = analyse(b)
        target = style_spans(spans)[0]
        s = suppression.Suppressions(
            fingerprints=[suppression.span_fingerprint(target, b)])
        kept = suppression.filter_spans(spans, blocks, s)
        self.assertEqual(len(kept), len(spans) - 1)


class Rescoring(unittest.TestCase):
    def test_suppressed_phrase_lowers_the_score_and_leaves_the_rest(self):
        b = block()
        spans, blocks = analyse(b)
        before = style_spans(spans)[0]
        s = suppression.Suppressions(phrases=["comprehensive", "robust"])
        after = style_spans(suppression.filter_spans(spans, blocks, s))[0]

        self.assertLess(after.score, before.score)
        self.assertNotIn("robust", after.details["cliches"])
        # The reasons that were not suppressed are still reported.
        self.assertIn("unlock the potential", after.details["cliches"])

    def test_suppressing_a_signal_zeroes_it_in_the_explanation(self):
        b = block()
        spans, blocks = analyse(b)
        s = suppression.Suppressions(rules=["dashes"])
        after = style_spans(suppression.filter_spans(spans, blocks, s))[0]
        self.assertEqual(after.details["signals"]["dashes"], 0.0)

    def test_a_finding_with_nothing_left_to_say_is_dropped(self):
        b = block("Our comprehensive platform is robust.")
        spans, blocks = analyse(b)
        s = suppression.Suppressions(phrases=["comprehensive", "robust"])
        self.assertEqual(style_spans(suppression.filter_spans(spans, blocks, s)), [])

    def test_an_untouched_finding_keeps_its_exact_score(self):
        b = block()
        spans, blocks = analyse(b)
        before = style_spans(spans)[0]
        s = suppression.Suppressions(phrases=["something else entirely"])
        after = style_spans(suppression.filter_spans(spans, blocks, s))[0]
        self.assertEqual(after.score, before.score)


class CharacterAndScopeSuppression(unittest.TestCase):
    def test_a_character_category_can_be_switched_off(self):
        b = block("This costs 5 — 6 euros.")
        spans, blocks = analyse(b)
        s = suppression.Suppressions(rules=["typography"])
        kept = suppression.filter_spans(spans, blocks, s)
        self.assertEqual([x for x in kept
                          if (x.details or {}).get("category") == "typography"], [])

    def test_a_whole_document_can_be_skipped(self):
        b = block()
        spans, blocks = analyse(b)
        s = suppression.Suppressions(paths=["http://x/a"])
        self.assertEqual(suppression.filter_spans(spans, blocks, s), [])

    def test_a_region_of_the_page_can_be_skipped(self):
        b = block(dom="html > body > footer:nth-of-type(1) > p:nth-of-type(1)")
        spans, blocks = analyse(b)
        s = suppression.Suppressions(selectors=["footer"])
        self.assertEqual(suppression.filter_spans(spans, blocks, s), [])

    def test_an_empty_list_changes_nothing(self):
        b = block()
        spans, blocks = analyse(b)
        empty = suppression.Suppressions()
        self.assertIs(suppression.filter_spans(spans, blocks, empty), spans)


class AccessibilitySuppression(unittest.TestCase):
    def test_a_rule_can_be_switched_off(self):
        from audit import analyze_document

        issues = analyze_document('<img src="/a.png">', "p.html").issues
        s = suppression.Suppressions(rules=["image-alt"])
        kept = suppression.filter_issues(issues, s)
        # Only the accessibility rule is switched off. The same <img> also
        # legitimately produces an SEO finding about missing dimensions, and
        # suppressing one category must not silently take the other with it.
        self.assertEqual([i.rule_id for i in kept if i.category == "accessibility"], [])
        self.assertTrue([i for i in kept if i.category == "seo"])

    def test_one_accessibility_finding_can_be_dismissed(self):
        from audit import analyze_document

        issues = analyze_document('<img src="/a.png"><img src="/b.png">', "p.html").issues
        s = suppression.Suppressions(
            fingerprints=[suppression.issue_fingerprint(issues[0])])
        self.assertEqual(len(suppression.filter_issues(issues, s)), len(issues) - 1)

    def test_one_list_governs_both_analyses(self):
        # The user thinking "not this part of the site" means it for the
        # whole tool, not per subsystem.
        from audit import analyze_document

        s = suppression.Suppressions(paths=["vendor/"])
        issues = analyze_document('<img src="/a.png">', "vendor/theme.html").issues
        self.assertTrue(issues)  # the page does have findings when not ignored
        self.assertEqual(suppression.filter_issues(issues, s), [])

        b = block(url="vendor/theme.html")
        spans, blocks = analyse(b)
        self.assertEqual(suppression.filter_spans(spans, blocks, s), [])


class KnownIds(unittest.TestCase):
    def test_the_settings_ui_can_list_every_switchable_check(self):
        ids = suppression.known_rule_ids()
        self.assertIn("dashes", ids["style"])
        self.assertIn("typography", ids["characters"])
        self.assertIn("image-alt", ids["accessibility"])


if __name__ == "__main__":
    unittest.main()
