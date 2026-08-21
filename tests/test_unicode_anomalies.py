"""Tests for the unicode anomalies detector."""
import unittest
from detectors.unicode_anomalies import UnicodeAnomalyDetector
from models import TextBlock, Confidence


def _make_block(text: str, lang: str = "en") -> TextBlock:
    return TextBlock(block_id="test", page_url="test", dom_path="test",
                     text=text, language_hint=lang)


class TestUnicodeAnomalyDetector(unittest.TestCase):
    """Test the unicode anomalies detector."""

    def test_em_dash_detected(self):
        """Em dash should be detected."""
        block = _make_block("Hello — world")
        detector = UnicodeAnomalyDetector()
        spans = detector.analyze_block(block)
        self.assertGreater(len(spans), 0, "Em dash should be detected")
        self.assertEqual(spans[0].details["source"], "characters")

    def test_curly_quote_detected(self):
        """Curly quote should be detected."""
        block = _make_block("Hello \u2018world\u2019")
        detector = UnicodeAnomalyDetector()
        spans = detector.analyze_block(block)
        self.assertGreater(len(spans), 0, "Curly quote should be detected")

    def test_zero_width_space_detected(self):
        """Zero-width space should be detected."""
        block = _make_block("Hello\u200bworld")
        detector = UnicodeAnomalyDetector()
        spans = detector.analyze_block(block)
        self.assertGreater(len(spans), 0, "Zero-width space should be detected")

    def test_normal_text_no_finds(self):
        """Normal ASCII text should have no findings."""
        block = _make_block("Hello world, this is normal text.")
        detector = UnicodeAnomalyDetector()
        spans = detector.analyze_block(block)
        self.assertEqual(len(spans), 0, "Normal text should have no findings")

    def test_ukrainian_text_no_false_positive(self):
        """Ukrainian text with guillemets should not be flagged."""
        block = _make_block("Привіт, «світ»! Це нормальний текст.", "uk")
        detector = UnicodeAnomalyDetector()
        spans = detector.analyze_block(block)
        # Guillemets are normal for Ukrainian
        self.assertEqual(len(spans), 0, "Ukrainian guillemets should not be flagged")

    def test_italian_accents_no_false_positive(self):
        """Italian accents should not be flagged."""
        block = _make_block("Città è molto bella. Perché no?", "it")
        detector = UnicodeAnomalyDetector()
        spans = detector.analyze_block(block)
        self.assertEqual(len(spans), 0, "Italian accents should not be flagged")

    def test_replacement_provided(self):
        """Findings should have replacement text."""
        block = _make_block("Hello—world")
        detector = UnicodeAnomalyDetector()
        spans = detector.analyze_block(block)
        self.assertGreater(len(spans), 0)
        self.assertIsNotNone(spans[0].replacement)

    def test_score_range(self):
        """Score should be in 0..1 range."""
        block = _make_block("Hello—world 'test'")
        detector = UnicodeAnomalyDetector()
        spans = detector.analyze_block(block)
        for span in spans:
            self.assertGreaterEqual(span.score, 0.0)
            self.assertLessEqual(span.score, 1.0)


class TestHomoglyphs(unittest.TestCase):
    """Mixed-alphabet words are the invisible attack; they must be caught
    per word, and a lone look-alike letter must be reported without a
    deterministic replacement."""

    def _homoglyph_spans(self, text: str, lang: str = "en"):
        block = _make_block(text, lang)
        return [s for s in UnicodeAnomalyDetector().analyze_block(block)
                if "omoglyph" in s.details.get("description", "")
                or s.details.get("category") == "homoglyph"
                or s.category == "homoglyph"]

    def test_cyrillic_a_inside_english_word(self):
        spans = self._homoglyph_spans("Login to pаypal.com and verify")
        self.assertGreater(len(spans), 0, "Cyrillic а inside paypal must be caught")

    def test_latin_a_inside_ukrainian_word(self):
        spans = self._homoglyph_spans("Це укрaїнський текст", "uk")
        self.assertGreater(len(spans), 0, "Latin a inside укрaїнський must be caught")

    def test_lone_cyrillic_letter_in_english_text(self):
        """The case that per-word judging cannot see: one wrong letter
        standing alone."""
        spans = self._homoglyph_spans("This text has Cyrillic а instead of Latin a")
        self.assertGreater(len(spans), 0, "Lone Cyrillic а in English text must be caught")
        self.assertIsNone(spans[0].replacement,
                          "Lone look-alike is report-only, not auto-fixed")

    def test_brand_single_letter_not_autocorrected(self):
        """A legitimate Latin X in Ukrainian prose may be flagged for review,
        but --fix must never rewrite it to Cyrillic Х silently."""
        spans = self._homoglyph_spans("Купуйте товар brand X на сайті", "uk")
        for span in spans:
            self.assertIsNone(span.replacement)

    def test_clean_texts_stay_silent(self):
        for text, lang in (("Plain English text with no foreign letters", "en"),
                           ("Use Docker та Kubernetes для деплою", "uk"),
                           ("Привіт, «світ»!", "uk")):
            with self.subTest(text=text):
                self.assertEqual(self._homoglyph_spans(text, lang), [])


if __name__ == "__main__":
    unittest.main()
