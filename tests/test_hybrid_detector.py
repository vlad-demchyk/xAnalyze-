"""The hybrid detector's merge, which is where its behaviour lives.

The two halves are already tested on their own (`test_detection.py` for the
offline engine, `test_scan_provider.py` for the judges), so nothing here
calls a model: the judge is a stub that returns exactly the spans a test
needs, which is the only way to assert on agreement and disagreement without
paying for a run whose answer would change between runs anyway.
"""
import unittest

from detectors.base import Detector, DetectorUnavailable
from detectors.factory import DetectorFactory
from detectors.hybrid import (
    AGREE_BOTH, AGREE_MODEL_ONLY, AGREE_OFFLINE_ONLY, HybridDetector,
)
from models import Confidence, TextBlock, TextSpan

#: Two real corpus entries (`corpus/labelled.jsonl`), not invented strings:
#: the offline engine's thresholds were calibrated on that corpus, so a
#: sentence written here to "look generated" would only prove that a test
#: author can guess the current weights. FLAGGED_TEXT is a labelled model
#: entry the offline pass scores above the reporting threshold; QUIET_TEXT is
#: a labelled human entry it scores at zero.
FLAGGED_TEXT = (
    "Незалежно від того, чи ви фрилансер, чи частина великої компанії, "
    "наш інтуїтивний інтерфейс дозволяє почати роботу за кілька хвилин."
)
QUIET_TEXT = (
    "Timeouts are not a nice-to-have. Without one, a hung server will hang "
    "your program too, for as long as it likes."
)


class StubJudge(Detector):
    """A judge whose answer the test writes."""

    name = "stub-judge"
    display_name = "Stub judge"

    def __init__(self, spans=None, unavailable: bool = False, **config):
        super().__init__(**config)
        self._spans = spans or []
        self._unavailable = unavailable

    def analyze_block(self, block):
        return list(self._spans)

    def analyze_blocks(self, blocks):
        if self._unavailable:
            raise DetectorUnavailable("no account")
        return list(self._spans)


DetectorFactory.register(StubJudge.name, StubJudge)


def block(text: str = FLAGGED_TEXT, block_id: str = "b1") -> TextBlock:
    return TextBlock(block_id=block_id, page_url="https://example.com",
                     dom_path="p", text=text, language_hint="uk")


def model_span(one_block, start=0, end=None, score=0.8, reason="reads as generated"):
    return TextSpan(
        block_id=one_block.block_id,
        start=start,
        end=len(one_block.text) if end is None else end,
        score=score,
        confidence=Confidence.HIGH,
        detector_name="stub-judge",
        explanation=reason,
        details={"source": "model", "model": "stub"},
    )


def hybrid(spans=None, unavailable=False, categories=()):
    return HybridDetector(judge_name=StubJudge.name,
                          judge_config={"spans": spans or [],
                                        "unavailable": unavailable},
                          categories=categories)


class Merging(unittest.TestCase):
    def test_a_passage_both_engines_flag_is_one_finding(self):
        one = block()
        detector = hybrid([model_span(one)])
        spans = detector.analyze_blocks([one])

        self.assertEqual(len(spans), 1, spans)
        merged = spans[0]
        self.assertEqual(merged.details["agreement"], AGREE_BOTH)
        # Both records survive: the model's prose and the offline signals.
        self.assertTrue(merged.explanation)
        self.assertIn("offline", merged.details)
        self.assertIn("offline_score", merged.details)

    def test_agreement_takes_the_higher_score_and_invents_nothing(self):
        one = block()
        detector = hybrid([model_span(one, score=0.62)])
        merged = detector.analyze_blocks([one])[0]

        offline_score = merged.details["offline_score"]
        self.assertEqual(merged.score, max(0.62, offline_score))
        self.assertLessEqual(merged.score, 1.0)

    def test_what_only_the_model_saw_is_kept_and_labelled(self):
        # A human corpus entry: nothing for the offline pass to report.
        one = block(QUIET_TEXT)
        detector = hybrid([model_span(one)])
        spans = detector.analyze_blocks([one])

        # The offline pass still returns its zero-scored span for the block
        # (every caller drops those on confidence); what matters is that it
        # was not counted as a confirmation.
        labelled = [s.details["agreement"] for s in spans if "agreement" in s.details]
        self.assertEqual(labelled, [AGREE_MODEL_ONLY])

    def test_what_only_the_offline_pass_saw_is_not_dropped(self):
        one = block()
        detector = hybrid([])  # the model quoted nothing
        spans = detector.analyze_blocks([one])

        self.assertTrue(spans, "an unconfirmed offline finding must survive")
        self.assertEqual({s.details["agreement"] for s in spans}, {AGREE_OFFLINE_ONLY})

    def test_a_block_the_model_could_not_read_does_not_swallow_the_block(self):
        """An error span covers the whole block by construction. Letting it
        match would hide every offline finding in that block behind it."""
        one = block()
        error = model_span(one, reason="detector error: boom")
        error.details = {"source": "model", "error": "boom"}
        detector = hybrid([error])
        spans = detector.analyze_blocks([one])

        self.assertTrue(any(s.details.get("error") for s in spans))
        self.assertTrue(any(s.details.get("agreement") == AGREE_OFFLINE_ONLY
                            for s in spans),
                        "the offline finding was absorbed by a failure notice")

    def test_character_findings_pass_through_untouched(self):
        # A zero-width space is an exact defect, not a matter of opinion.
        one = block("Текст із​прихованим символом усередині речення.")
        detector = hybrid([], categories=("invisible",))
        spans = detector.analyze_blocks([one])

        characters = [s for s in spans if s.details.get("source") == "characters"]
        self.assertTrue(characters)
        for span in characters:
            self.assertNotIn("agreement", span.details)

    def test_an_unusable_account_is_reported_not_papered_over(self):
        """The whole point of the option: a hybrid run that could not reach
        the model must not return the offline half and look successful."""
        detector = hybrid(unavailable=True)
        with self.assertRaises(DetectorUnavailable):
            detector.analyze_blocks([block()])

    def test_findings_follow_the_document_order(self):
        first, second = block(block_id="b1"), block(block_id="b2")
        detector = hybrid([])
        spans = detector.analyze_blocks([first, second])
        self.assertEqual([s.block_id for s in spans][:1], ["b1"])

    def test_the_character_pass_is_declared_as_included(self):
        """`ui/worker.run_unicode_pass` asks the class this, so that a hybrid
        run does not report every character defect twice."""
        self.assertTrue(DetectorFactory.lookup("hybrid").includes_character_pass)


if __name__ == "__main__":
    unittest.main()
