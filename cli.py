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
from dataclasses import asdict, is_dataclass
from pathlib import Path

import detectors  # noqa: F401 - registers the detectors
import suppression
import unicode_rules
import config
from audit.base import CATEGORIES, CONFIDENCE_ORDER, meets_confidence
from detectors.factory import DetectorFactory
from file_writer import ReplacementPlan, apply_replacements
from lang_detect import guess_language
from models import Confidence, RepoAnalysisResult, score_to_confidence
from repo_scanner import DEFAULT_EXTENSIONS, scan_repo
# The scan pipeline and the terminal output live in `cli_impl`; the names are
# imported here so both this module's own commands and anything that does
# `import cli` keep working unchanged.
from cli_impl.scanning import (  # noqa: F401 - re-exported for `import cli`
    CHARACTER_SOURCE, HYBRID_NAME,
    _analyze, _build_ignore_list, _build_scan_config, _categories,
    _collect_files, _create_detector, _ignore_root, _report_detector_errors,
    _settings_for_ignore, _split_unchanged, _store_unchanged,
)
from cli_impl.output import (  # noqa: F401 - re-exported for `import cli`
    _counts, _coverage_line, _print_human, _print_json, _public, _visible,
)
from cli_impl.reports import (  # noqa: F401 - re-exported for `import cli`
    _file_map, _fix_summary, _history_dir, _history_key, _now, _previous_run,
    _read_history, _report_markdown, _write_history, _write_report,
    _write_styled_text_report,
)
from cli_impl.auditpass import (  # noqa: F401 - re-exported for `import cli`
    PAGE_FILE_SUFFIXES, _audit_at_widths, _browser_url,
    _chosen_breakpoints, _crawl_maybe_rendering, _is_page_file,
    _render_mode, _run_browser_pass, _wrap, looks_like_url, with_scheme,
)
from cli_impl.aicmds import (  # noqa: F401 - re-exported for `import cli`
    _provider_for, _xformat_provider,
    cmd_ai_apps, cmd_ai_grant, cmd_ai_login, cmd_ai_logout, cmd_ai_revoke,
    cmd_ai_rewrite, cmd_ai_status,
)
from cli_impl.agentcmds import (  # noqa: F401 - re-exported for `import cli`
    _agent_detection_rules, cmd_agent_judge, cmd_agent_scan,
)
from cli_impl.fullscan import (  # noqa: F401 - re-exported for `import cli`
    cmd_fullscan,
)
from cli_impl.uninstall import (  # noqa: F401 - re-exported for `import cli`
    cmd_uninstall,
)

# Re-exported rather than defined here: the window needs the same mapping,
# and the copy that used to live in this file was invisible to it. See
# `detectors/judges.py`.
from detectors.judges import (  # noqa: F401 - re-exported for `import cli`
    JUDGE_ALIASES, JUDGE_BY_PROVIDER, JUDGE_NAMES, judge_for_provider,
)

from cli_impl import (  # noqa: F401 - re-exported for `import cli`
    EXIT_ERROR, EXIT_FINDINGS, EXIT_OK,
)


# ---------------------------------------------------------------- commands

