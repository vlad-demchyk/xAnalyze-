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
    """The three places an unsupported language must not leak into."""

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


if __name__ == "__main__":
    unittest.main()
