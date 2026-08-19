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
from scripts.calibrate import load, score_rows, split

#: What the corpus currently supports, rounded down hard.
MIN_HELD_OUT_RECALL = 0.5
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
