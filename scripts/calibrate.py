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
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from corpus_split import split  # noqa: E402
from detectors.factory import DetectorFactory  # noqa: E402
from lang_detect import guess_language_safe  # noqa: E402
from models import TextBlock, score_to_confidence  # noqa: E402

CORPUS = ROOT / "corpus"


def needs_holdout(detector_name: str) -> bool:
    """Whether the whole-corpus number for this detector would be a lie.

    True when the detector is built out of the corpus. Its reference is the tune
    half, so the tune half cannot also be scored: those entries are in the set
    they would be compared against, and the margin against a set containing the
    text is +/-1 by construction.
    """
    detector_cls = DetectorFactory.lookup(detector_name)
    return bool(detector_cls is not None and detector_cls.uses_corpus_as_reference)


#: What the window treats as worth showing, for a detector that does not carry
#: a cut-off of its own.
_WINDOW_BAND = 0.33


def live_threshold(detector_name: str) -> float:
    """The cut-off this detector applies in a run.

    Read off the detector rather than passed in, because a report printed at
    some other number describes a detector nobody is running.
    """
    try:
        return float(DetectorFactory.create(detector_name).threshold)
    except Exception:
        return _WINDOW_BAND


def load(name: str) -> list:
    path = CORPUS / name
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def score_rows(rows: list, detector_name: str = "offline",
               **detector_config) -> list:
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
    detector = DetectorFactory.create(detector_name, **detector_config)
    scored = []
    for index, row in enumerate(rows):
        # The hint a **run** would carry, not the corpus's own `language`.
        # The corpus knows the true language; a scan does not, it calls
        # `guess_language_safe` in `crawler._make_block`, and handing the
        # detector the truth measures a detector nobody has.
        #
        # It was not a rounding difference. Measured 2026-08-31: Italian
        # recall read 61.1% with the true label and **50.0%** with the label a
        # run produces, because two Italian positives contain none of the
        # original Italian markers and were read as English, which switched
        # off the Italian cliché list. Calibration overstated live Italian
        # recall by 11 points and nothing said so. The gap is closed now (the
        # marker list was extended), and this line is what keeps it closed:
        # a future gap shows up as a number here instead of on a live page.
        #
        # `row["language"]` still decides which language a row is *reported*
        # under - that is ground truth and stays ground truth.
        block = TextBlock(block_id=f"row-{index}", text=row["text"],
                          page_url="corpus://labelled", dom_path="",
                          language_hint=guess_language_safe(row["text"]))
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


#: Below this many entries on a side, that side's number is a statement about
#: the corpus, not about the detector. Italian at 25+ words sat at 2 negatives
#: while the report printed the same confident 0/2 it prints for 125, which is
#: how a measurement ceiling reads as a result.
#:
#: It applies to **both** sides, and the positive side is the one that was
#: missed. Measured 2026-08-31 while re-auditing `P-02`: the negatives at 25+
#: words went 21 -> 116 when the encyclopedic paragraphs were added, and the
#: ceiling did not disappear, it moved. The model side of that band is 16
#: entries - 8 English, 6 Italian, **2 Ukrainian** - and `recall 100.0%` off
#: two entries printed exactly like `recall 100.0%` off forty-five.
_THIN = 10


def _show(label: str, stats: dict) -> None:
    def pct(value):
        return "  n/a" if value is None else f"{value * 100:5.1f}%"

    notes = []
    if 0 < stats["humans"] < _THIN:
        notes.append(f"{stats['humans']} negatives")
    if 0 < stats["models"] < _THIN:
        notes.append(f"{stats['models']} positives")
    thin = f" - too few to read: {', '.join(notes)}" if notes else ""
    print(f"  {label:22} precision {pct(stats['precision'])}   "
          f"recall {pct(stats['recall'])}   "
          f"false alarms {stats['false_alarms']}/{stats['humans']}{thin}")


#: The word-count bands the corpus is read in. They exist because the two
#: halves are not the same length: the human half is largely interface strings
#: and the model half is paragraphs, so a recall number computed over the whole
#: corpus is partly a statement about length. Inside a band length is roughly
#: held still, and what is left is the writing.
_STRATA = (
    ("under 10 words", 0, 10),
    ("10-24 words", 10, 25),
    ("25+ words", 25, None),
)


def _in_stratum(row: dict, low: int, high) -> bool:
    words = len(_words_of(row["text"]))
    return words >= low and (high is None or words < high)


def length_only_baseline(rows: list) -> tuple:
    """The best `(cut, precision, recall)` a word count alone can reach.

    A single rule - "flag everything at least this long" - swept over every
    cut-off. It knows nothing about writing, so it is the line any real signal
    has to clear: a feature that scores no better than this has not been shown
    to detect anything except that generated copy tends to be longer.
    """
    models = [r for r in rows if r["label"] == "model"]
    best = (0, 0.0, 0.0)
    for cut in range(3, 60):
        flagged = [r for r in rows if len(_words_of(r["text"])) >= cut]
        if not flagged or not models:
            continue
        hits = [r for r in flagged if r["label"] == "model"]
        precision = len(hits) / len(flagged)
        if precision > best[1]:
            best = (cut, precision, len(hits) / len(models))
    return best


