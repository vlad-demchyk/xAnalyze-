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

#: Below this many documents the *document* ratio means nothing - one file
#: with twelve missing `alt` attributes is a normal Tuesday, and one document
#: out of one is always "nearly every document". That is why a second measure
#: exists below rather than this bar simply being lowered.
_MIN_DOCUMENTS = 3

#: The single-page measure: what share of the elements a document actually
#: contains did one rule fire on. A page is not a population of documents, so
#: the population it does have is used instead - `DocumentReport.elements_checked`.
#:
#: Calibrated on both shapes rather than picked:
#:
#: * the failure this guard exists for - the focus pass on `https://www.gov.uk/`
#:   - reported 588 findings over ten pages against the 120 candidates it
#:     examines per page: **~49%** of what it looked at;
#: * the noisiest real rule on `https://www.python.org/` is `htmlcs:1_4_3` at
#:   145 findings against 833 elements: **17.4%**, and 4.3% once the undecided
#:   are out of the view.
#:
#: A quarter sits between them with room on both sides. A rule under it is
#: describing the page; a rule over it is describing itself.
_ELEMENT_SHARE = 0.25


@dataclass(frozen=True)
class Saturation:
    """One rule that fired too evenly to be describing the content."""
    rule: str
    findings: int
    documents: int
    documents_total: int
    #: How many elements the document held, when the finding is about one
    #: document rather than about a spread across many. Zero for the
    #: multi-document shape, where the population is documents.
    elements: int = 0

    @property
    def per_document(self) -> float:
        return self.findings / self.documents if self.documents else 0.0

    @property
    def element_share(self) -> float:
        return self.findings / self.elements if self.elements else 0.0

    def message(self) -> str:
        if self.elements:
            return (f"{self.rule}: {self.findings} findings on "
                    f"{self.elements} elements "
                    f"({self.element_share:.0%} of what was examined) - "
                    f"a rule firing on that share of a page is measuring "
                    f"itself, not the page")
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
        return _saturated_within_documents(documents)

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


def _saturated_within_documents(documents) -> list:
    """The same question asked of one page: what share of it did a rule take?

    This is where the guard was blind. It measured the share of *documents* a
    rule reached, so it needed at least three of them - and a single page is
    exactly where the noise is loudest, because there is nothing to compare
    against and every rule reaches "all" one document.

    The population of a page is its elements, and `elements_checked` is the
    number the static pass already counted. A document that reports no count
    is skipped rather than guessed at: dividing by an assumption would invent
    the very number the guard exists to check.
    """
    found = []
    for document in documents:
        elements = getattr(document, "elements_checked", 0) or 0
        if elements <= 0:
            continue
        # A count smaller than the number of findings is not a population.
        # Several passes report `elements_checked=1` meaning "one thing was
        # examined" - a response's headers, a site's link graph, a file's
        # provenance - and dividing by that produced "20 findings on 1
        # element (2000% of what was examined)", a sentence that is both
        # nonsense and, worse, a warning about a rule that had done nothing
        # wrong. Skipped rather than clamped: an impossible share means the
        # denominator is the wrong number, and a clamped wrong number is
        # still a wrong number wearing a plausible face.
        if len(document.issues) > elements:
            continue
        per_rule: dict = {}
        for issue in document.issues:
            per_rule[issue.rule_id] = per_rule.get(issue.rule_id, 0) + 1
        for rule, count in per_rule.items():
            if count < _PER_DOCUMENT:
                continue
            if count / elements < _ELEMENT_SHARE:
                continue
            found.append(Saturation(rule=rule, findings=count, documents=1,
                                    documents_total=len(documents),
                                    elements=elements))
    return sorted(found, key=lambda s: -s.findings)
