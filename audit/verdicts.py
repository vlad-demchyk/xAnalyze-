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

`corpus/audit_verdicts.jsonl` holds one verdict per line. Markup only, never a
client's text, cookies, tokens or personal data: a verdict is about the shape
of the markup, and the shape is all it needs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from audit.base import (
    ADVISORY, CONFIDENCE_ORDER, CRITICAL, MINOR, SERIOUS, SEVERITY_ORDER,
    RuleRegistry,
)

CORPUS = Path(__file__).resolve().parent.parent / "corpus" / "audit_verdicts.jsonl"

#: The engines a verdict can be replayed through.
STATIC = "static"
HTMLCS = "htmlcs"
ENGINES = (STATIC, HTMLCS)

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
            verdicts.append(Verdict(**record))
    return verdicts


def findings(verdict: Verdict) -> list:
    """The issues of the verdict's rule, replayed on its markup."""
    if verdict.engine == HTMLCS:
        from audit.browser import issues_from_htmlcs

        issues = issues_from_htmlcs(
            json.dumps({"messages": [verdict.message]}), verdict.url)
    else:
        from audit.engine import analyze_document

        issues = analyze_document(verdict.html, verdict.url,
                                  syntax=verdict.syntax,
                                  stacks=verdict.stacks).issues
    return [issue for issue in issues if issue.rule_id == verdict.rule]


def _full_weight(issue, rule_id: str) -> bool:
    """Reported as the rule means it, not lowered to a note."""
    try:
        rule = RuleRegistry.create(rule_id)
    except KeyError:
        # An engine's code: no declared weight to compare with, so a note is
        # what MINOR or ADVISORY says.
        return issue.severity != MINOR and issue.confidence != ADVISORY
    heavier_or_equal = (SEVERITY_ORDER.index(issue.severity)
                        <= SEVERITY_ORDER.index(rule.severity))
    as_sure = (CONFIDENCE_ORDER.index(issue.confidence)
               >= CONFIDENCE_ORDER.index(rule.confidence))
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