def strata(scored: list, threshold: float) -> None:
    """The same threshold, read inside comparable lengths.

    Without this, every recall figure in this report means something slightly
    different per language, because the languages' negatives are not the same
    size: the Italian human median was 37 characters against Ukrainian's 65,
    which is the difference between a button label and a sentence. Reading the
    bands is also what showed that the Italian false-alarm rate rested on two
    entries; dated Italian prose was added to the corpus because of it.

    Each band also prints what flagging *everything* in it would score. That is
    the base rate, and a detector whose precision inside a band equals it is
    not separating anything there - it is only agreeing with the band.
    """
    print("by length, at the same threshold")
    for name, low, high in _STRATA:
        band = [r for r in scored if _in_stratum(r, low, high)]
        if not band:
            print(f"  {name}: empty")
            continue
        stats = _rates(band, threshold)
        base = stats["models"] / len(band) * 100
        print(f"  {name}: {stats['models']} model, {stats['humans']} human, "
              f"flag-everything precision {base:5.1f}%")
        _show("all languages", stats)
        for language in sorted({r.get("language", "?") for r in band}):
            subset = [r for r in band if r.get("language") == language]
            _show(language, _rates(subset, threshold))
    print("  a band with no model entries can show no recall, and a band with "
          "two can show any recall at all: that is the corpus speaking, not "
          "the detector.")


def registers(scored: list, threshold: float) -> None:
    """Read the same detector by corpus register, never calling it genre data.

    The labelled corpus carries `register` rather than a guessed literary
    genre. Keeping that field's name matters: product copy, documentation and
    encyclopedic prose can be compared, but this cannot make a claim about a
    genre the corpus did not label. Thin samples retain the same warning as
    language and length reports.
    """
    groups: dict[str, list] = {}
    for row in scored:
        register = str(row.get("register") or "unlabelled register")
        groups.setdefault(register, []).append(row)
    print("by register")
    for register, subset in sorted(groups.items()):
        print(f"  {register}: {len(subset)} entries")
        _show("all languages", _rates(subset, threshold))
        for language in sorted({row.get("language", "?") for row in subset}):
            _show(language, _rates([row for row in subset
                                    if row.get("language") == language], threshold))


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
    strata(scored, threshold)

    print()
    registers(scored, threshold)

    print()
    cut, precision, recall = length_only_baseline(scored)
    print(f"length alone tops out at precision {precision * 100:.1f}% "
          f"(words>={cut}, recall {recall * 100:.1f}%)")
    print("  read the numbers above against that line, not against zero.")

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

    It was measuring length, because the human half was largely interface
    strings - "Save", "Carica file" - which contain no conjunctions because
    they contain no clauses. Conditioned on entries of 25 words or more, the
    difference reverses: humans coordinate *more* than models do.

    Re-measured 2026-08-31, after 95 encyclopedic paragraphs took the human
    side of that band from 21 entries to 116. The reversal held and got
    firmer - model 3.33 per 100 words against human 4.21, and humans ahead in
    each language separately (en -3.23, uk -2.00, it -0.46). What the larger
    corpus changed is which side is now too thin: 16 model entries at 25+
    words, two of them Ukrainian.

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

    cut, precision, recall = length_only_baseline(rows)
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
    parser.add_argument("--threshold", type=float, default=None,
                        help="defaults to the cut-off this detector actually "
                             "uses, so the report is about what runs")
    parser.add_argument("--sweep", action="store_true")
    parser.add_argument("--review", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--confounds", action="store_true",
                        help="what length alone scores, before believing a signal")
    parser.add_argument("--holdout", action="store_true",
                        help="report the tune half and the held-out half apart")
    args = parser.parse_args()
    if args.threshold is None:
        args.threshold = live_threshold(args.detector)

    if args.review:
        review(args.detector, args.limit)
        return 0

    rows = load("labelled.jsonl")
    if not rows:
        print("corpus/labelled.jsonl is empty; nothing to calibrate against")
        return 1

    if needs_holdout(args.detector):
        if not args.holdout:
            print(f"'{args.detector}' builds its answer out of this corpus, so a "
                  f"number over the whole corpus would be it recognising itself.")
            print("  Re-run with --holdout: the tune half becomes its reference "
                  "and the held-out half is what gets scored.")
            return 1
        train_rows, test_rows = split(rows)
        config = DetectorFactory.lookup(args.detector).calibration_config()
        scored = score_rows(test_rows, args.detector, **config)
        if args.confounds:
            confounds(scored, args.threshold)
        print(f"reference: the tune half ({len(train_rows)} entries), which the "
              f"detector reads in a run too. It cannot also be scored.")
        print(f"held out ({len(scored)} entries) - the only number there is")
        report(scored, args.threshold)
        print()
        if args.sweep:
            sweep(scored)
        return 0

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
