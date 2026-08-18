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

CATEGORIES = (ACCESSIBILITY, PERFORMANCE, SEO, BEST_PRACTICES)

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
    #: Maps a bs4 tag to a CSS-ish path. Injected rather than imported so the
    #: web and repo paths can supply their own (a repo file also wants a line
    #: number, which a live page has no notion of).
    dom_path = None
    line_of = None

    def locate(self, tag) -> tuple:
        selector = self.dom_path(tag) if self.dom_path else ""
        line = self.line_of(tag) if self.line_of else None
        return selector, line


def snippet_of(tag, limit: int = 160) -> str:
    """The opening tag, without its children.

    Deliberately not `str(tag)`: a `<div>` wrapping half the page would put
    that half into the report, and the attributes are what the finding is
    about anyway.
    """
    text = str(tag)
    closing = text.find(">")
    opening = text[:closing + 1] if closing != -1 else text
    return opening if len(opening) <= limit else opening[:limit - 1] + "…"
