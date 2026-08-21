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
from datetime import datetime
from pathlib import Path

import suppression

import detectors  # noqa: F401 - registers the detectors
from detectors.factory import DetectorFactory

from cli_impl import EXIT_ERROR, EXIT_FINDINGS, EXIT_OK
from cli_impl.agentcmds import _agent_detection_rules
from cli_impl.auditpass import (
    _crawl_maybe_rendering, _is_page_file, _run_browser_pass,
)
from cli_impl.output import _public
from cli_impl.scanning import (
    _analyze, _build_scan_config, _collect_files, _ignore_root,
    _settings_for_ignore,
)

#: Offline spans under this score never reach the agent candidate list.
_AGENT_CANDIDATE_FLOOR = 0.25


def _fullscan_report_paths(args, target: str, is_url: bool) -> None:
    """Default both reports onto ~/Desktop unless the caller named them."""
    desktop = Path.home() / "Desktop"
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    if is_url:
        name = target.replace("https://", "").replace("http://", "")
        name = name.replace("/", "_")[:30]
    else:
        name = Path(target).stem
    if not getattr(args, "styled_report", None):
        args.styled_report = str(desktop / f"xanalyze-{name}-{timestamp}.pdf")
    if not getattr(args, "report", None):
        args.report = str(desktop / f"xanalyze-{name}-{timestamp}.md")


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


def _content_findings_from_pages(pages) -> list:
    """The AI-patterns and typography pass for a crawled site.

    Local targets get this through the ordinary scan; a crawled page never
    was a file, so the same offline detector runs over its text blocks here
    and the spans become the finding dicts the reports read. Without this,
    a website scan silently lost whole report sections a repo scan had.
    """
    from models import Confidence

    offline = DetectorFactory.create("offline", include_style=True)
    findings = []
    for page in pages:
        for block in page.blocks:
            for span in offline.analyze_block(block):
                if (span.details or {}).get("error"):
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
        print(f"# Pages may appear empty. Install PySide6 + QtWebEngine for full support.", file=sys.stderr)
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
    write_styled_report(args.styled_report, model, lang)
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
                             lang: str) -> None:
    from cli_impl.reports import _write_report

    if not getattr(args, "report", None) or audit_result is None:
        return
    ai_for_report = _markdown_briefing_input(
        agent_mode, agent_candidates, scan_findings)
    _write_report(audit_result, args, lang, None, ai_findings=ai_for_report)
    print(f"# agent briefing: {args.report}", file=sys.stderr)


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
    is_url = target.startswith(("http://", "https://")) or args.url
    is_page = _is_page_file(target) if not is_url else False
    # Browser is automatic for URLs and HTML files, not for repos
    no_browser = getattr(args, "no_browser", False)
    wants_browser = (is_url or is_page) and not no_browser
    agent_mode = getattr(args, "agent", False)

    _fullscan_report_paths(args, target, is_url)

    # Validate target
    if not is_url and not is_page:
        if not Path(target).exists():
            print(f"path not found: {target}", file=sys.stderr)
            return EXIT_ERROR

    # --- Phase 1: AI patterns scan (for local files/repos) ---
    pages = None
    agent_candidates: list = []
    if not is_url:
        scan_findings, scan_result, agent_candidates = \
            _scan_local_target(target, args, lang, agent_mode)
    else:
        scan_findings, scan_result = [], None

    # --- Phase 2: Accessibility audit ---
    audit_issues: list = []
    audit_result = None
    if is_url:
        pages, target = _crawl_for_fullscan(target, args, no_browser)
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
            scan_findings = _content_findings_from_pages(pages)
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

        audit_result = _audit_fullscan_target(True, False, target, args, pages)
    elif is_page:
        audit_result = _audit_fullscan_target(False, True, target, args, pages)
    else:
        audit_result = _audit_fullscan_target(False, False, target, args, pages)

    if audit_result:
        # Run browser pass automatically for URLs and HTML files
        if wants_browser:
            suppressions = suppression.Suppressions.load(
                _settings_for_ignore(args), _ignore_root(args))
            _run_browser_pass(audit_result, suppressions, args)
        for doc in audit_result.documents:
            audit_issues.extend(doc.issues)

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

    _write_styled_report(args, audit_result, all_content_findings, lang)
    _write_markdown_briefing(args, audit_result, agent_mode,
                             agent_candidates, scan_findings, lang)

    # --- Phase 5: Output (always JSON for agent) ---
    print(json.dumps(combined, indent=2, ensure_ascii=False))

    if args.check:
        critical = combined['audit']['counts']['critical']
        serious = combined['audit']['counts']['serious']
        if critical > 0 or serious > 0:
            return EXIT_FINDINGS
    return EXIT_OK
