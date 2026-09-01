#!/usr/bin/env python
"""Whether a smaller encoder can do the embedding detector's job.

The embedding detector is the only reading that works on Italian: measured
2026-09-01 on the held-out half, offline recall there is 14.3% and embedding
is 100%. It is also the reading nobody can afford - 359 ms a block and a
model that unpacks to hundreds of megabytes beside a binary that is meant to
be downloaded.

So this script asks one question about a candidate model and answers it in
numbers, not impressions:

    precision, recall (overall and per language), false alarms,
    milliseconds per block, and megabytes on disk.

The acceptance criteria were set by the owner on 2026-09-01, before any
candidate was tried, which is the only order in which a criterion means
anything:

    Italian recall  >= 80%
    precision       == 100%
    per block       <= 50 ms
    on disk         <  100 MB

A candidate that misses one of those is reported with the number it missed
it by. Nothing here changes a default; swapping the model is a separate
decision that this table is the evidence for.

    python scripts/embedding-models.py                     # every candidate
    python scripts/embedding-models.py --model NAME ...    # named ones
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from corpus_split import split  # noqa: E402
from detectors.embedding import DEFAULT_MODEL, EmbeddingDetector  # noqa: E402
from lang_detect import guess_language_safe  # noqa: E402
from models import TextBlock  # noqa: E402
from scripts.calibrate import load  # noqa: E402

#: The owner's criteria, fixed before measuring.
WANTED = {"italian_recall": 0.80, "precision": 1.0, "ms_per_block": 50.0,
          "disk_mb": 100.0}

#: A quantised build of the incumbent, expressed the way `SentenceTransformer`
#: takes it. The only realistic route to a model under 100 MB that this
#: measurement found: every off-the-shelf multilingual encoder carries the
#: XLM-R vocabulary, and 250k x 384 float32 is 384 MB before a single
#: transformer layer. int8 is that same matrix at a quarter of the size.
#:
#: It costs a runtime: `onnxruntime` has to be installed and, for a frozen
#: bundle, shipped. That is a decision, not a detail, which is why this is a
#: candidate to be measured rather than a default that was changed.
ONNX_QUANTISED = {
    "backend": "onnx",
    "model_kwargs": {"file_name": "onnx/model_qint8_arm64.onnx"},
}

#: Candidates, most promising first. Every one is multilingual - a model that
#: cannot read Italian fails the one thing this detector is for - and every
#: one is smaller or faster than the incumbent in some measurable way.
CANDIDATES = (
    DEFAULT_MODEL,
    "sentence-transformers/static-similarity-mrl-multilingual-v1",
    "sentence-transformers/distiluse-base-multilingual-cased-v2",
    "intfloat/multilingual-e5-small",
)


def _cache_mb(model_name: str) -> float:
    """What this model costs on disk, from the HuggingFace cache."""
    stem = "models--" + model_name.replace("/", "--")
    root = Path.home() / ".cache" / "huggingface" / "hub" / stem
    if not root.is_dir():
        # Some names resolve under the `sentence-transformers/` org even when
        # written bare, which is how the incumbent is spelled everywhere else.
        root = (Path.home() / ".cache" / "huggingface" / "hub" /
                f"models--sentence-transformers--{model_name}")
    if not root.is_dir():
        return 0.0
    total = sum(path.stat().st_size for path in root.rglob("*")
                if path.is_file() and not path.is_symlink())
    return total / (1024 * 1024)


def _score(detector, rows: list) -> list:
    """The highest style score this detector gives each entry.

    Character findings are dropped for the same reason `calibrate.score_rows`
    drops them: a curly apostrophe in good human copy is not a missed
    detection of AI writing.
    """
    scored = []
    for index, row in enumerate(rows):
        block = TextBlock(block_id=f"row-{index}", text=row["text"],
                          page_url="corpus://labelled", dom_path="",
                          language_hint=guess_language_safe(row["text"]))
        spans = [s for s in detector.analyze_block(block)
                 if (s.details or {}).get("source") != "characters"]
        scored.append({**row,
                       "score": max((s.score for s in spans), default=0.0)})
    return scored


def _rates(scored: list, threshold: float) -> dict:
    hits = [r for r in scored if r["score"] >= threshold]
    models = [r for r in scored if r["label"] == "model"]
    flagged_model = [r for r in hits if r["label"] == "model"]
    return {
        "precision": (len(flagged_model) / len(hits)) if hits else None,
        "recall": (len(flagged_model) / len(models)) if models else None,
        "false_alarms": len(hits) - len(flagged_model),
        "humans": sum(1 for r in scored if r["label"] == "human"),
        "models": len(models),
    }


def _best_threshold(scored: list) -> float:
    """The lowest cut-off at which nothing human is flagged.

    The same rule the incumbent's 0.55 was chosen by: precision first, then
    as much recall as precision allows. Swept over the scores themselves, so
    the answer is a value the data actually produced.
    """
    steps = sorted({round(r["score"], 3) for r in scored if r["score"] > 0})
    best = 1.0
    for cut in steps:
        rates = _rates(scored, cut)
        if rates["precision"] == 1.0:
            best = cut
            break
    return best


def _pct(value) -> str:
    return "  n/a" if value is None else f"{value * 100:5.1f}%"


def measure(model_name: str, rows: list, onnx: bool = False) -> dict:
    train, test = split(rows)
    if onnx:
        # `EmbeddingDetector` builds the model from its name alone, so the
        # backend is applied to the object it built rather than passed
        # through a constructor that has no argument for it.
        from sentence_transformers import SentenceTransformer

        detector = EmbeddingDetector(model_name=model_name, threshold=0.0)
        detector._model = SentenceTransformer(model_name, **ONNX_QUANTISED)
    else:
        detector = EmbeddingDetector(model_name=model_name, threshold=0.0)
    started = time.monotonic()
    scored = _score(detector, test)
    seconds = time.monotonic() - started
    threshold = _best_threshold(scored)
    overall = _rates(scored, threshold)
    per_language = {
        language: _rates([r for r in scored if r.get("language") == language],
                         threshold)
        for language in sorted({r.get("language") for r in scored} - {None})
    }
    return {
        "model": model_name,
        "threshold": threshold,
        "overall": overall,
        "languages": per_language,
        "ms_per_block": seconds * 1000 / max(len(test), 1),
        "disk_mb": _cache_mb(model_name),
        "entries": len(test),
    }


def verdict(result: dict) -> list:
    """Every criterion this candidate misses, with the number it missed by."""
    misses = []
    italian = result["languages"].get("it", {}).get("recall")
    if italian is None or italian < WANTED["italian_recall"]:
        misses.append(f"Italian recall {_pct(italian).strip()} "
                      f"< {WANTED['italian_recall'] * 100:.0f}%")
    precision = result["overall"]["precision"]
    if precision is None or precision < WANTED["precision"]:
        misses.append(f"precision {_pct(precision).strip()} < 100%")
    if result["ms_per_block"] > WANTED["ms_per_block"]:
        misses.append(f"{result['ms_per_block']:.0f} ms/block "
                      f"> {WANTED['ms_per_block']:.0f} ms")
    if result["disk_mb"] == 0.0:
        misses.append("size unknown (not in the local cache)")
    elif result["disk_mb"] >= WANTED["disk_mb"]:
        misses.append(f"{result['disk_mb']:.0f} MB on disk "
                      f">= {WANTED['disk_mb']:.0f} MB")
    return misses


def report(result: dict) -> None:
    print(f"\n{result['model']}")
    print(f"  threshold {result['threshold']:.3f} on {result['entries']} "
          f"held-out entries")
    overall = result["overall"]
    print(f"  overall   precision {_pct(overall['precision'])}   "
          f"recall {_pct(overall['recall'])}   "
          f"false alarms {overall['false_alarms']}/{overall['humans']}")
    for language, rates in result["languages"].items():
        print(f"  {language:9} precision {_pct(rates['precision'])}   "
              f"recall {_pct(rates['recall'])}   "
              f"({rates['models']} positives)")
    print(f"  {result['ms_per_block']:.0f} ms/block, "
          f"{result['disk_mb']:.0f} MB on disk")
    misses = verdict(result)
    print("  accepted" if not misses else "  rejected: " + "; ".join(misses))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--onnx", action="store_true",
                        help="load the int8 ONNX build of the named model "
                             "(needs `onnxruntime`, which a bundle would "
                             "have to ship)")
    parser.add_argument("--model", action="append", default=None,
                        help="a candidate to measure (repeatable); "
                             "default: every name in CANDIDATES")
    args = parser.parse_args()

    rows = load("labelled.jsonl")
    if not rows:
        print("corpus/labelled.jsonl is empty; nothing to measure against")
        return 1
    failures = 0
    for model_name in (args.model or list(CANDIDATES)):
        try:
            report(measure(model_name, rows, onnx=args.onnx))
        except Exception as exc:  # noqa: BLE001 - a candidate that will not
            # load is a result about that candidate, not a crash of the run.
            print(f"\n{model_name}\n  unavailable: {exc}")
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
