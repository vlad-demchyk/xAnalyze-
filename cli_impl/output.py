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
    terminal — an empty-looking finding is worse than useless."""
    out = []
    for ch in text:
        if ch.isprintable() and not unicode_rules.INVISIBLE_CHARS.get(ch) == "":
            out.append(ch)
        else:
            out.append(f"<U+{ord(ch):04X}>")
    return "".join(out)


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


def _print_human(findings, walked=None) -> None:
    coverage = _coverage_line(walked)
    if not findings:
        print("No findings.")
        if coverage:
            print(coverage)
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
