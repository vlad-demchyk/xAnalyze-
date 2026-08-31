"""A run whose detector is the weak one for that page should say so.

Measured on the held-out half: the offline wording pass finds 36% of known
Italian AI passages where the embedding detector finds 100%. That number
lived in a calibration report nobody runs, so an Italian page got a third of
the available answer and looked like a finished scan.
"""
import unittest

import detector_advice
from models import TextBlock


def _blocks(language, count=8, words=10):
    return [TextBlock(block_id=str(i), page_url="https://example.it/",
                      dom_path="p", text=" ".join(["parola"] * words),
                      language_hint=language)
            for i in range(count)]


class ItSaysWhichDetectorSuitsThePage(unittest.TestCase):

    def test_italian_on_the_offline_pass_is_worth_saying(self):
        note = detector_advice.weak_language_note("offline", _blocks("it"))
        self.assertIsNotNone(note)
        self.assertIn("embedding", note)
        self.assertIn("36%", note)
        self.assertIn("100%", note)

    def test_english_is_left_alone(self):
        """The gap is real there too, but not the difference between an
        answer and no answer, and a warning on every English scan is noise."""
        self.assertIsNone(detector_advice.weak_language_note("offline", _blocks("en")))
        self.assertIsNone(detector_advice.weak_language_note("offline", _blocks("uk")))

    def test_the_detector_that_is_already_best_says_nothing(self):
        self.assertIsNone(detector_advice.weak_language_note("embedding", _blocks("it")))

    def test_an_unmeasured_detector_says_nothing(self):
        # A judge has no held-out number here, and inventing a comparison
        # would be the defect this whole file exists against.
        self.assertIsNone(detector_advice.weak_language_note("hybrid", _blocks("it")))
        self.assertIsNone(detector_advice.weak_language_note("claude-llm-judge", _blocks("it")))


class TheLanguageOfAPageIsReadFromWhatWasRead(unittest.TestCase):

    def test_blocks_too_short_to_read_do_not_vote(self):
        """`None` means "too short to tell". Counting those would let a
        navigation bar decide what language an article is in."""
        page = _blocks(None, 20) + _blocks("it", 6)
        self.assertEqual(detector_advice.dominant_language(page), "it")

    def test_a_menu_does_not_outvote_the_article(self):
        """The case that made this word-weighted. Measured on a live Italian
        site: 23 English blocks against 19 Italian ones, but 162 English
        words against 452 Italian - the English is a navigation bar and the
        Italian is what the page says."""
        menu = _blocks("en", count=23, words=7)
        article = _blocks("it", count=19, words=24)
        self.assertEqual(detector_advice.dominant_language(menu + article), "it")
        self.assertIsNotNone(
            detector_advice.weak_language_note("offline", menu + article))

    def test_a_page_with_no_dominant_language_gets_no_advice(self):
        mixed = _blocks("it", 4) + _blocks("en", 4) + _blocks("uk", 4)
        self.assertIsNone(detector_advice.dominant_language(mixed))
        self.assertIsNone(detector_advice.weak_language_note("offline", mixed))

    def test_too_little_readable_text_says_nothing(self):
        self.assertIsNone(detector_advice.dominant_language(
            _blocks("it", count=2, words=6)))

    def test_the_numbers_match_the_languages_the_corpus_has(self):
        for detector, table in detector_advice.HELD_OUT_RECALL.items():
            with self.subTest(detector):
                self.assertEqual(set(table), {"en", "it", "uk"})
                for value in table.values():
                    self.assertTrue(0.0 <= value <= 1.0)


if __name__ == "__main__":
    unittest.main()
