"""Runs the accessibility rules over a crawled site or a local folder.

The two sources differ in exactly two ways, and both are handled by the
context rather than by the rules: a page locates an element by CSS path, a
file locates it by line number. Everything else — parsing, rule order,
de-duplication, the result shape — is shared, which is what keeps the rules
from having to know which mode they are in.

Same-domain crawling is not re-implemented here: `crawler.crawl` already
walks to a depth and refuses to leave the domain, and this runs over what it
returned. That is the point of reusing it — the rule holds for both modes of
the app because there is only one crawler.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from .base import CATEGORIES, SEVERITY_ORDER, Issue, RuleContext, RuleRegistry


@dataclass
class DocumentReport:
    """Findings for one page or one file, plus what was actually examined."""
    source: str
    issues: list = field(default_factory=list)
    error: str | None = None
    elements_checked: int = 0

    def by_severity(self) -> dict:
        out = {level: [] for level in SEVERITY_ORDER}
        for issue in self.issues:
            out.setdefault(issue.severity, []).append(issue)
        return out


@dataclass
class AccessibilityResult:
    """A whole run: every document, and the roll-up the report needs."""
    root: str
    mode: str = "web"          # "web" | "repo"
    documents: list = field(default_factory=list)
    rules_run: list = field(default_factory=list)

    def issues(self) -> list:
        out = []
        for document in self.documents:
            out.extend(document.issues)
        return out

    def counts(self) -> dict:
        counts = {level: 0 for level in SEVERITY_ORDER}
        for issue in self.issues():
            counts[issue.severity] = counts.get(issue.severity, 0) + 1
        return counts

    def by_rule(self) -> dict:
        """Issues grouped by rule, most-affected rule first.

        This is the view that makes a report actionable: fifty missing `alt`
        attributes are one job to schedule, not fifty separate problems to
        triage.
        """
        grouped: dict = {}
        for issue in self.issues():
            grouped.setdefault(issue.rule_id, []).append(issue)
        return dict(sorted(grouped.items(),
                           key=lambda kv: (-len(kv[1]), kv[0])))

    def documents_with_issues(self) -> list:
        return [d for d in self.documents if d.issues]


def _dom_path(tag) -> str:
    """CSS-ish path to an element.

    Sibling position is found by identity, not by `list.index()`: bs4 tags
    compare equal by content, so index() returns the first tag with matching
    markup and would produce a selector pointing at the wrong element.
    """
    parts = []
    node = tag
    while node is not None and getattr(node, "name", None) not in (None, "[document]"):
        index = 1
        if node.parent is not None:
            siblings = node.parent.find_all(node.name, recursive=False)
            for position, sibling in enumerate(siblings):
                if sibling is node:
                    index = position + 1
                    break
        parts.append(f"{node.name}:nth-of-type({index})")
        node = node.parent
    return " > ".join(reversed(parts))


def _line_lookup(raw_text: str):
    """Map a tag back to a 1-based line in the source file.

    bs4's html.parser records `sourceline` on every tag, so the line comes
    from the parser rather than from searching the text for the snippet —
    which would land on the wrong one whenever a file repeats an element.
    """
    def line_of(tag):
        line = getattr(tag, "sourceline", None)
        return int(line) if line else None
    return line_of


def analyze_document(markup: str, source: str, rules=None,
                     line_numbers: bool = False, ai_review=None) -> DocumentReport:
    """Run every rule over one document.

    `ai_review` is an optional `AIAccessibilityReview`. It runs on the same
    parsed document as the rules rather than on a second pass, so the AI only
    ever judges wording the offline rules could not settle, and its findings
    land in the same list, sorted by the same severity order.
    """
    rules = rules if rules is not None else RuleRegistry.all_rules()
    try:
        document = BeautifulSoup(markup, "html.parser")
    except Exception as exc:  # noqa: BLE001 - malformed markup is a finding, not a crash
        return DocumentReport(source=source, error=str(exc))

    context = RuleContext(source=source)
    context.dom_path = _dom_path
    if line_numbers:
        context.line_of = _line_lookup(markup)

    report = DocumentReport(source=source)
    report.elements_checked = len(document.find_all(True))
    seen = set()
    for rule in rules:
        try:
            found = rule.check(document, context)
        except Exception as exc:  # noqa: BLE001 - one broken rule can't fail the run
            report.issues.append(Issue(
                rule_id=rule.id, severity="minor", source=source,
                details={"rule_error": str(exc)},
            ))
            continue
        for issue in found:
            if issue.key in seen:
                continue
            seen.add(issue.key)
            report.issues.append(issue)

    if ai_review is not None:
        try:
            report.issues.extend(ai_review.review_document(document, context))
        except Exception as exc:  # noqa: BLE001 - the offline findings still stand
            report.issues.append(Issue(
                rule_id="ai-review", severity="minor", source=source,
                details={"rule_error": str(exc)},
            ))

    report.issues.sort(key=lambda i: (SEVERITY_ORDER.index(i.severity)
                                      if i.severity in SEVERITY_ORDER else 99,
                                      i.rule_id, i.line or 0))
    return report


def analyze_pages(pages, root: str, rules=None, ai_review=None) -> AccessibilityResult:
    """Web mode: run over what the crawler returned.

    Pages the crawler could not read are carried through with their error
    rather than dropped — a page that failed to load is a finding about the
    site, and silently omitting it would make the run look cleaner than it is.
    """
    rules = rules if rules is not None else RuleRegistry.all_rules()
    result = AccessibilityResult(root=root, mode="web",
                                 rules_run=[r.id for r in rules])
    for page in pages:
        if page.error or not page.raw_html:
            result.documents.append(DocumentReport(
                source=page.url,
                error=page.error or "no HTML received (see crawl diagnostics)",
            ))
            continue
        result.documents.append(
            analyze_document(page.raw_html, page.url, rules, ai_review=ai_review))
    return result


def analyze_files(file_results, root: str, rules=None, ai_review=None) -> AccessibilityResult:
    """Repo mode: run over the markup files the scanner read.

    Only files that actually contain markup are examined. A `.py` opened for
    its comments has no elements to check, and reporting "no issues" for it
    would pad the report with meaningless rows.
    """
    rules = rules if rules is not None else RuleRegistry.all_rules()
    result = AccessibilityResult(root=root, mode="repo",
                                 rules_run=[r.id for r in rules])
    for file_result in file_results:
        if file_result.error or not file_result.raw_text:
            continue
        if "<" not in file_result.raw_text:
            continue
        report = analyze_document(file_result.raw_text, file_result.path, rules,
                                  line_numbers=True, ai_review=ai_review)
        if report.issues or report.error:
            result.documents.append(report)
    return result
