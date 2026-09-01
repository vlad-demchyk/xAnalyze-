"""What went wrong, in words, with the evidence and what to do next.

A run can end badly in more than one way, and the ways are not
interchangeable. A server refusing seven of twelve addresses, a browser
giving up on one page, a crawl stopping at its own page limit and a scan
raising an exception are four different pieces of news, and only the last
one is a bug. Before this the window had one answer for all of them - a
modal with `str(exception)` in it and an empty title bar - and three of the
four never reached it at all: a page that returned 429 was recorded in
`PageDiagnostics` and then never mentioned, so a run that read five pages
out of twelve reported "done" and let a clean result stand for a site
nobody had read.

So each diagnosis carries four things (artboard 3m):

* a **title** in plain words, not the exception;
* a **body** saying what it means for the result, because that is the part
  a person is actually deciding on;
* the **evidence** it was derived from - status codes, counts, limits - so
  the reader can disagree with the diagnosis rather than having to trust it;
* the **moves** that follow, and only the ones that are real.

This module is deliberately Qt-free. The window renders it now and the TUI
is meant to render the same thing later, and the one thing that must not
happen is two implementations of "what does 429 on seven pages mean".

**An unrecognised failure is not diagnosed.** `diagnose_failure` returns the
message verbatim under a plain heading rather than reaching for the nearest
rule: a confident wrong explanation costs more than no explanation, because
it sends someone to fix the wrong thing.
"""
from __future__ import annotations

from dataclasses import dataclass, field

#: The kinds, which are also the translation-key stems. Each one is a
#: different piece of news, which is the whole reason they are separate.
BLOCKED = "blocked"
UNREACHABLE = "unreachable"
RENDER_FAILED = "render_failed"
TRUNCATED = "truncated"
MEDIA_UNCHECKED = "media_unchecked"
#: What was audited was the door, not the site. Not a failure of the run and
#: not a finding about the page: it is the reason the findings in the report
#: are about a login form. See `audit.authwall`.
AUTH_WALL = "auth_wall"
AUTH_WALL_WHOLE = "auth_wall_whole"
SATURATED_RULE = "saturated_rule"
UNKNOWN_FAILURE = "unknown_failure"

#: Said *before* a run rather than after it, and about depth rather than
#: failure: what this run is not going to reach, and which switch reaches it.
#: The CLI has printed these since `cli_impl/prerun.py`; the window said
#: nothing at all, so a person there could not know the same tool would have
#: answered more if asked differently.
MISSED_REPO = "missed_repo"
MISSED_DEVSERVER = "missed_devserver"
MISSED_BROWSER = "missed_browser"
MISSED_BREAKPOINTS = "missed_breakpoints"

#: What a diagnosis offers. Names rather than callables: this module knows
#: which moves make sense, and the window knows how to perform them.
RETRY = "retry"
RAISE_LIMIT = "raise_limit"
DISMISS = "dismiss"
#: The moves a missed-depth notice offers: point at the checkout behind the
#: site, and audit every width rather than the desktop one.
PAIR_REPO = "pair_repo"
ALL_BREAKPOINTS = "all_breakpoints"

#: Statuses that mean "the server refused", not "the page is empty". Kept in
#: step with `crawler._BLOCKED_STATUSES`, which decides the same thing one
#: page at a time.
REFUSING_STATUSES = {401, 403, 405, 429}

#: How many addresses a diagnosis names before it says "+N". Enough to
#: recognise the pattern, short enough to stay one line.
_NAMED = 3


@dataclass
class Diagnosis:
    """One thing that went wrong, and what follows from it."""
    kind: str
    #: Values for the sentence, interpolated by the caller's `t()`.
    fields: dict = field(default_factory=dict)
    #: The measurements it was derived from, already a string. Not
    #: translated, and it must not contain prose: what goes here is machine
    #: output - status codes, addresses, an exception's own words - which is
    #: what a reader checks the diagnosis against.
    evidence: str = ""
    #: When the evidence needs a word of mine rather than a machine's, it
    #: goes through the translation table like everything else I wrote. A
    #: label I authored sitting untranslated in a Ukrainian window is not
    #: "raw data", it is an untranslated string.
    evidence_key: str = ""
    #: Moves, in the order they should be offered. May be empty - a server
    #: refusing requests has no in-app answer, and inventing a button for it
    #: would be a control that exists to disappoint.
    actions: tuple = ()

    @property
    def title_key(self) -> str:
        return f"diagnosis_{self.kind}_title"

    @property
    def body_key(self) -> str:
        return f"diagnosis_{self.kind}_body"