def cmd_scan(args) -> int:
    missing: list = []
    unjudged: list = []
    walked: list = []

    files = _collect_files(args.paths, args, missing_out=missing,
                           diagnostics_out=walked)

    incremental = bool(getattr(args, "incremental", False))
    cached_findings: list = []
    to_read = files
    if incremental:
        to_read, cached_findings, reused = _split_unchanged(files, args)
        print(f"# incremental: {reused} file(s) unchanged since the last scan, "
              f"{len(to_read)} re-read", file=sys.stderr)

    findings, _ = _analyze(to_read, args, unjudged_out=unjudged)
    if incremental:
        _store_unchanged(to_read, findings, args)
        # Cached rows have no `TextSpan` behind them - it does not survive
        # JSON - so the styled report, which reads spans, covers only the
        # files actually re-read this run. It says so; see
        # `_write_styled_text_report`.
        findings = findings + cached_findings
        findings.sort(key=lambda f: (f.get("file", ""), f.get("offset", 0)))
    if args.json:
        _print_json(findings, walked=walked)
    else:
        _print_human(findings, walked=walked,
                     scope=getattr(args, "scope", "content"))
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
    from i18n.translations import t

    # Built before the crawl so a missing sign-in fails immediately, rather
    # than after crawling thirty pages.
    reviewer = None
    if getattr(args, "ai", False):
        from audit.ai_review import AIAccessibilityReview

        name, provider = _provider_for(args)
        print(f"# AI pass via {name}", file=sys.stderr)
        reviewer = AIAccessibilityReview(provider=provider)

    target = args.target
    # `example.com` is what people type; treating it as a path and answering
    # "path not found" is the wrong answer to a question that had one obvious
    # reading. An existing path still wins - see `looks_like_url`.
    is_url = looks_like_url(target) or args.url
    if is_url:
        target = with_scheme(target)
    # A target that is neither a URL nor a path that exists is a typo, and the
    # only honest answer is to say so. Auditing it used to print "0 findings"
    # and exit 0 - which in a pipeline is a pass, so a mistyped path read as a
    # clean bill of health.
    if not is_url and not Path(target).exists():
        print(f"path not found: {target}", file=sys.stderr)
        return EXIT_ERROR

    if _is_page_file(target) and not args.url:
        # A page built into one file is a finished document, so it is audited
        # as a page: `<head>` included, line numbers on, and - with --browser -
        # rendered from `file://`, which is faithful precisely because
        # everything it needs is inlined.
        result = audit.analyze_page_file(target, ai_review=reviewer)
    elif is_url:
        from crawler import CrawlConfig, EMPTY_JS_RENDERED, crawl

        # Same crawler as the text scan: depth-limited, and refusing to leave
        # the domain. That rule holds for both modes because there is one
        # crawler, not two.
        config = CrawlConfig(max_depth=args.depth, max_pages=args.max_pages,
                             render_mode=_render_mode(args))

        crawled = 0

        def _crawl_progress(url: str, depth: int) -> None:
            nonlocal crawled
            crawled += 1
            limit = f"/{args.max_pages}" if args.max_pages else ""
            print(f"# [crawl {crawled}{limit}] depth={depth} {url}",
                  file=sys.stderr, flush=True)

        pages = _crawl_maybe_rendering(target, config, progress_cb=_crawl_progress)
        print(f"# [crawl done] {len(pages)} page(s)", file=sys.stderr, flush=True)
        
        # Check if SPA pages were detected but not rendered
        spa_pages = [p for p in pages if EMPTY_JS_RENDERED in (p.diagnostics.reasons or [])]
        rendered_pages = [p for p in pages if "rendered" in (p.diagnostics.reasons or [])]
        if spa_pages and not rendered_pages:
            print(f"# WARNING: {len(spa_pages)} SPA page(s) detected but browser rendering failed.", file=sys.stderr)
            print(f"# Install PySide6 + QtWebEngine for SPA support, or use --no-browser to skip rendering.", file=sys.stderr)
        elif spa_pages and rendered_pages:
            print(f"# SPA: {len(rendered_pages)} page(s) rendered via browser, {len(spa_pages)} failed.", file=sys.stderr)
        
        result = audit.analyze_pages(pages, target, ai_review=reviewer)
    else:
        from repo_scanner import scan_repo

        files = scan_repo(target, _build_scan_config(args, target=target))
        result = audit.analyze_files(files, target, ai_review=reviewer,
                                     force_medium=getattr(args, "medium", None))

    # The same suppression list governs both analyses: a user thinking "not
    # this part of the site" means it for the whole tool, not per subsystem.
    suppressions = suppression.Suppressions.load(
        _settings_for_ignore(args), _ignore_root(args))

    # The browser pass is part of what "audit a page" means: a URL or a
    # self-contained file is loaded for real unless --no-browser says
    # otherwise. Repo mode never had a page to load, and the pass refuses
    # it on its own.
    if not getattr(args, "no_browser", False):
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

    # A certainty floor, for a reader who wants only what the markup settles.
    # Every finding has carried its confidence since the rules were written
    # and nothing let anyone act on it, so "this element is absolutely
    # positioned and the background color can not be determined" arrived
    # beside a missing `alt`. Filtered here, next to the category filter, for
    # the same reason: both are a *view* over one pass, not a different run.
    floor = getattr(args, "confidence", None)
    if floor:
        for document in result.documents:
            document.issues = [i for i in document.issues
                               if meets_confidence(i, floor)]

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
            "platform_owned": _owned_counts(result),
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
                    # Which platform emitted the element, when one did. An
                    # agent reading this can skip what the site owner cannot
                    # change; empty means the page's own markup.
                    "owner": issue.owner,
                }
                for issue in result.issues()
            ],
        }, ensure_ascii=False, indent=2, default=_json_default))
    else:
        for document in result.documents_with_issues():
            print()
            print(document.source)
            for issue in document.issues:
                explanation = render(issue, lang)
                location = f"line {issue.line}" if issue.line else issue.selector[-60:]
                owned = (f"  <- {t('a11y_owned_marker', lang, platform=issue.owner)}"
                         if issue.owner else "")
                print(f"  [{issue.severity}] {explanation.title}  ({location}){owned}")
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
        for platform, count in sorted(_owned_counts(result).items()):
            print(t("a11y_platform_owned", lang, count=count, platform=platform))

    counts = result.counts()
    if args.check and (counts.get("critical") or counts.get("serious")):
        return EXIT_FINDINGS
    return EXIT_OK


