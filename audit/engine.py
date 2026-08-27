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
import re
from pathlib import Path, PurePath

from bs4 import BeautifulSoup

import applog
from project_profile import looks_generated

from . import medium
from .base import (
    CATEGORIES, SEVERITY_ORDER, Issue, RuleContext, RuleRegistry,
    remember_source, resolve_bound_attributes, resolve_text_directives,
    unwrap_template_text,
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
    #: What the repository said about itself, when it was asked. Carries the
    #: reason git could not answer, which is the difference between "no
    #: assistant commits" and "no history to look at".
    repo: object = None
    #: A slice of the markup the crawl actually saw, kept so the report can
    #: ask what platform served it. The documents keep addresses, not bodies,
    #: so without this the answer would have to be fetched a second time.
    markup_sample: str = ""

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
#: Suffixes with no markup to read, skipped before a rule ever runs.
#:
#: `.tsx` and `.jsx` are deliberately *not* here. They were, and that made the
#: whole fragment path — `document_kind`, `Rule.page_level`,
#: `Rule.needs_external_css`, `mask_code_comments` — unreachable for React,
#: because this check runs before the `kind = "fragment"` branch below. A Vite
#: repository then audited down to its empty `index.html` shell and reported
#: zero findings, which reads as clean. See `P-19`.
#:
#: `.ts`, `.js` and `.mjs` stay skipped, and the reason is not the same one.
#: JSX is not valid in them, so their `<` is an operator: `if (a < b)` handed
#: to an HTML parser is an open tag, and every finding under it would be about
#: markup nobody wrote. A `.tsx` file's `<` is markup by definition of the
#: extension.
SKIP_AUDIT_SUFFIXES = {".mjs", ".ts", ".js", ".py", ".rb", ".go", ".rs", ".java", ".c", ".cpp", ".h"}
#: Directory names that mean "not the product". Matched as whole path
#: segments, never as substrings: `test` inside a substring also matches
#: `src/features/coach/CoachTestEditor.tsx` and `SmartTestModal.tsx`, two real
#: screens in `~/repositories/XFormat` that were being skipped as tests.
#:
#: `spec` and `specs` are deliberately absent. A directory by that name is a
#: written specification at least as often as a test suite - this repository's
#: own `specs/` holds `read-once` and `resumable-runs`, neither of which is a
#: test. The JS convention that *is* unambiguous is the filename, `Foo.spec.tsx`,
#: and that is covered below; RSpec's `foo_spec.rb` is skipped by suffix.
#: `fixtures`, `__fixtures__` and `testdata` are here because
#: `project_profile._MARKER_BLIND` already treats them that way and the two
#: modules were answering the same question differently. A fixture is markup
#: written to be wrong on purpose, and reporting it as a defect of the
#: project is the audit failing to know what it is reading.
SKIP_AUDIT_DIRS = {"test", "tests", "__tests__", "__mocks__",
                   "fixtures", "__fixtures__", "testdata",
                   "node_modules", "dist", "build", ".next"}
#: Filename markers that mean the same thing, matched inside the name only.
SKIP_AUDIT_NAME_MARKERS = (".test.", ".spec.", ".stories.", ".min.")


def _is_skipped_path(path: str) -> bool:
    """Is this a file the repo audit has no business reading?

    Split out of `analyze_files` because it is the half of that loop that
    decides what is *never seen*, and a wrong answer here is invisible: the
    report simply comes back shorter, and a shorter report reads as a
    cleaner one.
    """
    parts = PurePath(path.replace("\\", "/")).parts
    if any(part.lower() in SKIP_AUDIT_DIRS for part in parts[:-1]):
        return True
    name = parts[-1].lower() if parts else ""
    if any(marker in name for marker in SKIP_AUDIT_NAME_MARKERS):
        return True
    return PurePath(name).suffix in SKIP_AUDIT_SUFFIXES


#: How much of the first page to keep for platform detection.
_MARKUP_SAMPLE = 200_000

#: What a finished document has and a template of one does not. A page is not
#: one tag, it is the whole shape: a root, and the two halves inside it.
_PAGE_ROOT = re.compile(r"<!doctype\s+html|<html[\s>]", re.I)
_PAGE_HALVES = re.compile(r"<head[\s>]|<body[\s>]", re.I)


def _document_kind(path: str, markup: str) -> str:
    """"page" for a finished document, "fragment" for a piece of one.

    The suffix is not enough, and believing it cost a whole framework. An
    Angular component template is a `.html` file with no `<html>` in it, so
    every page-level rule fired on it: `bp-charset`, `landmark-regions`,
    `skip-link`, `seo-canonical`, `seo-open-graph` - eight findings against a
    file that was never going to be a page on its own. The same is true of
    every `_header.html` partial ever written.

    So the question is asked of the content instead, and asked about the
    whole shape rather than one tag: a finished document has a root - a
    doctype or `<html>` - **and** the halves inside it, a `<head>` or a
    `<body>`. A fragment has neither, and a file with a stray `<html>` and
    nothing else is not a page anybody is going to serve. That is evidence
    rather than a naming convention, and it is the same test in every
    technology.

    `analyze_page_file` is unaffected - naming a single file on the command
    line *is* the statement that it is a page.
    """
    if Path(path).suffix.lower() not in PAGE_SUFFIXES:
        return "fragment"
    text = markup or ""
    complete = bool(_PAGE_ROOT.search(text)) and bool(_PAGE_HALVES.search(text))
    return "page" if complete else "fragment"


def analyze_document(markup: str, source: str, rules=None,
                     line_numbers: bool = False, ai_review=None,
                     document_kind: str = "page",
                     source_text: str | None = None,
                     force_medium: str | None = None) -> DocumentReport:
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
    # What the document is *for*, which the file format does not say. See
    # `audit.medium`: an email and a page are both complete HTML documents.
    context.medium = force_medium or medium.detect(markup).name
    context.dom_path = _dom_path
    if line_numbers:
        context.line_of = _line_lookup(markup)

    # `:alt="caption"` is an `alt`, spelled the way Vue, Angular, Alpine,
    # Svelte and Thymeleaf spell it. Given its plain name back before any rule
    # runs, so no rule has to know five framework syntaxes and none of them
    # reports a correct component as missing what it has.
    #
    # Run for a page as well as a fragment, and safely: both of these only
    # ever *add* a plain attribute where a bound one exists, and a served page
    # has no `th:alt`, `[alt]` or `:alt` to find. A Thymeleaf template is a
    # whole page and still needs them.
    resolve_bound_attributes(document)
    # An element whose text arrives at runtime - `x-text`, `v-text`,
    # `th:text`, `ng-bind`, `data-i18n` - is written empty on purpose. Read
    # literally it is an empty link with no accessible name.
    resolve_text_directives(document)
    if context.medium == medium.EMAIL:
        # An HTML email is the same file format as a page and almost nothing
        # else: no canonical URL, never crawled, not shared to Open Graph, and
        # rendered by clients that implement neither landmarks nor skip links.
        # The accessibility rules are untouched - `alt`, control names, table
        # headers and contrast are as real in a mail client as in a browser.
        rules = [rule for rule in rules if not getattr(rule, "web_only", False)]
    if document_kind != "page":
        # A Vue single-file component *is* a `<template>`, whose text bs4
        # hides the way it hides a comment. Fragments only: on a served page
        # a `<template>` really is an inert prototype.
        unwrap_template_text(document)
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
            applog.error("rule.raised", rule=rule.id, source=source,
                          error=f"{type(exc).__name__}: {exc}")
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
        if not result.markup_sample:
            # The first page that loaded is enough to say what served it: a
            # platform's signature is in the shell, and the shell is the same
            # on every page it renders. Bounded, because this is kept for a
            # regex and not for reading.
            result.markup_sample = page.raw_html[:_MARKUP_SAMPLE]
        result.documents.append(
            analyze_document(page.raw_html, page.url, rules, ai_review=ai_review))
    # What the response said. Free: these bytes arrived with the page, and
    # until now everything but `Content-Type` was discarded. See
    # `audit.headers`.
    from audit import crosspage as crosspage_pass
    from audit import headers as header_pass

    result.documents.extend(header_pass.as_documents(pages))
    # What only a whole crawl can see: the same title, description or
    # canonical repeated across pages. Every rule above reads one document,
    # so this class of problem was invisible by construction.
    result.documents.extend(crosspage_pass.as_documents(pages))
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
    owned = attribute_ownership(result)
    applog.info("audit.web_done", pages=len(pages),
                documents=len(result.documents), findings=len(result.issues()),
                counts=result.counts(), platform_owned=owned)
    return result



def attribute_ownership(result) -> dict:
    """Name the platform that emitted each finding, where one did.

    Runs once per crawl, after the rules, because it needs two things that
    only exist together at the end: what the site turned out to be, and every
    finding's markup.

    Why the detection has to end here rather than in a line of the report:
    a platform's own bundles are not the site owner's to fix, and a report
    that mixes them into the same list is asking a person to triage work they
    cannot do. On `wordpress.org/news` five of the eight `serious` findings
    were core's own enqueued stylesheets.

    Returns `{platform: count}` for the summary. Nothing is removed and no
    severity is lowered - see `PLATFORM_ASSETS` for why suppression is the
    wrong answer here.
    """
    from project_profile import detect_from_markup, platform_owner

    names = [stack.name for stack in
             detect_from_markup(getattr(result, "markup_sample", "") or "").stacks]
    counts: dict = {}
    if not names:
        return counts
    for issue in result.issues():
        # The snippet is the offending element, so an address in it is the
        # address the platform wrote. The selector is a DOM path and carries
        # no provenance, which is why it is not consulted.
        owner = platform_owner(names, issue.snippet or "")
        if owner:
            issue.owner = owner
            counts[owner] = counts.get(owner, 0) + 1
    return counts

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
                  media: bool = True, repo_facts: bool = True,
                  force_medium: str | None = None) -> AccessibilityResult:
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

    `repo_facts` reads what the repository says about itself rather than
    about any file in it (`audit.repo_facts`): who the commits name as
    authors, which assistant configuration is committed, and whether a
    secrets file is sitting where the next `git add .` will take it. On by
    default for the same reason - a `.env` nobody ignores is a fact about
    this project, and a scan that walks past it to count image dimensions
    has its priorities wrong.
    """
    rules = rules if rules is not None else RuleRegistry.all_rules()
    result = AccessibilityResult(root=root, mode="repo",
                                 rules_run=[r.id for r in rules])
    for file_result in file_results:
        if file_result.error or not file_result.raw_text:
            continue
        if "<" not in file_result.raw_text:
            continue
        if _is_skipped_path(file_result.path):
            continue
        if looks_generated(file_result.raw_text):
            # A finding in a generated file is not wrong, it is unactionable:
            # the fix belongs in the generator and the file is overwritten on
            # the next build. The marker is a convention rather than a
            # technology - protobuf, GraphQL codegen, OpenAPI clients, Prisma
            # and `.d.ts` emitters all write one - so it is checked here,
            # where every stack passes through, rather than per stack.
            continue
        kind = _document_kind(file_result.path, file_result.raw_text)
        markup = file_result.raw_text
        if kind == "fragment":
            # A source file's comments are prose, and prose talks about markup:
            # `// the <img> is replaced on remount` is an element with no alt
            # to an HTML parser. Masked rather than stripped, so every line and
            # column still points where it did.
            from repo_scanner import mask_code_comments, mask_server_tags
            # Server tags first, and the order is load-bearing. A PHP block
            # may hold a `//` comment of its own:
            #
            #     <a href="..."<?php echo $aria; // phpcs:ignore ?>>
            #
            # Masking comments first blanks from `//` to end of line, which
            # takes the closing `?>>` with it. The block is then unterminated,
            # the anchor swallows everything down to the next `?>`, and a link
            # whose text sits on the following line reports as nameless.
            # Removing the whole server tag first means its comment never
            # reaches the comment masker.
            markup = mask_server_tags(markup)
            # `<?php echo esc_html($name); ?>` is a *processing instruction*
            # to the parser and carries no text, so a link or a field named by
            # the server read as nameless. On three real WordPress projects
            # this was the largest single source of false `control-name`
            # criticals.
            markup = mask_code_comments(markup, file_result.path,
                                        server_tags_masked=True)
        report = analyze_document(markup, file_result.path, rules,
                                  line_numbers=True, ai_review=ai_review,
                                  document_kind=kind,
                                  source_text=file_result.raw_text,
                                  force_medium=force_medium)
        if report.issues or report.error:
            result.documents.append(report)
    if media:
        from audit import media as media_pass

        # Appended, not merged into a document: an image is a document of
        # its own, and the rest of the pipeline - the report, the grouping,
        # the file list in the window - already works in documents.
        result.documents.extend(
            media_pass.as_documents(media_pass.scan_media(root)))
    if repo_facts:
        from audit import repo_facts as facts_pass

        facts = facts_pass.read_facts(root)
        # Blamed before the findings are turned into documents, because one
        # of those documents reports how many of them landed on lines an
        # assistant commit last touched - and that count does not exist
        # until the blame has run.
        facts_pass.blame_issues(root, result.issues(), facts)
        result.repo = facts
        result.documents.extend(facts_pass.as_documents(facts, root))
    return result
