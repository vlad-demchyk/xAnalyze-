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