def _owned_counts(result) -> dict:
    """`{platform: findings}` for what a platform emitted itself.

    Reported separately rather than subtracted from the totals. The finding
    is real - the stylesheet does block rendering - and hiding it would make
    the run quieter without making the site better. What the split buys is
    the next question a person actually asks: which of these can I fix?
    """
    counts: dict = {}
    for issue in result.issues():
        if getattr(issue, "owner", ""):
            counts[issue.owner] = counts.get(issue.owner, 0) + 1
    return counts


def _json_default(value):
    """Serialise the dataclasses a finding's `details` can carry.

    `details` is a free-form dict that rules and passes fill in, and one of
    them puts a whole object there: `audit.repo_facts.blame_issues` writes
    `details["arrived"] = Arrival(...)` so the window and the report can read
    `arrival.summary` and `arrival.assistant` by attribute. `json.dumps` has
    no answer for that, and `audit --json` died with "Object of type Arrival
    is not JSON serializable" the moment a repo finding was blamed.

    It went unseen because repo mode had no findings to blame: `.tsx` was
    skipped before any rule ran (`P-19`), so the only repository this was
    tried on came back empty. Handled here rather than by flattening
    `Arrival` into a dict at the source, because the attribute access is what
    every other consumer is written against.
    """
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _reaudit(args, target: str, previous):
    """Run the same audit again over the same files, after correcting them."""
    import audit

    if previous.mode == "file":
        return audit.analyze_page_file(target)
    from repo_scanner import scan_repo

    files = scan_repo(target, _build_scan_config(args, target=target))
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


