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
from pathlib import Path

from bs4 import BeautifulSoup

from .base import (
    CATEGORIES, SEVERITY_ORDER, Issue, RuleContext, RuleRegistry,
    remember_source,
)


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
    mode: str = "web"          # "web" | "repo" | "file"
    documents: list = field(default_factory=list)
    rules_run: list = field(default_factory=list)
    #: What the media pass reached, when one ran. An image nobody fetched
    #: has not come back clean - it has not come back - and without these
    #: counts the run has no way to say so.
    media: object = None

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


#: Suffixes whose contents are a finished document rather than a fragment of
#: one. Everything else in a repository is source that merely contains markup.
PAGE_SUFFIXES = {".html", ".htm", ".xhtml"}
# Files to skip in repo audit — source code, tests, configs
SKIP_AUDIT_SUFFIXES = {".tsx", ".jsx", ".mjs", ".ts", ".js", ".py", ".rb", ".go", ".rs", ".java", ".c", ".cpp", ".h"}
SKIP_AUDIT_PATTERNS = {"test", "spec", "__tests__", "node_modules", ".min."}


def analyze_document(markup: str, source: str, rules=None,
                     line_numbers: bool = False, ai_review=None,
                     document_kind: str = "page",
                     source_text: str | None = None) -> DocumentReport:
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

    # The source text, kept with the parsed document so a finding can quote
    # the file rather than the parser's re-print of it. See `snippet_of`.
    # The *unmasked* text, when the caller had to mask something to parse it:
    # a snippet must show what the developer will find in the file.
    remember_source(document, source_text if source_text is not None else markup)

    context = RuleContext(source=source)
    context.document_kind = document_kind
    context.dom_path = _dom_path
    if line_numbers:
        context.line_of = _line_lookup(markup)

    if document_kind != "page":
        # A component file is a piece of a page. Asking it for a doctype, a
        # title or exactly one h1 reports the absence of things that belong to
        # the page it will be part of. A rule that needs a stylesheet is
        # skipped for the same reason: the fragment carries none, so an
        # "absent" verdict would be indistinguishable from an unseen one.
        rules = [rule for rule in rules
                if not getattr(rule, "page_level", False)
                and not getattr(rule, "needs_external_css", False)]

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


def analyze_pages(pages, root: str, rules=None, ai_review=None,
                  media: bool = True, media_fetch=None) -> AccessibilityResult:
    """Web mode: run over what the crawler returned.

    Pages the crawler could not read are carried through with their error
    rather than dropped — a page that failed to load is a finding about the
    site, and silently omitting it would make the run look cleaner than it is.

    `media` reads what the site's images say about how they were made
    (`audit.media`). Unlike every other check here it needs the network: the
    crawler kept the markup, not the pictures. `media_fetch` is injected the
    way the crawler injects `render`, so a test proves what the pass does
    with bytes without needing a network to hand them over.
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
    if media:
        from audit import media as media_pass

        # On by default, bounded hard. A site's images are part of what was
        # published, and a check that only runs when asked for is a check
        # that mostly does not run - the same reasoning that made both
        # questions the default. The budget is what keeps "read the images"
        # from becoming "mirror the site", and whatever it did not reach is
        # counted so the run can say so.
        scan = media_pass.scan_page_media(pages, fetch=media_fetch)
        result.media = scan
        result.documents.extend(media_pass.as_web_documents(scan))
    return result


def analyze_page_file(path: str, rules=None, ai_review=None) -> AccessibilityResult:
    """One self-contained HTML file, treated as a page rather than as source.

    A page exported or built into a single file - inlined CSS, inlined
    scripts, data-URI images - is a finished document, not a template. Repo
    mode is the wrong reading of it: that mode exists for markup fragments
    inside a project and deliberately skips whatever has no elements, while
    this file is the whole page and its `<head>` is worth auditing exactly as
    a served one would be.

    It also unlocks the browser pass, which repo mode cannot have. A file with
    everything inlined renders faithfully from `file://`, so axe, the state
    pass and the load measurements all mean what they mean on a real page.
    """
    rules = rules if rules is not None else RuleRegistry.all_rules()
    result = AccessibilityResult(root=path, mode="file",
                                 rules_run=[r.id for r in rules])
    try:
        markup = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        result.documents.append(DocumentReport(source=path, error=str(exc)))
        return result
    # Line numbers on: the user has the file open, so "line 42" is directly
    # actionable in a way a CSS selector into a one-file build is not.
    result.documents.append(
        analyze_document(markup, path, rules, line_numbers=True, ai_review=ai_review))
    return result


def analyze_files(file_results, root: str, rules=None, ai_review=None,
                  media: bool = True) -> AccessibilityResult:
    """Repo mode: run over the markup files the scanner read.

    Only files that actually contain markup are examined. A `.py` opened for
    its comments has no elements to check, and reporting "no issues" for it
    would pad the report with meaningless rows.

    `media` also reads what the project's image files say about how they
    were made (`audit.media`). A second walk rather than a filter over
    `file_results`, because the scanner never opens an image: its extension
    list is the list of files that hold *text*, so the assets are not in
    that list to be filtered. On by default because a repository's images
    are part of the repository, and off is there for a caller that has
    already read them or does not want the walk.
    """
    rules = rules if rules is not None else RuleRegistry.all_rules()
    result = AccessibilityResult(root=root, mode="repo",
                                 rules_run=[r.id for r in rules])
    for file_result in file_results:
        if file_result.error or not file_result.raw_text:
            continue
        if "<" not in file_result.raw_text:
            continue
        # Skip source code files and test files
        path_lower = file_result.path.lower()
        if any(path_lower.endswith(ext) for ext in SKIP_AUDIT_SUFFIXES):
            continue
        if any(pat in path_lower for pat in SKIP_AUDIT_PATTERNS):
            continue
        kind = ("page" if Path(file_result.path).suffix.lower() in PAGE_SUFFIXES
                else "fragment")
        markup = file_result.raw_text
        if kind == "fragment":
            # A source file's comments are prose, and prose talks about markup:
            # `// the <img> is replaced on remount` is an element with no alt
            # to an HTML parser. Masked rather than stripped, so every line and
            # column still points where it did.
            from repo_scanner import mask_code_comments
            markup = mask_code_comments(markup, file_result.path)
        report = analyze_document(markup, file_result.path, rules,
                                  line_numbers=True, ai_review=ai_review,
                                  document_kind=kind,
                                  source_text=file_result.raw_text)
        if report.issues or report.error:
            result.documents.append(report)
    if media:
        from audit import media as media_pass

        # Appended, not merged into a document: an image is a document of
        # its own, and the rest of the pipeline - the report, the grouping,
        # the file list in the window - already works in documents.
        result.documents.extend(
            media_pass.as_documents(media_pass.scan_media(root)))
    return result
