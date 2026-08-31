"""The one split of `corpus/labelled.jsonl`, shared by everything that reads it.

There are two jobs the corpus does, and they pull opposite ways.

It is the **yardstick**: the file that says what precision and recall are worth.
It is also a **component** of `EmbeddingDetector`, whose score is a nearest
neighbour margin against it. Held together, the detector is asked whether a text
resembles a set that contains the text, and it answers yes: measured 2026-08-31,
scoring the corpus that way separated it almost perfectly - model entries
0.73-0.79 against human entries near 0.16 - and every point of that separation
was the corpus recognising itself.

So the halves have jobs. The tune half is what the detector is built from; the
held-out half is what any number about it is measured on. They never overlap,
which is what makes the measured threshold the threshold that actually runs:
before this, calibration used a reference half and production used the whole
file, so the number and the behaviour were about different detectors.

The split is by a hash of the text, not by position, so it does not move when
entries are added or reordered - a new entry lands in one half and stays there.
"""
from __future__ import annotations

import hashlib


def is_reference(text: str) -> bool:
    """Whether this entry belongs to the half detectors are allowed to see."""
    return hashlib.sha1(text.encode("utf-8")).digest()[0] % 2 == 0


def split(rows: list) -> tuple[list, list]:
    """`(tune, held_out)` - what may be built from, and what may be measured on."""
    tune, held_out = [], []
    for row in rows:
        (tune if is_reference(row["text"]) else held_out).append(row)
    return tune, held_out
