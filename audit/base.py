"""Audit rules: the interface, the finding, and the registry.

This started as accessibility only and now covers four categories, because
they turned out to be the same job. A page that ships 2 MB of render-blocking
JavaScript is unusable on a slow connection for the same practical reason a
missing label is unusable with a screen reader: the person cannot do what
they came to do. And the checks overlap outright — `lang`, `<title>`, `alt`
and heading order are each simultaneously an accessibility rule and an SEO
rule. Running them as one pass over one parsed document means each is
written once and reported under the category the user is thinking in.

Same shape as `detectors/` — one interface, a registry, concrete rules that
register themselves — for the same reason: the UI, the report and the CLI
talk to the interface and never to a rule directly, so adding a check is
one class and one registration.

What is different from the text detectors, and why it matters:

**An accessibility finding is a fact, not a probability.** An `<img>` either
has an `alt` attribute or it does not. So `Issue` carries no score. It
carries a severity, which is about *consequence* — whether a person using a
screen reader is blocked or merely inconvenienced — not about how sure the
rule is.

**Every finding must say how to fix it.** A list of violated success
criteria is not useful to the person who has to change the markup. Each rule
therefore produces `details` (what it found, as data) and, wherever the
correction is derivable from the markup, a `fix_snippet` showing the element
as it should be written.

**The honest limit is recorded, not hidden.** This runs no browser: no
JavaScript executes and no styles are computed. Contrast after the cascade,
focus order, and anything that only exists after hydration are out of reach
of a static pass. Rules that can only partly check their criterion say so
via `Rule.confidence` = `NEEDS_BROWSER`, and the report prints that next to
the finding rather than implying full WCAG coverage.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

# --------------------------------------------------------------- categories
#
# What kind of problem this is, from the point of view of the person reading
# the report. A rule declares one; a finding carries it so the report can be
# grouped and filtered without asking each rule where it came from.
ACCESSIBILITY = "accessibility"
PERFORMANCE = "performance"
SEO = "seo"
BEST_PRACTICES = "best-practices"
#: What the repository exposes rather than what a page does. A `.env` sitting
#: where the next `git add .` will take it is not a best practice anyone
#: departed from - it is a credential about to be published, and filing it
#: under "best practices" would state it too quietly to act on.
SECURITY = "security"

CATEGORIES = (ACCESSIBILITY, PERFORMANCE, SEO, BEST_PRACTICES, SECURITY)

# --------------------------------------------------------------- severity
#
# Ordered by what happens to the person using the page, which is what should
# drive the order of work — not by how easy the fix is.
CRITICAL = "critical"   # blocks the task outright: unlabelled control, keyboard trap
SERIOUS = "serious"     # the content is reachable but its meaning is lost
MODERATE = "moderate"   # navigation is harder than it should be
MINOR = "minor"         # a smell; correct in some designs

SEVERITY_ORDER = (CRITICAL, SERIOUS, MODERATE, MINOR)

# ------------------------------------------------------------- confidence
EXACT = "exact"                  # the markup answers the question completely
NEEDS_BROWSER = "needs-browser"  # a static pass can only see part of this


@dataclass
class Issue:
    """One accessibility problem, at one place in one document."""
    rule_id: str
    severity: str
    #: Where it is. `selector` is a CSS-ish DOM path for a page; `line` is
    #: set instead when the source is a file on disk.
    selector: str = ""
    line: int | None = None
    #: The offending markup, truncated — enough to recognise, not to flood.
    snippet: str = ""
    #: Rule-specific data, rendered into a sentence in the user's language
    #: by `a11y.explanations`. Data rather than prose for the same reason as
    #: `TextSpan.details`: the UI language can change after a scan.
    details: dict = field(default_factory=dict)
    #: The element as it should be written, where that follows from the
    #: markup. None when the fix needs a human decision (what the alt text
    #: should actually say, which heading level is correct).
    fix_snippet: str | None = None
    confidence: str = EXACT
    #: Document this came from: a URL in web mode, a path in repo mode.
    source: str = ""
    #: Which of the four audit categories this belongs to.
    category: str = ACCESSIBILITY
    #: Which engine produced it: "static" (our own rules), "axe",
    #: "htmlcs", "browser" (a measurement), or "ai". Kept so the report can
    #: say where a finding came from and so two engines finding the same
    #: thing can be collapsed into one row.
    engine: str = "static"

    @property
    def key(self) -> tuple:
        """Identity for de-duplication across a crawl: the same rule firing
        on the same element of the same document is one problem, even when
        the crawler reached that page twice."""
        return (self.source, self.rule_id, self.selector or self.snippet, self.line)


class Rule(ABC):
    """One check, run over one parsed document."""

    #: stable machine name, used as the i18n key stem and in --json output
    id: str = "base"
    category: str = ACCESSIBILITY
    severity: str = MODERATE
    confidence: str = EXACT
    #: WCAG success criteria this contributes to. Deliberately "contributes
    #: to": a static check almost never covers a criterion in full, and
    #: claiming otherwise is how tools end up promising compliance.
    wcag: tuple = ()
    #: True when the check only means something for a whole document: a
    #: doctype, a title, exactly one h1. A component file holds a fragment of
    #: a page, so running these over it reports the absence of things that
    #: were never supposed to be there — which is how a repo report fills up
    #: with findings nobody can act on.
    page_level: bool = False
    #: True when a "missing" verdict depends on a stylesheet the parser never
    #: sees. `<img>` with no `width`/`height` still might have both reserved
    #: by a CSS class or a sibling `.module.css` file - true on a live page,
    #: which is why `--browser` catches the real absence there. A repo
    #: fragment carries none of that: its own file is all a rule ever sees,
    #: and treating an unknown as a violation is indistinguishable from
    #: treating an unstyled `<div>` as one. Confirmed against
    #: `~/repositories/xformat`: every one of 48 `seo-image-dimensions`
    #: findings on `.tsx` fragments had no `width`/`height` *and* no
    #: `className`/`style` visible in the snippet either - not a bound
    #: expression to read, evidence genuinely absent rather than hidden.
    needs_external_css: bool = False

    @abstractmethod
    def check(self, document, context) -> list:
        """Return `Issue`s. `document` is a BeautifulSoup tree; `context`
        carries the source name and a `dom_path` helper so rules don't each
        reimplement one."""
        raise NotImplementedError


class RuleRegistry:
    _rules: dict = {}

    @classmethod
    def register(cls, rule_cls) -> None:
        cls._rules[rule_cls.id] = rule_cls

    @classmethod
    def available(cls) -> list:
        return sorted(cls._rules)

    @classmethod
    def all_rules(cls, categories=None) -> list:
        rules = [cls._rules[name]() for name in sorted(cls._rules)]
        if categories is None:
            return rules
        wanted = set(categories)
        return [r for r in rules if r.category in wanted]

    @classmethod
    def by_category(cls) -> dict:
        grouped: dict = {}
        for rule in cls.all_rules():
            grouped.setdefault(rule.category, []).append(rule.id)
        return grouped

    @classmethod
    def create(cls, rule_id: str):
        return cls._rules[rule_id]()


@dataclass
class RuleContext:
    """What a rule needs to know about where it is running."""
    source: str = ""
    #: "page" for a served page or a self-contained file, "fragment" for a
    #: source file that merely contains markup. Page-level rules are skipped
    #: on a fragment; see `Rule.page_level`.
    document_kind: str = "page"
    #: Maps a bs4 tag to a CSS-ish path. Injected rather than imported so the
    #: web and repo paths can supply their own (a repo file also wants a line
    #: number, which a live page has no notion of).
    dom_path = None
    line_of = None

    def locate(self, tag) -> tuple:
        selector = self.dom_path(tag) if self.dom_path else ""
        line = self.line_of(tag) if self.line_of else None
        return selector, line


def is_binding(value) -> str:
    """Is this attribute value an unevaluated template expression?

    `onClick={handleClose}` in JSX, `:href="url"` in Vue, `{#if}` in Svelte:
    an HTML parser reads these as ordinary attribute values, so a rule sees
    the literal text `{handleClose}` where the browser will see a function
    reference — or, for an aria-label, a string the parser cannot know.
    Judging the placeholder as if it were the final value is what turns every
    React handler into an "inline event handler" finding.

    Returns the kind of binding for the report, or "" when the value is a
    plain literal.
    """
    text = (value if isinstance(value, str) else " ".join(value or [])).strip()
    if not text:
        return ""
    if text.startswith("{{") and text.endswith("}}"):
        return "mustache"       # Vue, Angular, Handlebars
    if text.startswith("{"):
        return "expression"     # JSX, Svelte
    if text.startswith(("<%", "${")):
        return "template"       # ERB/EJS, template literal
    return ""


#: Where a parsed document remembers the text it was parsed from, so a
#: snippet can be quoted from the source instead of re-serialised. Attached to
#: the soup by `analyze_document`; absent for a document that has no source
#: text of its own, such as a DOM read back out of a browser.
SOURCE_ATTR = "_xa_source"
LINE_STARTS_ATTR = "_xa_line_starts"


def remember_source(document, markup: str) -> None:
    """Let `snippet_of` quote this document rather than re-print it."""
    starts = [0]
    for index, char in enumerate(markup):
        if char == "\n":
            starts.append(index + 1)
    setattr(document, SOURCE_ATTR, markup)
    setattr(document, LINE_STARTS_ATTR, starts)


def _source_of(tag):
    """The markup this tag was parsed from, and its line offsets."""
    node = tag
    while node is not None:
        markup = getattr(node, SOURCE_ATTR, None)
        if markup is not None:
            return markup, getattr(node, LINE_STARTS_ATTR, None)
        node = getattr(node, "parent", None)
    return None, None


def _open_tag_end(markup: str, start: int) -> int:
    """Where the opening tag that begins at `start` ends.

    Not `markup.find(">")`: a JSX attribute can contain one
    (`title={a > b ? "x" : "y"}`), and so can a quoted value. Quotes and brace
    depth are tracked for exactly that reason.
    """
    quote = ""
    depth = 0
    for index in range(start, len(markup)):
        char = markup[index]
        if quote:
            if char == quote:
                quote = ""
            continue
        if char in "\"'":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth = max(0, depth - 1)
        elif char == ">" and depth == 0:
            return index + 1
    return -1


def snippet_of(tag, limit: int = 160) -> str:
    """The opening tag as it is written in the file.

    Deliberately not `str(tag)` when the source is known. An HTML parser is
    the only practical way to run these rules over a JSX or Vue file, but it
    re-prints what it parsed: `className` comes back as `classname`, and an
    expression attribute (`alt={photo.caption}`) comes back as the debris
    `alt="{photo.caption}"` or as empty `="" ?=""` pairs. A developer reading
    the report then cannot find the line, because that text is not in their
    file. So the snippet is cut out of the original markup by the position the
    parser recorded, and `str(tag)` remains the fallback for a document with
    no source text - a DOM read back out of a browser, where the serialisation
    *is* the truth.

    A `<div>` wrapping half the page is still cut at its opening tag: the
    attributes are what the finding is about.
    """
    markup, line_starts = _source_of(tag)
    line = getattr(tag, "sourceline", None)
    column = getattr(tag, "sourcepos", None)
    if markup and line_starts and line and column is not None:
        index = int(line) - 1
        if 0 <= index < len(line_starts):
            start = line_starts[index] + int(column)
            if 0 <= start < len(markup) and markup[start] == "<":
                end = _open_tag_end(markup, start)
                if end != -1:
                    return _clip(markup[start:end], limit)

    text = str(tag)
    closing = text.find(">")
    return _clip(text[:closing + 1] if closing != -1 else text, limit)


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1] + "…"
