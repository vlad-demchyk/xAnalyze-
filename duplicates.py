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

import re

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

    Generated identifiers inside the markup are masked first, and that is not
    cosmetic. A theme that stamps a unique id into a component - WordPress
    writes `aria-controls="page-toc-panel-6a8c2c05ce8bd"` - produces markup
    that differs on every page while describing one bug in one template. On a
    live ten-page crawl that turned one broken TOC toggle into ten separate
    critical findings, which is the same inflation grouping exists to remove,
    wearing a different disguise.

    Masked narrowly on purpose: long hex runs, UUIDs and long digit runs are
    machine-made, and anything shorter is likely to be meaningful (`h2`,
    `col-6`, `id="nav"`). Over-masking would merge findings that really are
    different, and a wrongly merged problem hides a real one.
    """
    snippet = mask_generated_ids(
        " ".join((getattr(issue, "snippet", "") or "").split()))
    return (
        getattr(issue, "rule_id", ""),
        getattr(issue, "category", ""),
        getattr(issue, "severity", ""),
        snippet or (getattr(issue, "selector", "") or ""),
    )


#: A UUID, first: it contains hex runs that the next pattern would otherwise
#: chew up piecemeal, leaving the dashes behind as false structure.
_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
#: Eight hex characters or more. Short enough to catch a theme's suffix,
#: long enough that ordinary words and class names do not qualify.
_HEXRUN_RE = re.compile(r"\b[0-9a-f]{8,}\b", re.I)
#: Four digits or more: a timestamp, a post id, a counter. Three would catch
#: `col-3` and every year in a copyright line.
_DIGITRUN_RE = re.compile(r"\d{4,}")


def mask_generated_ids(text: str) -> str:
    """Replace machine-generated identifiers with `#`.

    Exported because the report, the GUI and the tests all have to agree on
    what "the same markup" means, and a second copy of these three patterns
    is how they would stop agreeing.
    """
    if not text:
        return text
    text = _UUID_RE.sub("#", text)
    text = _HEXRUN_RE.sub("#", text)
    return _DIGITRUN_RE.sub("#", text)


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


# ------------------------------------------------------- text blocks
#
# One step earlier than everything above. The functions before this group
# findings *after* they were produced; this one stops the same passage being
# read twice in the first place.
#
# A crawl of ten pages produced 573 blocks and 236 distinct texts: a header
# and a footer appear on every page, so `Tel. +39 0432 924815` was read 26
# times. The offline pass paid for that in wasted local work and the judge
# paid for it in network round trips - on the Claude Code route each one is a
# process start, so the waste was minutes and real money spent asking the
# same question of the same string.


def block_identity(block) -> tuple:
    """What makes two extracted passages the same passage.

    The text, normalised, and the language it was taken to be. The language
    belongs in the identity because the detectors genuinely answer
    differently for it - the same string read as Italian and as English is
    two questions, and collapsing them would silently pick one answer for
    both.

    Machine-generated identifiers are masked, so a menu that renders with a
    fresh uuid on every page is still one passage. Same reasoning, and the
    same function, as `issue_identity`.
    """
    text = mask_generated_ids(" ".join((getattr(block, "text", "") or "").split()))
    return (text, getattr(block, "language_hint", None) or "")


def distinct_blocks(blocks: list) -> list:
    """`[(representative, [every block with that identity])]`, in arrival order.

    The representative is the first occurrence, and it is the one handed to a
    detector. Every occurrence is carried alongside because each is a real
    place on a real page that a fix has to visit: this changes what is
    *asked*, never what is *reported*.
    """
    order: list = []
    seen: dict = {}
    for block in blocks:
        key = block_identity(block)
        if key in seen:
            seen[key].append(block)
            continue
        group = [block]
        seen[key] = group
        order.append((block, group))
    return order
