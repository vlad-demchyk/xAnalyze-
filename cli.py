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
import unicode_rules
import config
from audit.base import CATEGORIES
from detectors.factory import DetectorFactory
from file_writer import ReplacementPlan, apply_replacements
from lang_detect import guess_language
from models import Confidence
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

def _collect_files(paths: list[str], args) -> list:
    """Turn the given paths into FileResults. A directory is walked with the
    exclusion rules; a file named directly is always scanned."""
    ignore = _parse_ignore_text(DEFAULT_IGNORE_PATTERNS) if args.use_default_excludes else []
    ignore += list(args.exclude or [])
    # None lets the scope pick the extension set (comments are worth reading
    # in far more file types than copy is); an explicit --ext still wins.
    extensions = tuple(e if e.startswith(".") else "." + e for e in args.ext) if args.ext else None
    scope = getattr(args, "scope", "content")

    results = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            results.extend(scan_repo(str(p), ScanConfig(
                extensions=extensions,
                ignore_patterns=ignore,
                max_files=args.max_files,
                scope=scope,
            )))
        elif p.exists():
            results.append(scan_file(str(p), scope))
        else:
            print(f"path not found: {raw}", file=sys.stderr)
    return results


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


def _analyze(file_results, args):
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
        detector = DetectorFactory.create(args.detector)
        spans.extend(s for s in detector.analyze_blocks(blocks)
                     if s.confidence != Confidence.LOW)

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


def _print_json(findings, applied=None) -> None:
    payload = {
        "findings": [_public(f) for f in findings],
        "counts": _counts(findings),
    }
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


def _print_human(findings) -> None:
    if not findings:
        print("No findings.")
        return
    current = None
    for f in findings:
        if f["file"] != current:
            current = f["file"]
            print(f"\n{current}")
        rep = "" if f["replacement"] is None else f"  ->  {f['replacement']!r}"
        print(f"  line {f['line']:>4}  [{f['confidence']}]  {_visible(f['text'])!r}{rep}")
        print(f"              {f['explanation']}")
    c = _counts(findings)
    print(f"\n{c['total']} finding(s) in {c['files']} file(s).")


# ---------------------------------------------------------------- commands

def cmd_scan(args) -> int:
    files = _collect_files(args.paths, args)
    findings, _ = _analyze(files, args)
    if args.json:
        _print_json(findings)
    else:
        _print_human(findings)
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
        for path in result.files_changed:
            backup = path + ".bak"
            if os.path.exists(backup):
                os.remove(backup)

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
    if target.startswith(("http://", "https://")) or args.url:
        from crawler import CrawlConfig, crawl

        # Same crawler as the text scan: depth-limited, and refusing to leave
        # the domain. That rule holds for both modes because there is one
        # crawler, not two.
        if not target.startswith(("http://", "https://")):
            target = "https://" + target
        pages = crawl(target, CrawlConfig(max_depth=args.depth, max_pages=args.max_pages))
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
        _run_browser_pass(result, suppressions)

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


def _run_browser_pass(result, suppressions) -> None:
    """Load each audited page in a real browser and fold the findings in.

    URL mode only: a browser has nothing to load for a file on disk that was
    never served, and half-auditing a template would report problems the
    built page does not have.

    The suppression list is handed to the engines rather than applied to
    their output, so an excluded region is never analysed in the first place
    — for axe that is the difference between "ignore these results" and "do
    not spend seconds computing them".
    """
    if result.mode != "web":
        return
    from audit import browser as browser_mod
    from audit import driver

    usable, reason = driver.available()
    if not usable:
        print(f"# browser pass skipped: {reason}", file=sys.stderr)
        return

    targets = [d for d in result.documents
               if not d.error and d.source.startswith(("http://", "https://"))]
    if not targets:
        return

    options = browser_mod.BrowserAuditOptions(
        exclude=list(suppressions.selectors),
        disabled_rules=list(suppressions.rules),
    )
    print(f"# browser pass over {len(targets)} page(s)", file=sys.stderr)
    audits = driver.audit_urls([d.source for d in targets], options)
    by_url = {a.url: a for a in audits}
    for document in targets:
        page_audit = by_url.get(document.source)
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
            list(document.issues) + list(page_audit.issues))


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


# ------------------------------------------------------------------ parser

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-content-scanner",
        description="Find and fix characters no keyboard produces (and optionally "
                    "flag AI-sounding copy) in web pages' source files. "
                    "Designed to run after an LLM coding agent.",
    )
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
                                "claude-llm-judge | xformat-llm-judge | none")
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
    p_audit.add_argument("target", help="URL to crawl, or directory to scan")
    p_audit.add_argument("--url", action="store_true",
                         help="treat the target as a URL even without a scheme")
    p_audit.add_argument("--depth", type=int, default=0,
                         help="link depth to crawl; same-domain only (default 0: one page)")
    p_audit.add_argument("--max-pages", type=int, default=30)
    p_audit.add_argument("--max-files", type=int, default=5000)
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
    p_audit.add_argument("--browser", action="store_true",
                         help="also load each page in a real browser: runs "
                              "axe-core, HTML_CodeSniffer, the keyboard/focus "
                              "state pass and load measurements (URL targets "
                              "only; slower)")
    p_audit.set_defaults(func=cmd_audit)

    # `ai` groups everything that spends money or needs an account, so the
    # commands that never do (scan, fix, audit) stay usable with no setup.
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

    p_clean = sub.add_parser("clean", help="filter text from stdin to stdout")
    common(p_clean, with_paths=False)
    p_clean.add_argument("--language", default=None, choices=["uk", "it", "en"],
                         help="override language detection")
    p_clean.set_defaults(func=cmd_clean)

    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
