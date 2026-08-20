"""Abbreviation lists for sentence splitting.

The sentence splitter must not cut on periods that follow abbreviations,
because "es." in Italian or "Dr." in English are not sentence boundaries.
This module provides per-language abbreviation sets and a helper that
checks whether a word before a period is one of them.

Why a separate module: the list is shared between the heuristic detector's
sentence splitter and any future tokenizer that needs the same knowledge.
Keeping it in one place means adding an abbreviation never requires
hunting through detector code.
"""
from __future__ import annotations

import re

# Common abbreviations per language that end with a period and should NOT
# be treated as sentence boundaries. Case-insensitive matching.
#
# English: titles, business, academic, common Latin
ENGLISH_ABBREVIATIONS = frozenset({
    # Titles
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr",
    # Business
    "inc", "ltd", "corp", "co", "dept", "est", "div",
    # Academic
    "ed", "vol", "fig", "ref", "no", "nr", "pp", "ch",
    # Common Latin
    "etc", "eg", "ie", "vs", "viz", "al",
    # Time
    "am", "pm",
    # Geographic / Country abbreviations
    "us", "uk", "eu", "un",
    # Misc
    "approx", "avg", "min", "max", "temp", "qty",
    # Single letters used as abbreviations (A. B. C.)
    "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
    "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
})

# Italian: titles, business, common
ITALIAN_ABBREVIATIONS = frozenset({
    # Titles
    "dott", "dottssa", "prof", "profssa", "avv", "ing", "arch",
    "sig", "sigg", "sogg", "gent",
    # Business
    "soc", "srl", "spa", "snc", "sas",
    # Common
    "ecc", "pag", "vol", "fig", "n", "nr", "tel", "fax",
    "es",  # esempio (example)
    # Geographic
    "loc", "prov", "reg", "circ",
    # Time
    "sec", "min",
})

# Ukrainian: titles, geographic, common
UKRAINIAN_ABBREVIATIONS = frozenset({
    # Titles
    "проф", "док", "канд", "акад", "доц",
    # Geographic
    "вул", "бул", "просп", "обл", "р-н", "м",
    # Common
    "ін", "тобто", "напр", "тощо", "і т д", "і т п",
    # Academic
    "ст", "стор", "табл", "рис", "мал",
    # Time
    "хв", "сек", "р",
})

# Latin abbreviations used across languages
LATIN_ABBREVIATIONS = frozenset({
    "etc", "eg", "ie", "vs", "viz", "al", "cf", "ibid", "idem",
    "op cit", "loc cit", "et al", "ad hoc", "de facto", "de jure",
})

_ABBREVIATIONS_BY_LANGUAGE: dict[str, frozenset[str]] = {
    "en": ENGLISH_ABBREVIATIONS | LATIN_ABBREVIATIONS,
    "it": ITALIAN_ABBREVIATIONS | LATIN_ABBREVIATIONS,
    "uk": UKRAINIAN_ABBREVIATIONS | LATIN_ABBREVIATIONS,
}

# All abbreviations combined, for when language is unknown
_ALL_ABBREVIATIONS: frozenset[str] = frozenset(
    abbr for lang_set in _ABBREVIATIONS_BY_LANGUAGE.values()
    for abbr in lang_set
)

# Pattern to extract the word immediately before a period
_WORD_BEFORE_PERIOD_RE = re.compile(r"(\b\w+)\.$")


def is_abbreviation(word: str, language: str | None = None) -> bool:
    """Check if `word` (without trailing period) is a known abbreviation.

    Args:
        word: The word to check, WITHOUT the trailing period.
              "Dr" not "Dr."
        language: Optional language code. If None, checks all languages.

    Returns:
        True if the word is a known abbreviation.
    """
    normalized = word.lower().strip()
    if not normalized:
        return False

    if language and language in _ABBREVIATIONS_BY_LANGUAGE:
        return normalized in _ABBREVIATIONS_BY_LANGUAGE[language]

    return normalized in _ALL_ABBREVIATIONS


def find_word_before_period(text: str, period_pos: int) -> str | None:
    """Extract the word immediately before a period at `period_pos`.

    Args:
        text: The full text.
        period_pos: The index of the period character.

    Returns:
        The word without the period, or None if no word found.
    """
    if period_pos <= 0 or period_pos >= len(text):
        return None
    if text[period_pos] != '.':
        return None

    # Look backwards from the period
    end = period_pos
    start = end - 1
    while start >= 0 and (text[start].isalnum() or text[start] in "'-"):
        start -= 1
    start += 1

    if start == end:
        return None
    return text[start:end]
