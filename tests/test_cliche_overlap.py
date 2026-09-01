"""One phrase in the copy is one piece of evidence.

The lists hold both `seamless` and `seamless experience`, both
`a testament to` and `testament`, both `розкрийте повний потенціал` and the
`повний потенціал` inside it - fourteen such pairs in English alone. A
passage containing the longer one matched both entries, and `combine_score`
charged for both: 0.30 for a phrase plus 0.10 for its own fragment. The
report then listed two clichés where the reader can see one.

Measured 2026-09-01 on a live tourism site: five passages matched
`a testament to` **and** `testament`, scoring 0.57 where the single phrase
they contain is worth 0.46.
"""
import unittest

from detectors.heuristic import _cliche_hits, combine_score


class OverlappingEntries(unittest.TestCase):

    def test_the_fragment_of_a_matched_phrase_is_not_a_second_hit(self):
        hits = _cliche_hits(
            "The bastions are a testament to military engineering", "en")
        self.assertEqual(hits, ["a testament to"])

    def test_the_same_word_elsewhere_is_a_second_occurrence(self):
        """Only the *span* is collapsed. A fragment that also appears on its
        own is a real second match and stays."""
        hits = _cliche_hits(
            "A seamless experience. Everything else is seamless too, and "
            "the onboarding is seamless.", "en")
        self.assertIn("seamless experience", hits)

    def test_two_different_phrases_are_still_two(self):
        hits = _cliche_hits(
            "Delve into a seamless experience and unlock the potential", "en")
        self.assertGreaterEqual(len(hits), 2)

    def test_the_score_no_longer_counts_one_phrase_twice(self):
        one = combine_score(uniformity=0.79, repetition=0.0, dashes=0.0,
                            structural=False, cliches=["a testament to"])
        both = combine_score(uniformity=0.79, repetition=0.0, dashes=0.0,
                             structural=False,
                             cliches=["a testament to", "testament"])
        self.assertLess(one, both)
        hits = _cliche_hits("This is a testament to the work", "en")
        self.assertEqual(
            combine_score(uniformity=0.79, repetition=0.0, dashes=0.0,
                          structural=False, cliches=hits), one)


if __name__ == "__main__":
    unittest.main()
