"""Deterministic formatting attacks preserve content labels and source lineage."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import unicodedata

from .corpus import validate_dataset

VARIANTS = ("fullwidth-latin", "zero-width", "nbsp")


def unicode_variant(row, variant):
    """Keep original provenance and map gold spans to transformed code points."""
    if variant not in VARIANTS:
        raise ValueError("unknown Unicode variant")
    result = deepcopy(row)
    output, starts, ends = [], [], []
    for index, char in enumerate(row["text"]):
        if variant == "zero-width" and index and unicodedata.category(char).startswith("L") and unicodedata.category(row["text"][index - 1]).startswith("L"):
            output.append("\u200b")
        starts.append(len(output))
        if variant == "fullwidth-latin" and ("A" <= char <= "Z" or "a" <= char <= "z"):
            char = chr(ord(char) + 0xFEE0)
        elif variant == "nbsp" and char == " ":
            char = "\u00a0"
        output.append(char)
        ends.append(len(output))
    result["text"] = "".join(output)
    result["id"] = row["id"] + ":" + variant
    result["parents"] = [row["id"]]
    result["condition"] = "unicode-attack"
    if row.get("gold_spans") is not None:
        result["gold_spans"] = [[starts[a], ends[b - 1]] for a, b in row["gold_spans"]]
    result["provenance"]["transformation"] = {"name": variant, "version": 1,
        "date": datetime.now(timezone.utc).isoformat(), "source_sample": row["id"],
        "label_policy": "formatting only; inherited content authorship, not new ground truth"}
    return result


def add_unicode_variants(data):
    validate_dataset(data)
    result = deepcopy(data)
    for row in data["samples"]:
        if row["condition"] == "original":
            result["samples"].extend(unicode_variant(row, name) for name in VARIANTS)
    validate_dataset(result)
    return result
