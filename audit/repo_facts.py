"""What a repository reveals about itself, as opposed to what its pages do.

Three different questions live here, and they share a module because they
share a method: none of them judges anything. Each reads a fact that is
either present or absent, the way `unicode_rules` reads a zero-width
character and `audit/rules/provenance.py` reads a vendor class name.

**Who wrote it.** A commit trailer naming an assistant is a record, not an
inference. Every classifier in this tool is guessing at whether a model
wrote a passage; the repository has been keeping the answer in plain text
the whole time. It is reported as provenance, not as a problem: writing code
with an assistant is not a defect, and the tool that says otherwise is
telling people how to work.

**What the assistants left behind.** `CLAUDE.md`, `.cursor/`, a Copilot
instructions file: committed configuration for tools that wrote here.
Interesting for the same reason, and for one more - these files often carry
project context somebody did not mean to publish.

**What is about to leak.** A `.env` that no ignore rule covers is a
credential waiting for the next `git add .`, and one that is already tracked
is a credential that has been published and needs rotating, not deleting.
Those are different findings with different fixes, and telling them apart
needs git rather than the filesystem - so it asks git, and says so when it
cannot.

Everything here degrades to silence rather than to a guess. A folder that is
not a git repository produces no commit findings at all, because "no
assistant commits found" and "no history to look at" are opposite statements
and only one of them is true.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

#: Trailers and phrases that name an assistant as an author. Matched against
#: the whole commit message, case-insensitively. Each is something a tool
#: writes about itself, not a word a person might use in passing: "claude"
#: alone would match "reviewed with claude's suggestion in mind", which is a
#: sentence about a person's process and nobody else's business.
_ASSISTANT_MARKS = (
    r"co-authored-by:\s*claude",
    r"co-authored-by:.*\bcopilot\b",
    r"co-authored-by:.*\bcursor\b",
    r"co-authored-by:.*\baider\b",
    r"co-authored-by:.*\bdevin\b",
    r"generated with \[?claude",
    r"generated with \[?github copilot",
    r"🤖 generated with",
)
_ASSISTANT_RE = re.compile("|".join(_ASSISTANT_MARKS), re.I)

#: Files and folders an assistant leaves in a project. Paths relative to the
#: repository root, matched exactly for files and as a prefix for folders.
_TOOL_ARTIFACTS = (
    "CLAUDE.md", "AGENTS.md", ".claude/", ".cursor/", ".cursorrules",
    ".github/copilot-instructions.md", ".aider.chat.history.md",
    ".aider.input.history", ".continue/", ".windsurfrules", ".codeium/",
)

#: Files that carry credentials. `.env.example` and friends are the
#: convention for *not* carrying them, so they are excluded by name rather
#: than by guessing at contents.
_ENV_RE = re.compile(r"(^|/)\.env(\.|$)", re.I)
_ENV_SAFE_SUFFIXES = (".example", ".sample", ".template", ".dist")

#: How many commits back to read. Enough to describe a project's habits,
#: bounded so a repository with a decade of history does not turn a scan
#: into a `git log` of the whole thing.
_COMMITS_READ = 500

#: Seconds any one git call may take. A repository on a slow disk, or one
#: git decides to garbage-collect mid-scan, must not hang a run.
_GIT_TIMEOUT = 20


@dataclass
class RepoFacts:
    """What the walk established, including what it could not."""
    is_git: bool = False
    commits_read: int = 0
    assistant_commits: list = field(default_factory=list)
    tool_artifacts: list = field(default_factory=list)
    exposed_env: list = field(default_factory=list)
    tracked_env: list = field(default_factory=list)
    #: Why git was not consulted, when it was not. Empty when it was.
    git_unavailable: str = ""


def _git(root: Path, *args: str) -> str | None:
    """Run one git command in `root`. None when git could not answer.

    Never raises: a missing git, a folder that is not a repository, a
    timeout and a non-zero exit are all the same answer here - we do not
    know - and each of them must leave the rest of the scan running.
    """
    try:
        done = subprocess.run(("git", "-C", str(root)) + args,
                              capture_output=True, text=True,
                              timeout=_GIT_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def _is_env_file(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1].lower()
    if not _ENV_RE.search("/" + rel.lower()):
        return False
    return not name.endswith(_ENV_SAFE_SUFFIXES)


def read_facts(root, config=None) -> RepoFacts:
    """Everything this module can establish about `root`."""
    from repo_scanner import ScanConfig, build_matcher, is_ignored

    root = Path(root)
    config = config or ScanConfig()
    facts = RepoFacts()
    if not root.is_dir():
        return facts

    inside = _git(root, "rev-parse", "--is-inside-work-tree")
    facts.is_git = bool(inside and inside.strip() == "true")
    if not facts.is_git:
        facts.git_unavailable = "not a git repository"

    # -- who wrote it
    if facts.is_git:
        log = _git(root, "log", f"-{_COMMITS_READ}", "--format=%H%x1f%s%x1f%b%x1e")
        if log is None:
            facts.git_unavailable = "git could not read this repository's log"
        else:
            for record in log.split("\x1e"):
                record = record.strip("\n")
                if not record:
                    continue
                parts = record.split("\x1f")
                if len(parts) < 3:
                    continue
                facts.commits_read += 1
                sha, subject, body = parts[0], parts[1], parts[2]
                if _ASSISTANT_RE.search(f"{subject}\n{body}"):
                    facts.assistant_commits.append((sha[:12], subject))

    # -- what the assistants left behind, and what is about to leak
    matcher = build_matcher(config.ignore_patterns)
    tracked = None
    if facts.is_git:
        listing = _git(root, "ls-files", "-z")
        if listing is not None:
            tracked = {name for name in listing.split("\0") if name}

    for artifact in _TOOL_ARTIFACTS:
        path = root / artifact.rstrip("/")
        if path.exists():
            facts.tool_artifacts.append(artifact)

    for path in sorted(root.rglob("*")):
        if path.is_dir():
            continue
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if not _is_env_file(rel):
            continue
        # An ignored `.env` is the normal, correct arrangement and not a
        # finding. This is the whole check: the danger is the one nothing
        # covers.
        if is_ignored(rel, matcher) or _git_ignores(root, rel, facts):
            continue
        if tracked is not None and rel in tracked:
            facts.tracked_env.append(rel)
        else:
            facts.exposed_env.append(rel)
    return facts


def _git_ignores(root: Path, rel: str, facts: RepoFacts) -> bool:
    """Does the repository's own `.gitignore` cover this path?

    Asked of git rather than parsed here, because git is the authority on
    its own ignore rules and a second implementation of them would
    eventually disagree - and disagreeing in the safe direction means
    staying quiet about a credential.
    """
    if not facts.is_git:
        return False
    return _git(root, "check-ignore", "-q", rel) is not None


# --------------------------------------------------------------- as findings

RULE_ASSISTANT_COMMITS = "bp-assistant-commits"
RULE_TOOL_ARTIFACTS = "bp-assistant-artifacts"
RULE_ENV_EXPOSED = "sec-env-not-ignored"
RULE_ENV_TRACKED = "sec-env-tracked"

#: How many examples a finding names before it says "+N". Enough to
#: recognise the pattern, short enough to stay one line.
_NAMED = 3


def _listed(values: list) -> str:
    named = ", ".join(str(v) for v in values[:_NAMED])
    extra = len(values) - _NAMED
    return f"{named}, +{extra}" if extra > 0 else named


def as_documents(facts: RepoFacts, root: str) -> list:
    """The facts as `DocumentReport`s, in the order they matter.

    Security first, and not as a formality: a credential in the working tree
    is the only thing here that gets worse the longer it is not read.
    """
    from audit.base import (
        BEST_PRACTICES, CRITICAL, EXACT, Issue, MINOR, SECURITY, SERIOUS,
    )
    from audit.engine import DocumentReport

    documents = []

    def add(source: str, rule: str, severity: str, category: str, details: dict,
            snippet: str = "") -> None:
        documents.append(DocumentReport(
            source=source, elements_checked=1,
            issues=[Issue(rule_id=rule, severity=severity, category=category,
                          confidence=EXACT, source=source, selector="",
                          line=None, snippet=snippet, details=details,
                          engine="repo")]))

    for rel in facts.tracked_env:
        # Already published. Deleting the file does not undo that, and a
        # finding that says "remove it" would be advice that leaves the
        # secret where it is.
        add(rel, RULE_ENV_TRACKED, CRITICAL, SECURITY, {"path": rel})
    for rel in facts.exposed_env:
        add(rel, RULE_ENV_EXPOSED, SERIOUS, SECURITY, {"path": rel})

    if facts.tool_artifacts:
        add(root, RULE_TOOL_ARTIFACTS, MINOR, BEST_PRACTICES,
            {"count": len(facts.tool_artifacts),
             "names": _listed(facts.tool_artifacts)},
            snippet=_listed(facts.tool_artifacts))
    if facts.assistant_commits:
        add(root, RULE_ASSISTANT_COMMITS, MINOR, BEST_PRACTICES,
            {"count": len(facts.assistant_commits),
             "read": facts.commits_read,
             "names": _listed([subject for _sha, subject
                               in facts.assistant_commits])},
            snippet=_listed([f"{sha} {subject}"
                             for sha, subject in facts.assistant_commits]))
    return documents
