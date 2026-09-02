"""The defects the 2026-09-02 review found, each with the case that shows it.

Four findings, all of which the suite was green through. They are kept
together because they share a shape rather than a module: every one is a rule
or a table that *looks* right when read and produces the wrong answer when
run, which is the only kind of defect a green suite can hide.

Each test below fails if the fix is reverted - verified by reverting it.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import offline_suggestions  # noqa: E402
from audit import engine  # noqa: E402


def _page(body: str, lang: str = "uk") -> str:
    return (f'<!DOCTYPE html><html lang="{lang}"><head><meta charset="utf-8">'
            f'<title>T</title></head><body><h1>H</h1>{body}</body></html>')


def _fired(body: str, rule: str, lang: str = "uk") -> bool:
    result = engine.analyze_document(_page(body, lang), "t.html")
    return any(issue.rule_id == rule for issue in result.issues)


class HreflangNeedsALanguageAndNotAWord(unittest.TestCase):
    """`"/en" in href` is true of `/enterprise`.

    A one-language site with an "Enterprise" link in its menu was told to
    add hreflang alternates. The rule now asks for a path *segment* that is a
    language code, or a link that names a language in its own text.
    """

    def test_a_word_that_starts_with_a_language_code_is_not_a_switcher(self):
        for href in ("/enterprise", "/energy", "/end-of-life", "/italy",
                     "/deutschland-news", "/esports"):
            with self.subTest(href=href):
                self.assertFalse(
                    _fired(f'<a href="{href}">Link</a>', "hreflang-links"),
                    f"{href} was read as a language switcher")

    def test_a_language_segment_still_is_one(self):
        for href in ("/en/pricing", "/pricing/en", "/en",
                     "https://example.com/it/chi-siamo"):
            with self.subTest(href=href):
                self.assertTrue(
                    _fired(f'<a href="{href}">Link</a>', "hreflang-links"),
                    f"{href} is a language switcher and was missed")

    def test_a_switcher_that_says_so_in_words_is_found(self):
        """The half the discarded `text` variable was meant for.

        A `?lang=` or flag-icon switcher says nothing in its href; what it
        does say is the language's own name.
        """
        for label in ("English", "Українська", "Italiano", "EN"):
            with self.subTest(label=label):
                self.assertTrue(
                    _fired(f'<a href="/switch">{label}</a>',
                           "hreflang-links"),
                    f"a link reading {label!r} is a switcher")


class ThePhraseTableIsAppliedLongestFirst(unittest.TestCase):
    """A shorter phrase inside a longer one used to consume it.

    `suggest` applies every pattern in turn, so ordering decides the answer.
    In dictionary order two entries could never fire, and both left the text
    worse than they found it rather than merely unchanged.
    """

    def test_a_ukrainian_opener_is_removed_whole(self):
        self.assertEqual(
            offline_suggestions.suggest(
                "Підсумовуючи вищесказане, це найкращий вибір.", "uk"),
            "Це найкращий вибір.")

    def test_an_italian_phrase_keeps_the_noun_it_qualifies(self):
        self.assertEqual(
            offline_suggestions.suggest(
                "Una soluzione all'avanguardia per il team.", "it"),
            "Una soluzione per il team.")

    def test_no_entry_in_any_table_is_unreachable(self):
        """The property, not the two instances of it.

        A future edit that adds a long phrase after a short one it contains
        fails here rather than in somebody's report.
        """
        for lang in offline_suggestions.PHRASE_SUGGESTIONS:
            compiled = offline_suggestions._COMPILED[lang]
            order = {phrase: i for i, (phrase, _, _) in enumerate(compiled)}
            for long in order:
                for short in order:
                    if short != long and short in long:
                        self.assertLess(
                            order[long], order[short],
                            f"[{lang}] {long!r} can never fire: {short!r} "
                            f"is applied first")


class OneKeyOneValue(unittest.TestCase):
    """A dict literal with the same key twice keeps the last one silently."""

    def test_the_italian_table_has_one_entry_per_phrase(self):
        """`all'avanguardia` was in the table twice.

        The second row mapped it to `""` - delete the word - which beat the
        first row's real replacement, so the advice Italian readers got was
        the one nobody chose.
        """
        self.assertEqual(
            offline_suggestions.PHRASE_SUGGESTIONS["it"]["all'avanguardia"],
            "aggiornato")

    def test_no_table_repeats_a_key(self):
        """Read from the source, because the dict itself cannot show this.

        By the time the literal is a `dict` the duplicate is gone - that is
        what makes the defect invisible - so the check is on the parse tree.
        """
        import ast

        tree = ast.parse((ROOT / "offline_suggestions.py")
                         .read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            keys = [k.value for k in node.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)]
            self.assertEqual(
                len(keys), len(set(keys)),
                f"duplicate key in the dict at line {node.lineno}: "
                f"{[k for k in keys if keys.count(k) > 1]}")


if __name__ == "__main__":
    unittest.main()
