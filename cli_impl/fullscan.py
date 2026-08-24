"""The `fullscan` command: AI patterns + accessibility audit + reports.

Combines scan (AI patterns, characters) and audit (accessibility, SEO,
performance, best practices) into one command, saves the styled report
and the agent briefing, and prints one JSON document for agent consumption.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import suppression

import detectors  # noqa: F401 - registers the detectors
from detectors.factory import DetectorFactory

from cli_impl import EXIT_ERROR, EXIT_FINDINGS, EXIT_INCOMPLETE, EXIT_OK
from cli_impl.agentcmds import _agent_detection_rules
from cli_impl.auditpass import (
    _crawl_maybe_rendering, _is_page_file, _run_browser_pass, looks_like_url,
    with_scheme,
)
from cli_impl.output import _public
from cli_impl import checkpoint, runfolder, runstate
from cli_impl.scanning import (
    _analyze, _build_scan_config, _collect_files, _ignore_root,
    _settings_for_ignore,
)

#: Offline spans under this score never reach the agent candidate list.
_AGENT_CANDIDATE_FLOOR = 0.25


def _fullscan_report_paths(args, target: str):
    """Put this run's documents in this target's folder on the Desktop.

    A folder per target, a sub-folder per run: see `cli_impl.runfolder`. The
    documents used to be timestamped files dropped loose on the Desktop,
    which made a second run of the same site impossible to find next to the
    first - and the run history was keyed on those ever-changing file names,
    so no run was ever compared with any other.

    The folder is created either way. Naming both report paths says where the
    *reports* go, and it used to mean no run folder at all - which also meant
    no phase record and no checkpoints, so the one caller who had asked for
    control over their output was the one who could not resume. The reports
    now go exactly where they were asked for, and the run still has a folder
    to keep its state and its intermediate results in.
    """
    from cli_impl import runfolder

    named_styled = bool(getattr(args, "styled_report", None))
    named_report = bool(getattr(args, "report", None))
    folder = runfolder.prepare(target)
    if not named_styled:
        args.styled_report = str(folder.styled_report)
    if not named_report:
        args.report = str(folder.report)
    return folder


def _candidate(block, source_url: str, line: int, span) -> dict:
    """One candidate row as the agent pipeline consumes it."""
    return {
        "block_id": span.block_id,
        "file": source_url,
        "line": line,
        "text": block.text,
        "language": block.language_hint or "en",
        "offline_score": round(span.score, 3),
        "offline_explanation": span.explanation,
    }


def _agent_candidates_from_blocks(blocks) -> list:
    """Candidates for a local repo: one detector pass over every block."""
    offline = DetectorFactory.create("offline", include_style=True)
    spans = offline.analyze_blocks(blocks)
    by_id = {b.block_id: b for b in blocks}
    seen: set = set()
    candidates = []
    for span in spans:
        if span.score < _AGENT_CANDIDATE_FLOOR or (span.details or {}).get("error"):
            continue
        if span.block_id in seen:
            continue
        seen.add(span.block_id)
        block = by_id.get(span.block_id)
        if block:
            candidates.append(_candidate(block, block.file_path,
                                         block.line_number, span))
    return candidates


def _agent_candidates_from_pages(pages) -> list:
    """Candidates for a crawled site: per-page passes over page blocks."""
    offline = DetectorFactory.create("offline", include_style=True)
    seen: set = set()
    candidates = []
    for page in pages:
        for block in page.blocks:
            for span in offline.analyze_block(block):
                if span.score < _AGENT_CANDIDATE_FLOOR \
                        or (span.details or {}).get("error"):
                    continue
                if span.block_id in seen:
                    continue
                seen.add(span.block_id)
                candidates.append(_candidate(block, page.url, 0, span))
    return candidates


def _content_passes(args) -> list:
    """The detectors a crawled page's text is read by, given `--detector`.

    Mirrors what `cli_impl.scanning._analyze` does for a folder, and it has to:
    the two are the same question asked of a page and of a file, and the moment
    they answer differently the flag means one thing on disk and another on the
    web - which is exactly what happened.

    Offline is always in the list, because it carries the character pass. When
    a judge was asked for, it is added rather than substituted: the offline
    engine finds the exact character defects a model does not, so replacing it
    would be a downgrade wearing an upgrade's name.
    """
    offline = DetectorFactory.create("offline", include_style=True)
    name = getattr(args, "detector", None) if args is not None else None
    if not name or DetectorFactory.resolve(name) == "offline":
        return [offline]

    from .scanning import _create_detector

    try:
        judge = _create_detector(args)
    except Exception as exc:  # noqa: BLE001 - said out loud, not swallowed
        # Loud, and the run continues on the offline pass. A judge that cannot
        # be built (no account, an exhausted plan, a typo in a name) must not
        # cost the crawl that already happened - but it must never be silent
        # either, which is the whole defect this function exists to close.
        print(f"# warning: --detector {name} could not be used ({exc}); "
              f"the offline engine ran instead", file=sys.stderr, flush=True)
        return [offline]
    # The judge's own name, not the flag's. `ai` and `llm-judge` mean "ask a
    # model" without saying whose account pays, and which account it turned
    # out to be is the part worth printing - it is what the run will be
    # billed to.
    print(f"# [stage] AI patterns: {getattr(judge, 'name', name)}",
          file=sys.stderr, flush=True)
    return [offline, judge]


def _content_findings_from_pages(pages, args=None) -> list:
    """The AI-patterns and typography pass for a crawled site.

    Local targets get this through the ordinary scan; a crawled page never
    was a file, so the detector runs over its text blocks here and the spans
    become the finding dicts the reports read. Without this, a website scan
    silently lost whole report sections a repo scan had.

    **`--detector` reaches this.** It did not, and that was the whole of the
    AI mode on the path most people use: this hardcoded the offline engine, so
    `fullscan https://site --detector llm-judge` crawled the site, said
    nothing, and ran the free heuristic. The flag was accepted, reported
    nowhere, and did nothing - the failure mode this project keeps finding,
    where a control looks like it works because nothing raises.

    The character pass stays offline whatever was asked for. It is exact and
    free, a model has nothing to add to "this is an en dash", and paying a
    judge to re-answer it would be a cost with no result.

    The same threshold as the repo scan, and this is not a detail. Without it
    this path appended *every* span the detector produced, scored or not: a
    real 192-page run reported 10,976 "AI text patterns" of which 10,946 were
    `low` - blocks that scored 0.00 and were listed anyway. They inflated the
    count the user reads, and they are most of why that run's artifacts came
    to 14 MB of JSON, 31 MB of HTML and a 117 MB PDF.

    Character findings are kept at any confidence, exactly as the repo scan
    keeps them: a wrong dash is a fact about the text, so a low score there
    means "a small defect", not "probably nothing". A style score below the
    threshold means the second thing, and saying it 10,946 times says nothing.
    """
    from models import Confidence

    from .scanning import CHARACTER_SOURCE

    passes = _content_passes(args)
    # A judge reads every block over the network, and on ten pages that is
    # minutes with nothing on screen. The crawl and the browser pass both
    # count themselves out loud; this stage did not, so the one stage that
    # can legitimately take longest was also the one that looked hung. The
    # offline pass stays quiet - it finishes in a tenth of a second, and a
    # progress line for it would be noise.
    talkative = len(passes) > 1
    total = len(pages)
    findings = []
    for index, page in enumerate(pages, 1):
        if talkative:
            print(f"# [AI patterns {index}/{total}] {page.url}",
                  file=sys.stderr, flush=True)
        blocks = list(page.blocks)
        by_id = {block.block_id: block for block in blocks}
        # `analyze_blocks`, not a loop over `analyze_block`. The judges batch
        # in groups of eight, and the per-block call defeats that completely:
        # the Claude Code judge starts one `claude -p` process per call, so a
        # ten-page site went from roughly a hundred requests to roughly eight
        # hundred. Measured on a live run - the stage was still going after
        # five minutes and would have taken about an hour.
        spans = []
        for detector in passes:
            spans.extend(detector.analyze_blocks(blocks))
        for span in spans:
            if (span.details or {}).get("error"):
                continue
            if span.confidence == Confidence.LOW \
                    and (span.details or {}).get("source") != CHARACTER_SOURCE:
                continue
            block = by_id.get(span.block_id)
            if block is None:
                continue
            confidence = span.confidence
            if isinstance(confidence, Confidence):
                confidence = confidence.value
            findings.append({
                "file": page.url,
                "line": 0,
                "text": block.text[:200],
                "source": (span.details or {}).get("source", ""),
                "score": round(span.score, 3),
                "confidence": confidence,
                "explanation": span.explanation,
            })
    return findings


def _scan_local_target(target, args, lang, agent_mode):
    """Phase 1 for repos and loose files: the AI-patterns pass.

    Returns (scan_findings, scan_result, agent_candidates).
    """
    scan_args = argparse.Namespace(
        paths=[target],
        ext=args.ext,
        exclude=args.exclude,
        use_default_excludes=not getattr(args, "no_default_excludes", False),
        max_files=args.max_files,
        detector=args.detector,
        scope=args.scope,
        no_typography=getattr(args, "no_typography", False),
        no_ignore=False,
        no_unicode=False,
        categories=None,
        json=False,
        check=False,
        incremental=False,
        styled_report=None,
        language=lang,
    )

    scan_findings: list = []
    scan_result = None
    agent_candidates: list = []

    files = _collect_files(scan_args.paths, scan_args)
    if not files:
        return scan_findings, scan_result, agent_candidates

    if agent_mode:
        # Agent mode: run offline scan, collect candidates for LLM judgment
        blocks = [b for f in files for b in f.blocks]
        agent_candidates = _agent_candidates_from_blocks(blocks)
        scan_result = {
            "findings": [],
            "counts": {"total": 0, "style": 0, "characters": 0},
            "agent_mode": True,
            "candidates_count": len(agent_candidates),
        }
    else:
        scan_findings, _ = _analyze(files, scan_args)
        clean_findings = [_public(f) for f in scan_findings]
        scan_result = {
            "findings": clean_findings,
            "counts": {
                "total": len(clean_findings),
                "style": len([f for f in clean_findings if f.get("source") == "style"]),
                "characters": len([f for f in clean_findings if f.get("source") == "characters"]),
            },
        }
    return scan_findings, scan_result, agent_candidates


def _crawl_for_fullscan(target: str, args, no_browser: bool):
    """Crawl a URL for the fullscan pass; returns (pages, resolved target)."""
    from crawler import CrawlConfig, RENDER_AUTO, RENDER_NEVER

    if not target.startswith(("http://", "https://")):
        target = "https://" + target
    # Use RENDER_AUTO for fullscan on URLs, RENDER_NEVER if --no-browser
    render_mode = RENDER_NEVER if no_browser else RENDER_AUTO
    config = CrawlConfig(max_depth=args.depth, max_pages=args.max_pages,
                         render_mode=render_mode)
    print(f"# [stage crawl] depth={args.depth} "
          f"max_pages={args.max_pages or 'unlimited'} render={render_mode}",
          file=sys.stderr, flush=True)

    crawled = 0

    def _crawl_progress(url: str, depth: int) -> None:
        nonlocal crawled
        crawled += 1
        limit = f"/{args.max_pages}" if args.max_pages else ""
        print(f"# [crawl {crawled}{limit}] depth={depth} {url}",
              file=sys.stderr, flush=True)

    pages = _crawl_maybe_rendering(target, config, progress_cb=_crawl_progress)
    print(f"# [crawl done] {len(pages)} page(s)", file=sys.stderr, flush=True)
    return pages, target


def _warn_about_spa(pages) -> None:
    """Say so when client-rendered pages came back empty shells."""
    from crawler import EMPTY_JS_RENDERED

    spa_pages = [p for p in pages
                 if EMPTY_JS_RENDERED in (p.diagnostics.reasons or [])]
    rendered_pages = [p for p in pages
                      if "rendered" in (p.diagnostics.reasons or [])]
    if spa_pages and not rendered_pages:
        print(f"# WARNING: {len(spa_pages)} SPA page(s) detected but browser rendering failed.", file=sys.stderr)
        print("# Pages may appear empty. Install PySide6 + QtWebEngine "
              "for full support.", file=sys.stderr)
    elif spa_pages and rendered_pages:
        print(f"# SPA: {len(rendered_pages)} page(s) rendered via browser, {len(spa_pages)} failed.", file=sys.stderr)


def _audit_fullscan_target(is_url: bool, is_page_file: bool, target: str,
                           args, pages):
    """Phase 2: accessibility/SEO/performance over whichever shape came in."""
    import audit

    if is_url:
        return audit.analyze_pages(pages, target)
    if is_page_file:
        return audit.analyze_page_file(target)
    from repo_scanner import scan_repo

    repo_files = scan_repo(target, _build_scan_config(args))
    if repo_files:
        return audit.analyze_files(repo_files, target)
    return None


def _detect_report_language(lang, pages) -> str:
    """Auto-detect the report language from crawled page content."""
    if lang is not None:
        return lang
    hints = []
    for page in (pages or []):
        hints.extend(b.language_hint for b in page.blocks if b.language_hint)
    return Counter(hints).most_common(1)[0][0] if hints else "en"


def _build_combined(args, target: str, is_url: bool, lang: str,
                    scan_result, clean_findings: list, audit_issues: list) -> dict:
    """Phase 3: the single JSON document the command prints."""
    return {
        "target": target,
        "is_url": is_url,
        "language": lang,
        "scan": scan_result or {"findings": [], "counts": {"total": 0, "style": 0, "characters": 0}},
        "audit": {
            "counts": {
                "critical": sum(1 for i in audit_issues if i.severity == "critical"),
                "serious": sum(1 for i in audit_issues if i.severity == "serious"),
                "moderate": sum(1 for i in audit_issues if i.severity == "moderate"),
                "minor": sum(1 for i in audit_issues if i.severity == "minor"),
            },
            "issues": [
                {
                    "rule": i.rule_id,
                    "category": i.category,
                    "severity": i.severity,
                    "selector": i.selector,
                    "snippet": i.snippet[:200] if i.snippet else None,
                    "fix_snippet": i.fix_snippet[:200] if i.fix_snippet else None,
                }
                for i in audit_issues
            ],
        },
        "summary": {
            "total_findings": len(clean_findings) + len(audit_issues),
            "ai_patterns": len([f for f in clean_findings if f.get("source") == "style"]),
            "characters": len([f for f in clean_findings if f.get("source") == "characters"]),
            "accessibility": sum(1 for i in audit_issues if i.category == "accessibility"),
            "seo": sum(1 for i in audit_issues if i.category == "seo"),
            "performance": sum(1 for i in audit_issues if i.category == "performance"),
            "best_practices": sum(1 for i in audit_issues if i.category == "best_practices"),
        },
    }


def _attach_agent_payload(combined: dict, agent_candidates: list,
                          target: str) -> None:
    """Agent mode: hand the candidates plus judging rules to the caller."""
    combined["agent_candidates"] = agent_candidates
    combined["detection_rules"] = _agent_detection_rules()
    combined["agent_instruction"] = (
        "You are an AI text judge. Use the detection_rules to evaluate "
        "each candidate. Consider ALL signals: statistical (uniformity, "
        "repetition, dash density), structural patterns, and cliché phrases. "
        "Do NOT dismiss dash density as 'typography' — it IS an AI signal. "
        "For each candidate return block_id, score (0.0=human, 1.0=AI), "
        "and a one-sentence reason. Then pipe judgments to: "
        "xanalyze agent-judge " + target + " --judgments -"
    )


class _ScanResultShim:
    """Adapts raw finding dicts to what report.model.from_text_analysis reads."""

    def __init__(self, findings):
        self.spans = []
        self._findings = findings

    def blocks(self):
        return []


def _split_style_typography(content_findings: list):
    """Sort content findings into wording vs character buckets."""
    style_findings: list = []
    typo_findings: list = []
    for f in content_findings:
        exp = f.get("explanation", f.get("offline_explanation", "")).lower()
        src = f.get("source", "").lower()
        if "typography" in exp or "characters" in src:
            typo_findings.append(f)
        else:
            style_findings.append(f)
    return style_findings, typo_findings


def _populate_ai_patterns(model, style_findings: list) -> None:
    model.ai_patterns = {
        "total": len(style_findings),
        "high": len([f for f in style_findings if f.get("confidence") == "high"]),
        "medium": len([f for f in style_findings if f.get("confidence") == "medium"]),
        "low": len([f for f in style_findings if f.get("confidence") == "low"]),
        "files": len({f.get("file", "") for f in style_findings}),
        "top_patterns": [
            {"text": f.get("text", f.get("offline_explanation", ""))[:100],
             "score": f.get("score", f.get("offline_score", 0)),
             "confidence": f.get("confidence", "low"),
             "explanation": f.get("explanation", f.get("offline_explanation", ""))[:120]}
            for f in sorted(style_findings,
                            key=lambda x: x.get("score", x.get("offline_score", 0)),
                            reverse=True)[:10]
        ],
    }


def _populate_typography(model, typo_findings: list) -> None:
    by_char: dict = {}
    for f in typo_findings:
        exp = f.get("explanation", f.get("offline_explanation", ""))
        char_name = exp.split("] ")[-1].split(" ->")[0] if "] " in exp else exp[:50]
        by_char.setdefault(char_name, 0)
        by_char[char_name] += 1
    model.typography = {
        "total": len(typo_findings),
        "files": len({f.get("file", "") for f in typo_findings}),
        "by_character": dict(sorted(by_char.items(), key=lambda x: -x[1])[:10]),
    }


def _styled_report_model(audit_result, content_findings: list, lang: str):
    """Build the ReportModel behind --styled-report."""
    from report.model import from_accessibility, from_text_analysis

    model = None
    if audit_result:
        model = from_accessibility(audit_result, lang=lang)

    if content_findings:
        text_model = from_text_analysis(_ScanResultShim(list(content_findings)))
        if model:
            model.findings.extend(text_model.findings)
        else:
            model = text_model

    if model is None:
        return None

    if audit_result:
        model.pages = [
            {"source": doc.source, "findings_count": len(doc.issues),
             "error": doc.error or ""}
            for doc in audit_result.documents
        ]

    style_findings, typo_findings = _split_style_typography(content_findings)
    if style_findings:
        _populate_ai_patterns(model, style_findings)
    if typo_findings:
        _populate_typography(model, typo_findings)
    return model


def _write_styled_report(args, audit_result, content_findings: list,
                         lang: str) -> None:
    if not getattr(args, "styled_report", None):
        return
    model = _styled_report_model(audit_result, content_findings, lang)
    if model is None:
        return
    from report.export import write_styled_report

    print("# [stage] writing reports...", file=sys.stderr, flush=True)
    # The markdown path travels with it so that, if the PDF cannot be
    # printed, the one-page stand-in can name the report to read instead of
    # merely gesturing at the folder.
    write_styled_report(args.styled_report, model, lang,
                        markdown_path=getattr(args, "report", None))
    print(f"# styled report: {args.styled_report}", file=sys.stderr)


def _markdown_briefing_input(agent_mode: bool, agent_candidates: list,
                             scan_findings: list) -> list:
    """AI-pattern rows for the markdown briefing."""
    if agent_mode and agent_candidates:
        return [
            {"file": c.get("file", ""), "line": c.get("line", 0),
             "text": c.get("text", "")[:200],
             "score": c.get("offline_score", 0),
             "confidence": "medium" if c.get("offline_score", 0) >= 0.5 else "low",
             "explanation": c.get("offline_explanation", "")}
            for c in agent_candidates
        ]
    return [
        {"file": f.get("file", ""), "line": f.get("line", 0),
         "text": f.get("text", "")[:200],
         "score": f.get("score", 0),
         "confidence": f.get("confidence", ""),
         "explanation": f.get("explanation", "")}
        for f in scan_findings
    ]


def _write_markdown_briefing(args, audit_result, agent_mode: bool,
                             agent_candidates: list, scan_findings: list,
                             lang: str) -> dict | None:
    """Write the briefing and hand back the payload it wrote.

    The payload carries the grouped problems and the run history, which the
    comparison document needs; recomputing either would mean grouping the
    findings twice.
    """
    from cli_impl.reports import _write_report

    if not getattr(args, "report", None) or audit_result is None:
        return None
    ai_for_report = _markdown_briefing_input(
        agent_mode, agent_candidates, scan_findings)
    # No second "agent briefing: <path>" line here: `_write_report` already
    # prints the path it wrote, and two lines naming one file read as two
    # files.
    return _write_report(audit_result, args, lang, None,
                         ai_findings=ai_for_report)


def _write_run_documents(folder, target: str, timings, payload, combined,
                         documents: int) -> None:
    """The two documents that describe the run rather than the target.

    `timings.md` says where the time went, so "why did this take an hour"
    has an answer without re-running anything. `changes.md` says what the
    last round of work achieved - and is not written at all on a first run,
    because a comparison document with nothing to compare reads as a broken
    comparison rather than as a first run.
    """
    from cli_impl.reports import write_comparison_document

    summary = combined.get("summary", {})
    timings.write(folder.timings, target, extra={
        "pages or files examined": documents,
        "findings": summary.get("total_findings", 0),
        "AI patterns": summary.get("ai_patterns", 0),
        "accessibility": summary.get("accessibility", 0),
        "run folder": str(folder.run),
    })
    if payload is not None:
        wrote = write_comparison_document(folder.changes, payload)
        if not wrote:
            earlier = folder.previous_runs()
            print("# first run of this target - nothing to compare against"
                  if not earlier else
                  "# no comparable previous run recorded for this target",
                  file=sys.stderr)


def _stop_short(state, folder, target, timings, phase, reason, *,
                paused=False) -> int:
    """End a run that could not finish, keeping everything it produced.

    The whole point of the phase record is this function existing at all: a
    run that stops has to leave behind what it computed, a statement of where
    it stopped, and one command that continues. Before this, a failure in the
    last of six phases discarded the five that had succeeded - on a real site
    that was forty-six minutes of crawling and auditing thrown away because a
    two-minute step raised.
    """
    if state is None:
        print(f"# {'paused' if paused else 'stopped'}: {reason}",
              file=sys.stderr, flush=True)
        return EXIT_INCOMPLETE
    if not paused:
        state.fail(phase, reason)
    timings.finish()
    if folder is not None:
        try:
            timings.write(folder.timings, target,
                          extra={"stopped in": phase, "reason": reason})
        except Exception as exc:  # noqa: BLE001 - the state file matters more
            print(f"# warning: timings failed: {exc}", file=sys.stderr)
    state.write_feedback()
    state.write_markdown()
    info = state.feedback()
    print(f"# {'paused' if paused else 'stopped'} in {phase}: {reason}",
          file=sys.stderr, flush=True)
    if info["artifacts"]:
        print(f"# kept {len(info['artifacts'])} artifact(s) in {state.run_dir}",
              file=sys.stderr)
    if info["resume_with"]:
        print(f"# continue with: {info['resume_with']}", file=sys.stderr)
    # The machine-readable half goes to stdout, where every other command
    # puts its JSON: an agent that ran this must be able to read the outcome
    # the same way it reads a success, and not have to scrape stderr.
    print(json.dumps({"target": target, "incomplete": True,
                      "run": str(state.run_dir), "state": info},
                     indent=2, ensure_ascii=False))
    return EXIT_INCOMPLETE


def cmd_fullscan(args) -> int:
    """Full scan: AI patterns + accessibility audit + reports for agent.

    Combines scan (AI patterns, characters) and audit (accessibility, SEO,
    performance, best practices) into one command. Saves styled report and
    agent briefing, outputs JSON for agent consumption.

    For URLs and HTML files: automatically enables browser rendering and
    responsive breakpoints (desktop, tablet, mobile). Reports are auto-saved
    to ~/Desktop unless --styled-report/--report specify a different path.

    With --agent: runs offline scan and outputs candidate blocks for the
    agent to judge with its own LLM (no API key needed). The agent reads
    the candidates, judges them, and pipes judgments to `agent-judge`.

    Usage:
      xanalyze fullscan https://example.com           # full scan with browser
      xanalyze fullscan ./repo                        # repo scan (no browser)
      xanalyze fullscan https://example.com --breakpoints desktop  # desktop only
      xanalyze fullscan ./repo --agent                # agent judges AI patterns
    """
    lang = args.language  # None if not specified, will auto-detect after crawl
    target = args.target
    is_url = looks_like_url(target) or args.url
    if is_url:
        # Normalised here rather than inside the crawl, so the report file
        # names and the JSON `target` say the same address that was fetched.
        target = with_scheme(target)
    is_page = _is_page_file(target) if not is_url else False
    # Browser is automatic for URLs and HTML files, not for repos
    no_browser = getattr(args, "no_browser", False)
    wants_browser = (is_url or is_page) and not no_browser
    agent_mode = getattr(args, "agent", False)

    # Validated before the run folder is created: a typo must not leave an
    # empty folder behind on someone's Desktop.
    if not is_url and not is_page and not Path(target).exists():
        print(f"path not found: {target}", file=sys.stderr)
        return EXIT_ERROR

    resumed = getattr(args, "_resume_state", None)
    if resumed is not None:
        folder = runfolder.RunFolder(resumed.run_dir.parent, resumed.run_dir)
        state = resumed
    else:
        folder = _fullscan_report_paths(args, target)
        state = (runstate.RunState.begin(folder, target) if folder is not None
                 else None)
    timings = runfolder.Timings()

    def already(phase: str) -> bool:
        """Did an earlier attempt finish this phase?

        Only ever true on a resume, and it is what makes resume worth having:
        the crawl and the browser pass are three minutes and forty-three on a
        real site, against two for everything after them.
        """
        entry = state.phase(phase) if state is not None else None
        return bool(entry and entry["status"] == runstate.DONE)

    def guard(phase: str) -> None:
        """Honour a pause request at a phase boundary."""
        if state is not None:
            state.checkpoint(phase)

    try:
        return _run_phases(args, state, folder, timings, target, lang, is_url,
                           is_page, wants_browser, agent_mode, already, guard)
    except runstate.Paused as paused:
        return _stop_short(state, folder, target, timings,
                           state.next_phase() if state else "", str(paused),
                           paused=True)


def _run_phases(args, state, folder, timings, target, lang, is_url, is_page,
                wants_browser, agent_mode, already, guard) -> int:
    """The phases themselves, each recording its own outcome.

    Split out from `cmd_fullscan` so the pause exception has one place to be
    caught: a `Paused` raised at any boundary unwinds to exactly one handler,
    and a paused run and a failed run then leave the same shape behind - which
    is what lets `resume` have one code path instead of two.
    """
    # --- Phase 1: AI patterns scan (for local files/repos) ---
    pages = None
    agent_candidates: list = []
    scan_findings, scan_result = [], None
    if not is_url:
        guard("scan")
        if already("scan"):
            scan_findings, counts = checkpoint.load_scan(state.run_dir)
            scan_result = {"findings": scan_findings or [],
                           "counts": counts or {}}
            print("# [resume] AI patterns scan reused", file=sys.stderr)
        else:
            timings.start("AI patterns scan")
            if state is not None:
                state.start("scan")
            try:
                scan_findings, scan_result, agent_candidates = \
                    _scan_local_target(target, args, lang, agent_mode)
            except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
                return _stop_short(state, folder, target, timings, "scan",
                                   f"the AI patterns scan failed: {exc}")
            if state is not None:
                # The public form, not the raw findings: those carry `_span`
                # and `_block` keys holding live detector objects, which are
                # what `fix` rewrites files through and are not serialisable.
                # Nothing after this phase reads them - the reports take the
                # same public dicts a crawl produces - so the checkpoint is
                # complete for every consumer that exists.
                saved = checkpoint.save_scan(
                    state.run_dir, (scan_result or {}).get("findings", []),
                    (scan_result or {}).get("counts"))
                state.done("scan", artifacts=[saved])
    elif state is not None:
        state.skip("scan", "folded into the crawl for a website")
    if not is_url and state is not None:
        # A folder is not crawled. Said explicitly, because a phase left
        # `pending` is one `resume` will try to run: without this a finished
        # repo scan reported itself as unfinished and offered to continue.
        state.skip("crawl", "not a website")

    # --- Phase 2: Accessibility audit ---
    audit_issues: list = []
    audit_result = None
    if is_url:
        guard("crawl")
        timings.start("crawl")
        if state is not None:
            state.start("crawl")
        try:
            pages, target = _crawl_for_fullscan(target, args, no_browser=
                                                getattr(args, "no_browser", False))
        except Exception as exc:  # noqa: BLE001
            return _stop_short(state, folder, target, timings, "crawl",
                               f"the crawl failed: {exc}")
        if state is not None:
            state.done("crawl")
        _warn_about_spa(pages)

        # Agent mode: extract candidates from crawled pages
        if agent_mode and pages:
            agent_candidates = _agent_candidates_from_pages(pages)
            scan_result = {
                "findings": [],
                "counts": {"total": 0, "style": 0, "characters": 0},
                "agent_mode": True,
                "candidates_count": len(agent_candidates),
            }
        elif pages:
            # Not agent mode: the same content pass a repo gets, so the
            # AI-patterns and typography sections exist in the reports.
            timings.start("AI patterns scan")
            scan_findings = _content_findings_from_pages(pages, args)
            scan_result = {
                "findings": scan_findings,
                "counts": {
                    "total": len(scan_findings),
                    "style": len([f for f in scan_findings
                                  if f.get("source") != "characters"]),
                    "characters": len([f for f in scan_findings
                                       if f.get("source") == "characters"]),
                },
            }

    guard("audit")
    if already("audit") and not already("browser"):
        # The static findings survived; the browser pass did not finish, so
        # it runs again over the reloaded result. Not resumed at page 97 -
        # per-page checkpointing is a bigger change, and the crawl, which is
        # the expensive part, is what this already saves.
        audit_result = checkpoint.load_audit(state.run_dir)
        if audit_result is not None:
            print("# [resume] static audit reused", file=sys.stderr)
    if audit_result is None:
        timings.start("static audit")
        if state is not None:
            state.start("audit")
        try:
            audit_result = _audit_fullscan_target(
                is_url, is_page and not is_url, target, args, pages)
        except Exception as exc:  # noqa: BLE001
            return _stop_short(state, folder, target, timings, "audit",
                               f"the static audit failed: {exc}")
        if state is not None:
            state.done("audit", artifacts=filter(
                None, [checkpoint.save_audit(state.run_dir, audit_result)]))

    if audit_result:
        # Run browser pass automatically for URLs and HTML files
        if already("browser"):
            reloaded = checkpoint.load_audit(state.run_dir)
            if reloaded is not None:
                audit_result = reloaded
                print("# [resume] browser pass reused", file=sys.stderr)
        elif wants_browser:
            guard("browser")
            timings.start("browser pass")
            if state is not None:
                state.start("browser")
            suppressions = suppression.Suppressions.load(
                _settings_for_ignore(args), _ignore_root(args))
            try:
                _run_browser_pass(audit_result, suppressions, args)
            except Exception as exc:  # noqa: BLE001
                # The static findings are already checkpointed, so stopping
                # here keeps them: a browser pass that dies half-way used to
                # cost the crawl and the static audit as well.
                return _stop_short(state, folder, target, timings, "browser",
                                   f"the browser pass failed: {exc}")
            if state is not None:
                state.done("browser", artifacts=filter(
                    None, [checkpoint.save_audit(state.run_dir, audit_result)]))
        elif state is not None:
            state.skip("browser", "no browser pass for this target")
        for doc in audit_result.documents:
            audit_issues.extend(doc.issues)
    timings.finish()

    # Auto-detect report language from site content
    lang = _detect_report_language(lang, pages)

    # --- Phase 3: Build combined result ---
    clean_findings = scan_result["findings"] if scan_result else []
    combined = _build_combined(args, target, is_url, lang, scan_result,
                               clean_findings, audit_issues)

    if agent_mode and agent_candidates:
        _attach_agent_payload(combined, agent_candidates, target)

    # --- Phase 4: Save reports ---
    all_content_findings = []
    if agent_mode and agent_candidates:
        all_content_findings = list(agent_candidates)
    elif scan_findings:
        all_content_findings = list(scan_findings)

    # Markdown first: it is plain text written in milliseconds and is the
    # artifact every consumer parses. The styled export starts a browser and
    # can take minutes on a large scan, so each writer is isolated: one
    # report failing must not take the others or the JSON below down with
    # it (a 158-page PDF once died after the whole browser pass and left
    # the run without any output at all).
    guard("reports")
    timings.start("writing reports")
    if state is not None:
        state.start("reports")
    written: dict = {}
    report_failures: list = []

    def _briefing() -> None:
        written["payload"] = _write_markdown_briefing(
            args, audit_result, agent_mode, agent_candidates, scan_findings,
            lang)

    for label, write in (
        ("agent briefing", _briefing),
        ("styled report",
         lambda: _write_styled_report(args, audit_result,
                                      all_content_findings, lang)),
    ):
        try:
            write()
        except Exception as exc:  # noqa: BLE001 - keep shipping the rest
            report_failures.append(f"{label}: {exc}")
            print(f"# warning: {label} failed: {exc}",
                  file=sys.stderr, flush=True)

    if state is not None:
        produced = [p for p in (getattr(args, "report", None),
                                getattr(args, "styled_report", None))
                    if p and Path(p).exists()]
        if report_failures and not produced:
            # Every writer failed, so there is no report at all. Recorded as
            # a failure rather than warned about, because "no findings" and
            # "nothing was written" look identical to whoever opens the
            # folder next, and only one of them is a clean result.
            return _stop_short(state, folder, target, timings, "reports",
                               "; ".join(report_failures))
        if report_failures:
            # Partly written: the phase did its job, and the reason records
            # which writer did not, so a resume can be a deliberate choice
            # rather than a guess.
            state.phase("reports")["reason"] = "; ".join(report_failures)
        state.done("reports", artifacts=produced)

    # The comparison and the timings go in the run folder next to the
    # documents they describe. Isolated the same way as the reports above:
    # a failure here must not cost the caller the JSON result.
    if folder is not None:
        if state is not None:
            state.start("documents")
        try:
            _write_run_documents(
                folder, target, timings, written.get("payload"), combined,
                len(audit_result.documents) if audit_result else 0)
            if state is not None:
                state.done("documents", artifacts=[
                    p for p in (folder.timings, folder.changes) if p.exists()])
        except Exception as exc:  # noqa: BLE001 - keep shipping the rest
            print(f"# warning: run documents failed: {exc}",
                  file=sys.stderr, flush=True)
            if state is not None:
                state.fail("documents", str(exc))
        print(f"# run folder: {folder.run}", file=sys.stderr)

    if state is not None:
        if state.next_phase() is None:
            state.finish()
        state.write_feedback()
        state.write_markdown()

    # --- Phase 5: Output (always JSON for agent) ---
    print(json.dumps(combined, indent=2, ensure_ascii=False))

    if args.check:
        critical = combined['audit']['counts']['critical']
        serious = combined['audit']['counts']['serious']
        if critical > 0 or serious > 0:
            return EXIT_FINDINGS
    return EXIT_OK