def _short(url: str) -> str:
    """The path, which is what tells two addresses of one site apart."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else "")


def _listed(urls: list) -> str:
    named = ", ".join(_short(url) for url in urls[:_NAMED])
    extra = len(urls) - _NAMED
    return f"{named}, +{extra}" if extra > 0 else named


def diagnose_result(result) -> list:
    """Everything worth saying about a run that finished.

    Ordered worst first: a site that refused most of its addresses is a
    different conversation from one page that would not render, and the
    order is what says so when both happened.
    """
    pages = list(getattr(result, "pages", ()) or ())
    out = []

    refused = [page for page in pages
               if getattr(page.diagnostics, "status_code", None)
               in REFUSING_STATUSES]
    if refused:
        codes = sorted({page.diagnostics.status_code for page in refused})
        out.append(Diagnosis(
            BLOCKED,
            fields={"refused": len(refused), "total": len(pages)},
            evidence=" · ".join([
                ", ".join(str(code) for code in codes),
                _listed([page.url for page in refused])]),
            # No "slower mode": there is no rate setting to turn down, and a
            # button that leads nowhere is worse than none. Retrying is real
            # - a rate limit passes.
            actions=(RETRY,)))

    unreachable = [page for page in pages
                   if page.error and getattr(page.diagnostics, "status_code", None)
                   not in REFUSING_STATUSES]
    if unreachable:
        out.append(Diagnosis(
            UNREACHABLE,
            fields={"count": len(unreachable), "total": len(pages)},
            evidence=" · ".join([
                _listed([page.url for page in unreachable]),
                unreachable[0].error or ""]).strip(" ·"),
            actions=(RETRY,)))

    unrendered = [page for page in pages
                  if getattr(page.diagnostics, "render_error", "")]
    if unrendered:
        out.append(Diagnosis(
            RENDER_FAILED,
            fields={"count": len(unrendered), "total": len(pages)},
            evidence=" · ".join([
                _listed([page.url for page in unrendered]),
                unrendered[0].diagnostics.render_error]),
            actions=(RETRY,)))

    crawl = getattr(result, "crawl", None)
    if crawl is not None and crawl.truncated:
        # The number is a floor, not a total: the pages never fetched would
        # have contributed links of their own, so "at least" is the only
        # honest word for it.
        out.append(Diagnosis(
            TRUNCATED,
            fields={"read": crawl.pages_read, "at_least": crawl.at_least,
                    "limit": crawl.limit},
            evidence_key="diagnosis_truncated_evidence",
            actions=(RAISE_LIMIT,)))
    return out


def diagnose_audit(result) -> list:
    """What an audit could not look at.

    Only one thing so far, and it is the media pass. Reading an image's
    provenance means downloading it, so the pass runs under a budget - and
    an image nobody fetched has not come back clean, it has not come back.
    Reporting those two the same way is the one thing this whole family of
    checks must not do: the value of a provenance reader is entirely in the
    difference between "looked and found nothing" and "did not look".
    """
    scan = getattr(result, "media", None)
    if scan is None or not getattr(scan, "unchecked", 0):
        return []
    return [Diagnosis(
        MEDIA_UNCHECKED,
        fields={"unchecked": scan.unchecked, "checked": scan.checked,
                "found": scan.found},
        evidence_key="diagnosis_media_unchecked_evidence",
        actions=())]


def diagnose_auth_wall(result) -> list:
    """The login walls a crawl ran into, as one notice per crawl.

    One notice and not one per address, because a wall answering on forty
    addresses is one wall - and the count is the part worth reading, since
    those forty pages were not audited. When *everything* the run read was a
    wall, that is said separately and more plainly: a clean summary over
    nothing but login forms is the most misleading output this tool has.
    """
    report = getattr(result, "auth", None)
    if report is None or not report.blocked:
        return []
    signals = report.by_signal()
    kinds = ", ".join(sorted(signals))
    evidence = "; ".join(
        f"{signal} · " + ", ".join(_short(wall.url) for wall in walls[:_NAMED])
        + (f", +{len(walls) - _NAMED}" if len(walls) > _NAMED else "")
        for signal, walls in sorted(signals.items()))
    kind = AUTH_WALL_WHOLE if report.whole_site else AUTH_WALL
    return [Diagnosis(
        kind,
        fields={"blocked": report.blocked, "pages": report.pages_read,
                "signals": kinds},
        evidence=evidence,
        actions=())]


def diagnose_saturation(result) -> list:
    """Rules that fired on so much of the page that they are measuring the
    harness rather than the content.

    `audit.saturation` has answered this since the focus pass reported 588
    findings over ten pages of GOV.UK, and the answer went to `stderr` - so
    it reached whoever ran the CLI and nobody who works in the window, which
    is the surface where a saturated rule does the most damage: it fills the
    list a person is reading and pushes everything else off the bottom.
    """
    from audit.saturation import saturated_rules

    return [Diagnosis(
        SATURATED_RULE,
        fields={"rule": item.rule, "findings": item.findings,
                "elements": item.elements or item.documents},
        evidence=item.message(),
        actions=())
        for item in saturated_rules(result)]


#: Which notice each `cli_impl.prerun` code becomes, and what it offers.
#: `devserver` and `browser` carry no move: starting a dev server is already
#: a button of its own on a folder run, and "you asked for no browser" is
#: answered by not asking for that.
_MISSED = {
    "repo": (MISSED_REPO, (PAIR_REPO,)),
    "devserver": (MISSED_DEVSERVER, ()),
    "browser": (MISSED_BROWSER, ()),
    "breakpoints": (MISSED_BREAKPOINTS, (ALL_BREAKPOINTS,)),
}


def diagnose_missed_depth(items) -> list:
    """`[(code, fields)]` from `cli_impl.prerun.missed` as notices.

    The translation happens here rather than in `prerun` because `prerun`
    writes English lines with flag names in them - the right output for a
    terminal and the wrong one for a window, where there is no flag to type
    and the interface may not be in English.
    """
    out = []
    for code, fields in items or ():
        entry = _MISSED.get(code)
        if entry is None:
            continue
        kind, actions = entry
        out.append(Diagnosis(kind, fields=dict(fields), actions=actions))
    return out


def diagnose_failure(message: str) -> Diagnosis:
    """A run that raised, as something a person can act on.

    Only one kind so far, and it is the honest one: the message itself,
    under a heading that says a run stopped. Matching an exception string
    against a table of guesses is how a tool tells someone confidently that
    their network is down when their certificate expired - and a wrong
    diagnosis costs more than none, because it sends them to fix the wrong
    thing. Rules are worth adding here only where the signal is
    unambiguous, and each one should arrive with the failure that proves it.
    """
    return Diagnosis(UNKNOWN_FAILURE, evidence=(message or "").strip())
