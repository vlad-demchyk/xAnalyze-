"""An invisible character is a character, not a sentence a model wrote.

`fullscan.is_character_finding` exists because the same question was being
answered in two places that disagreed. Measured 2026-09-01 on a 250-page
run: there was a third copy, inside the briefing writer, and it read only
the explanation - so `[invisible] U+00AD SOFT HYPHEN`, which carries neither
the word "typography" nor anything else that copy looked for, was counted
under **AI-generated text patterns** at high confidence. Nine of the
twenty-nine rows in that section were invisible characters.

Saying a soft hyphen is an AI-written passage is not a rounding error in a
count. It is the tool's central claim, made about the wrong evidence.
"""
import unittest

from cli_impl.fullscan import _markdown_briefing_input, is_character_finding


def _finding(source, explanation, confidence="high"):
    return {"file": "https://x.test/", "line": 0, "text": "­",
            "source": source, "score": 1.0, "confidence": confidence,
            "explanation": explanation}


class WhichBucketAFindingLandsIn(unittest.TestCase):

    def test_an_invisible_character_is_a_character(self):
        found = _finding("characters", "[invisible] U+00AD SOFT HYPHEN -> removed")
        self.assertTrue(is_character_finding(found))

    def test_a_wording_finding_is_not(self):
        found = _finding("style", "style-uniformity=0.79; cliche: a testament to")
        self.assertFalse(is_character_finding(found))


class TheBriefingCarriesWhatItNeedsToSort(unittest.TestCase):

    def test_the_source_survives_the_row_it_is_sorted_by(self):
        """The row the briefing is handed used to drop `source`, which left
        the split reading an explanation that does not say."""
        rows = _markdown_briefing_input(
            False, [], [_finding("characters",
                                 "[invisible] U+200B ZERO WIDTH SPACE -> removed")])
        self.assertEqual(rows[0]["source"], "characters")
        self.assertTrue(is_character_finding(rows[0]))

    def test_an_invisible_character_does_not_reach_the_ai_section(self):
        from cli_impl.reports import _write_report
        import tempfile
        import argparse
        from pathlib import Path
        from audit.engine import AccessibilityResult

        rows = _markdown_briefing_input(
            False, [],
            [_finding("characters", "[invisible] U+00AD SOFT HYPHEN -> removed"),
             _finding("style", "cliche: a testament to", confidence="medium")])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "briefing.md"
            args = argparse.Namespace(report=str(path), styled_report=None,
                                      medium=None, confidence=None)
            result = AccessibilityResult(root="https://x.test/", mode="web")
            payload = _write_report(result, args, "en", None, ai_findings=rows)
        self.assertEqual(payload["ai_patterns"]["total"], 1)
        self.assertEqual(payload["ai_patterns"]["high"], 0)
        self.assertEqual(payload["typography"]["total"], 1)


if __name__ == "__main__":
    unittest.main()
