"""Tests for the heuristic detector — scoring, clichés, structural patterns."""
import unittest
from detectors.heuristic import (
    HeuristicDetector, combine_score, _sentences, _burstiness_score,
    _lexical_diversity_score, _em_dash_score, _cliche_hits, _structural_matches,
)
from models import TextBlock, Confidence


def _make_block(text: str, lang: str = "en") -> TextBlock:
    return TextBlock(block_id="test", page_url="test", dom_path="test",
                     text=text, language_hint=lang)


class TestCombineScore(unittest.TestCase):
    """Test the scoring formula."""

    def test_base_only(self):
        """No clichés, no structural — score from uniformity/repetition/dashes."""
        score = combine_score(uniformity=0.5, repetition=0.5, dashes=0.5,
                              structural=False, cliches=[])
        # base = (0.40*0.5 + 0.35*0.5 + 0.25*0.5) / 1.0 = 0.5
        # remaining = 1.0 - 0.5 = 0.5, no weights → score = 0.5
        self.assertAlmostEqual(score, 0.5, places=2)

    def test_one_strong_cliche(self):
        """One phrase cliché (weight 0.30) on top of base 0.5."""
        score = combine_score(uniformity=0.5, repetition=0.5, dashes=0.5,
                              structural=False, cliches=["comprehensive solution"])
        # base = 0.5, remaining = 0.5
        # remaining *= (1 - 0.30) = 0.35
        # score = 1 - 0.35 = 0.65
        self.assertAlmostEqual(score, 0.65, places=2)

    def test_one_weak_cliche(self):
        """One word cliché (weight 0.10) on top of base 0.5."""
        score = combine_score(uniformity=0.5, repetition=0.5, dashes=0.5,
                              structural=False, cliches=["delve"])
        # base = 0.5, remaining = 0.5
        # remaining *= (1 - 0.10) = 0.45
        # score = 1 - 0.45 = 0.55
        self.assertAlmostEqual(score, 0.55, places=2)

    def test_structural_pattern(self):
        """Structural pattern (weight 0.25) on top of base 0.5."""
        score = combine_score(uniformity=0.5, repetition=0.5, dashes=0.5,
                              structural=True, cliches=[])
        # base = 0.5, remaining = 0.5
        # remaining *= (1 - 0.25) = 0.375
        # score = 1 - 0.375 = 0.625
        self.assertAlmostEqual(score, 0.625, places=2)

    def test_multiple_cliches_diminishing_returns(self):
        """Each additional cliché adds less."""
        score1 = combine_score(0.5, 0.5, 0.5, False, ["delve"])
        score2 = combine_score(0.5, 0.5, 0.5, False, ["delve", "robust"])
        score3 = combine_score(0.5, 0.5, 0.5, False, ["delve", "robust", "scalable"])
        self.assertGreater(score2, score1)
        self.assertGreater(score3, score2)
        # Diminishing: second adds less than first
        delta1 = score1 - 0.5
        delta2 = score2 - score1
        self.assertGreater(delta1, delta2)

    def test_none_signals_excluded(self):
        """None signals are excluded from the average, not treated as zero."""
        score_none = combine_score(None, 0.5, 0.5, False, [])
        score_zero = combine_score(0.0, 0.5, 0.5, False, [])
        # With None: base = (0.35*0.5 + 0.25*0.5) / 0.6 = 0.5
        # With 0.0: base = (0.40*0.0 + 0.35*0.5 + 0.25*0.5) / 1.0 = 0.3
        self.assertGreater(score_none, score_zero)

    def test_all_none(self):
        """All None signals → base = 0."""
        score = combine_score(None, None, None, False, [])
        self.assertAlmostEqual(score, 0.0, places=2)


class TestBurstinessScore(unittest.TestCase):
    """Test sentence length uniformity detection."""

    def test_uniform_sentences(self):
        """Uniform sentences → high score (AI-like)."""
        sentences = ["This is a test sentence.", "Another test sentence here.",
                     "Yet another test sentence."]
        score = _burstiness_score(sentences)
        self.assertIsNotNone(score)
        self.assertGreater(score, 0.5)

    def test_varied_sentences(self):
        """Varied sentences → low score (human-like)."""
        sentences = ["Hi.", "This is a much longer sentence with many words.",
                     "Medium length sentence.", "Short.", 
                     "A very long sentence that goes on and on with many words."]
        score = _burstiness_score(sentences)
        self.assertIsNotNone(score)
        self.assertLess(score, 0.5)

    def test_too_few_sentences(self):
        """Less than 3 sentences → None."""
        self.assertIsNone(_burstiness_score(["One sentence.", "Two."]))
        self.assertIsNone(_burstiness_score(["One."]))
        self.assertIsNone(_burstiness_score([]))


