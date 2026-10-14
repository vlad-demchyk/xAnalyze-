"""Predeclare several detector protocols, then consume their shared test once."""
from __future__ import annotations

from datetime import datetime, timezone
import re

from .adapters import inference_policy
from .corpus import digest, validate_dataset
from .metrics import QualityPolicy, quality_failures
from .protocol import _evaluate_claimed, _test_paths, freeze, verify_protocol, verify_report, write_new


def freeze_comparison(data, methods, policy=None, *, allow_remote=False):
    """Fit every declared method on calibration before any shared test access."""
    validate_dataset(data)
    if not isinstance(methods, list) or not 2 <= len(methods) <= 12:
        raise ValueError("comparison requires 2..12 predeclared methods")
    seen_ids, seen_settings = set(), set()
    # Validate all method specifications before calibration can spend any API call.
    for method in methods:
        if not isinstance(method, dict) or set(method) - {"id", "detector", "config", "fixed_threshold"}:
            raise ValueError("invalid comparison method specification")
        key = method.get("id")
        if not isinstance(key, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", key) or key in seen_ids:
            raise ValueError("comparison method IDs must be unique simple names")
        settings_hash = digest([method.get("detector"), method.get("config", {}), method.get("fixed_threshold")])
        if settings_hash in seen_settings:
            raise ValueError("duplicate comparison method settings")
        seen_ids.add(key);seen_settings.add(settings_hash)
        if not isinstance(method.get("detector"), str):
            raise ValueError("comparison detector name is required")
        inference_policy(data["samples"], method["detector"], method.get("config", {}), allow_remote)
        if "fixed_threshold" in method and (type(method["fixed_threshold"]) not in (int, float)
                                             or not 0 <= method["fixed_threshold"] <= 1):
            raise ValueError("invalid comparison fixed threshold")
    protocols = {m["id"]: freeze(data, m["detector"], m.get("config", {}), policy,
                                allow_remote=allow_remote, fixed_threshold=m.get("fixed_threshold")) for m in methods}
    for protocol in protocols.values():
        verify_protocol(data, protocol)
    result = {"schema_version": 1, "kind": "detector-comparison", "dataset_id": data["dataset_id"],
              "dataset_sha256": digest(data), "purpose": data["purpose"], "protocols": protocols,
              "created_at": datetime.now(timezone.utc).isoformat(),
              "selection_policy": "all methods/thresholds declared before test; no winner selection on test"}
    result["comparison_sha256"] = digest(result)
    return result


def verify_comparison(data, frozen):
    if frozen.get("schema_version") != 1 or frozen.get("kind") != "detector-comparison":
        raise ValueError("invalid frozen comparison")
    if frozen.get("comparison_sha256") != digest({k: v for k, v in frozen.items() if k != "comparison_sha256"}):
        raise ValueError("comparison changed after freezing")
    if frozen["dataset_sha256"] != digest(data):
        raise ValueError("comparison dataset changed after freezing")
    if not isinstance(frozen.get("protocols"), dict) or not 2 <= len(frozen["protocols"]) <= 12:
        raise ValueError("comparison protocols missing")
    groups = validate_dataset(data)
    for protocol in frozen["protocols"].values():
        verify_protocol(data, protocol)
    return groups


def evaluate_comparison(data, frozen, *, allow_remote=False):
    """Preflight every method, claim test texts once, run all frozen protocols."""
    groups = verify_comparison(data, frozen)
    test = [r for r in data["samples"] if r["split"] == "test"]
    for protocol in frozen["protocols"].values():
        inference_policy(test, protocol["detector"]["name"], protocol["detector"]["config"], allow_remote)
    access = {"comparison_sha256": frozen["comparison_sha256"], "dataset_sha256": digest(data),
              "protocol_sha256s": [p["protocol_sha256"] for p in frozen["protocols"].values()],
              "accessed_at": datetime.now(timezone.utc).isoformat(), "purpose": data["purpose"]}
    paths = _test_paths(test)
    if any(path.exists() for path in paths.values()):
        raise ValueError("locked test has already been consumed")
    for path in paths.values():
        write_new(path, access)
    reports = {}
    for key, protocol in frozen["protocols"].items():
        verify_protocol(data, protocol)  # Another method cannot change code/artifacts mid-comparison.
        reports[key] = _evaluate_claimed(data, protocol, groups, access, allow_remote=allow_remote,
                                         comparison_sha256=frozen["comparison_sha256"])
    for protocol in frozen["protocols"].values():
        verify_protocol(data, protocol)
    result = {"schema_version": 1, "kind": "detector-comparison-result", "comparison": frozen,
              "reports": reports, "test_access": access, "completed_at": datetime.now(timezone.utc).isoformat(),
              "quality": {"passed": all(r["quality"]["passed"] for r in reports.values())},
              "selection_policy": frozen["selection_policy"]}
    result["report_sha256"] = digest(result)
    return result


def verify_comparison_report(result):
    """Verify every declared member; dropping a weak result invalidates the comparison."""
    if result.get("kind") != "detector-comparison-result" or result.get("schema_version") != 1:
        raise ValueError("invalid comparison report")
    if result.get("report_sha256") != digest({k: v for k, v in result.items() if k != "report_sha256"}):
        raise ValueError("comparison report changed")
    frozen = result["comparison"]
    if frozen["comparison_sha256"] != digest({k: v for k, v in frozen.items() if k != "comparison_sha256"}):
        raise ValueError("frozen comparison changed")
    if set(result["reports"]) != set(frozen["protocols"]):
        raise ValueError("comparison reports do not cover every predeclared method")
    metrics = {}
    passed = True
    for key, report in result["reports"].items():
        if report.get("comparison_sha256") != frozen["comparison_sha256"] or report["protocol"] != frozen["protocols"][key]:
            raise ValueError("comparison member protocol changed")
        metrics[key] = verify_report(report)
        if report["test_access"] != result["test_access"]:
            raise ValueError("comparison access record changed")
        failures = quality_failures(metrics[key], QualityPolicy(**report["protocol"]["policy"]),
                                    independent=report["protocol"]["purpose"] == "validation")
        if not report["protocol"]["detector"]["snapshot_verified"]:
            failures.append("external model weights/response identity not fully pinned")
        if report["quality"] != {"passed": not failures, "failures": failures}:
            raise ValueError("comparison member quality changed")
        passed = passed and not failures
    if result["quality"] != {"passed": bool(passed)}:
        raise ValueError("comparison quality changed")
    return metrics
