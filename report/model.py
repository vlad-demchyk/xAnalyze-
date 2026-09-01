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
    #: Every place this same problem was found, `location` included and
    #: first. Filled by `ReportModel.grouped_findings`; empty on an
    #: ungrouped finding, where `location` alone is the answer.
    locations: list = field(default_factory=list)
    #: The platform that emitted the element, when one did - so the branded
    #: report says which rows are not the reader's to fix. Empty is the
    #: author's own markup, which is most of them.
    owner: str = ""
    #: How many independent engines found this. 1 unless the browser pass ran
    #: and a second engine corroborated; the number the JSON already carried
    #: and the printed report did not.
    agreement: int = 1
    #: The engine's own identifier for the check, e.g. `axe:button-name`.
    #: Printed as-is beside the engine name: it is what a reader searches
    #: for, what a suppression list names, and what two runs are compared
    #: on. It was in the JSON and nowhere in the document a person reads.
    rule_id: str = ""
    #: The HTML element this finding is about, lowercased, or `""` when the
    #: finding is not about one (a passage of prose, a response header, a
    #: page-level rule). Read off the markup the engine quoted rather than
    #: guessed from the selector - see `report.markup.element_of` - and used
    #: to ink the finding by role.
    element: str = ""

    @property
    def severity_rank(self) -> int:
        return SEVERITY_RANK.get(self.severity, 9)

    @property
    def occurrences(self) -> int:
        """How many places this problem was found in - 1 when ungrouped."""
        return max(1, len(self.locations))

    @property
    def identity(self) -> tuple:
        """What makes two findings the same problem in different places.

        Everything the reader would compare *except* where it is. Two pages
        missing a meta description produce the same title, the same
        explanation and the same (empty) markup, so they are one problem
        with two places; two different images missing `alt` differ in
        `snippet` and stay two problems.

        The snippet is compared with generated identifiers masked, the same
        way `duplicates.issue_identity` compares it, and for the same reason
        that function already documents: a theme that stamps a unique id into
        a component - WordPress writes `aria-controls="page-toc-panel-6a8c2c05ce8bd"`
        - produces markup that differs on every page while describing one bug
        in one template.

        It was not masked here, and that mattered, because this is the
        identity behind the *branded* report - the PDF a person reads. On a
        three-page crawl of a real WordPress site the two groupings disagreed
        (374 problems here against 369 there) over the same 552 occurrences,
        and the human-facing half was the one inflating. The audit-facing
        half had been protected against exactly this since the function was
        written.

        The rule id joins it now that the document *prints* the rule id.
        Two checks can produce the same sentence - `axe` and HTML_CodeSniffer
        both say a contrast is too low - and a group that merged them would
        show one id above occurrences the other found, which is a printed
        fact that is wrong for half its rows.
        """
        from duplicates import mask_generated_ids

        return (self.category, self.severity, self.rule_id, self.title,
                self.found, self.why, self.fix,
                mask_generated_ids(" ".join((self.snippet or "").split())),
                self.replacement, self.engine, self.wcag)


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

    def counts_by_title(self, limit: int = 8) -> list:
        """The problems that repeat most, worst first.

        This is the view a person schedules work from: "fifty missing `alt`
        attributes" is one job, and a report that only shows severity and
        category cannot say which job. Grouped rows, not raw findings, so a
        header repeated on thirty pages counts once per place rather than
        thirty times per page.
        """
        counts: dict = {}
        for finding in self.grouped_findings():
            key = (finding.title, finding.severity)
            # A grouped row carries every place it was seen at, so the count
            # is places rather than rows: one header repeated on thirty pages
            # is thirty jobs' worth of nothing and one job's worth of work,
            # and the number a reader schedules by is how many places a fix
            # has to visit.
            counts[key] = counts.get(key, 0) + max(1, len(finding.locations or []))
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0][0]))
        return [(title, severity, count)
                for (title, severity), count in ranked[:limit]]

    def counts_by_place(self, limit: int = 8) -> list:
        """Where the findings are, worst page first.

        The pages table lists every page examined; this answers a different
        question - which of them to open first.
        """
        counts: dict = {}
        for finding in self.findings:
            place = finding.location or ""
            if place:
                counts[place] = counts.get(place, 0) + 1
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return ranked[:limit]

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

    def grouped_findings(self) -> list:
        """The same findings, with one row per distinct problem.

        A crawl of thirty pages that share a header reports the header's
        every fault thirty times. Thirty identical cards is not thirty times
        the information — it is the same card, and a reader stops reading a
        list where every row repeats the previous one. So identical findings
        collapse into one, carrying the full list of places in `locations`,
        and nothing is lost: every address a fix has to visit is still named.

        Ordering follows `sorted_findings`, and the collapsed row keeps the
        first place it was seen at as its own `location`, so a grouped report
        and an ungrouped one open on the same finding.
        """
        from dataclasses import replace

        grouped: dict = {}
        order: list = []
        for finding in self.sorted_findings():
            key = finding.identity
            if key in grouped:
                where = finding.location
                if where and where not in grouped[key]:
                    grouped[key].append(where)
                continue
            grouped[key] = [finding.location] if finding.location else []
            order.append((key, finding))
        return [replace(first, locations=grouped[key]) for key, first in order]

    def counts_by_severity_grouped(self) -> dict:
        """`counts_by_severity`, counting each distinct problem once."""
        counts: dict = {}
        for finding in self.grouped_findings():
            counts[finding.severity] = counts.get(finding.severity, 0) + 1
        return counts


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
    from report.markup import element_of

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
                owner=getattr(issue, "owner", ""),
                agreement=(issue.details or {}).get("agreement", 1),
                element=element_of(issue.snippet, issue.selector),
                rule_id=issue.rule_id,
            ))
    return ReportModel(meta=ReportMeta(target=result.root, mode=f"audit-{result.mode}"),
                       findings=findings)