class TestLexicalDiversityScore(unittest.TestCase):
    """Test type-token ratio detection."""

    def test_repetitive_text(self):
        """Repetitive text → high score (AI-like)."""
        words = ["the"] * 50
        score = _lexical_diversity_score(words)
        self.assertIsNotNone(score)
        self.assertGreater(score, 0.5)

    def test_diverse_text(self):
        """Diverse text → low score (human-like)."""
        words = [f"word{i}" for i in range(50)]
        score = _lexical_diversity_score(words)
        self.assertIsNotNone(score)
        self.assertLess(score, 0.5)

    def test_too_few_words(self):
        """Less than 20 words → None."""
        self.assertIsNone(_lexical_diversity_score(["a", "b", "c"]))


class TestEmDashScore(unittest.TestCase):
    """Test em-dash density detection."""

    def test_heavy_dashes(self):
        """Heavy dash usage → high score."""
        text = "word " * 20 + "— " * 10
        score = _em_dash_score(text, 30)
        self.assertIsNotNone(score)
        self.assertGreater(score, 0.5)

    def test_no_dashes(self):
        """No dashes → low score."""
        text = "word " * 20
        score = _em_dash_score(text, 20)
        self.assertIsNotNone(score)
        self.assertAlmostEqual(score, 0.0, places=2)

    def test_too_short(self):
        """Less than 15 words → None."""
        self.assertIsNone(_em_dash_score("short text", 2))


class TestClicheHits(unittest.TestCase):
    """Test cliché phrase detection."""

    def test_english_cliche(self):
        """English cliché detected."""
        hits = _cliche_hits("It is worth mentioning that this works.", "en")
        self.assertIn("it is worth mentioning", hits)

    def test_ukrainian_cliche(self):
        """Ukrainian cliché detected."""
        hits = _cliche_hits("Варто зазначити, що це працює.", "uk")
        self.assertIn("варто зазначити", hits)

    def test_italian_cliche(self):
        """Italian cliché detected."""
        hits = _cliche_hits("È importante sottolineare che funziona.", "it")
        self.assertIn("è importante sottolineare", hits)

    def test_no_cliche(self):
        """No cliché in normal text."""
        hits = _cliche_hits("The quick brown fox jumps over the lazy dog.", "en")
        self.assertEqual(len(hits), 0)

    def test_unknown_language_checks_all(self):
        """Unknown language → checks all lists."""
        hits = _cliche_hits("Варто зазначити, що це працює.", None)
        self.assertIn("варто зазначити", hits)


class TestStructuralMatches(unittest.TestCase):
    """Test structural pattern detection."""

    def test_not_just_but(self):
        """'not just X but Y' pattern detected."""
        matches = _structural_matches("Not just a tool but a platform.", "en")
        self.assertGreater(len(matches), 0)

    def test_ukrainian_pattern(self):
        """Ukrainian structural pattern detected."""
        matches = _structural_matches("Це не просто про дизайн, це про досвід.", "uk")
        self.assertGreater(len(matches), 0)

    def test_no_pattern(self):
        """No structural pattern in normal text."""
        matches = _structural_matches("The quick brown fox jumps.", "en")
        self.assertEqual(len(matches), 0)


class TestHeuristicDetector(unittest.TestCase):
    """Test the full detector."""

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
        detector = HeuristicDetector()
        spans = detector.analyze_block(block)
        # Should find at least one MEDIUM or HIGH confidence span
        medium_high = [s for s in spans if s.confidence in (Confidence.MEDIUM, Confidence.HIGH)]
        self.assertGreater(len(medium_high), 0,
                           f"Expected MEDIUM/HIGH, got {[s.confidence.value for s in spans]}")

    def test_human_text_not_flagged(self):
        """Normal human text should not be flagged as MEDIUM/HIGH."""
        block = _make_block(
            "I went to the store yesterday. Bought some milk and bread. "
            "The weather was nice so I walked. Saw my neighbor on the way. "
            "We talked for a bit about the garden."
        )
        detector = HeuristicDetector()
        spans = detector.analyze_block(block)
        medium_high = [s for s in spans if s.confidence in (Confidence.MEDIUM, Confidence.HIGH)]
        self.assertEqual(len(medium_high), 0,
                         f"False positive: {[s.confidence.value for s in spans]}")

    def test_no_cliche_no_medium_rule(self):
        """Without clichés or structural patterns, score capped at 0.32."""
        block = _make_block(
            "The system processes data efficiently. It handles requests quickly. "
            "The interface is clean and simple. Users find it easy to navigate. "
            "Performance metrics show improvement over time."
        )
        detector = HeuristicDetector()
        spans = detector.analyze_block(block)
        for span in spans:
            if not (span.details or {}).get("cliches") and not (span.details or {}).get("structural"):
                self.assertLess(span.score, 0.33,
                                f"Score {span.score} should be < 0.33 without clichés")

    def test_short_text(self):
        """Short text should not crash."""
        block = _make_block("Hello world.")
        detector = HeuristicDetector()
        spans = detector.analyze_block(block)
        self.assertIsInstance(spans, list)


if __name__ == "__main__":
    unittest.main()
