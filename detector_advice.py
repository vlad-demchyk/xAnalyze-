"""When the detector that ran is the wrong one for what it was pointed at.

There is exactly one case so far and it is a large one. The offline wording
pass and the embedding detector were measured on the same held-out half of
`corpus/labelled.jsonl`, and they do not disagree slightly:

    language   wording pass   embedding
    en          11/20 (55%)   17/20 (85%)
    it           4/11 (36%)   11/11 (100%)
    uk          10/14 (71%)   12/14 (86%)

Italian is the outlier. A person scanning an Italian page with the default
detector is getting a third of what the same machine can already tell them,
and nothing said so - the number lived in a calibration report nobody runs.

This is not a reason to drop the wording pass. It costs nothing (0.01s where
the embedding detector takes 6.9s for the same fifty blocks), needs no
`torch`, names the phrase it matched, and offers an offline replacement for
it - and on the held-out half it catches four positives the embedding
detector misses, the blatant ones. It is a reason to say which one the
person should have used.
"""
from __future__ import annotations

#: Held-out recall per language, measured 2026-08-31. Kept as data rather
#: than prose because the advice is only worth giving while the gap is real:
#: re-measure with `python scripts/calibrate.py --holdout` after any change
#: to the cliché lists or the corpus.
HELD_OUT_RECALL = {
    "offline": {"en": 0.55, "it": 0.36, "uk": 0.71},
    "embedding": {"en": 0.85, "it": 1.00, "uk": 0.86},
}

#: How much better another detector has to be before the person is told.
#: 0.30 puts Italian (0.36 -> 1.00) well inside and leaves English and
#: Ukrainian alone, where the gap is real but not the difference between
#: an answer and no answer.
_WORTH_SAYING = 0.30

#: Below this share of the page's words, one language is not what the page
#: is in.
_DOMINANT = 0.5

#: A page with fewer readable words than this says nothing about its
#: language, so it says nothing about which detector suits it.
_MIN_WORDS = 40


def dominant_language(blocks) -> str | None:
    """The language of a page, or None when it does not have one.

    **Weighted by words, not by blocks**, and the difference decides real
    pages. Measured on a live Italian site: counting blocks gives English
    23 to 19 and the page reads as English, because a navigation bar is many
    short blocks; counting words gives Italian 452 to 162, which is what the
    page is actually made of. A menu is not what a page says.

    Blocks with no hint are not voters either: `None` means the passage was
    too short to read, and a guess is what this whole module exists to
    replace with a measurement.
    """
    words: dict[str, int] = {}
    for block in blocks:
        hint = getattr(block, "language_hint", None)
        if hint:
            words[hint] = words.get(hint, 0) + len(block.text.split())
    total = sum(words.values())
    if total < _MIN_WORDS:
        return None
    top = max(words, key=words.get)
    return top if words[top] / total >= _DOMINANT else None


def weak_language_note(detector_name: str, blocks) -> str | None:
    """One sentence for a run whose detector is weak in the page's language.

    Returns None when there is nothing to say, which is the common case.
    """
    recall = HELD_OUT_RECALL.get(detector_name)
    if recall is None:
        return None
    language = dominant_language(blocks)
    if language is None or language not in recall:
        return None

    mine = recall[language]
    better = [(other, table[language] - mine)
              for other, table in HELD_OUT_RECALL.items()
              if other != detector_name and table.get(language, 0) - mine >= _WORTH_SAYING]
    if not better:
        return None
    best, _gap = max(better, key=lambda pair: pair[1])
    return (f"this page reads as {language}, where the {detector_name} detector "
            f"found {mine:.0%} of known AI passages on the held-out corpus and "
            f"{best} found {HELD_OUT_RECALL[best][language]:.0%}; "
            f"try --detector {best} or --detector hybrid")
