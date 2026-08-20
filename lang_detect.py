"""Cheap language guess shared by the extractors and the detectors.

Lives at top level rather than inside detectors/ so the crawler and the
repo scanner can tag each extracted block with a language without
importing a detector — the tag then flows through to the rewrite provider,
which needs it to answer in the right language.
"""
from __future__ import annotations

import re

_CYRILLIC_RE = re.compile(r"[А-Яа-яЇїІіЄєҐґ]")

# Function words that are common in Italian and rare/absent in English.
_ITALIAN_MARKERS = (
    " è ", " non ", " che ", " della ", " gli ", " sono ", " perché ",
    " degli ", " nella ", " questo ", " anche ", " più ", " con ", " per ",
)


# Minimum word count for language detection to be meaningful. Below this,
# the guess is too noisy to be useful: a short UI string like "OK" or
# "Save" contains no marker words, and treating it as English would
# suppress the Italian or Ukrainian cliché lists that might actually match.
_MIN_WORDS_FOR_DETECTION = 5


def guess_language(text: str) -> str:
    """Return 'uk', 'it' or 'en'.

    Cyrillic is decided by *share* of the letters, not by presence of a
    single one. That matters more than it looks: a lone Cyrillic character
    hidden inside an English word is exactly the homoglyph defect this app
    hunts for, and treating that one character as proof of Ukrainian would
    flip the whole block's language — which in turn suppressed the
    language-specific checks for the rest of the block.
    """
    result = guess_language_safe(text)
    return result if result is not None else "en"


def guess_language_safe(text: str) -> str | None:
    """Return 'uk', 'it' or 'en', or None when the text is too short to tell.

    None rather than a default language: a short string like "Save" or
    "Копіювати" contains no Italian markers and no Cyrillic at all, but
    treating it as English would silently suppress the Italian and Ukrainian
    cliché lists. Returning None tells the caller to check all lists.

    Cyrillic is decided by *share* of the letters, not by presence of a
    single one. That matters more than it looks: a lone Cyrillic character
    hidden inside an English word is exactly the homoglyph defect this app
    hunts for, and treating that one character as proof of Ukrainian would
    flip the whole block's language — which in turn suppressed the
    language-specific checks for the rest of the block.
    """
    letters = [c for c in text if c.isalpha()]
    word_count = len(text.split())

    # Cyrillic detection: needs enough letters for the share to be meaningful
    if letters:
        cyrillic = sum(1 for c in letters if _CYRILLIC_RE.match(c))
        if cyrillic / len(letters) >= 0.30:
            return "uk"

    # For Italian and English: need enough words for marker detection to work
    if word_count < _MIN_WORDS_FOR_DETECTION:
        return None

    padded = f" {text.lower()} "
    if any(m in padded for m in _ITALIAN_MARKERS):
        return "it"
    return "en"
