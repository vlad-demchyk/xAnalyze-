"""The detector has to keep separating the two classes, not just run.

Every other test here asks whether a function returns what it says. These ask
whether the answer is any good, which is the question a heuristic detector
actually lives or dies by - and the one that stayed unasked while the thing
scored human and model text within 0.00 of each other.

The floors are deliberately below what the detector currently achieves. They are
a ratchet against regression, not a target: a change that drops held-out recall
from 71% to 20% is a change someone needs to look at, and a change that starts
flagging the documentation pool is worse than that.
"""
import unittest

from detectors.heuristic import combine_score
from scripts.calibrate import (_in_stratum, length_only_baseline, load,
                               score_rows, split)

#: What the corpus currently supports, rounded down hard.
MIN_HELD_OUT_RECALL = 0.4
#: How many human entries a language needs at paragraph length before its
#: false-alarm rate is a measurement rather than an accident of the corpus.
#: Italian sat at 2, English at 4, Ukrainian at 15 before dated encyclopedic
#: prose was added; all three are above this now.
MIN_PROSE_NEGATIVES = 20
#: Nothing in the human pool may be flagged. Precision is what decides whether
#: a tool stays switched on, so this one is not a ratchet but a rule.
MAX_FALSE_ALARMS = 0
THRESHOLD = 0.33


