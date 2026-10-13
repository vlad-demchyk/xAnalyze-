"""Versioned benchmark provenance, connected source groups and immutable splits."""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unicodedata

PARTITIONS = ("reference", "calibration", "test")
GROUP_FIELDS = ("author_id", "site_id", "source_id", "template_id")


def canonical_text(text: str) -> str:
    """Identity for leakage checks only; original text/offsets remain unchanged."""
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join("".join(c for c in text if unicodedata.category(c) != "Cf").split())


def digest(value) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def strict_json(text: str):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError(f"invalid JSON number: {value}")
    return json.loads(text, object_pairs_hook=object_pairs, parse_constant=invalid_constant)


def load_dataset(path) -> dict:
    data = strict_json(Path(path).read_text(encoding="utf-8"))
    validate_dataset(data)
    return data


def connected_groups(samples: list[dict]) -> dict[str, str]:
    """Transitive author/site/source/template/parent/duplicate links are indivisible."""
    parents = {row["id"]: row["id"] for row in samples}
    def find(key):
        while parents[key] != key:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key
    def join(first, second):
        a, b = find(first), find(second)
        if a != b:
            parents[max(a, b)] = min(a, b)
    seen = {}
    for row in samples:
        tokens = [(key, row["groups"][key]) for key in GROUP_FIELDS]
        tokens.append(("text", digest(canonical_text(row["text"]))))
        for token in tokens:
            if token in seen:
                join(row["id"], seen[token])
            else:
                seen[token] = row["id"]
        for parent in row.get("parents", []):
            if parent not in parents:
                raise ValueError(f"unknown parent {parent} for {row['id']}")
            join(row["id"], parent)
    return {key: find(key) for key in parents}


def validate_dataset(data: dict, *, require_splits=True) -> dict[str, str]:
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ValueError("benchmark requires schema_version 1")
    if data.get("purpose") not in ("validation", "fixture"):
        raise ValueError("purpose must be validation or fixture")
    if not isinstance(data.get("dataset_id"), str) or not data["dataset_id"].strip():
        raise ValueError("dataset_id is required")
    samples = data.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("samples must be a nonempty array")
    ids = set()
    for row in samples:
        if not isinstance(row, dict):
            raise ValueError("each sample must be an object")
        if set(row) - {"id", "text", "language", "register", "condition", "label", "split", "groups", "provenance", "parents", "gold_spans"}:
            raise ValueError("sample contains undeclared fields or precomputed scores")
        for key in ("id", "text", "language", "register", "condition"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                raise ValueError(f"sample requires {key}")
        if row["id"] in ids:
            raise ValueError(f"duplicate sample id {row['id']}")
        ids.add(row["id"])
        if row.get("label") not in ("human", "model", "mixed"):
            raise ValueError(f"unverified/invalid label for {row['id']}")
        if require_splits and row.get("split") not in PARTITIONS:
            raise ValueError(f"sample {row['id']} needs reference/calibration/test split")
        if "split" in row and row["split"] not in PARTITIONS:
            raise ValueError("invalid split")
        groups = row.get("groups") or {}
        if not isinstance(groups, dict) or any(not isinstance(groups.get(k), str) or not groups[k].strip() for k in GROUP_FIELDS):
            raise ValueError(f"sample {row['id']} requires all four source group IDs")
        provenance = row.get("provenance") or {}
        if not isinstance(provenance, dict):
            raise ValueError("provenance must be an object")
        for key in ("source", "date", "license", "verified_by", "evidence"):
            if not isinstance(provenance.get(key), str) or not provenance[key].strip():
                raise ValueError(f"sample {row['id']} requires provenance.{key}")
        if type(provenance.get("public_benchmark")) is not bool:
            raise ValueError("public_benchmark must be an explicit boolean")
        if row["label"] in ("model", "mixed"):
            generator = provenance.get("generator") or {}
            if not isinstance(generator, dict) or any(not isinstance(generator.get(k), str) or not generator[k].strip()
                    for k in ("name", "model_version", "prompt", "date")):
                raise ValueError(f"sample {row['id']} requires generator/model version/prompt/date")
        if not isinstance(row.get("parents", []), list) or any(not isinstance(p, str) for p in row.get("parents", [])):
            raise ValueError("parents must be sample IDs")
        spans = row.get("gold_spans")
        if spans is not None:
            if not isinstance(spans, list):
                raise ValueError("gold_spans must be an array or null (unannotated)")
            for span in spans:
                if not isinstance(span, list) or len(span) != 2 or any(type(x) is not int for x in span) or not 0 <= span[0] < span[1] <= len(row["text"]):
                    raise ValueError(f"invalid code-point gold span for {row['id']}")
            if row["label"] == "human" and spans:
                raise ValueError("human samples cannot have generated gold spans")
    groups = connected_groups(samples)
    splits = defaultdict(set)
    labels = defaultdict(set)
    for row in samples:
        if row.get("split"):
            splits[groups[row["id"]]].add(row["split"])
        labels[canonical_text(row["text"])].add(row["label"])
    if any(len(values) > 1 for values in splits.values()):
        raise ValueError("linked source groups or duplicates cross split boundaries")
    if any(len(values) > 1 for values in labels.values()):
        raise ValueError("canonical duplicate text has conflicting labels")
    return groups


def assign_splits(data: dict, seed: str) -> dict:
    validate_dataset(data, require_splits=False)
    if any("split" in row for row in data["samples"]):
        raise ValueError("partition only an unassigned dataset; existing splits are never rewritten")
    result = deepcopy(data)
    groups = connected_groups(result["samples"])
    for row in result["samples"]:
        bucket = int(digest([seed, groups[row["id"]]])[:8], 16) % 100
        row["split"] = "reference" if bucket < 50 else "calibration" if bucket < 75 else "test"
    result["partition_seed"] = seed
    validate_dataset(result)
    return result


def historical_overlap(samples: list[dict], corpus_dir: Path) -> list[str]:
    known = set()
    for path in corpus_dir.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = strict_json(line)
                if isinstance(row.get("text"), str):
                    known.add(canonical_text(row["text"]))
    return [row["id"] for row in samples if canonical_text(row["text"]) in known]
