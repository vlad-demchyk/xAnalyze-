"""A rule that fires on nearly everything is measuring the harness.

This is the check that would have caught, in one run and without a person
reading a report, every large false-positive class this tool has shipped:

* `focus-not-visible` reported 588 serious findings across ten pages of
  `https://www.gov.uk/` - one for very nearly every focusable element it
  examined - because a document that does not itself have focus never matches
  `:focus`, so no computed style ever changed.
* `focus-outside-viewport` reported the ordinary GOV.UK footer, 151 links,
  as content outside the viewport, because it was comparing against page
  length.
* `control-name` reported 455 criticals in one WordPress project, because
  `<?php echo esc_html($name); ?>` carries no text to an HTML parser.

Each looks different in the code and identical in the numbers: **the rule
fired on almost every candidate it had, on almost every document.** A real
defect is uneven - some pages have it, some do not, some elements are wrong
and most are right. Saturation is the shape of a broken measurement.

What this does *not* do is drop the findings. A saturated rule is sometimes
right - a site really can have removed every focus ring - and silently
discarding it would trade a false positive for a blind spot, which is the
worse of the two. It says so, loudly, next to the number.
"""
from __future__ import annotations

from dataclasses import dataclass

#: A rule has to fire this often, per document, before the shape is worth
#: mentioning. Set from what the real failures looked like: the focus pass
#: averaged 59 findings per page on GOV.UK, `control-name` 2.8 per file
#: across 164 files in xFormat. A rule reaching double figures on the average
#: document is not describing a defect a person can act on.
_PER_DOCUMENT = 10.0

#: And it has to do it nearly everywhere. A rule that fires 40 times on one
#: page of a hundred is a real problem on one page.
_DOCUMENT_SHARE = 0.9

#: Below this many documents the ratio means nothing - one file with twelve
#: missing `alt` attributes is a normal Tuesday.
_MIN_DOCUMENTS = 3


@dataclass(frozen=True)
class Saturation:
    """One rule that fired too evenly to be describing the content."""
    rule: str
    findings: int
    documents: int
    documents_total: int

    @property
    def per_document(self) -> float:
        return self.findings / self.documents if self.documents else 0.0

    def message(self) -> str:
        return (f"{self.rule}: {self.findings} findings across "
                f"{self.documents} of {self.documents_total} documents "
                f"({self.per_document:.0f} per document). A rule that fires "
                f"on nearly everything it examines is usually measuring the "
                f"scan, not the page - read a few before acting on the count.")


def saturated_rules(result) -> list:
    """Rules whose findings are spread too evenly to be a real defect.

    Returns worst first. Empty is the normal answer, and an empty answer is
    not a guarantee - this catches the shape those failures had, not every
    way a check can be wrong.
    """
    documents = [d for d in getattr(result, "documents", []) if not d.error]
    total = len(documents)
    if total < _MIN_DOCUMENTS:
        return []

    per_rule: dict = {}
    for document in documents:
        seen_here = set()
        for issue in document.issues:
            rule = issue.rule_id
            entry = per_rule.setdefault(rule, {"findings": 0, "documents": 0})
            entry["findings"] += 1
            if rule not in seen_here:
                seen_here.add(rule)
                entry["documents"] += 1

    found = []
    for rule, entry in per_rule.items():
        if entry["documents"] / total < _DOCUMENT_SHARE:
            continue
        if entry["findings"] / entry["documents"] < _PER_DOCUMENT:
            continue
        found.append(Saturation(rule=rule, findings=entry["findings"],
                                documents=entry["documents"],
                                documents_total=total))
    return sorted(found, key=lambda s: -s.findings)
