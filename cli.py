"""Headless mode — the same engine as the desktop app, driven from a
terminal so it can run as a post-processing step after an LLM coding agent
(Claude Code, Codex, Cursor and friends) has written files.

Typical use: the agent edits your source, then this runs over the result
and strips the characters no keyboard produces — curly quotes, em dashes,
non-breaking spaces, zero-width joiners, letters lifted from the wrong
alphabet — before anything reaches a commit.

    python cli.py fix ./src                  # clean files in place
    python cli.py scan ./src --json          # machine-readable report
    python cli.py scan ./src --check         # exit 1 if anything is found
    echo "text" | python cli.py clean        # filter text on stdin

Imports no GUI toolkit, so it runs anywhere Python does — a git hook, CI,
a container, an agent's shell tool.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import detectors  # noqa: F401 - registers the detectors
import suppression
import duplicates
import unicode_rules
import config
from audit.base import CATEGORIES
from detectors.factory import DetectorFactory
from file_writer import ReplacementPlan, apply_replacements
from lang_detect import guess_language
from models import Confidence, RepoAnalysisResult, ScanDiagnostics, score_to_confidence
from repo_scanner import DEFAULT_EXTENSIONS, DEFAULT_IGNORE_PATTERNS, ScanConfig, _parse_ignore_text, scan_file, scan_repo

# `fix` may only apply findings whose correction is fixed by a rule. That is
# now a property of the *pass* that produced a finding, not of a detector
# name: the character pass runs both standalone and inside the merged
# offline detector, so its findings arrive under more than one detector name
# but always carry this source stamp (see detectors/offline.py).
CHARACTER_SOURCE = "characters"

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2


# --------------------------------------------------------------- collection

def _collect_files(paths: list[str], args, missing_out=None,
                   diagnostics_out=None) -> list:
    """Turn the given paths into FileResults. A directory is walked with the
    exclusion rules; a file named directly is always scanned.

    `diagnostics_out`, if given, collects one `ScanDiagnostics` per walked
    directory, so the caller can say what was read rather than only what was
    found. A file named directly needs none: naming it is the answer.
    """
    ignore = _parse_ignore_text(DEFAULT_IGNORE_PATTERNS) if args.use_default_excludes else []
    ignore += list(args.exclude or [])
    # None lets the scope pick the extension set (comments are worth reading
    # in far more file types than copy is); an explicit --ext still wins.
    extensions = tuple(e if e.startswith(".") else "." + e for e in args.ext) if args.ext else None
    scope = getattr(args, "scope", "content")

    results = []
    #: Paths that do not exist, collected so the caller can fail rather than
    #: report a clean scan of nothing. A mistyped path is a pipeline pass
    #: otherwise, which is the worst kind of wrong answer.
    missing: list = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            walk = ScanDiagnostics()
            results.extend(scan_repo(str(p), ScanConfig(
                extensions=extensions,
                ignore_patterns=ignore,
                max_files=args.max_files,
                scope=scope,
            ), diagnostics=walk))
            if diagnostics_out is not None:
                diagnostics_out.append((str(p), walk))
        elif p.exists():
            results.append(scan_file(str(p), scope))
        else:
            print(f"path not found: {raw}", file=sys.stderr)
            missing.append(raw)
    if missing_out is not None:
        missing_out.extend(missing)
    return results


# Re-exported rather than defined here: the window needs the same mapping,
# and the copy that used to live in this file was invisible to it. See
# `detectors/judges.py`.
from detectors.judges import (  # noqa: E402 - kept beside its users
    JUDGE_ALIASES, JUDGE_BY_PROVIDER, JUDGE_NAMES, judge_for_provider,
)

#: The name that runs both engines over the same text and merges the result.
#: Spelled here as well as in the factory because `--detector hybrid` needs
#: the provider resolved for the judge half, exactly like a bare judge does.
HYBRID_NAME = "hybrid"


def _create_detector(args):
    """Build the detector `--detector` asked for, billed where it belongs.

    `scan` used to build it by name alone, which meant the name carried the
    billing decision: `claude-llm-judge` and only it, paid for with an
    `ANTHROPIC_API_KEY` from the environment. `audit --ai` had already stopped
    working that way - it asks `rewriter` which account is in play, so inside
    a Claude Code session it uses that session. The two commands disagreed on
    the same machine, and the disagreement showed up as an error message about
    a key the user did not need.
    """
    import rewriter

    name = args.detector
    provider = getattr(args, "provider", None)

    def resolved_judge() -> str:
        settings = config.Settings.load()
        return judge_for_provider(rewriter.effective_provider_name(
            settings, force=provider, allow_auto=True))

    if name == HYBRID_NAME:
        # The hybrid runs the offline pass itself, so only its judge half
        # needs an account - resolved the same way a bare judge is, which is
        # what keeps `--provider` meaning one thing across both.
        judge = resolved_judge()
        judge_config = ({"api_key": config.get_anthropic_api_key()}
                        if judge == "claude-llm-judge" else {})
        return DetectorFactory.create(
            name, judge_name=judge, judge_config=judge_config)

    if name in JUDGE_NAMES and (provider or name in JUDGE_ALIASES):
        name = resolved_judge()

    if name == "claude-llm-judge":
        # The key can live in the keychain as well as the environment; reading
        # only the environment made a key entered in Settings invisible here.
        return DetectorFactory.create(name, api_key=config.get_anthropic_api_key())
    return DetectorFactory.create(name)


def _categories(args) -> tuple[str, ...]:
    if args.categories:
        chosen = tuple(c.strip() for c in args.categories.split(",") if c.strip())
        unknown = [c for c in chosen if c not in unicode_rules.ALL_CATEGORIES]
        if unknown:
            raise SystemExit(
                f"unknown category: {', '.join(unknown)}. "
                f"Valid: {', '.join(unicode_rules.ALL_CATEGORIES)}"
            )
        return chosen
    if args.no_typography:
        return unicode_rules.HARD_CATEGORIES
    return unicode_rules.ALL_CATEGORIES


def _settings_for_ignore(args):
    """The user's own suppression list, unless --no-ignore was passed.

    Loaded lazily and defensively: the CLI must keep working in a container
    with no config directory, which is exactly where it runs in CI.
    """
    if getattr(args, "no_ignore", False):
        return None
    try:
        import config
        return config.Settings.load()
    except Exception:  # noqa: BLE001
        return None


def _ignore_root(args) -> str | None:
    if getattr(args, "no_ignore", False):
        return None
    paths = getattr(args, "paths", None) or []
    if paths:
        return paths[0]
    return getattr(args, "target", None)


def _report_detector_errors(spans) -> int:
    """Say, once, what the detector could not judge. Returns how many blocks."""
    failures = [s for s in spans if (s.details or {}).get("error")]
    if not failures:
        return 0
    reasons = []
    for span in failures:
        reason = span.details["error"]
        if reason not in reasons:
            reasons.append(reason)
    print(f"# {len(failures)} block(s) were not judged by "
          f"{failures[0].detector_name}:", file=sys.stderr)
    for reason in reasons[:3]:
        print(f"#   {reason}", file=sys.stderr)
    if len(reasons) > 3:
        print(f"#   ... and {len(reasons) - 3} other error(s)", file=sys.stderr)
    return len(failures)


def _analyze(file_results, args, unjudged_out: list | None = None):
    """Return (findings, blocks_by_id). Findings are plain dicts so the JSON
    output and the human output share one shape."""
    blocks = [b for f in file_results for b in f.blocks]
    blocks_by_id = {b.block_id: b for b in blocks}
    spans = []

    categories = _categories(args)
    # The offline detector holds both free passes. Style analysis is opt-in
    # here (it is reported, never auto-applied), so the two are requested
    # independently rather than as two detectors.
    wants_style = DetectorFactory.resolve(args.detector or "none") == "offline"
    if not args.no_unicode or wants_style:
        offline = DetectorFactory.create(
            "offline",
            categories=categories if not args.no_unicode else (),
            include_style=wants_style,
        )
        spans.extend(s for s in offline.analyze_blocks(blocks)
                     if s.confidence != Confidence.LOW
                     or (s.details or {}).get("source") == CHARACTER_SOURCE)
    if args.detector and args.detector != "none" and not wants_style:
        detector = _create_detector(args)
        judged = detector.analyze_blocks(blocks)
        # Blocks the detector could not read at all. Reported rather than
        # filtered away with the weak findings: an exhausted plan or a dead
        # key would otherwise print "No findings", which reads as a clean
        # result and is the one answer a failed run must never give.
        failed = _report_detector_errors(judged)
        if failed and unjudged_out is not None:
            unjudged_out.append(failed)
        spans.extend(s for s in judged
                     if s.confidence != Confidence.LOW
                     and not (s.details or {}).get("error"))

    # Applied before anything is reported, so a suppressed finding never
    # reaches --json, the exit code, or `fix`. The project's own
    # `.xanalyze-ignore` is read from the first scanned path.
    spans = suppression.filter_spans(
        spans, blocks_by_id,
        suppression.Suppressions.load(_settings_for_ignore(args), _ignore_root(args)),
    )

    findings = []
    for span in spans:
        block = blocks_by_id.get(span.block_id)
        if block is None:
            continue
        findings.append({
            "file": block.file_path,
            "line": block.line_number,
            "offset": block.start + span.start,
            "end_offset": block.start + span.end,
            "detector": span.detector_name,
            "source": (span.details or {}).get("source", ""),
            "confidence": span.confidence.value,
            "score": round(span.score, 3),
            "text": block.text[span.start:span.end],
            "replacement": span.replacement,
            "explanation": span.explanation,
            "_span": span,
            "_block": block,
        })
    findings.sort(key=lambda f: (f["file"], f["offset"]))
    return findings, blocks_by_id


# ------------------------------------------------------------------ output

def _public(finding: dict) -> dict:
    return {k: v for k, v in finding.items() if not k.startswith("_")}


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


# ---------------------------------------------------------------- commands

def cmd_scan(args) -> int:
    missing: list = []
    unjudged: list = []
    walked: list = []
    
    # Incremental scan: only scan changed files
    if getattr(args, "incremental", False):
        from scan_cache import get_cache
        cache = get_cache()
        # TODO: implement incremental logic
        # For now, just print a message
        print("# Incremental scan: checking cache...", file=sys.stderr)
    
    files = _collect_files(args.paths, args, missing_out=missing,
                           diagnostics_out=walked)
    findings, _ = _analyze(files, args, unjudged_out=unjudged)
    if args.json:
        _print_json(findings, walked=walked)
    else:
        _print_human(findings, walked=walked)
    if getattr(args, "styled_report", None):
        _write_styled_text_report(files, findings, args)
    if missing:
        # Said again at the end: the warning above scrolls past a long report,
        # and "nothing found" plus exit 0 is indistinguishable from success.
        print(f"# {len(missing)} path(s) did not exist; nothing was read from them",
              file=sys.stderr)
        return EXIT_ERROR
    if unjudged:
        # Same rule, one step further in: a detector that was asked and could
        # not answer leaves the text unread, and exit 0 would report that as
        # clean to whatever runs this in a pipeline.
        print("# the requested detector could not read the text; "
              "the result above is not a clean bill of health",
              file=sys.stderr)
        return EXIT_ERROR
    if args.check and findings:
        return EXIT_FINDINGS
    return EXIT_OK


def cmd_fix(args) -> int:
    files = _collect_files(args.paths, args)
    findings, _ = _analyze(files, args)

    # Only the non-keyboard-character findings carry a deterministic
    # correction; style findings need a human or a model and are reported
    # but never auto-applied.
    fixable = [f for f in findings
               if f["source"] == CHARACTER_SOURCE and f["replacement"] is not None
               and f["replacement"] != f["text"]]

    if args.dry_run:
        if args.json:
            _print_json(findings, applied={"dry_run": True, "would_fix": len(fixable)})
        else:
            _print_human(findings)
            print(f"\nDry run — would fix {len(fixable)} occurrence(s), nothing written.")
        return EXIT_FINDINGS if (args.check and findings) else EXIT_OK

    plans = [
        ReplacementPlan(
            file_path=f["_block"].file_path,
            abs_start=f["offset"],
            abs_end=f["end_offset"],
            original_text=f["text"],
            new_text=f["replacement"],
            block_id=f["_block"].block_id,
            allow_empty=(f["replacement"] == ""),
        )
        for f in fixable
    ]
    result = apply_replacements(plans) if plans else None

    if args.no_backup and result:
        # Don't delete existing .bak files from previous runs — only skip
        # creating new ones. The user might need them for recovery.
        pass

    applied = {
        "passages_applied": result.passages_applied if result else 0,
        "files_changed": result.files_changed if result else [],
        "skipped_stale": len(result.passages_skipped_stale) if result else 0,
        "skipped_overlap": len(result.passages_skipped_overlap) if result else 0,
        "errors": result.errors if result else [],
    }

    if args.json:
        _print_json(findings, applied=applied)
    else:
        _print_human(findings)
        print(f"\nFixed {applied['passages_applied']} occurrence(s) "
              f"in {len(applied['files_changed'])} file(s).")
        if applied["skipped_stale"]:
            print(f"Skipped {applied['skipped_stale']} (file changed since scan).")
        if applied["errors"]:
            for err in applied["errors"]:
                print(f"error: {err}", file=sys.stderr)

    if applied["errors"]:
        return EXIT_ERROR
    if args.check and findings:
        return EXIT_FINDINGS
    return EXIT_OK


def cmd_clean(args) -> int:
    """Filter text on stdin to stdout. Handy for piping a model's output
    through before it's written anywhere."""
    text = sys.stdin.read()
    language = args.language or guess_language(text)
    cleaned = unicode_rules.clean_text(text, language, _categories(args))
    sys.stdout.write(cleaned)
    if args.check and cleaned != text:
        return EXIT_FINDINGS
    return EXIT_OK


