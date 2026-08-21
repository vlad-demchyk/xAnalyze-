"""Report writing and run history.

A briefing another tool - or an agent - can act on directly: where the work
is concentrated, which files to open, what has already been done, and whether
the situation is getting better or worse. Markdown by default because that is
what a coding agent reads best; `.json` if the suffix asks for it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from models import RepoAnalysisResult


def _write_styled_text_report(files, findings, args) -> None:
    """`scan --styled-report`: the same findings as `--json`, laid out as a
    document for a person instead of a pipeline.

    Rebuilds a `RepoAnalysisResult` from what `_analyze` already computed —
    the actual `FileResult`s and the actual `TextSpan`s it kept under
    `finding["_span"]` — rather than re-scanning: `report.model.
    from_text_analysis` reads that type, and everything it needs was
    produced a few lines up in `cmd_scan`, at no extra cost.
    """
    from report.export import write_styled_report
    from report.model import from_text_analysis

    lang = getattr(args, "language", None) or "en"
    root = args.paths[0] if len(args.paths) == 1 else ", ".join(args.paths)
    result = RepoAnalysisResult(root_dir=root, files=files,
                                spans=[f["_span"] for f in findings])
    write_styled_report(args.styled_report, from_text_analysis(result), lang)
    print(f"# styled report: {args.styled_report}", file=sys.stderr)


def _write_report(result, args, lang: str, fix_outcome=None, ai_findings=None) -> None:
    """Write a briefing another tool - or an agent - can act on directly.

    The plain `--json` output is a list of findings, which is the right shape
    for a pipeline and the wrong shape for an agent about to edit the code. An
    agent needs to know where the work is concentrated, which files to open,
    what has already been done to them, and whether the situation is getting
    better or worse. So this is a different document, not a flag on the same
    one.

    Markdown by default because that is what a coding agent reads best; `.json`
    if the suffix asks for it, for anything that would rather parse than read.
    """
    from audit.explanations import render

    path = Path(args.report)
    history = _read_history(path)
    counts = result.counts()
    entry = {
        "at": _now(),
        "root": result.root,
        "mode": result.mode,
        "counts": counts,
        "documents": len(result.documents),
        "fixed": len(fix_outcome.applied) if fix_outcome else 0,
    }

    # AI pattern statistics (only style findings, not typography/characters)
    ai_stats = {}
    typo_stats = {}
    if ai_findings:
        # Split into style (AI) and typography findings
        style_findings = []
        typo_findings = []
        for f in ai_findings:
            exp = f.get("explanation", "").lower()
            src = f.get("source", "").lower()
            if "typography" in exp or "characters" in src:
                typo_findings.append(f)
            else:
                style_findings.append(f)

        if style_findings:
            ai_stats = {
                "total": len(style_findings),
                "high": len([f for f in style_findings if f.get("confidence") == "high"]),
                "medium": len([f for f in style_findings if f.get("confidence") == "medium"]),
                "low": len([f for f in style_findings if f.get("confidence") == "low"]),
                "files": len({f.get("file", "") for f in style_findings}),
                "top_patterns": [],
            }
            # Top AI patterns by score
            sorted_findings = sorted(style_findings, key=lambda f: f.get("score", 0), reverse=True)
            for f in sorted_findings[:10]:
                ai_stats["top_patterns"].append({
                    "text": f.get("text", "")[:100],
                    "score": f.get("score", 0),
                    "confidence": f.get("confidence", ""),
                    "explanation": f.get("explanation", "")[:120],
                    "file": f.get("file", ""),
                    "line": f.get("line", 0),
                })

        # Typography statistics
        if typo_findings:
            # Group by character type
            by_char = {}
            for f in typo_findings:
                exp = f.get("explanation", "")
                # Extract character name from explanation like "[typography] U+2013 EN DASH -> '-'"
                char_name = exp.split("] ")[-1].split(" ->")[0] if "] " in exp else exp[:50]
                by_char.setdefault(char_name, 0)
                by_char[char_name] += 1
            typo_stats = {
                "total": len(typo_findings),
                "files": len({f.get("file", "") for f in typo_findings}),
                "by_character": dict(sorted(by_char.items(), key=lambda x: -x[1])[:10]),
                "top_examples": [
                    {"text": f.get("text", "")[:80], "explanation": f.get("explanation", "")[:100]}
                    for f in typo_findings[:5]
                ],
            }

    payload = {
        "generated": entry["at"],
        "root": result.root,
        "mode": result.mode,
        "summary": {
            "counts": counts,
            "total": sum(counts.values()),
            "documents": len(result.documents),
            "documents_with_findings": len(result.documents_with_issues()),
            "rules_triggered": len(result.by_rule()),
        },
        "ai_patterns": ai_stats,
        "typography": typo_stats,
        "history": history + [entry],
        "changed_this_run": _fix_summary(fix_outcome),
        "files": _file_map(result, render, lang),
        "by_rule": [
            {"rule": rule, "count": len(issues),
             "severity": issues[0].severity,
             "category": issues[0].category,
             "title": render(issues[0], lang).title,
             "fix": render(issues[0], lang).fix,
             "where": [f"{i.source}:{i.line}" if i.line else i.source
                       for i in issues[:20]]}
            for rule, issues in result.by_rule().items()
        ],
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    else:
        path.write_text(_report_markdown(payload, lang), encoding="utf-8")
    _write_history(path, history + [entry])
    print(f"# report: {path}", file=sys.stderr)


def _fix_summary(fix_outcome) -> dict:
    if fix_outcome is None:
        return {"applied": 0, "files": [], "left_alone": [], "backups": []}
    return {
        "applied": len(fix_outcome.applied),
        "files": list(fix_outcome.files_changed),
        "backups": list(fix_outcome.backups),
        "written_by_model": list(getattr(fix_outcome, "ai_written", [])),
        "left_alone": [
            {"rule": s.rule_id, "where": f"{s.source}:{s.line}" if s.line else s.source,
             "reason": s.reason}
            for s in fix_outcome.skipped
        ],
        "errors": list(fix_outcome.errors),
    }


def _file_map(result, render, lang: str) -> list:
    """Every audited file, what is wrong in it, and where exactly."""
    files = []
    for document in result.documents:
        entry = {"source": document.source,
                 "error": document.error or "",
                 "elements_checked": document.elements_checked,
                 "findings": []}
        for issue in document.issues:
            explanation = render(issue, lang)
            entry["findings"].append({
                "rule": issue.rule_id,
                "severity": issue.severity,
                "category": issue.category,
                "line": issue.line,
                "selector": issue.selector,
                "engine": issue.engine,
                "title": explanation.title,
                "found": explanation.found,
                "why": explanation.why,
                "fix": explanation.fix,
                "ready_fix": issue.fix_snippet or "",
                "snippet": issue.snippet,
                "confirmed_by": (issue.details or {}).get("also_found_by", []),
            })
        files.append(entry)
    return files


def _report_markdown(payload: dict, lang: str) -> str:
    """The same facts, laid out for something that reads rather than parses."""
    summary = payload["summary"]
    counts = summary["counts"]
    files = payload.get("files", [])
    out = [
        f"# Audit of {payload['root']}",
        "",
        f"Generated {payload['generated']} · mode `{payload['mode']}` · "
        f"{summary['documents']} document(s) examined.",
        "",
    ]

    # List all crawled pages
    if files:
        out += [
            "## Pages examined",
            "",
        ]
        for i, f in enumerate(files, 1):
            url = f.get("source", "") or f.get("url", "")
            findings = len(f.get("findings", []))
            error = f.get("error", "")
            if error:
                out.append(f"{i}. {url} — *error: {error}*")
            else:
                out.append(f"{i}. {url} ({findings} findings)")
        out.append("")

    out += [
        "## Where the work is",
        "",
        f"| critical | serious | moderate | minor | total |",
        "|---|---|---|---|---|",
        f"| {counts.get('critical', 0)} | {counts.get('serious', 0)} | "
        f"{counts.get('moderate', 0)} | {counts.get('minor', 0)} | "
        f"{summary['total']} |",
        "",
    ]

    # AI patterns section
    ai = payload.get("ai_patterns", {})
    if ai.get("total", 0) > 0:
        out += [
            "## AI-generated text patterns",
            "",
            f"**{ai['total']}** passages flagged across **{ai['files']}** file(s).",
            "",
            f"| Confidence | Count |",
            "|---|---|",
            f"| high | {ai.get('high', 0)} |",
            f"| medium | {ai.get('medium', 0)} |",
            f"| low | {ai.get('low', 0)} |",
            "",
        ]
        top = ai.get("top_patterns", [])
        if top:
            out += [
                "### Top AI patterns detected",
                "",
                "| Score | Confidence | Text | Explanation |",
                "|---|---|---|---|",
            ]
            for p in top:
                text = p["text"].replace("|", "\\|")[:80]
                exp = p["explanation"].replace("|", "\\|")[:80]
                out.append(f"| {p['score']:.2f} | {p['confidence']} | {text} | {exp} |")
            out.append("")

    # Typography section
    typo = payload.get("typography", {})
    if typo.get("total", 0) > 0:
        out += [
            "## Typography issues (non-keyboard characters)",
            "",
            f"**{typo['total']}** passages with non-standard characters across **{typo['files']}** file(s).",
            "",
            "### By character type",
            "",
            "| Character | Count |",
            "|---|---|",
        ]
        for char_name, count in typo.get("by_character", {}).items():
            out.append(f"| {char_name} | {count} |")
        out.append("")
        examples = typo.get("top_examples", [])
        if examples:
            out += [
                "### Examples",
                "",
            ]
            for ex in examples:
                text = ex["text"].replace("|", "\\|")[:60]
                exp = ex["explanation"].replace("|", "\\|")[:60]
                out.append(f"- `{text}` — {exp}")
            out.append("")

    previous = _previous_run(payload)
    if previous is not None:
        before, now = sum(previous["counts"].values()), summary["total"]
        direction = "down" if now < before else ("up" if now > before else "unchanged")
        out += [
            "## Since the last run",
            "",
            f"Previous run {previous['at']}: {before} finding(s). "
            f"Now {now} - {direction}.",
            "",
        ]

    changed = payload.get("changed_this_run") or {}
    if changed.get("applied"):
        out += [
            "## Already corrected in this run",
            "",
            f"{changed['applied']} correction(s) written to "
            f"{len(changed['files'])} file(s). Backups: "
            f"{', '.join(changed['backups']) or 'none'} - `cli.py undo <path>` "
            f"puts every file back.",
            "",
        ]
        if changed.get("written_by_model"):
            out += [
                f"Written by a model, so worth reading before trusting: "
                f"{', '.join(sorted(set(changed['written_by_model'])))}.",
                "",
            ]

    left = [s for s in changed.get("left_alone", [])]
    if left:
        # Without line numbers on purpose. These were recorded before the
        # corrections were written, so their positions have since moved; the
        # file map below is the one that matches the file on disk now, and
        # two sets of line numbers that disagree is worse than one set.
        out += ["## Deliberately not corrected", "",
                "These need a decision rather than an edit. Current positions "
                "are in the file map below.", ""]
        seen = set()
        for item in left[:40]:
            key = (item["rule"], item["reason"])
            if key in seen:
                continue
            seen.add(key)
            source = item["where"].rsplit(":", 1)[0] if ":" in item["where"] else item["where"]
            same = sum(1 for other in left if (other["rule"], other["reason"]) == key)
            count = f" ({same}\u00d7)" if same > 1 else ""
            out.append(f"- `{item['rule']}`{count} in {source} - {item['reason']}")
        out.append("")

    out += ["## By rule, most affected first", "",
            "| rule | severity | count | what to do |", "|---|---|---|---|"]
    for rule in payload["by_rule"]:
        fix = " ".join(rule["fix"].split())[:150]
        out.append(f"| `{rule['rule']}` | {rule['severity']} | {rule['count']} | {fix} |")
    out.append("")

    out += ["## File map", ""]
    for entry in payload["files"]:
        if entry["error"]:
            out += [f"### {entry['source']}", "", f"Not checked: {entry['error']}", ""]
            continue
        if not entry["findings"]:
            continue
        out += [f"### {entry['source']}", "",
                f"{len(entry['findings'])} finding(s), "
                f"{entry['elements_checked']} element(s) examined.", ""]
        for finding in entry["findings"]:
            where = f"line {finding['line']}" if finding["line"] else finding["selector"] or "-"
            out.append(f"- **[{finding['severity']}] {finding['title']}** ({where})")
            out.append(f"  - found: {finding['found']}")
            out.append(f"  - why: {' '.join(finding['why'].split())}")
            out.append(f"  - fix: {' '.join(finding['fix'].split())}")
            if finding["ready_fix"]:
                out.append(f"  - ready replacement: `{finding['ready_fix']}`")
            if finding["snippet"]:
                out.append(f"  - element: `{finding['snippet'][:160]}`")
        out.append("")

    out += [
        "## How to act on this",
        "",
        "Corrections marked *ready replacement* are exact: the element they "
        "name can be swapped for the markup given. Everything else is a "
        "decision - describing an image, writing a description - and the "
        "wording matters more than the markup.",
        "",
        "`python cli.py audit <target> --fix` applies the exact ones and keeps "
        "a `.bak` of every file it touches. `--fix --ai` also writes the ones "
        "that need words. `python cli.py undo <path>` reverses either.",
        "",
    ]
    return "\n".join(out)


def _previous_run(payload: dict) -> dict | None:
    """The last run of *this* target, or None if there was not one.

    The history file lives beside the report, so pointing `--report` at one
    path while scanning different things put unrelated runs in one list, and
    the comparison then read the count of another target as progress on this
    one - a run over a clean file announced "8 finding(s). Now 0 - down"
    because the previous entry was a different root. Matching on root and mode
    is what makes the sentence true: an audit and a text scan of the same
    directory count different things and are not each other's history either.
    """
    history = payload.get("history") or []
    root, mode = payload.get("root"), payload.get("mode")
    mine = [e for e in history[:-1]
            if e.get("root") == root and e.get("mode") == mode]
    return mine[-1] if mine else None


def _history_dir() -> Path:
    """Where run history lives: .xanalyze/ in the current working directory."""
    d = Path.cwd() / ".xanalyze"
    d.mkdir(exist_ok=True)
    return d


def _history_key(report_path: Path) -> str:
    """Stable filename from the report path, without directory traversal."""
    import hashlib
    return hashlib.md5(str(report_path).encode()).hexdigest()[:12]


def _read_history(report_path: Path) -> list:
    history_path = _history_dir() / f"{_history_key(report_path)}.json"
    try:
        data = json.loads(history_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _write_history(report_path: Path, history: list) -> None:
    history_path = _history_dir() / f"{_history_key(report_path)}.json"
    try:
        history_path.write_text(
            json.dumps(history[-20:], ensure_ascii=False, indent=2),
            encoding="utf-8")
    except OSError:
        pass


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