def cmd_update(args) -> int:
    """Self-update the CLI binary from the latest GitHub Release.

    Checks the configured GitHub repository for a newer version,
    downloads the platform-appropriate CLI asset, and replaces the
    running binary in place.  When running from source, prints the
    download link instead.
    """
    import updater
    return updater.do_update()


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
    sub = parser.add_subparsers(dest="command", required=False)

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
                              "auto (never with --no-browser)")
    p_audit.add_argument("--exclude", nargs="*", default=None)
    p_audit.add_argument("--no-default-excludes", dest="use_default_excludes",
                         action="store_false", default=True)
    p_audit.add_argument("--category", nargs="*", default=None,
                         choices=list(CATEGORIES),
                         help="report only these categories (default: all four)")
    p_audit.add_argument("--medium", default=None, choices=["web", "email"],
                         help="what these documents are for. Autodetected per "
                              "file from the markup (Outlook namespaces, merge "
                              "tags); set it when the deliverable is an email "
                              "that carries neither. On 'email' the browser-only "
                              "checks - canonical, Open Graph, structured data, "
                              "skip link, landmarks, WebP - are skipped, because "
                              "no mail client has them. Accessibility is not.")
    p_audit.add_argument("--confidence", default=None,
                         choices=list(CONFIDENCE_ORDER),
                         help="report only findings at least this certain: "
                              "'exact' keeps what the markup settles and drops "
                              "what needed a browser or a stylesheet to decide "
                              "(an engine's 'could not determine' is the second "
                              "kind); default: report both, each labelled")
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
                         help="kept for compatibility: the browser pass "
                              "(axe-core, HTML_CodeSniffer, the keyboard/focus "
                              "state pass, load measurements) already runs by "
                              "default for a URL and for a single .html file")
    p_audit.add_argument("--no-browser", action="store_true",
                         help="skip the browser pass and render nothing: "
                              "audit only what the markup alone proves. Faster")
    p_audit.add_argument("--breakpoints", nargs="?", const="all", default=None,
                         metavar="NAMES",
                         help="audit each page at several "
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
    p_fullscan.add_argument("--depth", type=int, default=1,
                            help="crawl depth for URLs (default 1: target + direct links)")
    p_fullscan.add_argument("--max-pages", type=int, default=30,
                            help="max pages to crawl (default 30, 0=unlimited)")
    p_fullscan.add_argument("--max-files", type=int, default=5000,
                            help="max files to scan (default 5000)")
    p_fullscan.add_argument("--ext", nargs="*", default=None,
                            help="file extensions to scan")
    p_fullscan.add_argument("--exclude", action="append", default=None,
                            help="additional gitignore patterns to exclude")
    p_fullscan.add_argument("--no-default-excludes", action="store_true",
                            help="don't skip node_modules/, dist/, .git/ etc")
    # Only meaningful alongside a URL target: a repo scan already reads its
    # own files directly, and has nothing to cross-reference against. A site
    # given without --repo scans exactly as it always did - this is additive,
    # not a mode switch, because a live site with no matching checkout is the
    # ordinary case, not the exception.
    p_fullscan.add_argument("--repo", default=None, metavar="PATH",
                            help="local checkout behind this URL, if any: AI-"
                                 "pattern findings that match a passage in it "
                                 "get the file and line to fix, not just the "
                                 "page")
    # Off by default: a repo's dev server may already be running in another
    # terminal, and starting a second one on a different port is a confusing
    # outcome, not a helpful one. A repo scanned without this flag is scanned
    # statically, exactly as it always has been - this is additive, not a
    # mode switch.
    p_fullscan.add_argument("--devserver", action="store_true",
                            help="detect and start a repo's own dev server "
                                 "(package.json, manage.py, Gemfile+bin/rails) "
                                 "and scan the rendered site instead of the "
                                 "source; already have one running? pass "
                                 "--url http://localhost:PORT instead")
    p_fullscan.add_argument("--start-command", default=None, metavar="CMD",
                            help="override the detected dev server start "
                                 "command, run without a shell (e.g. "
                                 "--start-command 'npm run dev:custom')")
    p_fullscan.add_argument("--dev-server-port", type=int, default=None,
                            help="port to expect, when it can't be read "
                                 "from the server's own output "
                                 "(Django/Rails; Node servers announce "
                                 "their own)")
    p_fullscan.add_argument("--yes", action="store_true",
                            help="install missing dev server dependencies "
                                 "without asking")
    # `ai` first, because it is the word people reach for and it was the one
    # the help did not mention: the list named `llm-judge`, a backend name,
    # and left the natural request undiscoverable even though it has always
    # worked. `ai`, `judge` and `llm-judge` all mean the same thing - ask a
    # model, billed to whichever account is configured (see
    # `detectors/judges.py`); the concrete judge is printed when the run
    # starts, so the answer to "whose account paid" is in the log.
    p_fullscan.add_argument("--detector", default="offline",
                            help="how to read for AI patterns: offline "
                                 "(default, free), ai (ask a model; also "
                                 "spelled llm-judge), hybrid (both), embedding")
    # Which model, and how hard it thinks. Both only matter when `--detector`
    # asks for a model at all; both default to whatever the account is
    # configured for, so naming them here is an override rather than a
    # requirement. `sonnet` at `low` effort is enough for this job - the pass
    # classifies short passages against a fixed rubric - and is what the
    # settings should hold for a route that runs over every block on a site.
    p_fullscan.add_argument("--model", default=None,
                            help="model for the AI pass, e.g. sonnet, opus "
                                 "(default: whatever the account is set to)")
    p_fullscan.add_argument("--effort", default=None,
                            choices=["low", "medium", "high"],
                            help="how hard the AI pass thinks (default: low "
                                 "for the API judge, the session's own "
                                 "setting for Claude Code)")
    # A cached wrong answer must not be un-fixable, and a rubric change that
    # the prompt hash somehow did not catch must have a way out.
    p_fullscan.add_argument("--no-judgment-cache", action="store_true",
                            help="re-ask the model about passages it has "
                                 "already judged (slower, and the only way to "
                                 "get a fresh opinion)")
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
    p_fullscan.add_argument("--medium", default=None, choices=["web", "email"],
                            help="what these documents are for (see "
                                 "`audit --medium`)")
    p_fullscan.add_argument("--confidence", default=None,
                            choices=list(CONFIDENCE_ORDER),
                            help="report only findings at least this certain "
                                 "(see `audit --confidence`)")
    p_fullscan.add_argument("--language", default=None,
                            help="uk | it | en; language of reports (auto-detected if omitted)")
    p_fullscan.add_argument("--breakpoints", nargs="?", const="all", default="desktop",
                            metavar="NAMES",
                            help="responsive breakpoints for browser audit: "
                                 "desktop (default), all, tablet, mobile, "
                                 "or comma-separated subset (e.g. desktop,mobile)")
    p_fullscan.add_argument("--no-browser", action="store_true",
                            help="skip browser rendering and responsive audit "
                                 "(faster, but misses JS-rendered content)")
    p_fullscan.add_argument("--agent", action="store_true",
                            help="run offline scan and output candidate blocks "
                                 "for agent to judge with its own LLM "
                                 "(no API key needed)")
    p_fullscan.add_argument("--json", action="store_true",
                            help="machine-readable JSON output for agent")
    p_fullscan.set_defaults(func=cmd_fullscan)

    # `runs` / `resume` / `pause`: a long scan that stops must not be a scan
    # that is lost. Registered from their own module because they are about
    # the run rather than about the target.
    from cli_impl.runcmds import add_run_parsers
    add_run_parsers(sub)

    p_update = sub.add_parser(
        "update",
        help="self-update the CLI binary from the latest GitHub Release")
    p_update.set_defaults(func=cmd_update)

    p_uninstall = sub.add_parser(
        "uninstall",
        help="remove XAnalyze from this machine (command, app, settings, keychain)")
    p_uninstall.add_argument("--yes", action="store_true", default=False,
                             help="remove without asking for confirmation")
    p_uninstall.add_argument("--dry-run", action="store_true", default=False,
                             help="only list what would be removed")
    p_uninstall.set_defaults(func=cmd_uninstall)

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

    # The global flags again, on every subcommand. `xanalyze fullscan X
    # --no-update-check` is what people type - the flag reads as belonging to
    # the command, not to the program - and argparse answered it with
    # "unrecognized arguments", which is a wrong answer to a correct request.
    #
    # `default=SUPPRESS` is what makes the two copies co-operate rather than
    # fight: without it the subparser's own default would write `False` over
    # a `True` set before the subcommand, so putting the flag first would
    # stop working the moment it also worked last.
    _accept_global_flags_everywhere(sub)
    return parser


def _accept_global_flags_everywhere(subparsers, seen: set | None = None) -> None:
    """Add `--no-update-check` to every subcommand, at every depth.

    Recursive because two commands nest further (`cache stats`, `ai login`),
    and a flag accepted on `cache` but not on `cache stats` is the same
    surprise one level down.

    Deduplicated by object identity: an alias (`a11y` for `audit`) is the
    same parser under a second name, and adding one flag to it twice raises.
    """
    seen = seen if seen is not None else set()
    for subparser in subparsers.choices.values():
        if id(subparser) in seen:
            continue
        seen.add(id(subparser))
        subparser.add_argument(
            "--no-update-check", action="store_true",
            default=argparse.SUPPRESS,
            help="skip the automatic daily check for a newer version")
        for action in subparser._subparsers._group_actions if \
                subparser._subparsers else ():
            if hasattr(action, "choices") and action.choices:
                _accept_global_flags_everywhere(action, seen)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    # No subcommand → launch interactive TUI
    if args.command is None:
        from tui.app import run_tui
        return run_tui()

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
