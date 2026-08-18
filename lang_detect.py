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


def guess_language(text: str) -> str:
    """Return 'uk', 'it' or 'en'.

    Cyrillic is decided by *share* of the letters, not by presence of a
    single one. That matters more than it looks: a lone Cyrillic character
    hidden inside an English word is exactly the homoglyph defect this app
    hunts for, and treating that one character as proof of Ukrainian would
    flip the whole block's language — which in turn suppressed the
    language-specific checks for the rest of the block.
    """
    letters = [c for c in text if c.isalpha()]
    if letters:
        cyrillic = sum(1 for c in letters if _CYRILLIC_RE.match(c))
        if cyrillic / len(letters) >= 0.30:
            return "uk"
    padded = f" {text.lower()} "
    if any(m in padded for m in _ITALIAN_MARKERS):
        return "it"
    return "en"
