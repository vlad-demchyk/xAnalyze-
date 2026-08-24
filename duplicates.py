"""Grouping findings that are the same finding in more than one file.

A project holds copies of its own code: the source, the compiled output, the
bundle, the deployed folder. One en dash in a Cherry Bank address arrived
four times from four such copies, and reading a list where three of every
four rows say the same thing is how a list stops being read.

The obvious fix - exclude directories called `lib/` and `release/` - was
tried and rejected: `src/lib/` is *source* in most React and Svelte
projects, and the exclusion blinded the scanner to 67 real findings in
xFormat the moment it was applied. A name cannot tell a build output from a
source directory. Identical text at identical fault can, and needs no
guessing.

**Grouping is presentational, and nothing is dropped.** Every finding stays
in the list with its own file and offset, because every copy is a real file
that a fix has to edit - collapsing them into one would mean writing the
correction into one file and leaving three stale. What grouping changes is
what the reader is shown first: one row, and a note that it also appears in
N other places.
"""
from __future__ import annotations

#: What makes two findings in two files the same finding. The flagged text
#: and what it becomes: the offsets differ between copies (the compiled file
#: has different line numbers), and the file is the thing that varies by
#: definition, so neither can be part of the identity.
def identity(finding: dict) -> tuple:
    return (
        finding.get("text", ""),
        finding.get("replacement"),
        finding.get("source", ""),
        finding.get("explanation", ""),
    )


def group(findings: list) -> list:
    """Return `[(first, others)]`, in the order the findings arrived.

    `first` is the finding to show; `others` are the identical ones in other
    files. A finding with no twin comes back with an empty `others`, so a
    caller can render every case through the same branch.
    """
    order: list = []
    seen: dict = {}
    for finding in findings:
        key = identity(finding)
        if key in seen:
            seen[key][1].append(finding)
            continue
        entry = (finding, [])
        seen[key] = entry
        order.append(entry)
    return order


def copies_of(finding: dict, others: list) -> list:
    """The other files the same finding sits in, as plain paths."""
    return [other.get("file", "") for other in others]


# ------------------------------------------------------- audit issues
#
# The same reasoning, one document type further out. A crawl of thirty pages
# that share a header reports the header's unlabelled search field thirty
# times, and a missing meta description once per page - the count says
# "thirty problems" when there is one problem and thirty places. Reports and
# lists therefore group on what the problem *is* and carry the places with
# it, rather than repeating the whole finding per place.


def issue_identity(issue) -> tuple:
    """What makes two audit findings the same problem.

    The rule that fired, and the element it fired on. `source` is excluded
    by definition - being in more than one document is what makes this a
    group - and so is `line`, since the same shared markup sits at a
    different line in every page that includes it.

    The element is identified by its markup rather than by its selector: a
    selector is a position (`body > header:nth-child(1) > img`) and shifts
    with anything the page renders above it, so two copies of one header
    image would look like two different problems. The markup is the same
    string in both.
    """
    snippet = " ".join((getattr(issue, "snippet", "") or "").split())
    return (
        getattr(issue, "rule_id", ""),
        getattr(issue, "category", ""),
        getattr(issue, "severity", ""),
        snippet or (getattr(issue, "selector", "") or ""),
    )


def group_issues(issues: list) -> list:
    """`[(first, others)]` for audit issues, in arrival order.

    Same contract as `group`: nothing is dropped, and a finding with no twin
    comes back with an empty `others`, so one branch renders every case.
    """
    order: list = []
    seen: dict = {}
    for issue in issues:
        key = issue_identity(issue)
        if key in seen:
            seen[key][1].append(issue)
            continue
        entry = (issue, [])
        seen[key] = entry
        order.append(entry)
    return order


def places_of(issue, others: list) -> list:
    """Every document the grouped problem was found in, first one included.

    Deduplicated and in arrival order: a page reached twice by the crawl, or
    two findings collapsed within one document, must not make the list say
    the same address twice.
    """
    places: list = []
    for candidate in [issue] + list(others):
        where = getattr(candidate, "source", "") or ""
        line = getattr(candidate, "line", None)
        label = f"{where}:{line}" if line else where
        if label and label not in places:
            places.append(label)
    return places
