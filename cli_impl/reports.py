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
    # A finding replayed from the incremental cache has no `TextSpan`: the
    # span does not survive JSON, and the report is built from spans. Such a
    # finding is skipped rather than faked, and the difference is said out
    # loud - a document that quietly covers fewer files than the scan did is
    # the kind of report that gets trusted wrongly.
    spans = [f["_span"] for f in findings if f.get("_span") is not None]
    skipped = len(findings) - len(spans)
    result = RepoAnalysisResult(root_dir=root, files=files, spans=spans)
    write_styled_report(args.styled_report, from_text_analysis(result), lang)
    print(f"# styled report: {args.styled_report}", file=sys.stderr)
    if skipped:
        print(f"# {skipped} finding(s) came from the incremental cache and are "
              f"not in the styled report; run without --incremental for a "
              f"complete document", file=sys.stderr)


def _write_report(result, args, lang: str, fix_outcome=None, ai_findings=None) -> dict:
    """Write a briefing another tool - or an agent - can act on directly.

    The plain `--json` output is a list of findings, which is the right shape
    for a pipeline and the wrong shape for an agent about to edit the code. An
    agent needs to know where the work is concentrated, which files to open,
    what has already been done to them, and whether the situation is getting
    better or worse. So this is a different document, not a flag on the same
    one.

    Markdown by default because that is what a coding agent reads best; `.json`
    if the suffix asks for it, for anything that would rather parse than read.

    Returns the payload it wrote, so a caller that also needs the grouped
    problems or the run history (the comparison document, for one) reads
    them from here instead of computing them a second time.
    """
    from audit.explanations import render

    path = Path(args.report)
    history = _read_history(result.root, result.mode)
    counts = result.counts()
    problems = _problem_map(result, render, lang)
    entry = {
        "at": _now(),
        "root": result.root,
        "mode": result.mode,
        "counts": counts,
        # Recorded per run so the comparison with the previous run can talk
        # about problems solved, not only about rows removed: fixing one
        # shared header takes thirty findings off the total and one problem
        # off this number, and those are two different pieces of news.
        "distinct": len(problems),
        "rules": sorted({p["rule"] for p in problems}),
        # How many places each rule fires in. The per-rule number is what
        # makes "did the last round of work help" answerable: grouping keys
        # on the offending markup, so correcting two of five copies *splits*
        # one group into two and the count of distinct problems goes up
        # while the situation improved. Occurrences per rule only go down
        # when something was actually fixed.
        "rule_counts": {rule: len(issues)
                        for rule, issues in result.by_rule().items()},
        "documents": len(result.documents),
        "fixed": len(fix_outcome.applied) if fix_outcome else 0,
        "report": str(path),
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
            # The same problem on thirty pages is one problem and thirty
            # places. Both counts are reported; see `_problem_map`.
            "distinct_problems": len(problems),
            "documents": len(result.documents),
            "documents_with_findings": len(result.documents_with_issues()),
            "rules_triggered": len(result.by_rule()),
        },
        "ai_patterns": ai_stats,
        "typography": typo_stats,
        "history": history + [entry],
        "changed_this_run": _fix_summary(fix_outcome),
        "files": _file_map(result, render, lang),
        "problems": problems,
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
    _write_history(result.root, result.mode, history + [entry])
    print(f"# report: {path}", file=sys.stderr)
    # Handed back so a caller that also writes a comparison document does
    # not have to recompute the grouping and re-read the history.
    return payload


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


#: How many places one grouped problem names in full before the rest become
#: a count. Same reasoning as `report.template._LOCATIONS_SHOWN`.
_PLACES_SHOWN = 15


def _problem_map(result, render, lang: str) -> list:
    """Every distinct problem once, with every place it was found.

    The counterpart of `_file_map`, which walks documents and repeats the
    whole finding in each. Both are kept: an agent about to edit files wants
    the file map, and a person reading the report wants to know there is one
    unlabelled search field in a shared header, not thirty of them. See
    `duplicates.group_issues`.
    """
    import duplicates

    issues = [issue for document in result.documents for issue in document.issues]
    problems = []
    for first, others in duplicates.group_issues(issues):
        explanation = render(first, lang)
        problems.append({
            "rule": first.rule_id,
            "severity": first.severity,
            "category": first.category,
            "engine": first.engine,
            "title": explanation.title,
            "found": explanation.found,
            "why": explanation.why,
            "fix": explanation.fix,
            "ready_fix": first.fix_snippet or "",
            "snippet": first.snippet,
            "selector": first.selector,
            "occurrences": len(others) + 1,
            "places": duplicates.places_of(first, others),
        })
    problems.sort(key=lambda p: (_SEVERITY_ORDER.get(p["severity"], 9),
                                 -p["occurrences"], p["rule"]))
    return problems


