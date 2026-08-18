"""Turns an accessibility `Issue` into something a person can act on.

Three things per finding, in the user's language:

* **What was found** — the concrete element and the concrete value.
* **Why it matters** — what actually happens to the person using the page.
  Not the number of the success criterion: "1.1.1" tells a developer nothing
  about why they should care, whereas "a screen reader announces the file
  name instead of the picture" does.
* **How to fix it** — the correction, plus the ready-made snippet where the
  markup allows one to be derived.

The criterion numbers are still carried, because an audit report is often
read against a checklist — but they sit alongside the explanation rather
than standing in for it.
"""
from __future__ import annotations

from dataclasses import dataclass

from i18n.translations import t

from .base import NEEDS_BROWSER, RuleRegistry


@dataclass
class IssueExplanation:
    title: str
    found: str
    why: str
    fix: str
    fix_snippet: str | None = None
    caveat: str = ""
    wcag: tuple = ()

    def as_text(self) -> str:
        parts = [self.title, self.found, self.why, self.fix]
        if self.fix_snippet:
            parts.append(self.fix_snippet)
        if self.caveat:
            parts.append(self.caveat)
        return "\n".join(p for p in parts if p)


def render(issue, lang: str = "uk") -> IssueExplanation:
    details = dict(issue.details or {})
    # A rule that raised is reported as itself rather than swallowed: a check
    # that silently stopped running is worse than one that failed loudly.
    if "rule_error" in details:
        return IssueExplanation(
            title=t("a11y_rule_error_title", lang, rule=issue.rule_id),
            found=details["rule_error"], why="", fix="",
        )

    stem = issue.rule_id.replace("-", "_")
    # Values are pre-formatted so a template only has to interpolate: the
    # keys differ per rule, and a missing one must not raise inside the UI.
    fields = _template_fields(details)

    # All four strings get the same values: "how to fix it" is worth far
    # more when it names the actual budget, the actual limit and the actual
    # replacement element than when it repeats the rule in the abstract.
    explanation = IssueExplanation(
        title=t(f"a11y_{stem}_title", lang, **fields),
        found=t(f"a11y_{stem}_found", lang, **fields),
        why=t(f"a11y_{stem}_why", lang, **fields),
        fix=t(f"a11y_{stem}_fix", lang, **fields),
        fix_snippet=issue.fix_snippet,
        wcag=_wcag_for(issue.rule_id),
    )
    if issue.confidence == NEEDS_BROWSER:
        explanation.caveat = t("a11y_needs_browser", lang)
    return explanation


def _template_fields(details: dict) -> dict:
    fields = {}
    for key, value in details.items():
        if isinstance(value, (list, tuple)):
            fields[key] = ", ".join(str(v) for v in value)
        else:
            fields[key] = value
    # Every template placeholder used anywhere gets a default, so a rule that
    # legitimately has nothing to say for one of them still renders.
    for key in ("src", "alt", "text", "href", "element", "id", "attribute",
                "missing", "value", "count", "rows", "tracks", "ratio",
                "required", "foreground", "background", "content", "from", "to"):
        fields.setdefault(key, "")
    return fields


def _wcag_for(rule_id: str) -> tuple:
    try:
        return RuleRegistry.create(rule_id).wcag
    except KeyError:
        return ()


def summary_line(result, lang: str = "uk") -> str:
    """One sentence over a whole run, for the status bar and report header."""
    counts = result.counts()
    return t(
        "a11y_summary", lang,
        critical=counts.get("critical", 0),
        serious=counts.get("serious", 0),
        moderate=counts.get("moderate", 0),
        minor=counts.get("minor", 0),
        documents=len(result.documents_with_issues()),
    )