class Separation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scored = score_rows(load("labelled.jsonl"))
        if not cls.scored:
            raise unittest.SkipTest("no corpus")

    def test_no_human_text_is_flagged(self):
        flagged = [r for r in self.scored
                   if r["label"] == "human" and r["score"] >= THRESHOLD]
        self.assertLessEqual(len(flagged), MAX_FALSE_ALARMS,
                             f"flagged human text: {[r['text'][:60] for r in flagged]}")

    def test_held_out_recall_stays_useful(self):
        _train, test = split(self.scored)
        models = [r for r in test if r["label"] == "model"]
        found = [r for r in models if r["score"] >= THRESHOLD]
        self.assertGreaterEqual(len(found) / len(models), MIN_HELD_OUT_RECALL)

    def test_the_classes_do_not_overlap_at_the_median(self):
        # The failure this replaces: model median 0.22, human maximum 0.22.
        def median(label):
            values = sorted(r["score"] for r in self.scored if r["label"] == label)
            return values[len(values) // 2]

        self.assertGreater(median("model"), median("human"))

    def test_both_languages_are_detected_not_just_english(self):
        # Ukrainian recall was 8% while English was 42%: an average would have
        # called that a working detector.
        for language in ("en", "uk"):
            subset = [r for r in self.scored
                      if r["label"] == "model" and r["language"] == language]
            found = [r for r in subset if r["score"] >= THRESHOLD]
            self.assertGreaterEqual(len(found) / len(subset), MIN_HELD_OUT_RECALL,
                                    f"{language} recall is below the floor")


class LengthIsNotTheSignal(unittest.TestCase):
    """The corpus measures length as well as writing, so both are read.

    Its human half is still mostly interface strings and its model half is
    paragraphs, which means a recall figure over the whole corpus is partly a
    statement about how long the entries are. These check the three things that
    keep that visible: the detector has to beat what a word count alone scores,
    it has to keep working inside a band where length is held still, and the
    band has to hold enough human prose for "no false alarms" to mean anything.
    """

    @classmethod
    def setUpClass(cls):
        cls.scored = score_rows(load("labelled.jsonl"))
        if not cls.scored:
            raise unittest.SkipTest("no corpus")

    def test_the_detector_beats_a_classifier_that_knows_only_length(self):
        _cut, baseline, _recall = length_only_baseline(self.scored)
        flagged = [r for r in self.scored if r["score"] >= THRESHOLD]
        hits = [r for r in flagged if r["label"] == "model"]
        self.assertTrue(flagged, "nothing was flagged at all")
        self.assertGreater(len(hits) / len(flagged), baseline,
                           "the detector scores no better than the length does")

    def test_italian_is_found_at_sentence_length_not_only_at_paragraph_length(self):
        # Measured 2026-08-27: Italian recall was 0.0% in the 10-24 word band
        # and 83.3% at 25+ words, so the language was not weak everywhere - it
        # was weak wherever there was only one sentence to go on. The whole of
        # the 27.8% Italian figure came from that band.
        band = [r for r in self.scored
                if r["label"] == "model" and r["language"] == "it"
                and _in_stratum(r, 10, 25)]
        if not band:
            self.skipTest("no Italian entries of that length")
        found = [r for r in band if r["score"] >= THRESHOLD]
        self.assertGreaterEqual(len(found) / len(band), 0.4,
                                "Italian is back to scoring nothing below 25 words")

    def test_every_language_has_prose_negatives_not_only_interface_strings(self):
        # Measured 2026-08-31: the human half held 2 Italian, 4 English and 15
        # Ukrainian entries of 25+ words, so "precision 100%, 0 false alarms"
        # per language was a claim about button labels. It said nothing about
        # whether the detector flags a person writing a paragraph, which is
        # what it is pointed at. Closed with dated encyclopedic prose
        # (Wikipedia revisions from 2018), so this floor is a ratchet on the
        # corpus, not on the detector.
        for language in ("en", "it", "uk"):
            prose = [r for r in self.scored
                     if r["label"] == "human" and r["language"] == language
                     and _in_stratum(r, 25, None)]
            self.assertGreaterEqual(len(prose), MIN_PROSE_NEGATIVES,
                                    f"{language} false alarms are back to "
                                    "resting on interface strings")
            flagged = [r for r in prose if r["score"] >= THRESHOLD]
            self.assertEqual(flagged, [],
                             f"{language} prose is being flagged as model-written")


class TheCorpusIsAlsoADetectorComponent(unittest.TestCase):
    """Adding correct data to the corpus must not quietly weaken a detector.

    `EmbeddingDetector` scores by nearest-neighbour margin over
    `labelled.jsonl`, so every human entry added lowers the score of every
    passage. Measured 2026-08-31: 95 new human paragraphs moved the human
    side of the margin from 0.461 to 0.541 and took a plainly AI-written
    passage from 0.590 to 0.549, under the 0.55 the suite asks for. The
    corpus improved and the detector got worse, which is a coupling that has
    to be visible rather than discovered by a failing test months later.
    """

    def test_the_reference_set_is_named_not_inherited(self):
        from detectors.embedding import REFERENCE_REGISTERS_EXCLUDED
        self.assertIn("encyclopedic", REFERENCE_REGISTERS_EXCLUDED)

    def test_the_measuring_corpus_is_larger_than_the_reference_set(self):
        # If these ever coincide again, the coupling is back and the next
        # honest addition to the corpus silently costs recall.
        rows = load("labelled.jsonl")
        from detectors.embedding import REFERENCE_REGISTERS_EXCLUDED
        reference = [r for r in rows
                     if r.get("register") not in REFERENCE_REGISTERS_EXCLUDED]
        self.assertLess(len(reference), len(rows))


class Combination(unittest.TestCase):
    """Properties of the score itself, independent of any corpus."""

    def test_an_unmeasured_signal_is_not_a_floor(self):
        # Short human text must be able to score zero. It could not before:
        # three unmeasurable signals contributed a constant 0.3 each.
        self.assertEqual(combine_score(None, None, None, False, []), 0.0)

    def test_removing_evidence_always_lowers_the_score(self):
        many = ["in today's fast-paced world", "unlock the potential",
                "comprehensive", "robust", "seamless"]
        previous = combine_score(0.9, 0.9, 0.9, True, many)
        for cut in range(1, len(many) + 1):
            current = combine_score(0.9, 0.9, 0.9, True, many[cut:])
            self.assertLess(current, previous,
                            "a suppressed phrase must move the score")
            previous = current

    def test_a_phrase_counts_for_more_than_a_single_word(self):
        phrase = combine_score(None, None, None, False, ["comprehensive solution"])
        word = combine_score(None, None, None, False, ["comprehensive"])
        self.assertGreater(phrase, word)

    def test_the_score_stays_in_range(self):
        crowded = ["a phrase here"] * 30 + ["word"] * 30
        self.assertLessEqual(combine_score(1.0, 1.0, 1.0, True, crowded), 1.0)
        self.assertGreaterEqual(combine_score(0.0, 0.0, 0.0, False, []), 0.0)


if __name__ == "__main__":
    unittest.main()
