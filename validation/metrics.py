"""Detection metrics with explicit abstention, prevalence and finite-sample limits."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
import math
from statistics import NormalDist, median


def wilson(successes: int, total: int, confidence=.95) -> list | None:
    if type(total) is not int or type(successes) is not int or not 0 <= successes <= total or not 0 < confidence < 1:
        raise ValueError("invalid binomial counts/confidence")
    if total == 0:
        return None
    z = NormalDist().inv_cdf(.5 + confidence / 2)
    p, z2 = successes / total, z * z
    center = (p + z2 / (2 * total)) / (1 + z2 / total)
    radius = z * math.sqrt(p * (1 - p) / total + z2 / (4 * total * total)) / (1 + z2 / total)
    return [max(0., center - radius), min(1., center + radius)]


def _ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def length_band(text: str) -> str:
    words = len(text.split())
    return "1-4" if words < 5 else "5-24" if words < 25 else "25+"


def rates(rows: list[dict], threshold: float, prevalence=.1) -> dict:
    if type(threshold) not in (int, float) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("threshold must be finite and between 0 and 1")
    if type(prevalence) not in (int, float) or not math.isfinite(prevalence) or not 0 < prevalence < 1:
        raise ValueError("prevalence must be between 0 and 1")
    for row in rows:
        if row.get("label") not in ("human", "model", "mixed"):
            raise ValueError("unverified labels cannot enter detection metrics")
        if row.get("status") not in ("checked", "abstained", "error"):
            raise ValueError("each prediction requires checked/abstained/error status")
        score = row.get("score")
        if row["status"] == "checked" and (type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1):
            raise ValueError("checked predictions require a finite 0..1 score")
    binary = [r for r in rows if r["label"] in ("human", "model")]
    human = [r for r in binary if r["label"] == "human"]
    model = [r for r in binary if r["label"] == "model"]
    checked = [r for r in binary if r["status"] == "checked"]
    checked_h = [r for r in human if r["status"] == "checked"]
    checked_m = [r for r in model if r["status"] == "checked"]
    tp = sum(r["score"] >= threshold for r in checked_m)
    fp = sum(r["score"] >= threshold for r in checked_h)
    tpr, fpr = _ratio(tp, len(checked_m)), _ratio(fp, len(checked_h))
    complete = len(checked) == len(binary)
    projected = _ratio(prevalence * tpr, prevalence * tpr + (1 - prevalence) * fpr) if complete and tpr is not None and fpr is not None else None
    # Group events give a second, conservative view: any human false flag,
    # and all model rows detected. No paragraph count is presented as the
    # number of independent websites/authors in the interval.
    clusters = defaultdict(list)
    for row in binary:
        if row.get("group_id"):
            clusters[row["group_id"]].append(row)
    human_groups = [[r for r in group if r["label"] == "human"] for group in clusters.values()]
    model_groups = [[r for r in group if r["label"] == "model"] for group in clusters.values()]
    human_groups = [g for g in human_groups if g]
    model_groups = [g for g in model_groups if g]
    group_fp = sum(any(r["status"] != "checked" or r["score"] >= threshold for r in g) for g in human_groups)
    group_tp = sum(all(r["status"] == "checked" and r["score"] >= threshold for r in g) for g in model_groups)
    latency = [r["latency_ms"] for r in rows if type(r.get("latency_ms")) in (int, float) and math.isfinite(r["latency_ms"])]
    known_cost = [r["cost_usd"] for r in rows if type(r.get("cost_usd")) in (int, float) and math.isfinite(r["cost_usd"])]
    return {"threshold": threshold, "total": len(rows), "binary_samples": len(binary),
            "humans": len(human), "models": len(model), "tp": tp, "fp": fp,
            "tn": len(checked_h) - fp, "fn": len(model) - tp,
            "conditional_fn": len(checked_m) - tp,
            "model_unresolved": len(model) - len(checked_m), "human_unresolved": len(human) - len(checked_h),
            "precision": _ratio(tp, tp + fp), "recall": _ratio(tp, len(model)),
            "conditional_recall": tpr, "fpr": fpr,
            "fpr_bounds_with_abstention": [_ratio(fp, len(human)), _ratio(fp + len(human) - len(checked_h), len(human))],
            "coverage": _ratio(len(checked), len(binary)),
            "all_sample_coverage": _ratio(sum(r["status"] == "checked" for r in rows), len(rows)),
            "abstained": sum(r["status"] == "abstained" for r in rows),
            "errors": sum(r["status"] == "error" for r in rows),
            "precision_at_prevalence": projected, "prevalence": prevalence,
            "nominal_sample_intervals": {"method": "Wilson, independent Bernoulli assumption",
                "recall": wilson(tp, len(model)), "fpr": wilson(fp, len(checked_h)),
                "precision": wilson(tp, tp + fp)},
            "group_intervals": {"method": "Wilson on independent source-group events, not document FPR/recall",
                "human_groups": len(human_groups), "model_groups": len(model_groups),
                "any_human_error": wilson(group_fp, len(human_groups)),
                "all_model_detected": wilson(group_tp, len(model_groups))},
            "latency_ms": {"samples": len(latency), "median": median(latency) if latency else None,
                           "total": sum(latency) if latency else None},
            "cost_usd": sum(known_cost) if len(known_cost) == len(rows) and rows else None,
            "cost_known_samples": len(known_cost)}


def _merge_ranges(ranges):
    merged = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    return merged


def span_localization(rows, threshold):
    intersection = predicted = gold = annotated = 0
    for row in rows:
        if row.get("gold_spans") is None or row["status"] != "checked":
            continue
        truth = _merge_ranges(row["gold_spans"])
        found = _merge_ranges([[s["start"], s["end"]] for s in row.get("spans", []) if s["score"] >= threshold])
        annotated += 1
        predicted += sum(b - a for a, b in found)
        gold += sum(b - a for a, b in truth)
        intersection += sum(max(0, min(b, d) - max(a, c)) for a, b in truth for c, d in found)
    union = predicted + gold - intersection
    return {"annotated_checked_samples": annotated, "character_precision": _ratio(intersection, predicted),
            "character_recall": _ratio(intersection, gold), "iou": _ratio(intersection, union),
            "coordinate_system": "original Unicode code points"}


def metric_report(rows, threshold, prevalence=.1):
    groups = {}
    for dimension in ("language", "length", "register", "condition"):
        values = sorted({length_band(r["text"]) if dimension == "length" else r.get(dimension, "unknown") for r in rows})
        groups[dimension] = {}
        for value in values:
            subset = [r for r in rows if (length_band(r["text"]) if dimension == "length" else r.get(dimension, "unknown")) == value]
            groups[dimension][value] = {**rates(subset, threshold, prevalence), "span_localization": span_localization(subset, threshold)}
    recalls = [r["recall"] for r in groups["language"].values() if r["recall"] is not None]
    return {"overall": rates(rows, threshold, prevalence), "subgroups": groups,
            "macro_language_recall": sum(recalls) / len(recalls) if recalls else None,
            "span_localization": span_localization(rows, threshold)}


@dataclass(frozen=True)
class QualityPolicy:
    languages: tuple = ("uk", "it", "en")
    lengths: tuple = ("1-4", "5-24", "25+")
    registers: tuple = ("product-copy", "technical-prose", "short-ui", "human-marketing")
    conditions: tuple = ("original", "paraphrase", "translation", "mixed", "unicode-attack")
    min_recall: float = .5
    min_precision: float = .9
    max_fpr: float = .01
    min_coverage: float = .95
    min_per_class: int = 30
    min_groups: int = 30
    prevalence: float = .1
    min_span_iou: float = .5

    def __post_init__(self):
        for key in ("languages", "lengths", "registers", "conditions"):
            values = getattr(self, key)
            if not isinstance(values, (tuple, list)) or not values or any(not isinstance(v, str) or not v for v in values) or len(set(values)) != len(values):
                raise ValueError(f"invalid policy {key}")
            object.__setattr__(self, key, tuple(values))
        for key in ("min_recall", "min_precision", "max_fpr", "min_coverage", "prevalence", "min_span_iou"):
            value = getattr(self, key)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"invalid policy {key}")
        if not 0 < self.prevalence < 1:
            raise ValueError("invalid policy prevalence")
        for key in ("min_per_class", "min_groups"):
            if type(getattr(self, key)) is not int or getattr(self, key) < 1:
                raise ValueError(f"invalid policy {key}")


def quality_failures(report: dict, policy=QualityPolicy(), *, independent=False) -> list[str]:
    failures = [] if independent else ["independent locked test not established"]
    selections = [("overall", report["overall"])]
    for dimension, values in (("language", policy.languages), ("length", policy.lengths),
                              ("register", policy.registers), ("condition", policy.conditions)):
        for value in values:
            subset = report["subgroups"][dimension].get(value)
            if subset is None:
                failures.append(f"missing {dimension}: {value}")
            elif dimension == "condition" and value == "mixed":
                localization = subset["span_localization"]
                if localization["annotated_checked_samples"] < policy.min_per_class or localization["iou"] is None or localization["iou"] < policy.min_span_iou:
                    failures.append("condition:mixed: insufficient span localization")
                if subset["all_sample_coverage"] is None or subset["all_sample_coverage"] < policy.min_coverage:
                    failures.append("condition:mixed: insufficient coverage")
            else:
                selections.append((f"{dimension}:{value}", subset))
    for name, subset in selections:
        negative_only = name == "register:human-marketing"
        for key in ("humans",) if negative_only else ("humans", "models"):
            if subset[key] < policy.min_per_class:
                failures.append(f"{name}: insufficient {key} ({subset[key]})")
        for key, minimum in (("recall", policy.min_recall), ("precision_at_prevalence", policy.min_precision), ("coverage", policy.min_coverage)):
            if negative_only and key != "coverage":
                continue
            value = subset[key]
            if value is None or value < minimum:
                failures.append(f"{name}: {key} unavailable or below {minimum:g}")
        upper = subset["fpr_bounds_with_abstention"][1]
        if upper is None or upper > policy.max_fpr:
            failures.append(f"{name}: worst-case FPR unavailable or above {policy.max_fpr:g}")
        ci = subset["group_intervals"]
        if ci["human_groups"] < policy.min_groups or (not negative_only and ci["model_groups"] < policy.min_groups):
            failures.append(f"{name}: insufficient independent source groups")
        if ci["any_human_error"] is None or ci["any_human_error"][1] > policy.max_fpr:
            failures.append(f"{name}: group error upper bound exceeds {policy.max_fpr:g}")
        if not negative_only and (ci["all_model_detected"] is None or ci["all_model_detected"][0] < policy.min_recall):
            failures.append(f"{name}: group detection lower bound below {policy.min_recall:g}")
    return failures
