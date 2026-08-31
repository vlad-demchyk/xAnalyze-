"""Cheap language guess shared by the extractors and the detectors.

Lives at top level rather than inside detectors/ so the crawler and the
repo scanner can tag each extracted block with a language without
importing a detector — the tag then flows through to the rewrite provider,
which needs it to answer in the right language.
"""
from __future__ import annotations

import re

_CYRILLIC_RE = re.compile(r"[А-Яа-яЇїІіЄєҐґ]")

#: Returned when the text is positively some other language. Not the same
#: answer as `None`: `None` means "too short to tell", and the callers that
#: see it check every list to be safe. This one means the opposite - we read
#: enough to know we are not equipped, so nothing language-specific applies.
UNSUPPORTED = "other"

# Function words that are common in Italian and rare/absent in English.
_ITALIAN_MARKERS = (
    " è ", " non ", " che ", " della ", " gli ", " sono ", " perché ",
    " degli ", " nella ", " questo ", " anche ", " più ", " con ", " per ",
)

#: Letters that exist in Ukrainian and not in Russian, and the reverse. A
#: share of Cyrillic said "Ukrainian" for any Cyrillic at all, so every
#: Russian page was scored with Ukrainian cliché lists and, worse, handed to
#: the rewrite provider as "(language: uk)" - a request to answer a Russian
#: page in Ukrainian.
#:
#: Measured on `corpus/labelled.jsonl` (155 Ukrainian human entries) against
#: 42 Russian paragraphs from dated Wikipedia revisions: the Ukrainian half
#: contains **no** Russian-only letter at all, and every Russian entry has at
#: least 0.75 per 100 letters. The two sets do not overlap on real text, so
#: the comparison needs no threshold - whichever side has more, wins.
_UKRAINIAN_ONLY = set("іїєґІЇЄҐ")
_RUSSIAN_ONLY = set("ыэъёЫЭЪЁ")

#: Function words of languages this tool has no lists for. Only words that
#: are *not* also ordinary Italian: `del`, `una`, `se`, `su` and `le` were in
#: here first and pulled 13 Italian entries out of the corpus with them.
_OTHER_LATIN_MARKERS = {
    "es": (" el ", " los ", " las ", " que ", " para ", " pero ", " está ",
           " esta ", " sus ", " por ", " con el ", " de la "),
    "fr": (" les ", " des ", " est ", " une ", " dans ", " pour ", " qui ",
           " sur ", " du ", " aux ", " cette "),
    "de": (" der ", " die ", " das ", " und ", " von ", " mit ", " ist ",
           " den ", " ein ", " auf ", " eine "),
    "pl": (" nie ", " jest ", " się ", " oraz ", " przez ", " które ",
           " lub ", " jako ", " są ", " do ", " na "),
}

#: Markers per 100 words before a foreign language is called. Swept against
#: 439 supported-language entries and 172 foreign paragraphs: at 6.0 nothing
#: in English, Italian or Ukrainian is misread (0/439) and 89% of the foreign
#: text is caught. Lower cut-offs catch a little more and start costing
#: English entries, and a wrong language is worse than a missing one here.
_OTHER_PER_100_WORDS = 6.0


# Minimum word count for language detection to be meaningful. Below this,
# the guess is too noisy to be useful: a short UI string like "OK" or
# "Save" contains no marker words, and treating it as English would
# suppress the Italian or Ukrainian cliché lists that might actually match.
_MIN_WORDS_FOR_DETECTION = 5

#: How many words one Italian marker is allowed to speak for. See
#: `guess_language_safe` for the measurement behind the number.
_ITALIAN_WORDS_PER_MARKER = 50


def _density(padded: str, word_count: int, markers) -> float:
    """Marker hits per 100 words. Density, not presence: see below."""
    hits = sum(padded.count(marker) for marker in markers)
    return hits / max(word_count, 1) * 100


def guess_language(text: str) -> str:
    """Return 'uk', 'it', 'en' or `UNSUPPORTED`.

    Text too short to read is named English, as it always was: a caller that
    needs a string cannot be handed None. `UNSUPPORTED` is different - it is
    a reading, not a fallback, and callers must not print it or send it to a
    model as a language.

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
    """Return 'uk', 'it', 'en', `UNSUPPORTED`, or None when too short to tell.

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
            # Cyrillic is not Ukrainian. Russian, Bulgarian and Serbian all
            # pass the share test, and calling them Ukrainian is not a
            # harmless label: it picks the cliché list and it is what the
            # rewrite provider is told to answer in.
            if (sum(1 for c in letters if c in _RUSSIAN_ONLY)
                    > sum(1 for c in letters if c in _UKRAINIAN_ONLY)):
                return UNSUPPORTED
            return "uk"

    # For Italian and English: need enough words for marker detection to work
    if word_count < _MIN_WORDS_FOR_DETECTION:
        return None

    padded = f" {text.lower()} "

    # A language we have no lists for is not English. Checked before the
    # Italian test because Spanish trips it: measured on 48 Spanish
    # paragraphs, 13 of them read as Italian on shared function words.
    italian_density = _density(padded, word_count, _ITALIAN_MARKERS)
    foreign = max(_density(padded, word_count, markers)
                  for markers in _OTHER_LATIN_MARKERS.values())
    if foreign >= _OTHER_PER_100_WORDS and foreign > italian_density:
        return UNSUPPORTED

    # Density, not presence. One marker anywhere used to be enough, and on a
    # short string that is right - but on a long English page the words
    # "per", "che" and "con" turn up once by accident, and `wordpress.org`
    # and `squarespace.com` were both being read as Italian on the strength
    # of a single hit in several hundred words.
    #
    # The rate is what separates them, and it is measured rather than
    # chosen: on `corpus/labelled.jsonl` the English half contains **no**
    # marker at all (0.0 per 100 words, at the maximum) while the Italian
    # half runs to a median of 5.9. One per fifty words sits far below the
    # real Italian floor and far above accidental English.
    hits = sum(padded.count(marker) for marker in _ITALIAN_MARKERS)
    if hits >= max(1, word_count // _ITALIAN_WORDS_PER_MARKER):
        return "it"
    return "en"
