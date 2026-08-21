"""The one shape `template.py` renders from.

Two very different analyses feed a styled report — the AI-text pass
(`AnalysisResult` / `RepoAnalysisResult`, scoring `TextSpan`s as a
probability) and the site audit (`AccessibilityResult`, reporting `Issue`s
as facts with a severity). They disagree about almost everything: one has a
0..1 score and a detector name, the other has a fixed severity vocabulary
and a WCAG reference. Rather than let the template know both, each source
gets its own adapter function here (`from_text_analysis` /
`from_accessibility`) that flattens it into one `ReportModel` of
`ReportFinding`s. The template — and the PDF renderer behind it — reads only
that, so it has exactly one shape to lay out regardless of which mode
produced it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from models import AnalysisResult, CodeBlock, Confidence

#: The category a text-mode finding is filed under. Kept distinct from the
#: audit categories (`audit.base.CATEGORIES`) rather than folded into
#: "best-practices": an AI-sounding sentence and a missing `alt` are not the
#: same kind of problem, and a report that mixed them under one label would
#: hide which pass found what.
CATEGORY_AI_TEXT = "ai-text"

#: Two severity vocabularies exist in this codebase and both reach the
#: report unchanged (`Confidence.value` for text, `Issue.severity` for
#: audit) — rewriting one to match the other would lose information the
#: source truly has. This is the shared ordering used to sort a mixed list
#: and to pick a display colour; lower is worse. Unknown values sort last
#: rather than raising, so a future severity name still renders (just
#: unordered) instead of breaking the report.
SEVERITY_RANK = {
    "critical": 0, "serious": 1, "moderate": 2, "minor": 3,
    "high": 0, "medium": 1, "low": 2,
}


@dataclass
class ReportFinding:
    """One row in the report, whichever pass produced it."""
    title: str
    category: str
    severity: str
    location: str
    #: What was found, plain text (a code/markup snippet is shown separately
    #: in `snippet`, so this stays a short human sentence).
    found: str = ""
    why: str = ""
    fix: str = ""
    #: The offending markup or the flagged passage, verbatim. Rendered as
    #: text in a monospace block by the template, never as markup — see
    #: `template.py`'s escaping.
    snippet: str = ""
    #: The ready replacement, when one exists: `Issue.fix_snippet` for an
    #: audit finding, an AI-rewritten draft or the exact character
    #: correction for a text finding. Empty when the correction needs a
    #: human decision.
    replacement: str = ""
    #: Which engine or detector produced this: "static" / "axe" / "htmlcs"
    #: for audit, the detector name for text.
    engine: str = ""
    wcag: tuple = ()

    @property
    def severity_rank(self) -> int:
        return SEVERITY_RANK.get(self.severity, 9)


@dataclass
class ReportMeta:
    target: str
    #: "text-web" | "text-repo" | "audit-web" | "audit-repo" | "audit-file"
    mode: str
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))
    generator: str = "AI Content Scanner"


@dataclass
class ReportModel:
    """Everything `template.render_html` needs, and nothing it has to guess."""
    meta: ReportMeta
    findings: list[ReportFinding] = field(default_factory=list)
    pages: list = field(default_factory=list)          # [{source, findings_count, error}]
    ai_patterns: dict = field(default_factory=dict)     # {total, high, medium, low, files, top_patterns}
    typography: dict = field(default_factory=dict)      # {total, files, by_character, top_examples}

    def counts_by_severity(self) -> dict:
        counts: dict[str, int] = {}
        for finding in self.findings:
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
        return counts

    def counts_by_category(self) -> dict:
        counts: dict[str, int] = {}
        for finding in self.findings:
            counts[finding.category] = counts.get(finding.category, 0) + 1
        return counts

    def sorted_findings(self) -> list:
        """Worst first, then grouped by category, then by where it is —
        so two findings in the same file sit next to each other."""
        return sorted(self.findings,
                      key=lambda f: (f.severity_rank, f.category, f.location))


# --------------------------------------------------------------- text mode

def _text_location(block) -> str:
    if isinstance(block, CodeBlock):
        return f"{block.file_path}:{block.line_number}"
    return getattr(block, "page_url", "")


def from_text_analysis(result, target: str | None = None,
                       drafts: dict | None = None) -> ReportModel:
    """Build a `ReportModel` from `AnalysisResult` (web) or
    `RepoAnalysisResult` (repo) — the AI-text scan.

    `drafts` mirrors the UI's `self.drafts`: `{(block_id, start, end): text}`,
    the rewritten replacement a person or the AI-rewrite pass produced for a
    span. Optional because a bare CLI scan has none — every finding then
    reports its exact character correction (when the character pass has one)
    and otherwise leaves `replacement` empty, same as `--json` does today.
    """
    drafts = drafts or {}
    blocks_by_id = {b.block_id: b for b in result.blocks()}
    findings: list[ReportFinding] = []
    for span in result.spans:
        if span.confidence == Confidence.LOW:
            continue
        block = blocks_by_id.get(span.block_id)
        if block is None:
            continue
        original = block.text[span.start:span.end]
        draft = drafts.get((block.block_id, span.start, span.end), "")
        title = " ".join(original.split())
        if len(title) > 90:
            title = title[:89] + "…"
        findings.append(ReportFinding(
            title=title or "(empty match)",
            category=CATEGORY_AI_TEXT,
            severity=span.confidence.value,
            location=_text_location(block),
            found=title,
            why=span.explanation,
            fix=draft,
            snippet=original,
            replacement=draft or (span.replacement or ""),
            engine=(span.details or {}).get("source") or span.detector_name,
        ))
    root = target or getattr(result, "root_url", None) or getattr(result, "root_dir", "")
    mode = "web" if isinstance(result, AnalysisResult) else "repo"
    return ReportModel(meta=ReportMeta(target=root or "", mode=f"text-{mode}"),
                       findings=findings)


# ------------------------------------------------------------ audit mode

def from_accessibility(result, lang: str = "uk") -> ReportModel:
    """Build a `ReportModel` from an `AccessibilityResult` — the site audit.

    Explanations come from `audit.explanations.render`, the same function
    the window and `cli.py --report` already call, so the wording a person
    reads in the styled report matches every other surface exactly.
    """
    from audit.explanations import render

    findings: list[ReportFinding] = []
    for document in result.documents:
        for issue in document.issues:
            explanation = render(issue, lang)
            if issue.line:
                where = f"line {issue.line}"
            else:
                where = issue.selector or ""
            location = f"{document.source} — {where}" if where else document.source
            findings.append(ReportFinding(
                title=explanation.title,
                category=issue.category,
                severity=issue.severity,
                location=location,
                found=explanation.found,
                why=explanation.why,
                fix=explanation.fix,
                snippet=issue.snippet,
                replacement=issue.fix_snippet or "",
                engine=issue.engine,
                wcag=explanation.wcag,
            ))
    return ReportModel(meta=ReportMeta(target=result.root, mode=f"audit-{result.mode}"),
                       findings=findings)
