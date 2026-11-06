"""Checked verdicts on audit findings, and what the rules do with them (T-1963).

The text detectors have a corpus and a measured precision; the site audit had
neither. Every rule written for it produced false positives on the first
real crawl, and each time a person found them by reading the output. This is
the record of what a person decided, kept as data so the rules can be held to
it:

* a **true** verdict is a finding that must be reported at the rule's own
  weight - its severity and its confidence, not lower;
* a **false** verdict is a shape that must not be: either the rule stays
  silent, or it lowers itself to a note (a lighter severity or confidence),
  which is how several fixes chose to say "a person should look" rather than
  "this is wrong".

`corpus/audit/verdicts.jsonl` holds one verdict per line. Markup only, never a
client's text, cookies, tokens or personal data: a verdict is about the shape
of the markup, and the shape is all it needs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from audit.base import (
    ADVISORY, CONFIDENCE_ORDER, CRITICAL, EXACT, MINOR, MODERATE, SERIOUS,
    SEVERITY_ORDER, RuleRegistry,
)

CORPUS = Path(__file__).resolve().parent.parent / "corpus" / "audit" / "verdicts.jsonl"

#: The engines a verdict can be replayed through.
STATIC = "static"
HTMLCS = "htmlcs"
AXE = "axe"
#: Several pages of one crawl, for the rules that compare pages.
PAGES = "pages"
ENGINES = (STATIC, HTMLCS, AXE, PAGES)

#: The weight the cross-page rules report at. They are not `Rule` classes,
#: so their weight is written where they build the issue; this is that
#: weight, so a lowered one can be told from the rule's normal answer.
_CRAWL_WEIGHTS = {
    "link-target-differs-across-translations": (MODERATE, ADVISORY),
    "seo-hreflang-not-reciprocal": (MODERATE, EXACT),
    "seo-untranslated-content": (MODERATE, EXACT),
    "seo-slug-not-translated": (MINOR, EXACT),
    "seo-duplicate-title": (MODERATE, EXACT),
    "seo-duplicate-canonical": (MODERATE, EXACT),
    "seo-duplicate-description": (MINOR, EXACT),
}

_REQUIRED = ("id", "rule", "engine", "verdict", "reason", "source", "date")


@dataclass(frozen=True)
class Verdict:
    id: str
    rule: str
    engine: str
    #: True: a real defect the rule must report. False: a false positive.
    verdict: bool
    reason: str
    source: str
    date: str
    html: str = ""
    url: str = "https://example.test/"
    #: "html" or "jsx": which parser the markup needs.
    syntax: str = "html"
    #: Detected stacks, for rules that only run on one (WordPress).
    stacks: tuple = ()
    #: An HTML_CodeSniffer message, for `engine == "htmlcs"`.
    message: dict = field(default_factory=dict)
    #: An axe result (`violations`, `incomplete`), for `engine == "axe"`.
    payload: dict = field(default_factory=dict)
    #: `[{"url": ..., "html": ...}, ...]`, for `engine == "pages"`.
    pages: tuple = ()


def load(path: Path = CORPUS) -> list:
    """Every verdict in the file. Raises on a malformed or duplicate line:
    a corpus that half-loads measures half of what it claims."""
    verdicts = []
    seen = set()
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            record = json.loads(line)
            missing = [key for key in _REQUIRED if key not in record]
            if missing:
                raise ValueError(f"line {number}: missing {', '.join(missing)}")
            if record["engine"] not in ENGINES:
                raise ValueError(f"line {number}: unknown engine {record['engine']!r}")
            if not isinstance(record["verdict"], bool):
                raise ValueError(f"line {number}: verdict must be true or false")
            if record["id"] in seen:
                raise ValueError(f"line {number}: duplicate id {record['id']!r}")
            seen.add(record["id"])
            record["stacks"] = tuple(record.get("stacks", ()))
            record["pages"] = tuple(record.get("pages", ()))
            verdicts.append(Verdict(**record))
    return verdicts


def findings(verdict: Verdict) -> list:
    """The issues of the verdict's rule, replayed on its markup."""
    if verdict.engine == HTMLCS:
        from audit.browser import issues_from_htmlcs

        issues = issues_from_htmlcs(
            json.dumps({"messages": [verdict.message]}), verdict.url)
    elif verdict.engine == AXE:
        from audit.browser import issues_from_axe

        issues = issues_from_axe(json.dumps(verdict.payload), verdict.url)
    elif verdict.engine == PAGES:
        from types import SimpleNamespace

        from audit import crosspage

        issues = crosspage.issues_for([
            SimpleNamespace(url=page["url"], raw_html=page["html"],
                            error=None, diagnostics=None)
            for page in verdict.pages])
    else:
        from audit.engine import _document_kind, _mask_for_audit, analyze_document

        # The way a file in a folder audit is read, masks and all: a verdict
        # replayed through a shorter path would measure a parser nobody runs.
        kind = (_document_kind(verdict.url, verdict.html)
                if "://" not in verdict.url else "page")
        markup = (_mask_for_audit(verdict.html, verdict.url)
                  if kind == "fragment" else verdict.html)
        issues = analyze_document(markup, verdict.url, document_kind=kind,
                                  source_text=verdict.html,
                                  syntax=verdict.syntax,
                                  stacks=verdict.stacks).issues
    return [issue for issue in issues if issue.rule_id == verdict.rule]


def _full_weight(issue, rule_id: str) -> bool:
    """Reported as the rule means it, not lowered to a note."""
    if rule_id in _CRAWL_WEIGHTS:
        severity, confidence = _CRAWL_WEIGHTS[rule_id]
    else:
        try:
            rule = RuleRegistry.create(rule_id)
        except KeyError:
            # An engine's own code (axe, HTML_CodeSniffer). The engine sets
            # the severity; what this tool does to an answer it doubts is
            # lower the confidence - an `incomplete`, an undetermined
            # message, a name the collector found - so that is the test.
            return issue.confidence == EXACT
        severity, confidence = rule.severity, rule.confidence
    heavier_or_equal = (SEVERITY_ORDER.index(issue.severity)
                        <= SEVERITY_ORDER.index(severity))
    as_sure = (CONFIDENCE_ORDER.index(issue.confidence)
               >= CONFIDENCE_ORDER.index(confidence))
    return heavier_or_equal and as_sure


def reported(verdict: Verdict) -> bool:
    """Does the rule report this markup at its own weight?"""
    return any(_full_weight(issue, verdict.rule) for issue in findings(verdict))


def holds(verdict: Verdict) -> bool:
    """The rule agrees with the person's verdict."""
    return reported(verdict) == verdict.verdict


def coverage(verdicts) -> dict:
    """`rule -> {"true": n, "false": n}` over the corpus."""
    out: dict = {}
    for verdict in verdicts:
        counts = out.setdefault(verdict.rule, {"true": 0, "false": 0})
        counts["true" if verdict.verdict else "false"] += 1
    return out


def weighty_rules() -> list:
    """Static rules that report as serious or critical: the ones a wrong
    answer costs most, and the ones the corpus must cover both ways."""
    import audit.engine  # noqa: F401 - registers every rule

    return sorted(rule.id for rule in RuleRegistry.all_rules()
                  if rule.severity in (CRITICAL, SERIOUS))
