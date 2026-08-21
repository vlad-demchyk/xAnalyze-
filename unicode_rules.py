"""Detects characters that a person would not type on a keyboard, and maps
them to the ones they would.

Why this is a useful signal: text produced or processed by a machine tends
to pick up characters no keyboard emits directly — typographic dashes and
curly quotes, non-breaking and hair spaces, zero-width joiners, letters
lifted from the wrong alphabet, styled mathematical letters. A person
typing the same sentence produces ASCII punctuation and one consistent
alphabet.

The hard part is not finding non-ASCII characters — it's *not* flagging
the ones that are perfectly normal for the language. Italian keyboards
type `è à ò ù` directly; Ukrainian text is Cyrillic end to end and uses
«guillemets» as its standard quotation marks. A naive "flag everything
above U+007F" rule would mark every Italian accent and every Ukrainian
letter. So each rule below is scoped by script and by language.

Two tiers, because they carry very different weight:

* HARD — invisible controls, mixed-alphabet letters, styled maths, fullwidth
  forms, exotic spaces. These have no legitimate role in ordinary copy in
  any of the three languages. Flagged everywhere, high confidence.
* TYPOGRAPHY — em dashes, curly quotes, ellipsis characters. Genuinely
  correct in professionally typeset text (an em dash is the standard
  Ukrainian тире), but also the single most-cited tell of machine-written
  copy. Flagged at medium confidence, and switchable off in Settings for
  anyone who wants to keep proper typography.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# ---------------------------------------------------------------- categories

CAT_INVISIBLE = "invisible"
CAT_SPACE = "space"
CAT_TYPOGRAPHY = "typography"
CAT_HOMOGLYPH = "homoglyph"
CAT_STYLED = "styled"

ALL_CATEGORIES = (CAT_INVISIBLE, CAT_SPACE, CAT_HOMOGLYPH, CAT_STYLED, CAT_TYPOGRAPHY)
HARD_CATEGORIES = (CAT_INVISIBLE, CAT_SPACE, CAT_HOMOGLYPH, CAT_STYLED)

CATEGORY_SCORES = {
    CAT_INVISIBLE: 1.0,
    CAT_HOMOGLYPH: 0.95,
    CAT_STYLED: 0.90,
    CAT_SPACE: 0.80,
    CAT_TYPOGRAPHY: 0.50,
}

# -------------------------------------------------------------- rule tables

# Invisible / formatting controls — deleted outright. Nothing in ordinary
# website copy needs them, and being invisible they survive proofreading.
INVISIBLE_CHARS = {
    "​": "",   # zero width space
    "‌": "",   # zero width non-joiner
    "‍": "",   # zero width joiner
    "⁠": "",   # word joiner
    "﻿": "",   # zero width no-break space / BOM
    "­": "",   # soft hyphen
    "‎": "",   # left-to-right mark
    "‏": "",   # right-to-left mark
    "‪": "", "‫": "", "‬": "", "‭": "", "‮": "",
    "⁦": "", "⁧": "", "⁨": "", "⁩": "",
    "᠎": "",   # mongolian vowel separator
    "؜": "",   # arabic letter mark
}

# Anything that renders as blank but isn't a plain space.
SPACE_CHARS = {c: " " for c in (
    " ",  # no-break space
    " ",  # ogham space mark
    " ", " ", " ", " ", " ", " ",
    " ", " ", " ", " ", " ",
    " ",  # narrow no-break space
    " ",  # medium mathematical space
    "　",  # ideographic space
)}

# Typographic punctuation -> what the same key produces.
TYPOGRAPHY_CHARS = {
    "‐": "-",    # hyphen
    "‑": "-",    # non-breaking hyphen
    "‒": "-",    # figure dash
    "–": "-",    # en dash
    "—": "-",    # em dash
    "―": "-",    # horizontal bar
    "−": "-",    # minus sign
    "‘": "'",    # left single quote
    "’": "'",    # right single quote / typographic apostrophe
    "‚": "'",    # single low-9 quote
    "‛": "'",    # single high-reversed-9 quote
    "′": "'",    # prime
    "ʼ": "'",    # modifier letter apostrophe
    "ʹ": "'",    # modifier letter prime
    "“": '"',    # left double quote
    "”": '"',    # right double quote
    "„": '"',    # double low-9 quote
    "‟": '"',    # double high-reversed-9 quote
    "″": '"',    # double prime
    "…": "...",  # horizontal ellipsis
    "•": "-",    # bullet
    "‣": "-",    # triangular bullet
    "⁃": "-",    # hyphen bullet
    "×": "x",    # multiplication sign
    "⁄": "/",    # fraction slash
    "∕": "/",    # division slash
    "«": '"',    # << guillemet  (language-gated below)
    "»": '"',    # >> guillemet  (language-gated below)
}

# Guillemets are the standard quotation marks in Ukrainian and are common
# in Italian, so they're only treated as an anomaly in English text.
LANGUAGE_EXEMPT = {
    "uk": {"«", "»", "'", "—", "–"},  # « » plus Ukrainian apostrophe, em/en dash
    "it": {"«", "»", "—", "–"},  # « » plus em/en dash (Italian typography)
    "en": set(),
}

# Confusable letters, per target script. Cyrillic letters that look exactly
# like Latin ones (and the reverse) are how a single word ends up written in
# two alphabets — invisible on screen, and it breaks search and spellcheck.
CYRILLIC_TO_LATIN = {
    "а": "a", "в": "b", "е": "e", "к": "k", "м": "m", "н": "h", "о": "o",
    "р": "p", "с": "c", "т": "t", "у": "y", "х": "x", "і": "i", "ѕ": "s",
    "ј": "j", "һ": "h", "ԛ": "q", "ԝ": "w", "ё": "e",
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O",
    "Р": "P", "С": "C", "Т": "T", "У": "Y", "Х": "X", "І": "I", "Ѕ": "S",
    "Ј": "J", "Ԛ": "Q", "Ԝ": "W", "Г": "T",
}
LATIN_TO_CYRILLIC = {
    "a": "а", "b": "в", "e": "е", "k": "к", "m": "м", "o": "о", "p": "р",
    "c": "с", "t": "т", "y": "у", "x": "х", "i": "і", "s": "ѕ", "j": "ј",
    "A": "А", "B": "В", "E": "Е", "K": "К", "M": "М", "O": "О", "P": "Р",
    "C": "С", "T": "Т", "Y": "У", "X": "Х", "I": "І", "H": "Н",
}
GREEK_TO_LATIN = {
    "α": "a", "β": "b", "ε": "e", "ι": "i", "κ": "k", "ν": "v", "ο": "o",
    "ρ": "p", "τ": "t", "υ": "u", "χ": "x", "γ": "y", "η": "n",
    "Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K",
    "Μ": "M", "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X",
}

_CYRILLIC_RE = re.compile(r"[Ѐ-ӿԀ-ԯ]")
_LATIN_RE = re.compile(r"[A-Za-zÀ-ɏ]")
_GREEK_RE = re.compile(r"[Ͱ-Ͽ]")
_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


@dataclass
class Anomaly:
    start: int          # char offset into the analysed text
    end: int
    original: str
    replacement: str
    category: str
    description: str    # human-readable, shown in the UI


def _char_name(ch: str) -> str:
    try:
        return unicodedata.name(ch)
    except ValueError:
        return "UNNAMED CONTROL CHARACTER"


def _describe(ch: str, replacement: str) -> str:
    shown = repr(replacement) if replacement else "removed"
    return f"U+{ord(ch):04X} {_char_name(ch)} -> {shown}"


def _script_of(ch: str) -> str | None:
    if _CYRILLIC_RE.match(ch):
        return "cyrillic"
    if _GREEK_RE.match(ch):
        return "greek"
    if _LATIN_RE.match(ch):
        return "latin"
    return None


def _styled_replacement(ch: str) -> str | None:
    """Fold mathematical alphanumerics (𝐀 𝑩 𝒞), fullwidth forms (Ａ), and
    similar compatibility characters back to their plain equivalent. NFKC
    is exactly the mapping Unicode defines for this, so anything it changes
    into a plain ASCII letter or digit was a styled variant."""
    if ord(ch) < 0x2000:
        return None
    folded = unicodedata.normalize("NFKC", ch)
    if folded == ch:
        return None
    if not folded.isascii() or not folded.strip():
        return None
    if not (folded.isalnum() or folded in "()[]{}+-=<>/\\"):
        return None
    return folded


def _find_homoglyphs(text: str) -> list[Anomaly]:
    """Report letters written in a different alphabet from the rest of
    their own word. Judged per word, so a Ukrainian sentence containing an
    English brand name is fine — only a word that mixes alphabets inside
    itself is reported."""
    out: list[Anomaly] = []
    for match in _WORD_RE.finditer(text):
        word = match.group(0)
        if len(word) < 2:
            continue
        scripts: dict[str, int] = {}
        for ch in word:
            script = _script_of(ch)
            if script:
                scripts[script] = scripts.get(script, 0) + 1
        if len(scripts) < 2:
            continue
        majority = max(scripts, key=lambda s: scripts[s])
        for offset, ch in enumerate(word):
            script = _script_of(ch)
            if script is None or script == majority:
                continue
            replacement = None
            if majority == "latin":
                replacement = CYRILLIC_TO_LATIN.get(ch) or GREEK_TO_LATIN.get(ch)
            elif majority == "cyrillic":
                replacement = LATIN_TO_CYRILLIC.get(ch)
            if not replacement:
                continue  # a genuinely different letter, not a look-alike
            start = match.start() + offset
            out.append(Anomaly(
                start=start, end=start + 1, original=ch, replacement=replacement,
                category=CAT_HOMOGLYPH,
                description=(
                    f"U+{ord(ch):04X} {_char_name(ch)} inside a "
                    f"{majority} word ({word!r}) -> {replacement!r}"
                ),
            ))
    return out


# HTML entities that represent non-keyboard characters
_HTML_ENTITIES = {
    "&mdash;": "-",
    "&#8212;": "-",
    "&ndash;": "-",
    "&#8211;": "-",
    "&lsquo;": "'",
    "&#8216;": "'",
    "&rsquo;": "'",
    "&#8217;": "'",
    "&ldquo;": '"',
    "&#8220;": '"',
    "&rdquo;": '"',
    "&#8221;": '"',
    "&hellip;": "...",
    "&#8230;": "...",
    "&nbsp;": " ",
    "&#160;": " ",
    "&bull;": "*",
    "&#8226;": "*",
    "&middot;": "*",
    "&#183;": "*",
}

_HTML_ENTITY_RE = re.compile("|".join(re.escape(e) for e in _HTML_ENTITIES))


def _find_html_entities(text: str) -> list[Anomaly]:
    """Find HTML entities that represent non-keyboard characters."""
    out = []
    for match in _HTML_ENTITY_RE.finditer(text):
        entity = match.group(0)
        replacement = _HTML_ENTITIES.get(entity, "")
        if replacement:
            out.append(Anomaly(
                start=match.start(), end=match.end(),
                original=entity, replacement=replacement,
                category=CAT_TYPOGRAPHY,
                description=f"HTML entity {entity} -> {replacement!r}"
            ))
    return out


def find_anomalies(text: str, language: str | None = None,
                    categories: tuple[str, ...] = ALL_CATEGORIES) -> list[Anomaly]:
    """Return every anomaly in `text`, sorted by position and merged into
    contiguous runs so that "— " (em dash plus no-break space) is reported
    and replaced as one edit rather than two adjacent ones."""
    exempt = LANGUAGE_EXEMPT.get(language or "", set())
    found: list[Anomaly] = []

    for i, ch in enumerate(text):
        if ch in exempt:
            continue
        if CAT_INVISIBLE in categories and ch in INVISIBLE_CHARS:
            found.append(Anomaly(i, i + 1, ch, "", CAT_INVISIBLE, _describe(ch, "")))
            continue
        if CAT_SPACE in categories and ch in SPACE_CHARS:
            found.append(Anomaly(i, i + 1, ch, " ", CAT_SPACE, _describe(ch, " ")))
            continue
        if CAT_TYPOGRAPHY in categories and ch in TYPOGRAPHY_CHARS:
            rep = TYPOGRAPHY_CHARS[ch]
            found.append(Anomaly(i, i + 1, ch, rep, CAT_TYPOGRAPHY, _describe(ch, rep)))
            continue
        if CAT_STYLED in categories:
            rep = _styled_replacement(ch)
            if rep is not None:
                found.append(Anomaly(i, i + 1, ch, rep, CAT_STYLED, _describe(ch, rep)))
                continue

    if CAT_HOMOGLYPH in categories:
        taken = {a.start for a in found}
        found.extend(a for a in _find_homoglyphs(text) if a.start not in taken)

    # HTML entities that represent non-keyboard characters
    found.extend(_find_html_entities(text))

    found.sort(key=lambda a: a.start)
    return _merge_adjacent(found)


def _merge_adjacent(items: list[Anomaly]) -> list[Anomaly]:
    if not items:
        return []
    merged = [items[0]]
    for item in items[1:]:
        prev = merged[-1]
        # Only same-kind neighbours are combined. Merging a homoglyph with an
        # adjacent soft hyphen would work mechanically but would report both
        # under a single category label, which is misleading in a tool whose
        # value is telling you exactly what it found.
        if item.start == prev.end and item.category == prev.category:
            merged[-1] = Anomaly(
                start=prev.start, end=item.end,
                original=prev.original + item.original,
                replacement=prev.replacement + item.replacement,
                category=prev.category,
                description=prev.description + "; " + item.description,
            )
        else:
            merged.append(item)
    return merged


def clean_text(text: str, language: str | None = None,
                categories: tuple[str, ...] = ALL_CATEGORIES) -> str:
    """Apply every replacement. Deterministic, offline, no model involved."""
    anomalies = find_anomalies(text, language, categories)
    if not anomalies:
        return text
    out = []
    cursor = 0
    for a in anomalies:
        out.append(text[cursor:a.start])
        out.append(a.replacement)
        cursor = a.end
    out.append(text[cursor:])
    return "".join(out)


def summarize(anomalies: list[Anomaly]) -> str:
    counts: dict[str, int] = {}
    for a in anomalies:
        counts[a.category] = counts.get(a.category, 0) + 1
    return ", ".join(f"{cat}: {n}" for cat, n in sorted(counts.items()))
