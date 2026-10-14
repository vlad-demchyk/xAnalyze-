"""Declared weighted ranking ensembles with conservative coverage and frozen components."""
from __future__ import annotations

import math

from .corpus import digest


def validate_ensemble_config(config):
    from .adapters import LOCAL, REMOTE, validate_config
    if not isinstance(config, dict) or set(config) != {"members", "weights"}:
        raise ValueError("ensemble requires only members and weights")
    members, weights = config["members"], config["weights"]
    if not isinstance(members, list) or not 2 <= len(members) <= 12 or not isinstance(weights, list) or len(weights) != len(members):
        raise ValueError("ensemble requires 2..12 members and matching weights")
    seen = set()
    for member in members:
        if not isinstance(member, dict) or set(member) - {"detector", "config"}:
            raise ValueError("invalid ensemble member")
        name = member.get("detector")
        if name not in LOCAL + REMOTE or name == "ensemble":
            raise ValueError("ensemble requires implemented non-ensemble members")
        settings = member.get("config", {})
        validate_config(settings, name)
        fingerprint = digest([name, settings])
        if fingerprint in seen:
            raise ValueError("duplicate ensemble member")
        seen.add(fingerprint)
    if any(type(w) not in (int, float) or not math.isfinite(w) or w <= 0 for w in weights) or not math.isfinite(sum(weights)):
        raise ValueError("ensemble weights must be positive finite numbers")


def _known_total(rows, key):
    values = [row.get(key) for row in rows]
    return sum(values) if all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in values) else None


def combine_predictions(samples, predictions, weights):
    if not isinstance(weights, list) or not weights or any(type(w) not in (int, float) or not math.isfinite(w) or w <= 0 for w in weights) or not math.isfinite(sum(weights)):
        raise ValueError("invalid ensemble weights")
    expected = {s["id"] for s in samples}
    if len(expected) != len(samples) or not predictions or len(predictions) != len(weights):
        raise ValueError("invalid ensemble sample/member alignment")
    indexed = []
    for rows in predictions:
        index = {r["id"]: r for r in rows}
        if len(index) != len(rows) or set(index) != expected:
            raise ValueError("ensemble member predictions are incomplete or duplicated")
        indexed.append(index)
    total = sum(weights)
    results = []
    for sample in samples:
        rows = [member[sample["id"]] for member in indexed]
        record = {**sample, "score": None, "spans": [], "localization_supported": False,
                  "latency_ms": _known_total(rows, "latency_ms"), "cost_usd": _known_total(rows, "cost_usd"),
                  "score_semantics": "declared normalized weighted ranking mean; calibration required",
                  "component_statuses": [row["status"] for row in rows]}
        if any(row["status"] not in ("checked", "abstained", "error") for row in rows):
            raise ValueError("unknown ensemble member status")
        if any(row["status"] == "error" for row in rows):
            record.update(status="error", reason="an ensemble member failed")
        elif any(row["status"] == "abstained" for row in rows):
            record.update(status="abstained", reason="an ensemble member abstained; weights not renormalized")
        else:
            if any(type(row["score"]) not in (int, float) or not math.isfinite(row["score"]) or not 0 <= row["score"] <= 1 for row in rows):
                raise ValueError("invalid ensemble member score")
            # Convexity establishes the bounds; guard only floating-point roundoff.
            mean = math.fsum(row["score"] * (weight / total) for row, weight in zip(rows, weights))
            record.update(status="checked", score=min(1., max(0., mean)),
                          component_scores=[row["score"] for row in rows])
        results.append(record)
    return results


def score_ensemble_samples(samples, config, reference, *, allow_remote=False):
    from .adapters import score_samples
    validate_ensemble_config(config)
    predictions = [score_samples(samples, member["detector"], member.get("config", {}), reference,
                                 allow_remote=allow_remote) for member in config["members"]]
    return combine_predictions(samples, predictions, config["weights"])
