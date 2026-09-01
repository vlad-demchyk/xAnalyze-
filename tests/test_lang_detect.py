"""Tests for language detection."""
import unittest

from lang_detect import UNSUPPORTED, guess_language, guess_language_safe


class TestGuessLanguage(unittest.TestCase):
    """Test language detection."""

    def test_english(self):
        """English text detected."""
        self.assertEqual(guess_language("The quick brown fox jumps over the lazy dog."), "en")

    def test_ukrainian(self):
        """Ukrainian text detected."""
        self.assertEqual(guess_language("Привіт, як справи? Це тестовий текст."), "uk")

    def test_italian(self):
        """Italian text detected."""
        self.assertEqual(guess_language("Città è molto bella. Perché no? È importante."), "it")

    def test_short_text_defaults_english(self):
        """Short text defaults to English."""
        self.assertEqual(guess_language("Hello"), "en")

    def test_empty_text(self):
        """Empty text defaults to English."""
        self.assertEqual(guess_language(""), "en")


class TestGuessLanguageSafe(unittest.TestCase):
    """Test safe language detection (returns None for short text)."""

    def test_short_text_returns_none(self):
        """Short text returns None."""
        self.assertIsNone(guess_language_safe("Hello"))
        self.assertIsNone(guess_language_safe("OK"))
        self.assertIsNone(guess_language_safe("Save"))

    def test_ukrainian_short_returns_none(self):
        """Short Ukrainian text returns None for very short text."""
        # "Привіт" has Cyrillic letters, so it returns 'uk' (Cyrillic detection works)
        # But "OK" or "Save" returns None
        self.assertIsNone(guess_language_safe("OK"))
        self.assertIsNone(guess_language_safe("Save"))

    def test_english_long(self):
        """Long English text returns 'en'."""
        self.assertEqual(guess_language_safe("The quick brown fox jumps over the lazy dog."), "en")

    def test_ukrainian_long(self):
        """Long Ukrainian text returns 'uk'."""
        self.assertEqual(guess_language_safe("Привіт, як справи? Це тестовий текст для перевірки."), "uk")

    def test_italian_long(self):
        """Long Italian text returns 'it'."""
        self.assertEqual(guess_language_safe("Città è molto bella. Perché no? È importante sottolineare."), "it")


class LanguagesThisToolDoesNotHave(unittest.TestCase):
    """A language with no lists must be said, not guessed at.

    Measured 2026-08-31 on 214 paragraphs from dated Wikipedia revisions in
    five languages this app has no lists for: every one of them came back as
    `uk`, `it` or `en`. Russian was called Ukrainian 42 times out of 42, and
    Spanish was called Italian in 13 of 48. The score never crossed the
    threshold - the statistical-only clamp held it at 0.32 - so this was not
    a false alarm. It was a wrong label, and the label is what picks the
    cliché list, what exempts a guillemet, and what the rewrite provider is
    told to answer in.
    """

    RUSSIAN = ("Всемирная паутина — это распределённая система, "
               "предоставляющая доступ к связанным документам.")
    UKRAINIAN = ("Всесвітня павутина це розподілена система, яка надає "
                 "доступ до пов'язаних між собою документів у мережі.")
    SPANISH = ("El software libre es el software que respeta la libertad de "
               "los usuarios para ejecutarlo, copiarlo y mejorarlo.")
    FRENCH = ("Les logiciels libres sont des programmes qui peuvent être "
              "utilisés dans une organisation pour tout usage.")
    GERMAN = ("Der Browser ist das Programm und die Oberfläche ist mit den "
              "Geräten und der Steuerung verbunden.")
    POLISH = ("Wolne oprogramowanie nie jest tym samym co oprogramowanie, "
              "które jest udostępniane przez producenta jako darmowe.")

    def test_russian_is_not_ukrainian(self):
        self.assertEqual(guess_language(self.RUSSIAN), UNSUPPORTED)

    def test_ukrainian_is_still_ukrainian(self):
        self.assertEqual(guess_language(self.UKRAINIAN), "uk")

    # `P-34`: a paragraph written entirely in letters both languages share.
    # The letter counts come out 0-0, and `>` used to hand that to Ukrainian.
    RUSSIAN_WITHOUT_UNIQUE_LETTERS = (
        "Маркетинг — вид человеческой деятельности, направленной на "
        "удовлетворение нужд и потребностей посредством обмена.")
    UKRAINIAN_WITHOUT_UNIQUE_LETTERS = (
        "Ця сторінка розповідає, як тексти для реклами пишуть на замовлення "
        "та чому вони так схожі один на одного.")

    def test_a_zero_zero_tie_is_read_by_words_not_by_the_left_operand(self):
        self.assertEqual(
            guess_language(self.RUSSIAN_WITHOUT_UNIQUE_LETTERS), UNSUPPORTED)
        self.assertEqual(
            guess_language(self.UKRAINIAN_WITHOUT_UNIQUE_LETTERS), "uk")

    def test_a_short_ukrainian_string_with_no_evidence_stays_ukrainian(self):
        # 11 of 185 Ukrainian corpus entries carry no unique letter either,
        # and most are short interface strings. Inverting the comparison
        # instead of asking the words would have cost every one of them.
        for text in ("Вибрати все", "Переглянути все", "Вийти з повного екрану",
                     "Прибрати з улюблених"):
            with self.subTest(text):
                self.assertEqual(guess_language(text), "uk")

    def test_latin_languages_without_lists_are_named_as_such(self):
        for name, text in (("spanish", self.SPANISH), ("french", self.FRENCH),
                           ("german", self.GERMAN), ("polish", self.POLISH)):
            with self.subTest(name):
                self.assertEqual(guess_language(text), UNSUPPORTED)

    def test_italian_is_not_swept_up_with_them(self):
        # These are real corpus entries. An earlier marker list included
        # `del`, `una`, `se`, `su` and `le`, which are ordinary Italian, and
        # it pulled 13 Italian entries out of the corpus with it.
        for text in (
            "Unisci i file nell'ordine di caricamento e ricevi una sola sintesi condivisa.",
            "Riduci il peso del file senza perdite di qualità visibili.",
            "Aggiungi un documento del candidato. La valutazione parte sempre da un file caricato.",
        ):
            with self.subTest(text[:30]):
                self.assertNotEqual(guess_language(text), UNSUPPORTED)

    def test_english_is_not_swept_up_with_them(self):
        for text in (
            "The quick brown fox jumps over the lazy dog and then does it again.",
            "Upload a document and the report will tell you which lines were flagged.",
        ):
            with self.subTest(text[:30]):
                self.assertEqual(guess_language(text), "en")

    def test_a_short_string_is_still_unknown_not_foreign(self):
        # None means "too short to tell" and makes callers check every list.
        # UNSUPPORTED means the opposite. They must not collapse into one.
        self.assertIsNone(guess_language_safe("Save"))


