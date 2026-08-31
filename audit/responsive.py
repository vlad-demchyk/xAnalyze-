"""One page, audited at several widths, reported as one list.

A page audited at one width has been audited at one width. That is not a
pedantic point: the mobile navigation of most sites does not exist in the DOM
until a media query brings it in, so its unlabelled buttons and its trapped
focus are invisible to a desktop-sized pass - and the desktop table that
overflows a phone screen is invisible to a mobile one. Both passes report
"clean" about the half they cannot see.

What makes this more than a loop is the merge. Running three widths and
concatenating produces three copies of every finding that has nothing to do
with width - a missing `lang`, a thin `<title>` - which is a report nobody
reads to the end. So a finding seen at several widths becomes one row that
records where it was seen, and a finding seen at one becomes a row that says
so. `details["breakpoints"]` carries the list either way; the "only at" case
is derived from it rather than stored twice.

**Matching across widths is the hard part, and it is done on the element
rather than on its position.** A selector is a path of `nth-of-type` steps,
and at a narrower width the path genuinely changes: a wrapper appears, a
sibling is hidden, the element moves. Two rows for one problem is exactly
what this module exists to prevent, so the key prefers the element's own
markup (`snippet`) and falls back to the selector only when there is no
markup to compare - which is the case for findings about the document as a
whole, where the selector is empty too and the rule id alone is the answer.

The honest limit: an element whose markup itself changes with width (a button
whose label is "Menu" at one size and "≡" at another) is two findings here,
one per width. Collapsing those would need a notion of element identity that
survives its own content changing, which is a guess rather than a fact.
"""
from __future__ import annotations

from dataclasses import replace

from . import browser, driver

#: The four widths, and why these four. Not a device list - a device list
#: dates - but the shapes a layout is written for plus the 320 CSS-pixel
#: reflow case. That last width is the condition behind WCAG 1.4.10: it finds
#: horizontal overflow that a 390-pixel phone viewport can hide. Heights are
#: realistic rather than important: media queries in the wild are written
#: against width.
BREAKPOINTS = (
    ("desktop", *browser.DEFAULT_VIEWPORT),
    ("tablet", 834, 1112),
    ("mobile", 390, 844),
    ("reflow", 320, 640),
)

#: Widest first. The first pass to report a finding is the one whose selector
#: and snippet the merged row keeps, and the desktop DOM is the one the
#: reader is most likely to have open when they go looking for it.


def breakpoint_names(chosen=None) -> tuple:
    """The names of the breakpoints that will run."""
    return tuple(name for name, _w, _h in (chosen or BREAKPOINTS))


def _identity(issue) -> tuple:
    """What makes two findings from two widths the same finding."""
    snippet = (issue.snippet or "").strip()
    if snippet:
        return (issue.rule_id, issue.source, snippet)
    if issue.selector:
        return (issue.rule_id, issue.source, issue.selector)
    return (issue.rule_id, issue.source)


def merge(results: dict) -> driver.PageAudit:
    """Fold per-breakpoint audits of one page into a single `PageAudit`.

    `results` maps breakpoint name to `PageAudit`, in the order the passes
    ran. Errors are not swallowed: a width that failed is recorded in
    `engine_errors` under its own name, and a page where *every* width failed
    comes back as an error rather than as a clean result.
    """
    merged_url = next((audit.url for audit in results.values()), "")
    merged = driver.PageAudit(url=merged_url)

    ran = [name for name, audit in results.items() if not audit.error]
    if not ran:
        first = next(iter(results.values()), None)
        merged.error = first.error if first is not None else "no breakpoint ran"
        return merged

    seen: dict = {}
    for name, audit in results.items():
        if audit.error:
            merged.engine_errors[name] = audit.error
            continue
        for engine, message in audit.engine_errors.items():
            merged.engine_errors[f"{name}/{engine}"] = message
        if not merged.measurements and audit.measurements:
            # The widest pass that produced numbers owns them: a transfer
            # size measured at three widths is one page loaded three times,
            # not three times the page.
            merged.measurements = audit.measurements
        if not merged.html and audit.html:
            merged.html = audit.html
        for issue in audit.issues:
            key = _identity(issue)
            existing = seen.get(key)
            if existing is None:
                details = dict(issue.details or {})
                details["breakpoints"] = [name]
                seen[key] = replace(issue, details=details)
            elif name not in existing.details["breakpoints"]:
                existing.details["breakpoints"].append(name)

    merged.issues = list(seen.values())
    return merged


def audit_responsive(url: str, breakpoints=None,
                     options: browser.BrowserAuditOptions | None = None,
                     runner=None) -> driver.PageAudit:
    """Audit one page at each breakpoint and merge the answers.

    One runner across all widths: starting a browser is the expensive part,
    resizing it is not. `runner` is injectable so a caller auditing many
    pages pays that cost once for the whole crawl rather than once per page.
    """
    sizes = tuple(breakpoints or BREAKPOINTS)
    options = options or browser.BrowserAuditOptions()
    own_runner = runner is None
    if own_runner:
        driver.ensure_headless_application()
        runner = driver.BrowserAuditRunner(
            replace(options, viewport=(sizes[0][1], sizes[0][2])))
    try:
        results = {}
        for name, width, height in sizes:
            runner.set_viewport(width, height)
            results[name] = runner.audit(url)
        return merge(results)
    finally:
        if own_runner:
            runner.close()


def only_at(issue) -> str:
    """The one breakpoint a finding was seen at, or "" when it was seen at
    more than one (or when the run was not responsive at all)."""
    names = (issue.details or {}).get("breakpoints") or []
    return names[0] if len(names) == 1 else ""
