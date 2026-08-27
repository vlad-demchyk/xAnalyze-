"""Terminal output for the CLI: JSON payloads, human-readable listings,
coverage lines and the visible-character rendering invisible findings need.
"""
from __future__ import annotations

import json

import duplicates
import unicode_rules


def _public(finding: dict) -> dict:
    return {k: v for k, v in finding.items() if not k.startswith("_")}


def _counts(findings) -> dict:
    counts: dict[str, int] = {}
    for f in findings:
        key = f["detector"]
        counts[key] = counts.get(key, 0) + 1
    counts["total"] = len(findings)
    counts["files"] = len({f["file"] for f in findings})
    # How many of those are the same text in a copy of the same file. A
    # project that keeps its build output beside its source reports every
    # defect once per copy, and the difference between the two numbers is
    # the only warning a reader gets that this is happening.
    counts["distinct"] = len(duplicates.group(findings))
    return counts


def _print_json(findings, applied=None, walked=None) -> None:
    payload = {
        "findings": [_public(f) for f in findings],
        "counts": _counts(findings),
    }
    if walked:
        # What was read, beside what was found. `counts.files` counts files
        # among the *findings*, so without this an empty result cannot say
        # whether it read 161 files or none.
        payload["read"] = [
            {
                "root": root,
                "files_read": walk.files_read,
                "blocks_found": walk.blocks_found,
                "skipped_ignored": walk.skipped_ignored,
                "skipped_too_large": walk.skipped_too_large,
                "unreadable": walk.unreadable,
                "truncated": walk.truncated,
                "limit": walk.limit,
            }
            for root, walk in walked
        ]
    if applied is not None:
        payload["applied"] = applied
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _visible(text: str) -> str:
    """Render a match so invisible characters are still readable in a
    terminal — an empty-looking finding is worse than useless.

    The rule itself lives beside the table of invisible characters now that
    the replacement list needs the same rendering; this stays as the name the
    terminal output already calls it by.
    """
    return unicode_rules.visible(text)


def _coverage_line(walked) -> str:
    """One sentence about what was actually opened.

    Printed whether or not anything was found, because the number that
    matters when nothing was found is this one.
    """
    if not walked:
        return ""
    files = sum(w.files_read for _root, w in walked)
    blocks = sum(w.blocks_found for _root, w in walked)
    skipped = sum(w.skipped_ignored for _root, w in walked)
    line = f"Read {files} file(s), {blocks} block(s) of text; {skipped} skipped by exclusions."
    truncated = [(root, w) for root, w in walked if w.truncated]
    for root, w in truncated:
        line += (f"\n! {root}: stopped at the {w.limit}-file limit - everything "
                 f"past it was not examined. Raise it with --max-files.")
    return line


#: What a `technical` scan is honestly able to say about style, printed
#: alongside the result. Measured before it was written (`P-09`): the offline
#: pass reported **zero** cliche or statistical findings over 7225 comment
#: blocks in `~/repositories/XFormat` and 55756 in this repository. Not a
#: threshold that happened to sit high - `CLICHE_PHRASES` in
#: `detectors/heuristic.py` is a marketing-copy list, and `heuristic.py`'s
#: floor pins any statistics-only score to 0.32, below reporting. So the
#: stylistic half of this mode is silent on comments by construction.
#:
#: Said rather than fixed with a second dictionary, because there is no
#: corpus of comments with a known author to build one against, and a list
#: assembled from examples would be calibrated to whoever assembled it. A
#: scan that reports nothing and explains why is more use than one that
#: reports nothing and looks clean.
TECHNICAL_STYLE_CAVEAT = (
    "! --scope technical: the character checks ran, the style checks did not "
    "say anything. The phrase list behind them is built from marketing copy "
    "and is not calibrated for comments or docstrings, so treat a quiet "
    "result here as 'not measured', not as 'clean'."
)


def technical_scope_note(scope: str, findings) -> str:
    """The caveat, when a technical scan produced no stylistic finding.

    Suppressed when the pass did say something: at that point the reader has
    a finding to judge, and a warning that the check is uncalibrated is more
    usefully attached to the finding than to the run.
    """
    if scope not in ("technical", "both"):
        return ""
    for finding in findings:
        details = finding.get("details") or {}
        if details.get("cliches") or details.get("source") == "model":
            return ""
    return TECHNICAL_STYLE_CAVEAT


def _print_human(findings, walked=None, scope: str = "content") -> None:
    coverage = _coverage_line(walked)
    note = technical_scope_note(scope, findings)
    if not findings:
        print("No findings.")
        if coverage:
            print(coverage)
        if note:
            print(note)
        return
    current = None
    # One row per distinct finding, with its copies named under it. Nothing
    # is dropped - see `duplicates.py` for why the copies still have to be
    # in the list even though they are not printed as separate rows.
    for f, others in duplicates.group(findings):
        if f["file"] != current:
            current = f["file"]
            print(f"\n{current}")
        rep = "" if f["replacement"] is None else f"  ->  {f['replacement']!r}"
        print(f"  line {f['line']:>4}  [{f['confidence']}]  {_visible(f['text'])!r}{rep}")
        print(f"              {f['explanation']}")
        if others:
            print(f"              same text in {len(others)} other file(s):")
            for copy in duplicates.copies_of(f, others)[:3]:
                print(f"                {copy}")
            if len(others) > 3:
                print(f"                ... and {len(others) - 3} more")
    c = _counts(findings)
    distinct = len(duplicates.group(findings))
    tail = "" if distinct == c["total"] else f" ({distinct} distinct)"
    print(f"\n{c['total']} finding(s) in {c['files']} file(s){tail}.")
    if coverage:
        print(coverage)
    if note:
        print(note)