def cmd_cache(args) -> int:
    """Manage the scan cache."""
    from scan_cache import get_cache
    
    cache = get_cache()
    
    if args.cache_command == "stats":
        stats = cache.stats()
        print(f"Cache entries: {stats['entries']}")
        print(f"Cache size: {stats['size_bytes']} bytes")
        return EXIT_OK
    
    if args.cache_command == "clear":
        cache.clear()
        print("Cache cleared.")
        return EXIT_OK
    
    if args.cache_command == "path":
        print(cache.cache_path)
        return EXIT_OK
    
    return EXIT_OK


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
    import audit
    from audit.explanations import summary_line

    lang = args.language or "en"
    target = args.target
    is_url = target.startswith(("http://", "https://")) or args.url
    is_page_file = _is_page_file(target) if not is_url else False
    # Browser is automatic for URLs and HTML files, not for repos
    wants_browser = is_url or is_page_file

    # Auto-generate report paths on Desktop if not specified
    desktop = Path.home() / "Desktop"
    timestamp = __import__("datetime").datetime.now().strftime("%Y-%m-%d-%H%M")
    target_name = Path(target).stem if not is_url else target.replace("https://", "").replace("http://", "").replace("/", "_")[:30]

    if not getattr(args, "styled_report", None):
        args.styled_report = str(desktop / f"xanalyze-{target_name}-{timestamp}.pdf")
    if not getattr(args, "report", None):
        args.report = str(desktop / f"xanalyze-{target_name}-{timestamp}.md")

    # --- Agent mode: run offline scan and output candidates ---
    agent_mode = getattr(args, "agent", False)

    # Validate target
    if not is_url and not is_page_file:
        if not Path(target).exists():
            print(f"path not found: {target}", file=sys.stderr)
            return EXIT_ERROR

    # --- Phase 1: AI patterns scan (for local files/repos) ---
    scan_findings = []
    scan_result = None
    agent_candidates = []
    if not is_url:
        # Build scan args
        class ScanArgs:
            paths = [target]
            ext = args.ext
            exclude = args.exclude
            no_default_excludes = getattr(args, "no_default_excludes", False)
            use_default_excludes = not getattr(args, "no_default_excludes", False)
            max_files = args.max_files
            detector = args.detector
            scope = args.scope
            no_typography = getattr(args, "no_typography", False)
            no_ignore = False
            no_unicode = False
            categories = None
            json = False
            check = False
            incremental = False
            styled_report = None
            language = lang

        files = _collect_files(ScanArgs.paths, ScanArgs)
        if files:
            if agent_mode:
                # Agent mode: run offline scan, collect candidates for LLM judgment
                from detectors.offline import OfflineDetector
                blocks = [b for f in files for b in f.blocks]
                offline = DetectorFactory.create("offline", include_style=True)
                spans = offline.analyze_blocks(blocks)
                blocks_by_id = {b.block_id: b for b in blocks}
                seen = set()
                for span in spans:
                    if span.score < 0.25 or (span.details or {}).get("error"):
                        continue
                    if span.block_id not in seen:
                        seen.add(span.block_id)
                        block = blocks_by_id.get(span.block_id)
                        if block:
                            agent_candidates.append({
                                "block_id": span.block_id,
                                "file": block.file_path,
                                "line": block.line_number,
                                "text": block.text,
                                "language": block.language_hint or "en",
                                "offline_score": round(span.score, 3),
                                "offline_explanation": span.explanation,
                            })
                scan_result = {
                    "findings": [],
                    "counts": {"total": 0, "style": 0, "characters": 0},
                    "agent_mode": True,
                    "candidates_count": len(agent_candidates),
                }
            else:
                scan_findings, _ = _analyze(files, ScanArgs)
                clean_findings = [_public(f) for f in scan_findings]
                scan_result = {
                    "findings": clean_findings,
                    "counts": {
                        "total": len(clean_findings),
                        "style": len([f for f in clean_findings if f.get("source") == "style"]),
                        "characters": len([f for f in clean_findings if f.get("source") == "characters"]),
                    },
                }

    # --- Phase 2: Accessibility audit ---
    audit_result = None
    audit_issues = []
    if is_url:
        from crawler import CrawlConfig, EMPTY_JS_RENDERED, RENDER_AUTO, crawl

        if not target.startswith(("http://", "https://")):
            target = "https://" + target
        # Always use RENDER_AUTO for fullscan on URLs
        config = CrawlConfig(max_depth=args.depth, max_pages=args.max_pages,
                             render_mode=RENDER_AUTO)
        pages = _crawl_maybe_rendering(target, config)

        # Check if SPA pages were detected but not rendered
        spa_pages = [p for p in pages if EMPTY_JS_RENDERED in (p.diagnostics.reasons or [])]
        rendered_pages = [p for p in pages if "rendered" in (p.diagnostics.reasons or [])]
        if spa_pages and not rendered_pages:
            print(f"# WARNING: {len(spa_pages)} SPA page(s) detected but browser rendering failed.", file=sys.stderr)
            print(f"# Pages may appear empty. Install PySide6 + QtWebEngine for full support.", file=sys.stderr)
        elif spa_pages and rendered_pages:
            print(f"# SPA: {len(rendered_pages)} page(s) rendered via browser, {len(spa_pages)} failed.", file=sys.stderr)

        # Agent mode: extract candidates from crawled pages
        if agent_mode and pages:
            from detectors.offline import OfflineDetector
            offline = DetectorFactory.create("offline", include_style=True)
            seen = set()
            for page in pages:
                for block in page.blocks:
                    spans = offline.analyze_block(block)
                    for span in spans:
                        if span.score < 0.25 or (span.details or {}).get("error"):
                            continue
                        if span.block_id not in seen:
                            seen.add(span.block_id)
                            agent_candidates.append({
                                "block_id": span.block_id,
                                "file": page.url,
                                "line": 0,
                                "text": block.text,
                                "language": block.language_hint or "en",
                                "offline_score": round(span.score, 3),
                                "offline_explanation": span.explanation,
                            })
            scan_result = {
                "findings": [],
                "counts": {"total": 0, "style": 0, "characters": 0},
                "agent_mode": True,
                "candidates_count": len(agent_candidates),
            }

        audit_result = audit.analyze_pages(pages, target)
    elif is_page_file:
        audit_result = audit.analyze_page_file(target)
    else:
        from repo_scanner import ScanConfig, scan_repo

        ignore = _parse_ignore_text(DEFAULT_IGNORE_PATTERNS) if not getattr(args, "no_default_excludes", False) else []
        ignore += list(args.exclude or [])
        repo_files = scan_repo(target, ScanConfig(ignore_patterns=ignore,
                                                   max_files=args.max_files))
        if repo_files:
            audit_result = audit.analyze_files(repo_files, target)

    if audit_result:
        # Run browser pass automatically for URLs and HTML files
        if wants_browser:
            suppressions = suppression.Suppressions.load(
                _settings_for_ignore(args), _ignore_root(args))
            _run_browser_pass(audit_result, suppressions, args)
        for doc in audit_result.documents:
            audit_issues.extend(doc.issues)

    # --- Phase 3: Build combined result ---
    clean_findings = scan_result["findings"] if scan_result else []
    combined = {
        "target": args.target,
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

    if agent_mode and agent_candidates:
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

    # --- Phase 4: Save reports ---
    if getattr(args, "styled_report", None):
        from report.export import write_styled_report
        from report.model import from_accessibility, from_text_analysis

        model = None
        if audit_result:
            model = from_accessibility(audit_result, lang=lang)

        # Collect all content findings for styled report
        all_content_findings = []
        if agent_mode and agent_candidates:
            all_content_findings = list(agent_candidates)
        elif scan_findings:
            all_content_findings = list(scan_findings)

        if all_content_findings:
            class _ScanResult:
                def __init__(self, findings):
                    self.spans = []
                    self._findings = findings
                def blocks(self):
                    return []
            text_model = from_text_analysis(_ScanResult(all_content_findings))
            if model:
                model.findings.extend(text_model.findings)
            else:
                model = text_model
        if model:
            write_styled_report(args.styled_report, model, lang)
            print(f"# styled report: {args.styled_report}", file=sys.stderr)

    if getattr(args, "report", None):
        if audit_result:
            # Collect AI pattern findings for the report
            ai_for_report = []
            if agent_mode and agent_candidates:
                ai_for_report = [
                    {"file": c.get("file", ""), "line": c.get("line", 0),
                     "text": c.get("text", "")[:200],
                     "score": c.get("offline_score", 0),
                     "confidence": "medium" if c.get("offline_score", 0) >= 0.5 else "low",
                     "explanation": c.get("offline_explanation", "")}
                    for c in agent_candidates
                ]
            elif scan_findings:
                ai_for_report = [
                    {"file": f.get("file", ""), "line": f.get("line", 0),
                     "text": f.get("text", "")[:200],
                     "score": f.get("score", 0),
                     "confidence": f.get("confidence", ""),
                     "explanation": f.get("explanation", "")}
                    for f in scan_findings
                ]
            _write_report(audit_result, args, lang, None, ai_findings=ai_for_report)
            print(f"# agent briefing: {args.report}", file=sys.stderr)

    # --- Phase 5: Output (always JSON for agent) ---
    print(json.dumps(combined, indent=2, ensure_ascii=False))

    if args.check:
        critical = combined['audit']['counts']['critical']
        serious = combined['audit']['counts']['serious']
        if critical > 0 or serious > 0:
            return EXIT_FINDINGS
    return EXIT_OK


def cmd_compare(args) -> int:
    """Compare different detectors on the same files."""
    files = _collect_files(args.paths, args)
    if not files:
        print("No files found.", file=sys.stderr)
        return EXIT_ERROR
    
    blocks = [b for f in files for b in f.blocks]
    if not blocks:
        print("No text blocks found.", file=sys.stderr)
        return EXIT_ERROR
    
    detectors_to_compare = ["offline", "embedding"]
    results = {}
    
    for det_name in detectors_to_compare:
        try:
            detector = DetectorFactory.create(det_name)
            spans = detector.analyze_blocks(blocks)
            style_spans = [s for s in spans 
                          if s.confidence != Confidence.LOW
                          and (s.details or {}).get("source") != "characters"]
            results[det_name] = {
                "total": len(style_spans),
                "scores": [s.score for s in style_spans],
            }
        except Exception as e:
            results[det_name] = {"error": str(e)}
    
    if args.json:
        import json
        output = {}
        for name, data in results.items():
            if "error" in data:
                output[name] = data
            else:
                output[name] = {
                    "total": data["total"],
                    "mean_score": sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0,
                    "max_score": max(data["scores"]) if data["scores"] else 0,
                }
        print(json.dumps(output, indent=2))
    else:
        print(f"Comparing detectors on {len(blocks)} blocks:")
        print()
        for name, data in results.items():
            if "error" in data:
                print(f"  {name}: error - {data['error']}")
            else:
                mean = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0
                max_s = max(data["scores"]) if data["scores"] else 0
                print(f"  {name}: {data['total']} findings, "
                      f"mean={mean:.3f}, max={max_s:.3f}")
    
    return EXIT_OK


def cmd_audit(args) -> int:
    """Audit a URL or a folder across all four categories.

    Kept in the same CLI as the text scan because it answers a question about
    the same artefact and belongs in the same pre-commit hook or pipeline
    step, not because the two analyses share code — they do not.
    """
    import audit
    from audit.explanations import render, summary_line

    # Built before the crawl so a missing sign-in fails immediately, rather
    # than after crawling thirty pages.
    reviewer = None
    if getattr(args, "ai", False):
        from audit.ai_review import AIAccessibilityReview

        name, provider = _provider_for(args)
        print(f"# AI pass via {name}", file=sys.stderr)
        reviewer = AIAccessibilityReview(provider=provider)

    target = args.target
    # A target that is neither a URL nor a path that exists is a typo, and the
    # only honest answer is to say so. Auditing it used to print "0 findings"
    # and exit 0 - which in a pipeline is a pass, so a mistyped path read as a
    # clean bill of health.
    if not (target.startswith(("http://", "https://")) or args.url):
        if not Path(target).exists():
            print(f"path not found: {target}", file=sys.stderr)
            return EXIT_ERROR

    if _is_page_file(target) and not args.url:
        # A page built into one file is a finished document, so it is audited
        # as a page: `<head>` included, line numbers on, and - with --browser -
        # rendered from `file://`, which is faithful precisely because
        # everything it needs is inlined.
        result = audit.analyze_page_file(target, ai_review=reviewer)
    elif target.startswith(("http://", "https://")) or args.url:
        from crawler import CrawlConfig, EMPTY_JS_RENDERED, crawl

        # Same crawler as the text scan: depth-limited, and refusing to leave
        # the domain. That rule holds for both modes because there is one
        # crawler, not two.
        if not target.startswith(("http://", "https://")):
            target = "https://" + target
        config = CrawlConfig(max_depth=args.depth, max_pages=args.max_pages,
                             render_mode=_render_mode(args))
        pages = _crawl_maybe_rendering(target, config)
        
        # Check if SPA pages were detected but not rendered
        spa_pages = [p for p in pages if EMPTY_JS_RENDERED in (p.diagnostics.reasons or [])]
        rendered_pages = [p for p in pages if "rendered" in (p.diagnostics.reasons or [])]
        if spa_pages and not rendered_pages:
            print(f"# WARNING: {len(spa_pages)} SPA page(s) detected but browser rendering failed.", file=sys.stderr)
            print(f"# Use --browser flag and install PySide6 + QtWebEngine for SPA support.", file=sys.stderr)
        elif spa_pages and rendered_pages:
            print(f"# SPA: {len(rendered_pages)} page(s) rendered via browser, {len(spa_pages)} failed.", file=sys.stderr)
        
        result = audit.analyze_pages(pages, target, ai_review=reviewer)
    else:
        from repo_scanner import ScanConfig, scan_repo

        ignore = _parse_ignore_text(DEFAULT_IGNORE_PATTERNS) if args.use_default_excludes else []
        ignore += list(args.exclude or [])
        files = scan_repo(target, ScanConfig(ignore_patterns=ignore,
                                             max_files=args.max_files))
        result = audit.analyze_files(files, target, ai_review=reviewer)

    # The same suppression list governs both analyses: a user thinking "not
    # this part of the site" means it for the whole tool, not per subsystem.
    suppressions = suppression.Suppressions.load(
        _settings_for_ignore(args), _ignore_root(args))

    if getattr(args, "browser", False):
        _run_browser_pass(result, suppressions, args)

    for document in result.documents:
        document.issues = suppression.filter_issues(document.issues, suppressions)

    # Category narrowing is a *view* over one pass, not a different run: the
    # rules are cheap and share the parse, so filtering after the fact keeps
    # `--category seo` and a full audit returning identical findings.
    wanted = set(getattr(args, "category", None) or CATEGORIES)
    if wanted != set(CATEGORIES):
        for document in result.documents:
            document.issues = [i for i in document.issues if i.category in wanted]

    lang = args.language or "en"

    fix_outcome = None
    if getattr(args, "fix", False):
        fix_outcome = _apply_fixes(result, args, lang)
        if fix_outcome.files_changed and result.mode in ("file", "repo"):
            # Re-read what is now on disk. Printing the numbers from before
            # the corrections were written would tell the user - or the agent
            # parsing `--json` - that work is outstanding when it is done.
            result = _reaudit(args, target, result)
            for document in result.documents:
                document.issues = suppression.filter_issues(
                    document.issues, suppressions)
            if wanted != set(CATEGORIES):
                for document in result.documents:
                    document.issues = [i for i in document.issues
                                       if i.category in wanted]
    if getattr(args, "report", None):
        _write_report(result, args, lang, fix_outcome)
    if getattr(args, "styled_report", None):
        from report.export import write_styled_report
        from report.model import from_accessibility

        write_styled_report(args.styled_report, from_accessibility(result, lang), lang)
        print(f"# styled report: {args.styled_report}", file=sys.stderr)

    if args.json:
        print(json.dumps({
            "root": result.root,
            "mode": result.mode,
            "counts": result.counts(),
            "rules_run": result.rules_run,
            "issues": [
                {
                    "rule": issue.rule_id,
                    "category": issue.category,
                    "severity": issue.severity,
                    "confidence": issue.confidence,
                    "source": issue.source,
                    "selector": issue.selector,
                    "line": issue.line,
                    "snippet": issue.snippet,
                    "details": issue.details,
                    "fix_snippet": issue.fix_snippet,
                }
                for issue in result.issues()
            ],
        }, ensure_ascii=False, indent=2))
    else:
        for document in result.documents_with_issues():
            print()
            print(document.source)
            for issue in document.issues:
                explanation = render(issue, lang)
                location = f"line {issue.line}" if issue.line else issue.selector[-60:]
                print(f"  [{issue.severity}] {explanation.title}  ({location})")
                print(f"      {explanation.found}")
                print(f"      {_wrap(explanation.why)}")
                print(f"      fix: {_wrap(explanation.fix)}")
                if issue.fix_snippet:
                    print(f"      -> {issue.fix_snippet}")
                if explanation.caveat:
                    print(f"      ! {explanation.caveat}")
        for document in result.documents:
            if document.error:
                print(f"\n{document.source}\n  not checked: {document.error}")
        print()
        print(summary_line(result, lang))

    counts = result.counts()
    if args.check and (counts.get("critical") or counts.get("serious")):
        return EXIT_FINDINGS
    return EXIT_OK


def _reaudit(args, target: str, previous):
    """Run the same audit again over the same files, after correcting them."""
    import audit

    if previous.mode == "file":
        return audit.analyze_page_file(target)
    from repo_scanner import ScanConfig, scan_repo

    ignore = _parse_ignore_text(DEFAULT_IGNORE_PATTERNS) if args.use_default_excludes else []
    ignore += list(args.exclude or [])
    files = scan_repo(target, ScanConfig(ignore_patterns=ignore,
                                         max_files=args.max_files))
    return audit.analyze_files(files, target)


def _apply_fixes(result, args, lang: str):
    """Write back what the audit already knows how to correct.

    Returns a small record of what happened, so `--report` and the JSON output
    can say it rather than the user having to diff their own files.

    The order is deliberate. Corrections that need no decision go in first and
    alone; the ones that encode a judgement are only written when `--ai` was
    asked for, and even then a value the model declined to invent is left
    undone rather than filled with something plausible.
    """
    from audit import fix_ai, fixer

    ready, pending, skipped = fixer.plan_fixes(result.documents)

    if pending:
        # The page's own language is in the page. Reading it beats asking a
        # model, and beats the rule's default, which is a guess.
        page_text = _document_text(result)
        filled, pending = fix_ai.fill_locally(pending, page_text)
        ready += filled

    ai_written = []
    if pending and getattr(args, "ai", False):
        name, provider = _provider_for(args)
        print(f"# writing the remaining corrections with {name}", file=sys.stderr)
        filled, pending = fix_ai.describe(pending, _document_text(result),
                                          provider, lang)
        ready += filled
        ai_written = [p.rule_id for p in filled]

    outcome = fixer.apply_fixes(ready)
    outcome.skipped.extend(skipped)
    for plan in pending:
        outcome.skipped.append(fixer.SkippedFix(
            plan.rule_id, plan.path, plan.line, plan.needs_input))

    print(f"# fixed {len(outcome.applied)} in {len(outcome.files_changed)} file(s); "
          f"{len(outcome.skipped)} left alone", file=sys.stderr)
    if outcome.backups:
        print(f"# backups: {', '.join(outcome.backups)} "
              f"(restore with `cli.py undo`)", file=sys.stderr)
    for error in outcome.errors:
        print(f"# {error}", file=sys.stderr)
    outcome.ai_written = ai_written
    return outcome


def _document_text(result) -> str:
    """The page's own words, for anything that has to read it."""
    import re as _re
    parts = []
    for document in result.documents:
        path = document.source
        if path.startswith(("http://", "https://")):
            continue
        try:
            with open(path, encoding="utf-8", errors="surrogateescape") as handle:
                markup = handle.read()
        except OSError:
            continue
        parts.append(_re.sub(r"<[^>]+>", " ", markup))
    return " ".join(parts)


def cmd_undo(args) -> int:
    """Put files back the way they were before the corrections went in."""
    import backups

    paths = []
    for target in args.paths:
        path = Path(target)
        if path.is_dir():
            paths += [str(p)[:-len(backups.SUFFIX)]
                      for p in path.rglob("*" + backups.SUFFIX)]
        elif str(path).endswith(backups.SUFFIX):
            paths.append(str(path)[:-len(backups.SUFFIX)])
        else:
            paths.append(str(path))

    if not paths:
        print("nothing to undo: no .bak copies found", file=sys.stderr)
        return EXIT_OK

    # Undo covers both writers - the character fixes from `fix` and the
    # corrections from `audit --fix` - because there is one backup rule and
    # therefore one way back.
    restored, problems = backups.restore(paths)
    for path in restored:
        print(f"restored {path}")
    for problem in problems:
        print(problem, file=sys.stderr)
    return EXIT_ERROR if problems and not restored else EXIT_OK


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


#: `--breakpoints` with no value means all of them.
def _chosen_breakpoints(args):
    """The widths to audit at, or () for the engine's default single pass."""
    from audit import responsive

    raw = getattr(args, "breakpoints", None)
    if not raw:
        return ()
    if raw == "all":
        return responsive.BREAKPOINTS
    wanted = [name.strip() for name in raw.split(",") if name.strip()]
    known = {name: (name, w, h) for name, w, h in responsive.BREAKPOINTS}
    unknown = [name for name in wanted if name not in known]
    if unknown:
        raise SystemExit(
            f"unknown breakpoint: {', '.join(unknown)}. "
            f"Valid: {', '.join(known)}")
    # Kept in the canonical order, widest first, whatever order they were
    # typed in: the first pass to see a finding is the one whose selector the
    # merged row keeps, and that should not depend on typing order.
    return tuple(known[name] for name, _w, _h in responsive.BREAKPOINTS
                 if name in wanted)


def _audit_at_widths(urls, options, sizes) -> list:
    """One browser, every page, every width."""
    from audit import driver
    from audit import responsive
    from dataclasses import replace

    driver.ensure_headless_application()
    runner = driver.BrowserAuditRunner(
        replace(options, viewport=(sizes[0][1], sizes[0][2])))
    try:
        return [responsive.audit_responsive(url, sizes, options, runner=runner)
                for url in urls]
    finally:
        runner.close()


def _run_browser_pass(result, suppressions, args=None) -> None:
    """Load each audited page in a real browser and fold the findings in.

    Runs for a crawled site and for a single self-contained HTML file. Not for
    repo mode: a browser has nothing to load for a `.jsx` fragment that was
    never a page, and half-auditing a template would report problems the built
    page does not have.

    The suppression list is handed to the engines rather than applied to
    their output, so an excluded region is never analysed in the first place
    — for axe that is the difference between "ignore these results" and "do
    not spend seconds computing them".
    """
    if result.mode not in ("web", "file"):
        return
    from audit import browser as browser_mod
    from audit import driver

    usable, reason = driver.available()
    if not usable:
        print(f"# browser pass skipped: {reason}", file=sys.stderr)
        return

    targets = [d for d in result.documents if not d.error]
    if not targets:
        return

    options = browser_mod.BrowserAuditOptions(
        exclude=list(suppressions.selectors),
        disabled_rules=list(suppressions.rules),
        allow_local_files=result.mode == "file",
    )
    sizes = _chosen_breakpoints(args) if args is not None else ()
    where = (f" at {len(sizes)} widths" if sizes else "")
    print(f"# browser pass over {len(targets)} page(s){where}", file=sys.stderr)
    # The document is still keyed by its own source (a path, in file mode), so
    # the findings land back on the row the user recognises rather than on a
    # `file://` URL they never typed.
    urls = [_browser_url(d.source) for d in targets]
    audits = (_audit_at_widths(urls, options, sizes) if sizes
              else driver.audit_urls(urls, options))
    by_url = {a.url: a for a in audits}
    for document, url in zip(targets, urls):
        page_audit = by_url.get(url)
        if page_audit is None:
            continue
        if page_audit.error:
            print(f"# {document.source}: {page_audit.error}", file=sys.stderr)
            continue
        for name, message in page_audit.engine_errors.items():
            print(f"# {document.source}: {name} {message}", file=sys.stderr)
        # Deduplicated against the static findings too, not just among
        # themselves: axe and our own rule both report a missing `alt`, and
        # a run with --browser must not double every such row.
        document.issues = browser_mod.deduplicate(
            list(document.issues) + list(page_audit.issues),
            markup=getattr(page_audit, "html", "") or "")


#: Extensions that make a file a page rather than a piece of a project.
PAGE_FILE_SUFFIXES = (".html", ".htm", ".xhtml")


def _is_page_file(target: str) -> bool:
    """Is this one HTML file rather than a folder or a URL?"""
    from pathlib import Path
    path = Path(target)
    return path.is_file() and path.suffix.lower() in PAGE_FILE_SUFFIXES


def _render_mode(args) -> str:
    """When to hand a page to a browser during the crawl.

    Defaults to following `--browser`: someone who asked for a browser pass has
    already accepted the cost of one, and a client-rendered site is precisely
    where the fetch finds nothing to audit. `--render` overrides that either
    way, because "audit what the server sends" is also a legitimate question.
    """
    from crawler import RENDER_AUTO, RENDER_NEVER

    explicit = getattr(args, "render", None)
    if explicit:
        return explicit
    return RENDER_AUTO if getattr(args, "browser", False) else RENDER_NEVER


def _crawl_maybe_rendering(target: str, config):
    """Crawl, starting a browser only if the configuration can use one."""
    from crawler import RENDER_NEVER, crawl

    if config.render_mode == RENDER_NEVER:
        return crawl(target, config)

    from audit import driver

    usable, reason = driver.available()
    if not usable:
        print(f"# Browser rendering unavailable: {reason}", file=sys.stderr)
        print(f"# SPA/React/Vue pages may return empty results.", file=sys.stderr)
        print(f"# Install PySide6 and QtWebEngine for full SPA support.", file=sys.stderr)
        return crawl(target, config)
    with driver.html_renderer() as render:
        return crawl(target, config, render=render)


def _browser_url(source: str) -> str:
    """The address the browser should open for a document.

    A crawled page already is a URL. A file has to become one, and it has to
    be absolute: `file://page.html` is not a path the browser can resolve.
    """
    if source.startswith(("http://", "https://", "file://")):
        return source
    from pathlib import Path
    return Path(source).resolve().as_uri()


def _wrap(text: str, width: int = 96, indent: str = "      ") -> str:
    """Fold a paragraph for terminal output; the explanations are written as
    prose, and prose at 400 columns is unreadable."""
    import textwrap
    lines = textwrap.wrap(text, width=width)
    return ("\n" + indent).join(lines)



# ------------------------------------------------------------------- ai
#
# Every AI-backed feature has a CLI entry point, for two reasons. The first
# is that this tool is meant to run unattended in hooks and pipelines, where
# there is no Settings dialog to sign in from. The second is that a feature
# only reachable through a window cannot be checked without a person and a
# mouse, so "does the subscription actually work" stops being an answerable
# question the moment the only path to it is the UI.

def _provider_for(args):
    """Build the provider the user asked for, or the automatic one.

    `allow_auto=True` is what routes a run started inside Claude Code to the
    signed-in Claude session instead of a paid subscription; `--provider`
    always wins over it.
    """
    import rewriter

    settings = config.Settings.load()
    name = rewriter.effective_provider_name(
        settings, force=getattr(args, "provider", None), allow_auto=True)
    return name, rewriter.build_provider(
        settings, force=getattr(args, "provider", None), allow_auto=True)


def cmd_ai_status(args) -> int:
    """What would a rewrite cost, and to whom — asked without spending it.

    Every provider answers this without billing anything: a key check for
    Anthropic, `claude auth status` for Claude Code, `/api/me` for xFormat.
    """
    from llm.base import LLMProviderFactory, LLMUnavailable

    settings = config.Settings.load()
    name, provider = _provider_for(args)
    auto = (name != (settings.llm_provider or "anthropic")
            and not getattr(args, "provider", None))

    print(f"provider: {name}  ({provider.display_name})")
    if auto:
        print("  auto-selected: this is a Claude Code session, so its own "
              "signed-in account pays rather than a second subscription")
        print("  (disable with prefer_claude_code_in_cli=false in settings.json)")
    print(f"configured in settings.json: {settings.llm_provider}")
    print(f"available: {', '.join(LLMProviderFactory.available())}")

    try:
        status = provider.auth_status()
    except LLMUnavailable as exc:
        print(f"  status: unavailable — {exc}")
        return EXIT_ERROR
    state = "signed in" if status.signed_in else "NOT signed in"
    print(f"  status: {state}  {status.detail}")
    if status.quota_remaining is not None:
        print(f"  budget left this period: {status.quota_remaining}")

    # Being signed in and being *allowed* are different questions on xFormat:
    # the account can be perfectly valid while this application has no consent,
    # and a status that reported only the first would call a broken setup ready.
    if status.signed_in and name == "xformat":
        try:
            app = provider.app_state()
        except LLMUnavailable as exc:
            print(f"  app consent: could not be read — {exc}")
            return EXIT_OK
        if app is None:
            print(f"  app consent: this backend does not know '{provider.client_app}'")
        elif app.get("connected"):
            print(f"  app consent: granted for {app.get('name')}")
        else:
            print(f"  app consent: MISSING for {app.get('name')} — run `ai grant`")
            return EXIT_FINDINGS
    return EXIT_OK if status.signed_in else EXIT_FINDINGS


def cmd_ai_login(args) -> int:
    """Sign in to the account that pays for AI calls.

    Only xFormat has credentials to take here. Claude Code owns its own
    login and Anthropic takes a key, so for those this says where to go
    rather than pretending to a flow it does not have.
    """
    import getpass

    from llm.base import LLMAuthError, LLMUnavailable

    settings = config.Settings.load()
    name = args.provider or "xformat"
    if name == "claude-code":
        print("Claude Code manages its own sign-in. Run: claude auth login")
        return EXIT_OK
    if name == "anthropic":
        print("The Anthropic provider takes an API key, not a login. Set "
              "ANTHROPIC_API_KEY, or enter the key in Settings (it is stored "
              "in the OS keychain, never in settings.json).")
        return EXIT_OK

    from llm.base import LLMProviderFactory

    provider = LLMProviderFactory.create(
        "xformat", base_url=settings.xformat_base_url,
        endpoints=settings.xformat_endpoints,
    )
    email = args.email or input("xFormat email: ").strip()
    # Never accepted as an argument: a password on the command line lands in
    # the shell history and in the process list of every user on the machine.
    password = os.environ.get("XFORMAT_PASSWORD") or getpass.getpass("Password: ")
    try:
        status = provider.sign_in(email, password)
    except (LLMAuthError, LLMUnavailable) as exc:
        print(f"sign-in failed: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(f"signed in: {status.detail}")
    if status.quota_remaining is not None:
        print(f"budget left this period: {status.quota_remaining}")
    return EXIT_OK


def cmd_ai_logout(args) -> int:
    from llm.base import LLMProviderFactory

    settings = config.Settings.load()
    name = args.provider or "xformat"
    if name != "xformat":
        print(f"nothing to sign out of for '{name}'.")
        return EXIT_OK
    provider = LLMProviderFactory.create(
        "xformat", base_url=settings.xformat_base_url,
        endpoints=settings.xformat_endpoints,
    )
    provider.sign_out()
    print("signed out of xFormat (session revoked server-side, tokens removed "
          "from the keychain).")
    return EXIT_OK


def _xformat_provider():
    """The xFormat provider specifically, regardless of what is configured.

    The consent commands only make sense for it: a personal API key and a local
    Claude Code session have no notion of a third-party application asking for
    access to someone's account.
    """
    from llm.base import LLMProviderFactory

    settings = config.Settings.load()
    return LLMProviderFactory.create(
        "xformat", base_url=settings.xformat_base_url,
        endpoints=settings.xformat_endpoints,
    )


def cmd_ai_apps(args) -> int:
    """Which applications this xFormat account has let in."""
    from llm.base import LLMAuthError, LLMUnavailable

    provider = _xformat_provider()
    try:
        apps = provider.list_apps()
    except (LLMAuthError, LLMUnavailable) as exc:
        print(f"could not read connected apps: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if not apps:
        print("the backend reported no applications (an older deployment?)")
        return EXIT_OK
    for app in apps:
        mark = "connected" if app.get("connected") else "not connected"
        needs = "" if app.get("requiresGrant") else "  (no consent needed)"
        here = "  <- this app" if app.get("slug") == provider.client_app else ""
        print(f"  {app.get('slug'):<12} {mark:<14} {app.get('name', '')}{needs}{here}")
    return EXIT_OK


def cmd_ai_grant(args) -> int:
    """Allow this application to use the signed-in xFormat account."""
    from llm.base import LLMAuthError, LLMUnavailable

    provider = _xformat_provider()
    slug = args.app or provider.client_app
    try:
        result = provider.grant_app(slug)
    except (LLMAuthError, LLMUnavailable) as exc:
        print(f"could not grant access: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(f"granted: {result.get('name') or slug} may now use this account.")
    return EXIT_OK


def cmd_ai_revoke(args) -> int:
    from llm.base import LLMAuthError, LLMUnavailable

    provider = _xformat_provider()
    slug = args.app or provider.client_app
    try:
        result = provider.revoke_app(slug)
    except (LLMAuthError, LLMUnavailable) as exc:
        print(f"could not revoke access: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if result.get("changed"):
        print(f"revoked: {slug} can no longer use this account.")
    else:
        print(f"nothing to revoke: {slug} had no active grant.")
    return EXIT_OK


def cmd_ai_rewrite(args) -> int:
    """Rewrite one passage, or a whole batch from stdin.

    The point is not the rewrite itself — the app does that from the results
    panel. It is that the billing path can be exercised end to end from a
    terminal, with one short passage, before anyone points a bulk run at it.
    """
    from llm.base import LLMAuthError, LLMUnavailable

    text = args.text
    if text is None:
        text = sys.stdin.read()
    passages = [p.strip() for p in text.split("\n\n") if p.strip()] if args.split else [text.strip()]
    if not any(passages):
        print("nothing to rewrite", file=sys.stderr)
        return EXIT_ERROR

    name, provider = _provider_for(args)
    if not args.quiet:
        print(f"# provider: {name}", file=sys.stderr)
    try:
        results = provider.rewrite_batch([(p, args.language) for p in passages])
    except (LLMAuthError, LLMUnavailable) as exc:
        print(f"rewrite failed: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print("\n\n".join(results))
    return EXIT_OK


def _agent_detection_rules() -> dict:
    """All AI detection rules the system knows, for the agent LLM judge."""
    return {
        "statistical_signals": {
            "uniformity": {
                "weight": 0.40,
                "description": "Sentence length variation (burstiness). Human writing varies a lot; AI is uniform.",
                "score_meaning": "0.0 = bursty (human), 1.0 = uniform (AI-like)",
                "threshold": "Below 3 sentences: not measured"
            },
            "repetition": {
                "weight": 0.35,
                "description": "Lexical diversity (type-token ratio). AI repeats words more.",
                "score_meaning": "0.0 = diverse (human), 1.0 = repetitive (AI-like)",
                "threshold": "Below 20 words: not measured"
            },
            "dash_density": {
                "weight": 0.25,
                "description": "Em/en-dash usage density. AI overuses em dashes as commas/parentheses.",
                "score_meaning": "0.3 dashes/100w = normal human, >2/100w = heavy AI-like",
                "note": "This IS a real AI signal. Do NOT dismiss it as 'just typography'."
            }
        },
        "structural_patterns": {
            "en": [
                "not just X but Y",
                "it's not about X, it's about Y",
                "no X. no Y. just Z.",
                "whether you're X or Y",
                "take your X to the next level"
            ],
            "uk": [
                "не просто X а Y",
                "справа не в X справа в Y",
                "чи ви X чи Y",
                "це не просто про X; це про Y",
                "жодних X. жодних Y. лише Z.",
                "вивести X на новий рівень"
            ],
            "it": [
                "non solo X ma anche Y",
                "non si tratta di X si tratta di Y",
                "che tu sia X o Y",
                "niente X. niente Y. solo Z.",
                "portare X a un nuovo livello"
            ]
        },
        "cliche_phrases": {
            "description": "Phrases AI reaches for far more than humans. Strong phrases (with space) weight 0.30, weak (single word) weight 0.10.",
            "en_strong": [
                "it's important to note", "it is worth mentioning", "it should be noted that",
                "in today's fast-paced world", "in today's digital age", "in the era of",
                "in a world where", "furthermore,", "moreover,", "additionally,",
                "in conclusion", "to summarize", "let's dive in", "let's explore",
                "unlock the potential", "seamless experience", "look no further",
                "elevate your", "unleash the power", "game-changer",
                "comprehensive solution", "all-in-one solution", "intuitive interface",
                "in just a few clicks", "join thousands of", "satisfied users",
                "streamline your workflow", "bridges the gap between"
            ],
            "en_weak": [
                "delve", "underscore", "pivotal", "realm", "harness", "illuminate",
                "facilitate", "refine", "bolster", "streamline", "revolutionize",
                "innovative", "transformative", "seamless", "scalable", "comprehensive",
                "robust", "stellar", "exceptional", "unparalleled", "dynamic",
                "intricate", "nuanced", "holistic", "paramount", "testament", "tapestry"
            ],
            "uk_strong": [
                "у сучасному світі", "варто зазначити", "важливо підкреслити",
                "зануримося", "розкрити потенціал", "на завершення", "підсумовуючи",
                "комплексне рішення", "все в одному", "інтуїтивний інтерфейс",
                "у кілька кліків", "за кілька хвилин", "все, що вам потрібно",
                "задоволених користувачів", "розкрийте повний потенціал"
            ],
            "it_strong": [
                "nel mondo di oggi", "è importante sottolineare", "vale la pena notare",
                "in conclusione", "soluzione completa", "tutto in uno",
                "interfaccia intuitiva", "in pochi clic", "utenti soddisfatti",
                "sblocca il pieno potenziale", "ottimizza il tuo flusso di lavoro"
            ]
        },
        "scoring_formula": {
            "description": "Evidence combines with diminishing returns. Base = weighted average of measured signals. Then each cliché/structural hit reduces remaining room.",
            "base": "0.40*uniformity + 0.35*repetition + 0.25*dashes (renormalized if any is None)",
            "cliches": "Each strong phrase reduces remaining by 30%, each weak word by 10%",
            "structural": "Each structural hit reduces remaining by 25%",
            "reporting_threshold": "Without at least one concrete marker (cliché or structural), score capped at 0.32"
        },
        "important_notes": [
            "Em dash density IS a real AI signal, not just typography",
            "Short phrases without spaces (single words) are weak signals",
            "Phrases with spaces are strong signals",
            "Statistical signals alone (uniformity, diversity, dashes) without cliché/structural markers are capped at 0.32",
            "Technical code/docstrings are almost never AI-generated",
            "Marketing copy, landing pages, onboarding text are prime AI targets"
        ]
    }


def cmd_agent_scan(args) -> int:
    """Offline scan that outputs candidate blocks for an agent to judge.

    Runs the free offline detector (heuristic + unicode anomalies) and
    outputs every block that scored >= threshold as JSON. The agent
    (opencode, Claude Code, Cursor) reads this, judges each block with
    its own LLM, and pipes the judgments to `xanalyze agent-judge`.

    With --full: also outputs all blocks for the agent to read and judge
    independently (hybrid mode). The agent judges both offline candidates
    AND reads raw blocks to find patterns the offline detector missed.

    No API key, no registration, no network call — the agent IS the judge.
    """
    walked: list = []
    files = _collect_files(args.paths, args, diagnostics_out=walked)

    categories = _categories(args)
    offline = DetectorFactory.create(
        "offline",
        categories=categories if not args.no_unicode else (),
        include_style=True,
    )

    blocks = [b for f in files for b in f.blocks]
    spans = offline.analyze_blocks(blocks)

    threshold = getattr(args, "threshold", 0.25)
    full_mode = getattr(args, "full", False)
    candidates = []
    seen_blocks = set()
    for span in spans:
        if span.score < threshold:
            continue
        if (span.details or {}).get("error"):
            continue
        block_id = span.block_id
        block = next((b for b in blocks if b.block_id == block_id), None)
        if block is None:
            continue
        if block_id not in seen_blocks:
            seen_blocks.add(block_id)
            candidates.append({
                "block_id": block_id,
                "file": block.file_path,
                "line": block.line_number,
                "text": block.text,
                "language": block.language_hint or "en",
                "offline_score": round(span.score, 3),
                "offline_explanation": span.explanation,
                "offline_details": span.details,
            })

    payload = {
        "candidates": candidates,
        "total_blocks": len(blocks),
        "total_candidates": len(candidates),
        "threshold": threshold,
        "mode": "full" if full_mode else "candidates-only",
        "detection_rules": _agent_detection_rules(),
    }

    if full_mode:
        # Output ALL blocks for the agent to read independently
        all_blocks = []
        for block in blocks:
            all_blocks.append({
                "block_id": block.block_id,
                "file": block.file_path,
                "line": block.line_number,
                "text": block.text,
                "language": block.language_hint or "en",
            })
        payload["blocks"] = all_blocks
        payload["instruction"] = (
            "HYBRID MODE: You have two tasks.\n"
            "1. JUDGE CANDIDATES: Evaluate each candidate in 'candidates' using "
            "detection_rules. For each return block_id, score, reason.\n"
            "2. READ BLOCKS: Read every block in 'blocks' independently. Find "
            "AI-generated passages the offline detector MISSED. For each finding "
            "return block_id, quote (verbatim from text), score, reason.\n"
            "Use ALL detection rules: statistical signals, structural patterns, "
            "cliché phrases. Do NOT dismiss dash density as typography.\n"
            "IMPORTANT: Pass the 'blocks' array through unchanged in your output.\n"
            "Output JSON: {\"judgments\": [...], \"agent_findings\": [...], "
            "\"blocks\": [...]}"
        )
    else:
        payload["instruction"] = (
            "You are an AI text judge. Use the detection_rules above to evaluate "
            "each candidate. Consider ALL signals: statistical (uniformity, "
            "repetition, dash density), structural patterns, and cliché phrases. "
            "Do NOT dismiss dash density as 'typography' — it IS an AI signal. "
            "For each candidate return block_id, score (0.0=human, 1.0=AI), "
            "and a one-sentence reason referencing which rules fired. "
            "Output JSON: [{\"block_id\": \"...\", \"score\": 0.8, "
            "\"reason\": \"...\"}]"
        )

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return EXIT_OK


def cmd_update(args) -> int:
    """Self-update the CLI binary from the latest GitHub Release.

    Checks the configured GitHub repository for a newer version,
    downloads the platform-appropriate CLI asset, and replaces the
    running binary in place.  When running from source, prints the
    download link instead.
    """
    import updater
    return updater.do_update()


def cmd_agent_judge(args) -> int:
    """Combine offline scan with agent's LLM judgments into a final report.

    Two input modes:

    SIMPLE (default): Reads judgments from --judgments or stdin:
        [{"block_id": "...", "score": 0.8, "reason": "..."}]
        Merges offline scores with agent judgments.

    HYBRID (--hybrid): Reads a dict with both judgments and agent_findings:
        {"judgments": [...], "agent_findings": [...]}
        agent_findings are the agent's independent analysis of raw blocks.
        Merges using hybrid logic: agreement / offline-only / model-only.
    """
    import_file = getattr(args, "judgments", None)
    if import_file and import_file != "-":
        with open(import_file) as f:
            raw = f.read()
    else:
        raw = sys.stdin.read()

    try:
        input_data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in input: {exc}", file=sys.stderr)
        return EXIT_ERROR

    # Parse input: simple (list) or hybrid (dict with judgments + agent_findings)
    hybrid_mode = getattr(args, "hybrid", False)
    judgments_list = []
    agent_findings_list = []
    pipeline_blocks = []  # blocks from agent-scan pipeline (stable block_ids)

    if isinstance(input_data, dict):
        judgments_list = input_data.get("judgments", [])
        agent_findings_list = input_data.get("agent_findings", [])
        pipeline_blocks = input_data.get("blocks", [])
        if agent_findings_list:
            hybrid_mode = True
    elif isinstance(input_data, list):
        judgments_list = input_data

    judgments = {j["block_id"]: j for j in judgments_list if "block_id" in j}

    walked: list = []
    files = _collect_files(args.paths, args, diagnostics_out=walked)
    blocks = [b for f in files for b in f.blocks]
    blocks_by_id = {b.block_id: b for b in blocks}

    # If pipeline blocks are provided, use them for stable block_ids
    # and build a mapping from file+line to pipeline block_id
    pipeline_block_map = {}  # (file, line) -> pipeline block_id
    if pipeline_blocks:
        for pb in pipeline_blocks:
            bid = pb.get("block_id", "")
            if bid:
                key = (pb.get("file", ""), pb.get("line", 0))
                pipeline_block_map[key] = bid
                # Also index by block_id for direct lookup
                if bid not in blocks_by_id:
                    class _PipelineBlock:
                        def __init__(self, data):
                            self.block_id = data["block_id"]
                            self.file_path = data.get("file", "")
                            self.line_number = data.get("line", 0)
                            self.text = data.get("text", "")
                            self.language_hint = data.get("language")
                            self.start = 0
                    blocks_by_id[bid] = _PipelineBlock(pb)

    categories = _categories(args)
    offline = DetectorFactory.create(
        "offline",
        categories=categories if not args.no_unicode else (),
        include_style=True,
    )
    offline_spans = offline.analyze_blocks(blocks)

    # Remap offline spans to use pipeline block_ids
    if pipeline_blocks:
        for span in offline_spans:
            block = blocks_by_id.get(span.block_id)
            if block:
                key = (block.file_path, block.line_number)
                if key in pipeline_block_map:
                    span.block_id = pipeline_block_map[key]

    # --- Build findings ---
    findings = []

    if hybrid_mode:
        # HYBRID MERGE: offline + agent judgments + agent independent findings
        # Agreement = both found it, offline-only, model-only
        AGREE_BOTH = "both"
        AGREE_OFFLINE_ONLY = "offline-only"
        AGREE_MODEL_ONLY = "model-only"

        # Index agent findings by block_id
        agent_by_block: dict[str, list] = {}
        for af in agent_findings_list:
            bid = af.get("block_id", "")
            agent_by_block.setdefault(bid, []).append(af)

        # Build block index from agent findings' file/line info
        # (block_ids from agent-scan may differ from re-scanned ones)
        agent_block_index: dict[str, object] = {}
        for af in agent_findings_list:
            bid = af.get("block_id", "")
            if bid and bid not in agent_block_index:
                # Try to find in re-scanned blocks
                block = blocks_by_id.get(bid)
                if block:
                    agent_block_index[bid] = block

        # Process offline spans
        for span in offline_spans:
            block = blocks_by_id.get(span.block_id)
            if block is None:
                continue

            # Check if agent also judged this block (via judgments)
            judgment = judgments.get(span.block_id)
            # Check if agent found something independently in this block
            agent_hits = agent_by_block.get(span.block_id, [])

            is_offline_style = (
                (span.details or {}).get("source") == "style"
                and span.confidence != Confidence.LOW
            )

            if is_offline_style:
                # Find overlapping agent findings
                overlapping = []
                for af in agent_hits:
                    af_start = af.get("start", 0)
                    af_end = af.get("end", len(block.text))
                    if span.start < af_end and af_start < span.end:
                        overlapping.append(af)

                if judgment is not None or overlapping:
                    # Agreement: offline + agent both found it
                    agent_score = float(judgment.get("score", 0)) if judgment else 0
                    agent_reason = judgment.get("reason", "") if judgment else ""
                    for af in overlapping:
                        agent_score = max(agent_score, float(af.get("score", 0)))
                        if af.get("reason"):
                            agent_reason = af["reason"]

                    merged_score = max(span.score, agent_score)
                    explanation = (
                        f"[{AGREE_BOTH}] agent: {agent_reason} "
                        f"(score={agent_score:.2f}); "
                        f"offline: {span.explanation}"
                    )
                    source = "agent+offline"
                else:
                    # Offline-only
                    merged_score = span.score
                    explanation = f"[{AGREE_OFFLINE_ONLY}] {span.explanation}"
                    source = "offline"
            else:
                # Character findings — keep as-is
                merged_score = span.score
                explanation = span.explanation
                source = (span.details or {}).get("source", "characters")

            if merged_score < 0.33 and source != "characters":
                continue

            findings.append({
                "file": block.file_path,
                "line": block.line_number,
                "offset": block.start + span.start,
                "end_offset": block.start + span.end,
                "detector": "agent-llm-judge",
                "source": source,
                "confidence": score_to_confidence(merged_score).value,
                "score": round(merged_score, 3),
                "text": block.text[span.start:span.end],
                "replacement": span.replacement,
                "explanation": explanation,
            })

        # Agent-only findings (not overlapping with any offline span)
        offline_block_ids = {s.block_id for s in offline_spans
                            if (s.details or {}).get("source") == "style"
                            and s.confidence != Confidence.LOW}
        for af in agent_findings_list:
            bid = af.get("block_id", "")
            block = blocks_by_id.get(bid)
            if block is None:
                continue
            # Skip if offline already covered this block with overlap
            af_start = af.get("start", 0)
            af_end = af.get("end", len(block.text))
            already_covered = False
            for span in offline_spans:
                if span.block_id == bid and span.start < af_end and af_start < span.end:
                    already_covered = True
                    break
            if already_covered:
                continue

            agent_score = float(af.get("score", 0))
            if agent_score < 0.33:
                continue

            findings.append({
                "file": block.file_path,
                "line": block.line_number,
                "offset": block.start + af_start,
                "end_offset": block.start + af_end,
                "detector": "agent-llm-judge",
                "source": "agent-only",
                "confidence": score_to_confidence(agent_score).value,
                "score": round(agent_score, 3),
                "text": block.text[af_start:af_end],
                "replacement": None,
                "explanation": f"[{AGREE_MODEL_ONLY}] {af.get('reason', 'Agent detected AI pattern')}",
            })

    else:
        # SIMPLE MERGE: offline + agent judgments (current behavior)
        for span in offline_spans:
            block = blocks_by_id.get(span.block_id)
            if block is None:
                continue

            judgment = judgments.get(span.block_id)
            if judgment is not None:
                agent_score = float(judgment.get("score", 0))
                agent_reason = judgment.get("reason", "")
                merged_score = max(span.score, agent_score)
                explanation = (
                    f"agent: {agent_reason} (score={agent_score:.2f}); "
                    f"offline: {span.explanation}"
                )
                source = "agent+offline"
            else:
                merged_score = span.score
                explanation = span.explanation
                source = (span.details or {}).get("source", "offline")

            if merged_score < 0.33:
                continue

            findings.append({
                "file": block.file_path,
                "line": block.line_number,
                "offset": block.start + span.start,
                "end_offset": block.start + span.end,
                "detector": "agent-llm-judge",
                "source": source,
                "confidence": score_to_confidence(merged_score).value,
                "score": round(merged_score, 3),
                "text": block.text[span.start:span.end],
                "replacement": span.replacement,
                "explanation": explanation,
            })

    findings.sort(key=lambda f: (f["file"], f["offset"]))

    if args.json:
        _print_json(findings, walked=walked)
    else:
        _print_human(findings, walked=walked)

    if findings:
        return EXIT_FINDINGS
    return EXIT_OK



# ------------------------------------------------------------------ parser

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="xanalyze",
        description="Find and fix characters no keyboard produces (and optionally "
                    "flag AI-sounding copy) in web pages' source files. "
                    "Designed to run after an LLM coding agent.",
    )
    parser.add_argument(
        "--no-update-check", action="store_true", default=False,
        help="skip the automatic daily check for a newer version")
    parser.add_argument(
        "--version", action="version",
        version=f"xanalyze {config.APP_VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p, with_paths=True):
        if with_paths:
            p.add_argument("paths", nargs="+", help="files or directories to process")
            p.add_argument("--ext", nargs="*", default=None,
                           help=f"extensions to scan (default: {' '.join(DEFAULT_EXTENSIONS)})")
            p.add_argument("--exclude", action="append", default=None,
                           help="extra gitignore-style exclude pattern (repeatable)")
            p.add_argument("--no-default-excludes", dest="use_default_excludes",
                           action="store_false", default=True,
                           help="don't skip node_modules/, dist/, .git/ etc.")
            p.add_argument("--max-files", type=int, default=5000)
            p.add_argument("--detector", default="none",
                           help="also run a content detector: offline (adds the "
                                "wording/cliche analysis to the character pass) | "
                                "llm-judge (ask a model, billed to whichever "
                                "account --provider names) | hybrid (offline "
                                "first, then a model checks and extends it) | "
                                "claude-llm-judge | xformat-llm-judge | "
                                "claude-code-llm-judge | agent-llm-judge "
                                "(offline fallback; for real LLM judgment use "
                                "'agent-scan' + 'agent-judge' workflow) | none")
            p.add_argument("--provider", default=None,
                           choices=["anthropic", "xformat", "claude-code"],
                           help="which account pays for --detector llm-judge; "
                                "the default is the same one `ai status` reports")
            p.add_argument("--no-unicode", action="store_true",
                           help="skip the non-keyboard character pass")
            p.add_argument("--scope", default="content",
                           choices=["content", "technical", "both"],
                           help="what to read: content (copy that ships to a "
                                "user: markup text plus injected strings) | "
                                "technical (comments and docstrings) | both")
        p.add_argument("--categories", default=None,
                       help="comma-separated: " + ",".join(unicode_rules.ALL_CATEGORIES))
        p.add_argument("--no-typography", action="store_true",
                       help="leave em dashes and curly quotes alone (keeps proper "
                            "Ukrainian/Italian typography)")
        p.add_argument("--no-ignore", action="store_true",
                       help="report everything, including findings suppressed by "
                            "settings or by a .xanalyze-ignore file")
        p.add_argument("--json", action="store_true", help="machine-readable output")
        p.add_argument("--check", action="store_true",
                       help="exit 1 when anything is found (for hooks and CI)")

    p_scan = sub.add_parser("scan", help="report findings without changing anything")
    common(p_scan)
    p_scan.add_argument("--incremental", action="store_true",
                        help="only scan files that changed since last scan "
                             "(uses cache)")
    p_scan.add_argument("--styled-report", default=None, metavar="PATH",
                        help="also write a branded, print-ready report for a "
                             "person to read: a .pdf or .html by suffix. "
                             "Different from --json/--check, which are for a "
                             "pipeline, not a reader")
    p_scan.add_argument("--language", default=None, help="uk | it | en; "
                        "language of --styled-report's own labels (default en)")
    p_scan.set_defaults(func=cmd_scan)

    p_fix = sub.add_parser("fix", help="rewrite non-keyboard characters in place")
    common(p_fix)
    p_fix.add_argument("--dry-run", action="store_true", help="show what would change")
    p_fix.add_argument("--no-backup", action="store_true",
                       help="don't keep .bak copies (fine when the repo is in git)")
    p_fix.set_defaults(func=cmd_fix)

    # Renamed from `a11y` when the pass grew past accessibility into SEO,
    # performance and best practices — one pass over one parsed document, so
    # one command. `a11y` stays as a hidden alias: it is in people's hooks
    # and CI files already, and breaking those to rename a word would be a
    # cost paid by users for a change that benefits only the vocabulary.
    p_audit = sub.add_parser(
        "audit", aliases=["a11y"],
        help="audit a URL or a folder: accessibility, SEO, performance, best practices")
    p_audit.add_argument(
        "target",
        help="URL to crawl, a directory to scan, or one .html file to audit "
             "as a page (for a site built into a single self-contained file)")
    p_audit.add_argument("--url", action="store_true",
                         help="treat the target as a URL even without a scheme")
    p_audit.add_argument("--depth", type=int, default=0,
                         help="link depth to crawl; same-domain only (default 0: one page)")
    p_audit.add_argument("--max-pages", type=int, default=30)
    p_audit.add_argument("--max-files", type=int, default=5000)
    p_audit.add_argument("--render", choices=("never", "auto", "always"),
                         default=None,
                         help="hand pages to a real browser during the crawl, "
                              "so a client-rendered site is read rather than "
                              "diagnosed: auto renders only the pages whose "
                              "fetch came back an empty shell. Defaults to "
                              "auto with --browser, never without it")
    p_audit.add_argument("--exclude", nargs="*", default=None)
    p_audit.add_argument("--no-default-excludes", dest="use_default_excludes",
                         action="store_false", default=True)
    p_audit.add_argument("--category", nargs="*", default=None,
                         choices=list(CATEGORIES),
                         help="report only these categories (default: all four)")
    p_audit.add_argument("--language", default=None, help="uk | it | en (output language)")
    p_audit.add_argument("--no-ignore", action="store_true",
                         help="report everything, including suppressed findings")
    p_audit.add_argument("--json", action="store_true", help="machine-readable output")
    p_audit.add_argument("--check", action="store_true",
                         help="exit 1 when a critical or serious issue is found")
    p_audit.add_argument("--ai", action="store_true",
                         help="also run the AI pass: whether alt text, link text "
                              "and headings actually describe what they point at "
                              "(costs tokens; see `ai status`)")
    p_audit.add_argument("--provider", default=None,
                         choices=["anthropic", "xformat", "claude-code"],
                         help="override the provider used by --ai")
    p_audit.add_argument("--fix", action="store_true",
                         help="write the corrections the audit already knows "
                              "back into the files, keeping a .bak copy of "
                              "each. Only the ones that need no decision; run "
                              "with --ai to have the rest written too")
    p_audit.add_argument("--report", default=None, metavar="PATH",
                         help="write a briefing an agent can act on: statistics, "
                              "a file map, every finding with its fix, what "
                              "changed since last time. .md or .json by suffix")
    p_audit.add_argument("--browser", action="store_true",
                         help="also load each page in a real browser: runs "
                              "axe-core, HTML_CodeSniffer, the keyboard/focus "
                              "state pass and load measurements. Works for a "
                              "URL and for a single .html file; not for a "
                              "project folder. Slower")
    p_audit.add_argument("--breakpoints", nargs="?", const="all", default=None,
                         metavar="NAMES",
                         help="with --browser: audit each page at several "
                              "widths (desktop 1440, tablet 834, mobile 390) "
                              "instead of one. Bare, or a comma-separated "
                              "subset. A finding seen at several widths stays "
                              "one row and records where it was seen; one seen "
                              "at a single width says so - which is the point, "
                              "since a mobile menu is not in the DOM at all at "
                              "desktop width")
    p_audit.add_argument("--styled-report", default=None, metavar="PATH",
                         help="also write a branded, print-ready report for a "
                              "person to read: a .pdf or .html by suffix. "
                              "Different from --report, which is a briefing "
                              "for an agent")
    p_audit.set_defaults(func=cmd_audit)

    # `ai` groups everything that spends money or needs an account, so the
    # commands that never do (scan, fix, audit) stay usable with no setup.
    p_undo = sub.add_parser(
        "undo",
        help="put files back the way they were before --fix wrote to them")
    p_undo.add_argument("paths", nargs="+",
                        help="files or folders that were corrected")
    p_undo.set_defaults(func=cmd_undo)

    p_cache = sub.add_parser(
        "cache",
        help="manage the scan cache")
    cache_sub = p_cache.add_subparsers(dest="cache_command", required=True)
    
    p_cache_stats = cache_sub.add_parser(
        "stats", help="show cache statistics")
    p_cache_stats.set_defaults(func=cmd_cache)
    
    p_cache_clear = cache_sub.add_parser(
        "clear", help="clear the cache")
    p_cache_clear.set_defaults(func=cmd_cache)
    
    p_cache_path = cache_sub.add_parser(
        "path", help="show cache file path")
    p_cache_path.set_defaults(func=cmd_cache)
    
    p_cache.set_defaults(func=cmd_cache)

    p_compare = sub.add_parser(
        "compare",
        help="compare different detectors on the same files")
    common(p_compare)
    p_compare.set_defaults(func=cmd_compare)

    p_ai = sub.add_parser("ai", help="account and AI-backed operations")
    ai_sub = p_ai.add_subparsers(dest="ai_command", required=True)

    def with_provider(parser):
        parser.add_argument(
            "--provider", default=None,
            choices=["anthropic", "xformat", "claude-code"],
            help="override the configured provider for this command")

    p_ai_status = ai_sub.add_parser(
        "status", help="which account pays, and is it usable (costs nothing)")
    with_provider(p_ai_status)
    p_ai_status.set_defaults(func=cmd_ai_status)

    p_ai_login = ai_sub.add_parser("login", help="sign in to the xFormat subscription")
    with_provider(p_ai_login)
    p_ai_login.add_argument("--email", default=None)
    p_ai_login.set_defaults(func=cmd_ai_login)

    p_ai_logout = ai_sub.add_parser("logout", help="revoke the session and forget the tokens")
    with_provider(p_ai_logout)
    p_ai_logout.set_defaults(func=cmd_ai_logout)

    p_ai_apps = ai_sub.add_parser(
        "apps", help="which applications this xFormat account has let in")
    p_ai_apps.set_defaults(func=cmd_ai_apps)

    p_ai_grant = ai_sub.add_parser(
        "grant", help="allow this application to use the xFormat account")
    p_ai_grant.add_argument("app", nargs="?", default=None,
                            help="application slug; default is this one")
    p_ai_grant.set_defaults(func=cmd_ai_grant)

    p_ai_revoke = ai_sub.add_parser(
        "revoke", help="take that permission back")
    p_ai_revoke.add_argument("app", nargs="?", default=None)
    p_ai_revoke.set_defaults(func=cmd_ai_revoke)

    p_ai_rewrite = ai_sub.add_parser(
        "rewrite", help="rewrite a passage through the configured provider")
    with_provider(p_ai_rewrite)
    p_ai_rewrite.add_argument("text", nargs="?", default=None,
                              help="the passage; omitted means read stdin")
    p_ai_rewrite.add_argument("--language", default=None, help="uk | it | en")
    p_ai_rewrite.add_argument("--split", action="store_true",
                              help="treat blank-line-separated blocks as separate "
                                   "passages and rewrite them in one batched call")
    p_ai_rewrite.add_argument("--quiet", action="store_true",
                              help="print only the rewrite")
    p_ai_rewrite.set_defaults(func=cmd_ai_rewrite)

    p_fullscan = sub.add_parser(
        "fullscan",
        help="full scan: AI patterns + accessibility audit + reports for agent")
    p_fullscan.add_argument(
        "target",
        help="URL to crawl, a directory to scan, or one .html file")
    p_fullscan.add_argument("--url", action="store_true",
                            help="treat target as URL even without scheme")
    p_fullscan.add_argument("--depth", type=int, default=2,
                            help="crawl depth for URLs (default 2: target + 2 levels)")
    p_fullscan.add_argument("--max-pages", type=int, default=0,
                            help="max pages to crawl (default 0: unlimited, same-domain only)")
    p_fullscan.add_argument("--max-files", type=int, default=5000,
                            help="max files to scan (default 5000)")
    p_fullscan.add_argument("--ext", nargs="*", default=None,
                            help="file extensions to scan")
    p_fullscan.add_argument("--exclude", action="append", default=None,
                            help="additional gitignore patterns to exclude")
    p_fullscan.add_argument("--no-default-excludes", action="store_true",
                            help="don't skip node_modules/, dist/, .git/ etc")
    p_fullscan.add_argument("--detector", default="offline",
                            help="detector for AI patterns: offline, embedding, "
                                 "hybrid, llm-judge")
    p_fullscan.add_argument("--scope", default="both",
                            choices=["content", "technical", "both"],
                            help="what to read for AI patterns (default: both)")
    p_fullscan.add_argument("--no-typography", action="store_true",
                            help="leave em dashes and curly quotes alone")
    p_fullscan.add_argument("--styled-report", default=None, metavar="PATH",
                            help="branded PDF/HTML report for a person")
    p_fullscan.add_argument("--report", default=None, metavar="PATH",
                            help="agent briefing: .md or .json by suffix")
    p_fullscan.add_argument("--check", action="store_true",
                            help="exit 1 when critical/serious issues found")
    p_fullscan.add_argument("--language", default=None,
                            help="uk | it | en; language of reports")
    p_fullscan.add_argument("--breakpoints", nargs="?", const="all", default="all",
                            metavar="NAMES",
                            help="responsive breakpoints for browser audit: "
                                 "all (default), desktop, tablet, mobile, "
                                 "or comma-separated subset (e.g. desktop,mobile)")
    p_fullscan.add_argument("--agent", action="store_true",
                            help="run offline scan and output candidate blocks "
                                 "for agent to judge with its own LLM "
                                 "(no API key needed)")
    p_fullscan.add_argument("--json", action="store_true",
                            help="machine-readable JSON output for agent")
    p_fullscan.set_defaults(func=cmd_fullscan)

    p_update = sub.add_parser(
        "update",
        help="self-update the CLI binary from the latest GitHub Release")
    p_update.set_defaults(func=cmd_update)

    p_clean = sub.add_parser("clean", help="filter text from stdin to stdout")
    common(p_clean, with_paths=False)
    p_clean.add_argument("--language", default=None, choices=["uk", "it", "en"],
                         help="override language detection")
    p_clean.set_defaults(func=cmd_clean)

    p_agent_scan = sub.add_parser(
        "agent-scan",
        help="offline scan → candidate blocks as JSON for agent to judge")
    common(p_agent_scan)
    p_agent_scan.add_argument(
        "--threshold", type=float, default=0.25,
        help="minimum offline score to include as candidate (default: 0.25)")
    p_agent_scan.add_argument(
        "--full", action="store_true",
        help="hybrid mode: also output all blocks for agent to read "
             "independently (agent judges candidates AND reads raw content)")
    p_agent_scan.set_defaults(func=cmd_agent_scan)

    p_agent_judge = sub.add_parser(
        "agent-judge",
        help="merge agent's LLM judgments with offline scan → final report")
    common(p_agent_judge)
    p_agent_judge.add_argument(
        "--judgments", default=None, metavar="PATH",
        help="JSON file with agent's judgments (default: read stdin)")
    p_agent_judge.add_argument(
        "--hybrid", action="store_true",
        help="hybrid merge: input contains both judgments and agent_findings")
    p_agent_judge.set_defaults(func=cmd_agent_judge)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    # Background update check (once per day, unless suppressed).
    # Skipped for the `update` command itself — that already checks.
    if not getattr(args, "no_update_check", False) and args.command != "update":
        try:
            import updater
            new = updater.check_for_update(quiet=True)
            if new:
                updater.print_update_hint(new)
        except Exception:  # noqa: BLE001
            pass  # never let the check break the real command

    try:
        return args.func(args)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
