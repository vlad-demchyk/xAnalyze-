#!/usr/bin/env python
"""Inspect, partition, freeze and evaluate an independent detector benchmark."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from validation.corpus import assign_splits, load_dataset, strict_json, validate_dataset  # noqa: E402
from validation.metrics import QualityPolicy  # noqa: E402
from validation.protocol import evaluate, freeze, write_new  # noqa: E402
from validation.transforms import add_unicode_variants  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("inspect", "partition", "unicode", "freeze", "run"):
        p = sub.add_parser(command)
        p.add_argument("dataset", type=Path)
        if command != "inspect":
            p.add_argument("--output", type=Path, required=True)
        if command == "partition":
            p.add_argument("--seed", required=True)
        if command in ("freeze", "run"):
            p.add_argument("--allow-remote", action="store_true",
                           help="explicitly permit inference on exclusively public benchmark text")
        if command == "freeze":
            p.add_argument("--detector", default="offline")
            p.add_argument("--config", type=Path)
            p.add_argument("--policy", type=Path)
            p.add_argument("--fixed-threshold", type=float)
        if command == "run":
            p.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if getattr(args, "output", None) and args.output.exists():
            raise ValueError("output already exists; reports/protocols are never overwritten")
        if args.command == "partition":
            data = strict_json(args.dataset.read_text())
            result = assign_splits(data, args.seed)
        else:
            data = load_dataset(args.dataset)
            if args.command == "inspect":
                groups = validate_dataset(data)
                print(json.dumps({"dataset_id": data["dataset_id"], "purpose": data["purpose"],
                    "samples": len(data["samples"]), "groups": len(set(groups.values())),
                    "splits": {s: sum(r["split"] == s for r in data["samples"]) for s in ("reference", "calibration", "test")}}, indent=2))
                return 0
            if args.command == "unicode":
                result = add_unicode_variants(data)
            elif args.command == "freeze":
                config = strict_json(args.config.read_text()) if args.config else {}
                policy = QualityPolicy(**strict_json(args.policy.read_text())) if args.policy else QualityPolicy()
                result = freeze(data, args.detector, config, policy, allow_remote=args.allow_remote, fixed_threshold=args.fixed_threshold)
            else:
                protocol = strict_json(args.protocol.read_text())
                result = evaluate(data, protocol, allow_remote=args.allow_remote)
        write_new(args.output, result)
        print(json.dumps({"output": str(args.output), "quality": result.get("quality"),
                          "protocol_sha256": result.get("protocol_sha256")}, indent=2))
        return 2 if args.command == "run" and not result["quality"]["passed"] else 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
