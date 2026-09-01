"""Which language a report is written in, and why.

Three steps, in order: what `--language` asked for, what the pages turned
out to be written in, and English. The third was missing.

`lang_detect` answers `other` for a page in a language this tool has no
lists for - German, French, Spanish, Polish, Russian - and that answer was
being used as the report language. A German site produced a report whose
language is `"other"`, for which no label table, no translation table and no
advice list has an entry. It read as English only because every lookup falls
back to English on a missing key: an accident standing in for a decision,
in the one place a reader judges the tool by.
"""
import unittest

from cli_impl.fullscan import REPORT_LANGUAGES, _detect_report_language


class _Block:
    def __init__(self, text, hint):
        self.text = text
        self.language_hint = hint


class _Page:
    def __init__(self, blocks):
        self.blocks = blocks


def _long(hint, count=4):
    return [_Block("A passage with enough words in it to be worth reading "
                   "and therefore worth a vote", hint) for _ in range(count)]


class WhatTheCallerAskedFor(unittest.TestCase):

    def test_each_supported_language_is_honoured(self):
        for language in REPORT_LANGUAGES:
            with self.subTest(language):
                self.assertEqual(
                    _detect_report_language(language, [_Page(_long("it"))]),
                    language)

    def test_a_language_the_report_does_not_exist_in_is_refused(self):
        said = []
        self.assertEqual(
            _detect_report_language("fr", [_Page(_long("it"))], said.append),
            "en")
        self.assertIn("not one of", said[0])


class WhatThePagesTurnedOutToBe(unittest.TestCase):

    def test_a_site_in_one_of_the_three_is_read_in_it(self):
        self.assertEqual(_detect_report_language(None, [_Page(_long("it"))]),
                         "it")

    def test_a_site_in_a_language_with_no_lists_falls_back_to_english(self):
        """`other` is a reading - "we know it is not one of ours" - and it is
        not a language a report can be written in."""
        self.assertEqual(_detect_report_language(None, [_Page(_long("other"))]),
                         "en")

    def test_the_supported_minority_wins_over_an_unreadable_majority(self):
        """Between a language the report exists in and one it does not, the
        one it exists in is the only real choice."""
        pages = [_Page(_long("other", 9) + _long("uk", 2))]
        self.assertEqual(_detect_report_language(None, pages), "uk")

    def test_nothing_readable_is_english(self):
        self.assertEqual(_detect_report_language(None, []), "en")
        self.assertEqual(_detect_report_language(None, [_Page([])]), "en")

    def test_the_choice_is_said_out_loud_with_its_count(self):
        said = []
        _detect_report_language(None, [_Page(_long("uk", 3))], said.append)
        self.assertIn("language uk", said[0])
        self.assertIn("3 of 3", said[0])


if __name__ == "__main__":
    unittest.main()
