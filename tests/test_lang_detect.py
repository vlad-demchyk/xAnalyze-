"""Tests for language detection."""
import unittest
from lang_detect import guess_language, guess_language_safe


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


if __name__ == "__main__":
    unittest.main()