class WhatTheLabelDecides(unittest.TestCase):
    """The four places an unsupported language must not leak into."""

    def test_unknown_language_keeps_its_own_punctuation(self):
        from unicode_rules import find_anomalies
        text = "Всемирная паутина — это система, «страницы» которой связаны."
        self.assertEqual(find_anomalies(text, UNSUPPORTED), [])
        # The point of the exemption: called English, the same text reports.
        self.assertTrue(find_anomalies(text, "en"))

    def test_no_language_is_named_to_the_model(self):
        from llm.base import prompt_language
        self.assertIsNone(prompt_language(UNSUPPORTED))
        self.assertEqual(prompt_language("uk"), "uk")
        self.assertIsNone(prompt_language(None))

    def test_a_calibrated_detector_says_nothing(self):
        # The fourth place, and the one that had nothing reading the label:
        # `supported_languages` was declared on eleven classes and read by no
        # line of code, so the wording pass scored German with English lists.
        from models import TextBlock
        from detectors.heuristic import HeuristicDetector

        german = ("Webbrowser sind spezielle Computerprogramme zur Darstellung "
                  "von Webseiten im World Wide Web oder allgemein von Dokumenten "
                  "und Daten, und sie stellen die Benutzeroberfläche dar.")
        block = TextBlock(block_id="b", page_url="u", dom_path="p", text=german)
        self.assertEqual(HeuristicDetector().analyze_block(block), [])

        # Silence for a language it has no lists for, not silence in general.
        english = TextBlock(block_id="b", page_url="u", dom_path="p",
                            text=("Upload a document and the report will tell "
                                  "you which of the lines were flagged here."))
        self.assertTrue(HeuristicDetector().analyze_block(english))


class SupportedLanguagesIsRead(unittest.TestCase):
    """The field means one thing, and every detector answers for itself.

    It used to be a copied `("uk", "it", "en")` on all eleven classes with no
    reader, which is a declaration that cannot be wrong and cannot be useful.
    """

    def _detector_classes(self):
        import detectors  # noqa: F401 - registers every backend
        from detectors.base import Detector

        def walk(cls):
            for sub in cls.__subclasses__():
                yield sub
                yield from walk(sub)

        return list(walk(Detector))

    def test_every_declared_language_is_one_the_corpus_has(self):
        for cls in self._detector_classes():
            if cls.supported_languages is None:
                continue
            with self.subTest(cls.name):
                self.assertTrue(set(cls.supported_languages) <= {"uk", "it", "en"})

    def test_an_undeclared_detector_answers_for_every_language(self):
        from detectors.base import Detector
        self.assertTrue(Detector.supports_language(UNSUPPORTED))
        self.assertTrue(Detector.supports_language("pl"))

    def test_too_short_to_tell_is_not_a_refusal(self):
        # None means "check every list", which is the opposite of UNSUPPORTED
        # and must not be collapsed into it by the gate.
        from detectors.heuristic import HeuristicDetector
        self.assertTrue(HeuristicDetector.supports_language(None))
        self.assertFalse(HeuristicDetector.supports_language(UNSUPPORTED))
        self.assertTrue(HeuristicDetector.supports_language("it"))


if __name__ == "__main__":
    unittest.main()
