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


if __name__ == "__main__":
    unittest.main()
