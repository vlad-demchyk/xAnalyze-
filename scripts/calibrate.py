#!/usr/bin/env python
"""What the detector's scores are actually worth.

A threshold moved by feel is a different arbitrary number, not a better one. So
this scores a corpus whose authors are known and prints the two numbers that
decide whether a band is usable:

  precision  of what it flags, how much is really model-written. Low precision
             is how a tool gets switched off - one wrong flag costs more trust
             than three right ones earn.
  recall     of what is model-written, how much it flags. Low recall is how a
             tool gets trusted for the wrong reason: a clean report that means
             nothing was looked at hard enough.

Both are reported per language, because the detector's features are not
language-neutral: sentence rhythm and cliché lists are built per language, and a
number averaged across them hides which one is broken.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from detectors.factory import DetectorFactory  # noqa: E402
from models import TextBlock, score_to_confidence  # noqa: E402

CORPUS = ROOT / "corpus"


def split(rows: list) -> tuple:
    """Deterministic halves: one to tune against, one to be judged by.

    By a hash of the text, so the split does not move when entries are added or
    reordered. The reason for having it at all: phrase lists are trivially
    tunable to whatever they were shown, and a number produced on the text used
    to tune them measures memory rather than detection.
    """
    train, test = [], []
    for row in rows:
        digest = hashlib.sha1(row["text"].encode("utf-8")).digest()[0]
        (train if digest % 2 == 0 else test).append(row)
    return train, test


def load(name: str) -> list:
    path = CORPUS / name
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def score_rows(rows: list, detector_name: str = "offline") -> list:
    """Attach the highest style score the detector gives each entry.

    Style only. The offline detector answers two questions at once - "does this
    read as model-written" and "does this contain characters no keyboard
    produces" - and they are not the same question. Mixing them made a curly
    apostrophe in perfectly good human copy score 0.50 and count as a missed
    detection of AI writing, which would have sent this whole calibration in
    the wrong direction.

    Highest, not mean: the detector reports per sentence and the window flags a
    passage if any sentence in it scores, so the number that decides what the
    user sees is the maximum.
    """
    detector = DetectorFactory.create(detector_name)
    scored = []
    for index, row in enumerate(rows):
        block = TextBlock(block_id=f"row-{index}", text=row["text"],
                          page_url="corpus://labelled", dom_path="",
                          language_hint=row.get("language") or "")
        spans = [s for s in detector.analyze_block(block)
                 if (s.details or {}).get("source") != "characters"]
        score = max((s.score for s in spans), default=0.0)
        scored.append({**row, "score": score,
                       "confidence": score_to_confidence(score).value})
    return scored


def _rates(scored: list, threshold: float) -> dict:
    flagged_model = sum(1 for r in scored if r["label"] == "model" and r["score"] >= threshold)
    flagged_human = sum(1 for r in scored if r["label"] == "human" and r["score"] >= threshold)
    models = sum(1 for r in scored if r["label"] == "model")
    humans = sum(1 for r in scored if r["label"] == "human")
    flagged = flagged_model + flagged_human
    return {
        "threshold": threshold,
        "precision": flagged_model / flagged if flagged else None,
        "recall": flagged_model / models if models else None,
        "false_alarms": flagged_human,
        "humans": humans,
        "models": models,
    }


def _show(label: str, stats: dict) -> None:
    def pct(value):
        return "  n/a" if value is None else f"{value * 100:5.1f}%"

    print(f"  {label:22} precision {pct(stats['precision'])}   "
          f"recall {pct(stats['recall'])}   "
          f"false alarms {stats['false_alarms']}/{stats['humans']}")


def report(scored: list, threshold: float) -> None:
    print(f"at threshold {threshold}")
    _show("all languages", _rates(scored, threshold))
    for language in sorted({r.get("language", "?") for r in scored}):
        subset = [r for r in scored if r.get("language") == language]
        if not any(r["label"] == "human" for r in subset):
            print(f"  {language:22} no human-labelled text: precision cannot be "
                  f"measured, only recall {(_rates(subset, threshold)['recall'] or 0) * 100:.1f}%")
            continue
        _show(language, _rates(subset, threshold))

    print()
    print("score distribution")
    for label in ("model", "human"):
        values = sorted(r["score"] for r in scored if r["label"] == label)
        if not values:
            continue
        middle = values[len(values) // 2]
        print(f"  {label:6} n={len(values):3}  min {values[0]:.2f}  "
              f"median {middle:.2f}  max {values[-1]:.2f}")


def sweep(scored: list) -> None:
    print("threshold sweep")
    print("  thr   precision  recall  false alarms")
    for step in range(2, 14):
        threshold = step / 20
        stats = _rates(scored, threshold)
        precision = "n/a" if stats["precision"] is None else f"{stats['precision']*100:5.1f}%"
        recall = "n/a" if stats["recall"] is None else f"{stats['recall']*100:5.1f}%"
        print(f"  {threshold:.2f}   {precision:>8}  {recall:>6}  "
              f"{stats['false_alarms']}/{stats['humans']}")


def review(detector_name: str, limit: int) -> None:
    """The unlabelled pool, highest score first.

    For a person who knows who wrote it. Nothing here counts towards a metric
    until someone says which label it carries.
    """
    rows = load("unlabelled.jsonl")
    if not rows:
        print("no unlabelled pool")
        return
    scored = sorted(score_rows(rows, detector_name), key=lambda r: -r["score"])
    print(f"unlabelled, {len(scored)} entries, highest score first")
    for row in scored[:limit]:
        print(f"  {row['score']:.2f} [{row['confidence']:6}] {row['language']}  "
              f"{row['text'][:96]}")


def confounds(rows: list, threshold: float) -> None:
    """Is the corpus measuring writing, or is it measuring length?

    This exists because a candidate signal passed and should not have. The
    2026 dependency-parse literature names clause coordination as a syntactic
    marker of generated text, and on this corpus it looked decisive: model
    entries averaged 4.2 coordinating conjunctions per 100 words against a
    human median of 0.00, in all three languages at once.

    It was measuring length. Model entries here run to a median of 19 words
    and human entries to 9, because the human half is largely interface
    strings - "Save", "Carica file" - which contain no conjunctions because
    they contain no clauses. Conditioned on entries of 25 words or more, the
    difference reverses: humans coordinate *more* than models do.

    So this reports the two things that make such a mistake visible, and both
    should be read before any new signal is believed:

    * how far apart the two halves are in length, and
    * what a classifier that knows *only* the length can score.

    A signal cannot be credited with separating the labels any better than
    length alone does, until it has been checked against comparable lengths.
    """
    lengths = {label: sorted(len(_words_of(r["text"]))
                             for r in rows if r["label"] == label)
               for label in ("model", "human")}
    print("length confound")
    for label, values in lengths.items():
        if not values:
            continue
        print(f"  {label:6} n={len(values):3}  median {values[len(values)//2]:3} words"
              f"  ({values[0]}-{values[-1]})")

    models = [r for r in rows if r["label"] == "model"]
    best_precision = (0, 0.0, 0.0)
    for cut in range(3, 60):
        flagged = [r for r in rows if len(_words_of(r["text"])) >= cut]
        if not flagged or not models:
            continue
        hits = [r for r in flagged if r["label"] == "model"]
        precision = len(hits) / len(flagged)
        recall = len(hits) / len(models)
        if precision > best_precision[1]:
            best_precision = (cut, precision, recall)
    cut, precision, recall = best_precision
    print(f"  a classifier that knows only the length tops out at "
          f"precision {precision*100:.1f}% (words>={cut}, recall {recall*100:.1f}%)")
    print("  read the detector's precision against that line: a signal that "
          "does no better has not been shown to detect writing.")
    print()


def _words_of(text: str) -> list:
    from detectors.heuristic import _words

    return _words(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detector", default="offline")
    parser.add_argument("--threshold", type=float, default=0.33,
                        help="the band the window treats as worth showing")
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--review", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--confounds", action="store_true",
                        help="what length alone scores, before believing a signal")
    parser.add_argument("--holdout", action="store_true",
                        help="report the tune half and the held-out half apart")
    args = parser.parse_args()

    if args.review:
        review(args.detector, args.limit)
        return 0

    rows = load("labelled.jsonl")
    if not rows:
        print("corpus/labelled.jsonl is empty; nothing to calibrate against")
        return 1
    scored = score_rows(rows, args.detector)
    if args.confounds:
        confounds(scored, args.threshold)
    if args.holdout:
        train, test = split(scored)
        print(f"tune half ({len(train)} entries)")
        report(train, args.threshold)
        print()
        print(f"held out ({len(test)} entries) - the only honest number")
        report(test, args.threshold)
        print()
        if args.sweep:
            sweep(test)
        return 0
    report(scored, args.threshold)
    print()
    if args.sweep:
        sweep(scored)
    return 0


if __name__ == "__main__":
    sys.exit(main())
