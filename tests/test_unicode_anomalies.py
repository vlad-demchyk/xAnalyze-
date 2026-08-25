"""Tests for the unicode anomalies detector."""
import unittest

from detectors.unicode_anomalies import UnicodeAnomalyDetector
from unicode_rules import CAT_HOMOGLYPH, find_anomalies
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


class ALoneLetterInBilingualText(unittest.TestCase):
    """The rule that called ordinary Ukrainian a forgery.

    A homoglyph attack is one stray letter: everything in "The password is
    not correct о" is Latin, and the lone Cyrillic `о` has no honest reason
    to be there. Technical Ukrainian is routinely two scripts at once -
    "Подивитись privacy і data retention деталі" is a sentence somebody
    wrote, and `і` is the word "and".

    The rule compared character counts, so Latin came out the majority there
    and it reported the Ukrainian conjunction as a forged Latin `i` - at
    0.95, the highest confidence this tool has, about text a person typed.
    Measured over 1106 strings of real product copy, that rule produced
    *every* high-confidence finding in the corpus: four of four, all false,
    and all of them Ukrainian.

    What separates the two cases is not which script has more characters. It
    is whether the minority script appears anywhere else in a real word. In
    an attack it does not. In a bilingual sentence it does.
    """

    def homoglyphs(self, text: str) -> list:
        return [a for a in find_anomalies(text) if a.category == CAT_HOMOGLYPH]

    def test_a_stray_cyrillic_letter_in_english_is_still_caught(self):
        """The reason the rule exists, and it has to keep working."""
        self.assertTrue(self.homoglyphs("The password is not correct о"))
        self.assertTrue(self.homoglyphs("Enter your name а here"))

    def test_a_swapped_letter_inside_a_word_is_still_caught(self):
        """A different branch, untouched, and the strongest signal there is."""
        found = self.homoglyphs("Please log in to your аccount today")
        self.assertTrue(found)
        self.assertEqual(found[0].original, "а")

    def test_the_ukrainian_word_for_and_is_not_a_forgery(self):
        self.assertEqual(
            self.homoglyphs("Подивитись privacy і data retention деталі"), [])

    def test_a_model_name_among_ukrainian_words_is_not_a_forgery(self):
        """`M1` is a chip, and Latin is all over that sentence anyway."""
        self.assertEqual(self.homoglyphs(
            "Лише Apple Silicon (M1 або новіший). Збірки під Intel поки немає."),
            [])

    def test_other_one_letter_ukrainian_words_are_safe_too(self):
        for text in ("Зберігати у cloud storage чи локально",
                     "Це я, а не bot",
                     "Файл з backup лежить поруч"):
            with self.subTest(text=text):
                self.assertEqual(self.homoglyphs(text), [])

    def test_it_is_the_company_of_the_letter_that_decides(self):
        """The same lone Cyrillic `о`: suspicious alone among Latin words,
        ordinary when other Cyrillic words are there with it."""
        self.assertTrue(self.homoglyphs("Set the password о now"))
        self.assertEqual(self.homoglyphs("Постав пароль о зараз please"), [])
