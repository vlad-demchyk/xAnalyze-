"""Tests for abbreviation handling in sentence splitting."""
import unittest
from abbreviations import is_abbreviation, find_word_before_period
from detectors.heuristic import _sentences


class TestIsAbbreviation(unittest.TestCase):
    """Test abbreviation detection."""

    def test_english_abbreviations(self):
        """English abbreviations detected."""
        self.assertTrue(is_abbreviation("dr", "en"))
        self.assertTrue(is_abbreviation("mr", "en"))
        self.assertTrue(is_abbreviation("etc", "en"))
        self.assertTrue(is_abbreviation("eg", "en"))

    def test_italian_abbreviations(self):
        """Italian abbreviations detected."""
        self.assertTrue(is_abbreviation("dott", "it"))
        self.assertTrue(is_abbreviation("es", "it"))
        self.assertTrue(is_abbreviation("prof", "it"))

    def test_ukrainian_abbreviations(self):
        """Ukrainian abbreviations detected."""
        self.assertTrue(is_abbreviation("проф", "uk"))
        self.assertTrue(is_abbreviation("вул", "uk"))
        self.assertTrue(is_abbreviation("ін", "uk"))

    def test_not_abbreviation(self):
        """Normal words are not abbreviations."""
        self.assertFalse(is_abbreviation("hello", "en"))
        self.assertFalse(is_abbreviation("world", "en"))
        self.assertFalse(is_abbreviation("привіт", "uk"))

    def test_case_insensitive(self):
        """Abbreviation detection is case-insensitive."""
        self.assertTrue(is_abbreviation("Dr", "en"))
        self.assertTrue(is_abbreviation("DR", "en"))
        self.assertTrue(is_abbreviation("dr", "en"))


class TestFindWordBeforePeriod(unittest.TestCase):
    """Test word extraction before period."""

    def test_simple(self):
        """Simple word before period."""
        self.assertEqual(find_word_before_period("Dr. Smith", 2), "Dr")

    def test_no_word(self):
        """No word before period."""
        self.assertIsNone(find_word_before_period(". Smith", 0))

    def test_not_period(self):
        """Character at position is not a period."""
        self.assertIsNone(find_word_before_period("Dr. Smith", 0))


class TestSentenceSplitting(unittest.TestCase):
    """Test sentence splitting with abbreviations."""

    def test_abbreviation_not_split(self):
        """Abbreviations should not cause splits."""
        text = "Dr. Smith went to the store. He bought milk."
        sentences = _sentences(text, "en")
        # Should be 2 sentences, not 3
        self.assertEqual(len(sentences), 2)

    def test_italian_abbreviation(self):
        """Italian abbreviations should not cause splits."""
        text = "Il dott. Rossi è andato via. Ha comprato il latte."
        sentences = _sentences(text, "it")
        self.assertEqual(len(sentences), 2)

    def test_normal_split(self):
        """Normal sentences should be split."""
        text = "Hello world. How are you? I am fine."
        sentences = _sentences(text, "en")
        self.assertEqual(len(sentences), 3)

    def test_empty_text(self):
        """Empty text returns empty list."""
        self.assertEqual(_sentences("", "en"), [])

    def test_single_sentence(self):
        """Single sentence returns list with one item."""
        text = "Hello world."
        sentences = _sentences(text, "en")
        self.assertEqual(len(sentences), 1)


if __name__ == "__main__":
    unittest.main()