#: Worst first. Local to the report writer rather than imported from
#: `audit.base`: this orders a rendered payload, which may have come from a
#: JSON file written by an older version whose vocabulary differed.
_SEVERITY_ORDER = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}


def _problems_section(payload: dict) -> list:
    """The grouped problem list, as markdown lines."""
    problems = payload.get("problems") or []
    if not problems:
        return []
    out = [
        "## Problems, worst and most widespread first",
        "",
        f"{len(problems)} distinct problem(s). A problem found on several "
        f"pages is listed once, with every place it was found.",
        "",
    ]
    for problem in problems:
        times = (f" — {problem['occurrences']}×"
                 if problem["occurrences"] > 1 else "")
        out.append(f"### [{problem['severity']}] {problem['title']}{times}")
        out.append("")
        out.append(f"- rule: `{problem['rule']}` · {problem['category']} "
                   f"· found by {problem['engine'] or 'static'}")
        if problem["found"]:
            out.append(f"- found: {' '.join(problem['found'].split())}")
        if problem["why"]:
            out.append(f"- why: {' '.join(problem['why'].split())}")
        if problem["fix"]:
            out.append(f"- fix: {' '.join(problem['fix'].split())}")
        if problem["ready_fix"]:
            out.append(f"- ready replacement: `{problem['ready_fix'][:200]}`")
        if problem["snippet"]:
            out.append(f"- element: `{problem['snippet'][:200]}`")
        places = problem["places"]
        shown = places[:_PLACES_SHOWN]
        out.append(f"- where ({len(places)}):")
        for place in shown:
            out.append(f"  - {place}")
        if len(places) > len(shown):
            out.append(f"  - and {len(places) - len(shown)} more")
        out.append("")
    return out


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

    # The index of what was examined, as a table and worst first.
    #
    # It used to be a numbered list of every page, in reading order, at the
    # top of the briefing: on a 192-page crawl that was 192 lines before the
    # first finding. It is context, not content - so it is a table, the pages
    # carrying the most problems come first, and it is cut off once it stops
    # informing. The full count stays in the heading, because truncating the
    # list must not truncate the fact.
    if files:
        ranked = sorted(
            files,
            key=lambda f: (bool(f.get("error")), -len(f.get("findings", []))))
        out += [
            f"## Pages examined ({len(files)})",
            "",
            "| page or file | findings |",
            "|---|---|",
        ]
        for f in ranked[:_PAGES_LISTED]:
            url = f.get("source", "") or f.get("url", "")
            error = f.get("error", "")
            count = f"*error: {error}*" if error else len(f.get("findings", []))
            out.append(f"| {url} | {count} |")
        rest = len(ranked) - _PAGES_LISTED
        if rest > 0:
            out.append(f"| *and {rest} more* | |")
        out.append("")

    # Both numbers, because they answer different questions and reporting
    # only one misleads: "70 findings" reads as seventy pieces of work when
    # it is fourteen problems on five pages, and "14 problems" hides how
    # much of the site each one touches.
    distinct = len(payload.get("problems") or [])
    out += [
        "## Where the work is",
        "",
        "| critical | serious | moderate | minor | total | distinct problems |",
        "|---|---|---|---|---|---|",
        f"| {counts.get('critical', 0)} | {counts.get('serious', 0)} | "
        f"{counts.get('moderate', 0)} | {counts.get('minor', 0)} | "
        f"{summary['total']} | {distinct or summary['total']} |",
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
            "| Confidence | Count |",
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

    comparison = compare_runs(payload)
    if comparison is not None:
        out += ["## Since the last run", ""] + _comparison_lines(comparison) + [""]

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

    # One entry per distinct problem, not per (document × problem). A crawl
    # of thirty pages sharing one header used to repeat that header's every
    # fault thirty times, and a list where every row restates the previous
    # one stops being read. The complete per-document map is still in the
    # `.json` form of this report, under `files`, for anything that parses
    # rather than reads.
    problems = _problems_section(payload)
    if problems:
        out += problems
    else:
        out += ["## File map", ""]
        for entry in payload["files"]:
            if entry["error"]:
                out += [f"### {entry['source']}", "",
                        f"Not checked: {entry['error']}", ""]

    unchecked = [e for e in payload["files"] if e["error"]]
    if problems and unchecked:
        out += ["## Not checked", ""]
        for entry in unchecked:
            out.append(f"- {entry['source']} — *{entry['error']}*")
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


def compare_runs(payload: dict) -> dict | None:
    """This run against the previous one of the same target, or None.

    Two numbers, not one. **Findings** is how many rows the report has, and
    it moves for reasons that are not progress: crawling five more pages
    raises it, a page that timed out lowers it. **Problems** is how many
    distinct faults were found (see `_problem_map`), and it is the number
    that answers "did we fix anything" - correcting one shared header takes
    thirty findings and exactly one problem off the total.

    Rule identity carries the rest: a rule in the previous run and not in
    this one was *solved*, the other way round is a *regression*, and naming
    them is what makes the comparison actionable rather than a score.
    """
    previous = _previous_run(payload)
    if previous is None:
        return None
    now_counts = {rule["rule"]: rule["count"] for rule in payload.get("by_rule") or []}
    before_counts = dict(previous.get("rule_counts") or {})
    now_rules = set(now_counts) or {p["rule"] for p in payload.get("problems") or []}
    before_rules = set(before_counts) or set(previous.get("rules") or [])
    summary = payload["summary"]
    # A run recorded before rule identity was stored knows only its totals.
    # Comparing rule sets against an empty set would announce every rule as
    # brand new and every count as a regression from zero - a confident lie
    # about a run we simply do not have the detail for. So the per-rule
    # verdicts are withheld, and the totals still compare.
    comparable = bool(before_rules)
    moved = [
        {"rule": rule,
         "before": before_counts.get(rule, 0),
         "now": now_counts.get(rule, 0)}
        for rule in sorted(before_rules | now_rules)
        if before_counts.get(rule, 0) != now_counts.get(rule, 0)
    ] if before_counts else []
    return {
        "previous_at": previous.get("at", "?"),
        "at": payload.get("generated", "?"),
        "findings_before": sum((previous.get("counts") or {}).values()),
        "findings_now": summary["total"],
        # `distinct` is absent from runs recorded before it was written;
        # `None` says "not comparable" rather than pretending it was zero.
        "problems_before": previous.get("distinct"),
        "problems_now": summary.get("distinct_problems", 0),
        "solved_rules": sorted(before_rules - now_rules) if comparable else [],
        "new_rules": sorted(now_rules - before_rules) if comparable else [],
        "still_open_rules": sorted(now_rules & before_rules) if comparable
        else sorted(now_rules),
        #: Rules whose number of places changed, in either direction. Empty
        #: for a run recorded before `rule_counts` existed.
        "moved_rules": moved,
        "comparable_per_rule": bool(before_counts),
        "comparable_rule_set": comparable,
        "places_fixed": sum(max(0, m["before"] - m["now"]) for m in moved),
        "places_added": sum(max(0, m["now"] - m["before"]) for m in moved),
    }


def _direction(before: int, now: int) -> str:
    if now < before:
        return f"down {before - now}"
    if now > before:
        return f"up {now - before}"
    return "unchanged"


def _comparison_lines(comparison: dict) -> list:
    """The comparison as markdown lines, shared by the report section and
    the standalone comparison document."""
    out = [
        f"Previous run {comparison['previous_at']} · this run "
        f"{comparison['at']}.",
        "",
        "| | previous | now | change |",
        "|---|---|---|---|",
        f"| findings | {comparison['findings_before']} | "
        f"{comparison['findings_now']} | "
        f"{_direction(comparison['findings_before'], comparison['findings_now'])} |",
    ]
    out.append("")
    # `distinct_problems` deliberately does not appear here. Grouping keys on
    # the offending markup, so correcting two of five copies of one bad
    # image splits one group into two: the count of distinct problems rises
    # while the site got better. It is an honest number for "how much is
    # there to read" and a misleading one for "did we make progress", and a
    # progress table is exactly the wrong place for it. Progress is the
    # per-rule table below.

    if comparison["comparable_per_rule"]:
        out += [
            f"**{comparison['places_fixed']} place(s) corrected**, "
            f"{comparison['places_added']} new one(s) appeared.",
            "",
        ]

    solved, appeared = comparison["solved_rules"], comparison["new_rules"]
    if solved:
        out += [f"**Gone entirely ({len(solved)}):** "
                + ", ".join(f"`{rule}`" for rule in solved), ""]
    if appeared:
        out += [f"**New since last run ({len(appeared)}):** "
                + ", ".join(f"`{rule}`" for rule in appeared), ""]

    moved = comparison["moved_rules"]
    if moved:
        out += [
            "### What moved, by rule",
            "",
            "| rule | previous | now | change |",
            "|---|---|---|---|",
        ]
        # Biggest improvement first: the point of the table is what the last
        # round of work achieved, not an alphabet.
        for row in sorted(moved, key=lambda r: (r["now"] - r["before"], r["rule"])):
            out.append(f"| `{row['rule']}` | {row['before']} | {row['now']} | "
                       f"{_direction(row['before'], row['now'])} |")
        out.append("")
    elif comparison["comparable_per_rule"]:
        out += ["Every rule fires in exactly as many places as last time: "
                "nothing was corrected and nothing regressed.", ""]
    elif not comparison["comparable_rule_set"]:
        out += ["The previous run recorded only its totals, not which rules "
                "fired, so what was solved and what appeared cannot be named "
                "for this comparison. The next one will have both.", ""]
    elif not solved and not appeared:
        out += ["The same rules fire as last time.", ""]

    still = comparison["still_open_rules"]
    if still:
        out += [f"**Still open ({len(still)}):** "
                + ", ".join(f"`{rule}`" for rule in still), ""]
    return out


def write_comparison_document(path, payload: dict) -> bool:
    """The comparison as a document of its own, next to the report.

    Separate from the report on purpose: the report answers "what is wrong
    now", and the question a second run actually asks is "what did the last
    round of work change". Two questions, two documents. Returns False -
    writing nothing - when there is no previous run to compare against, so
    a first run leaves no empty file behind.
    """
    comparison = compare_runs(payload)
    if comparison is None:
        return False
    path = Path(path)
    lines = [
        f"# What changed for {payload.get('root', '')}",
        "",
    ] + _comparison_lines(comparison) + [
        "## How to read this",
        "",
        "*Findings* counts rows in the report; it also moves when the crawl "
        "reaches a different number of pages, which is not progress. "
        "*Places corrected* and the per-rule table are the numbers that "
        "track work done: a rule fires in fewer places only when something "
        "was actually fixed.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"# comparison: {path}", file=sys.stderr)
    return True


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


#: Rows of the page index before the briefing cuts it short. Long enough to
#: be useful on an ordinary site, short enough that a large crawl does not
#: bury the findings under its own table of contents.
_PAGES_LISTED = 40


def _history_dir() -> Path:
    """Where run history lives: `~/.xanalyze/history/`.

    Not `.xanalyze/` in the working directory, which is where this used to
    live. Two reasons, both found by running the tool:

    * A run started from a different folder saw no history at all, so the
      comparison silently disappeared depending on where the terminal
      happened to be.
    * The history of a *website* has no working directory to belong to.

    The legacy location is still read - see `_legacy_history` - so runs
    recorded before this change keep counting.
    """
    d = Path.home() / ".xanalyze" / "history"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return d


def _history_key(root: str, mode: str) -> str:
    """Identity of a run series: what was scanned, and which analysis.

    Keyed on the *target*, not on the report path. The report path used to
    be the key, and `fullscan` puts a timestamp in the file name it
    generates - so every run produced a new key, every history read came
    back empty, and the "since the last run" comparison never once appeared
    in a default fullscan. An audit and a text scan of the same folder count
    different things, so `mode` is part of the identity too.
    """
    import hashlib
    return hashlib.md5(f"{root}|{mode}".encode()).hexdigest()[:12]


def _legacy_history(root: str, mode: str) -> list:
    """Entries for this target recorded under the old `.xanalyze/` scheme.

    Read once per run and merged in, so the runs already on disk - keyed by
    report path, one file per run - are not lost. Each file is filtered by
    root and mode because the old key said nothing about either.
    """
    legacy_dir = Path.cwd() / ".xanalyze"
    if not legacy_dir.is_dir():
        return []
    found: list = []
    for path in legacy_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, list):
            continue
        found.extend(e for e in data if isinstance(e, dict)
                     and e.get("root") == root and e.get("mode") == mode)
    return found


def _read_history(root: str, mode: str) -> list:
    history_path = _history_dir() / f"{_history_key(root, mode)}.json"
    try:
        data = json.loads(history_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = []
    entries = data if isinstance(data, list) else []
    known = {(e.get("at"), e.get("root"), e.get("mode"))
             for e in entries if isinstance(e, dict)}
    for entry in _legacy_history(root, mode):
        stamp = (entry.get("at"), entry.get("root"), entry.get("mode"))
        if stamp not in known:
            known.add(stamp)
            entries.append(entry)
    entries.sort(key=lambda e: e.get("at") or "")
    return entries


def _write_history(root: str, mode: str, history: list) -> None:
    history_path = _history_dir() / f"{_history_key(root, mode)}.json"
    try:
        history_path.write_text(
            json.dumps(history[-20:], ensure_ascii=False, indent=2),
            encoding="utf-8")
    except OSError:
        pass


def _now() -> str:
    # Seconds included: history is sorted on this string, and two runs
    # started in the same minute (a re-run right after a fix - the common
    # case) were indistinguishable without them, so "previous run" could
    # name either of the two.
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
