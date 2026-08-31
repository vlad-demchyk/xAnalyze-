"""Tests for the embedding detector."""
import json
import unittest

from corpus_split import is_reference, split
from detectors.embedding import CORPUS_PATH as CORPUS, THRESHOLD, EmbeddingDetector
from models import TextBlock, Confidence


_MODEL_SHAPED = (
    "It is worth noting that this comprehensive, robust, and scalable "
    "solution delves into the intricacies of modern software development. "
    "Moreover, the landscape has evolved significantly. Furthermore, it is "
    "important to understand that the beauty of this approach lies in its "
    "simplicity. When it comes to implementation, there are several key "
    "considerations. In terms of best practices, first and foremost, you "
    "should always leverage the power of automation."
)

_PLAIN_HUMAN = (
    "I went to the store yesterday. Bought some milk and bread. "
    "The weather was nice so I walked. Saw my neighbor on the way. "
    "We talked for a bit about the garden and the kids."
)


#: Below the measured 88.9%, so ordinary corpus growth does not fail the suite
#: while a threshold moved without measuring it does.
MIN_HELD_OUT_RECALL = 0.75


def _make_block(text: str, lang: str = "en") -> TextBlock:
    return TextBlock(block_id="test", page_url="test", dom_path="test",
                     text=text, language_hint=lang)


class TestEmbeddingDetector(unittest.TestCase):
    """Test the embedding detector."""

    def test_ai_text_scores_above_plain_human_prose(self):
        """The detector separates; it does not promise to clear the line.

        This used to assert that a cliche-stuffed passage is flagged, with a
        threshold hand-lowered to 0.55 to make it so. It is a weaker claim than
        it looks: measured on the held-out half, recall at the shipped 0.55 is
        88.9%, and this passage is one of the misses at 0.549. A single
        hand-written example is not a contract about recall - `scripts/
        calibrate.py --detector embedding --holdout` is - so what is asserted
        here is the thing that must never invert: model-shaped copy scores
        higher than a person writing plainly.
        """
        detector = EmbeddingDetector(threshold=0.0)
        model_score = detector.analyze_block(_make_block(_MODEL_SHAPED))[0].score
        human_score = detector.analyze_block(_make_block(_PLAIN_HUMAN))[0].score
        self.assertGreater(model_score, human_score)

    def test_human_text_not_flagged(self):
        """Normal human text should not be flagged."""
        block = _make_block(_PLAIN_HUMAN)
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


class TheReferenceIsHalfTheCorpus(unittest.TestCase):
    """What the detector is built from, and what it may be measured on.

    The score is a nearest-neighbour margin over the corpus, so the corpus is a
    component of this detector as much as it is the yardstick. Read whole, the
    detector is asked whether a text resembles a set containing that text and
    answers yes: scored that way it separated the corpus almost perfectly -
    model 0.73-0.79 against human near 0.16 - and all of it was self-recognition.
    """

    def test_the_reference_is_only_the_tune_half(self):
        detector = EmbeddingDetector()
        detector._load_corpus()
        self.assertTrue(all(is_reference(text) for text in detector._reference_texts))

    def test_held_out_entries_are_text_the_detector_has_not_seen(self):
        rows = [json.loads(line) for line in
                CORPUS.read_text(encoding="utf-8").splitlines() if line.strip()]
        tune, held_out = split(rows)
        self.assertTrue(tune and held_out, "both halves must be populated")
        seen = {row["text"] for row in tune}
        self.assertFalse(seen & {row["text"] for row in held_out})

    def test_the_shipped_threshold_is_the_measured_one(self):
        # 0.55 is where precision reaches 1.0 on the held-out half (recall
        # 88.9%, 0/187 false alarms). A default that drifts away from the
        # constant is a detector nobody measured.
        self.assertEqual(EmbeddingDetector().threshold, THRESHOLD)

    def test_the_threshold_still_measures_what_it_claims(self):
        """The number, not just the wiring.

        Asserting that the default equals the constant catches a drifting
        default and nothing else: set the constant to 0.60 and every other test
        here still passes. This is the one that fails, because it scores the
        held-out half - text the reference does not contain - and reads the two
        numbers the threshold was chosen for.

        The floors are below the measurement (100% precision, 88.9% recall) on
        purpose: this guards the claim, and `scripts/calibrate.py --detector
        embedding --holdout --sweep` reports the current figure.
        """
        detector = EmbeddingDetector(threshold=0.0)
        rows = [json.loads(line) for line in
                CORPUS.read_text(encoding="utf-8").splitlines() if line.strip()]
        _tune, held_out = split(rows)
        scored = []
        for index, row in enumerate(held_out):
            spans = detector.analyze_block(_make_block(
                row["text"], row.get("language") or "en"))
            scored.append((row["label"], max((s.score for s in spans), default=0.0)))

        crossed = [score for label, score in scored
                   if label == "human" and score >= THRESHOLD]
        self.assertEqual(crossed, [], "a human entry crossed the shipped line")

        models = [score for label, score in scored if label == "model"]
        found = [score for score in models if score >= THRESHOLD]
        self.assertGreaterEqual(len(found) / len(models), MIN_HELD_OUT_RECALL)


if __name__ == "__main__":
    unittest.main()
