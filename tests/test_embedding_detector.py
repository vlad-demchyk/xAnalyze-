"""Tests for the embedding detector."""
import unittest
from detectors.embedding import EmbeddingDetector
from models import TextBlock, Confidence


def _make_block(text: str, lang: str = "en") -> TextBlock:
    return TextBlock(block_id="test", page_url="test", dom_path="test",
                     text=text, language_hint=lang)


class TestEmbeddingDetector(unittest.TestCase):
    """Test the embedding detector."""

    def test_ai_text_detected(self):
        """Obvious AI text should be detected."""
        block = _make_block(
            "It is worth noting that this comprehensive, robust, and scalable "
            "solution delves into the intricacies of modern software development. "
            "Moreover, the landscape has evolved significantly. Furthermore, it is "
            "important to understand that the beauty of this approach lies in its "
            "simplicity. When it comes to implementation, there are several key "
            "considerations. In terms of best practices, first and foremost, you "
            "should always leverage the power of automation."
        )
        detector = EmbeddingDetector(threshold=0.55)  # Lower threshold for test
        spans = detector.analyze_block(block)
        self.assertGreater(len(spans), 0, "AI text should be detected")
        self.assertGreater(spans[0].score, 0.5,
                           f"Score {spans[0].score} should be > 0.5 for AI text")

    def test_human_text_not_flagged(self):
        """Normal human text should not be flagged."""
        block = _make_block(
            "I went to the store yesterday. Bought some milk and bread. "
            "The weather was nice so I walked. Saw my neighbor on the way. "
            "We talked for a bit about the garden and the kids."
        )
        detector = EmbeddingDetector()
        spans = detector.analyze_block(block)
        # Should either have no spans or low score
        if spans:
            self.assertLess(spans[0].score, 0.6,
                            f"Human text score {spans[0].score} should be < 0.6")

    def test_short_text_skipped(self):
        """Text with less than 5 words should be skipped."""
        block = _make_block("Hello world")
        detector = EmbeddingDetector()
        spans = detector.analyze_block(block)
        self.assertEqual(len(spans), 0, "Short text should be skipped")

    def test_empty_text(self):
        """Empty text should return no spans."""
        block = _make_block("")
        detector = EmbeddingDetector()
        spans = detector.analyze_block(block)
        self.assertEqual(len(spans), 0)

    def test_threshold_respected(self):
        """Below threshold should return no spans."""
        block = _make_block("Short text with few words here.")
        detector = EmbeddingDetector(threshold=0.99)  # Very high threshold
        spans = detector.analyze_block(block)
        self.assertEqual(len(spans), 0, "Below threshold should return no spans")

    def test_score_range(self):
        """Score should be in 0..1 range."""
        block = _make_block(
            "This is a test sentence with enough words to be analyzed by the "
            "embedding detector. It should produce a valid score in the range."
        )
        detector = EmbeddingDetector()
        spans = detector.analyze_block(block)
        if spans:
            self.assertGreaterEqual(spans[0].score, 0.0)
            self.assertLessEqual(spans[0].score, 1.0)


if __name__ == "__main__":
    unittest.main()
