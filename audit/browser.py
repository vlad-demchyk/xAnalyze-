"""Auditing the page a visitor actually gets, by running a real browser.

The static rules read the HTML the server sent. This reads the page after
the browser has finished with it, which is a different document on most
modern sites and the only one that matters to a visitor.

There is no new dependency for this. The app already ships QtWebEngine —
the same Chromium that draws the site preview — so the audit runs in a real
engine rather than an approximation of one. That single fact is what makes
this worth doing: it removes the two limits the static pass has to declare
as `NEEDS_BROWSER`, and it un-blinds the case where the static pass sees
nothing at all.

Three things happen once the page has settled:

1. **Engines.** `axe-core` and `HTML_CodeSniffer` are injected as plain
   scripts and run against the live DOM. They are Deque's and Squiz's rules,
   not ours, and they disagree with each other often enough to be worth
   running together: on a published comparison against 142 known problems,
   axe alone found 27%, HTML_CodeSniffer alone 20%, and both together 35%.
2. **Measurements.** Navigation and resource timings, read from the
   Performance API. These are readings, not inferences, and are labelled as
   such so the report never mixes the two.
3. **States.** The page is interacted with — every control focused, menus
   opened — and re-examined. This is the part no snapshot can do, and the
   largest remaining source of automatable findings that does not involve a
   model. See `audit/states.py`.

Everything here is asynchronous, because `QWebEnginePage.runJavaScript` and
`loadFinished` are. The driver is therefore built on signals and a callback,
not on blocking waits: blocking the thread that owns the page is what
deadlocks Qt.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .base import (
    ACCESSIBILITY, CRITICAL, MINOR, MODERATE, NEEDS_BROWSER, PERFORMANCE,
    SERIOUS, Issue,
)

VENDOR_DIR = Path(__file__).resolve().parent / "vendor"
AXE_PATH = VENDOR_DIR / "axe.min.js"
HTMLCS_PATH = VENDOR_DIR / "HTMLCS.js"

#: axe severity names -> ours. axe's "critical"/"serious"/"moderate"/"minor"
#: happen to be the same four words, which is why ours are named this way.
_AXE_IMPACT = {
    "critical": CRITICAL, "serious": SERIOUS,
    "moderate": MODERATE, "minor": MINOR,
}

#: HTML_CodeSniffer emits Error / Warning / Notice. A Notice is a "check this
#: manually" prompt, not a finding, so it is dropped rather than shown as a
#: problem the user then has to learn to ignore.
_HTMLCS_TYPE = {1: SERIOUS, 2: MODERATE}


@dataclass
class BrowserAuditOptions:
    """What to run, and what to leave alone."""
    run_axe: bool = True
    #: Both engines on by default: the overlap is what raises coverage from
    #: 27% to 35%, and the duplicates between them are collapsed below.
    run_htmlcs: bool = True
    run_measurements: bool = True
    run_states: bool = True
    #: CSS selectors excluded from the engines. Shared with the app's
    #: suppression list, so "not this part of the page" is said once.
    exclude: list = field(default_factory=list)
    #: Rule ids to switch off, passed through to axe as `rules: {id: {...}}`.
    disabled_rules: list = field(default_factory=list)
    #: Milliseconds to wait after load before auditing, for the JavaScript
    #: that renders the page to finish. Deliberately generous: auditing a
    #: half-rendered SPA produces confident nonsense.
    settle_ms: int = 1200


def engines_available() -> dict:
    """Which vendored engines are actually present.

    Checked rather than assumed: the files are large, and a checkout that
    skipped them should degrade to the static rules with a clear reason,
    not fail at the point of use.
    """
    return {"axe": AXE_PATH.is_file(), "htmlcs": HTMLCS_PATH.is_file()}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------- JS payloads

def axe_script(options: BrowserAuditOptions) -> str:
    """axe-core plus the call that runs it and hands back JSON.

    `exclude` and per-rule disabling are passed to axe rather than filtered
    afterwards, so a suppressed region costs nothing to analyse instead of
    being analysed and then thrown away.
    """
    config = {
        "resultTypes": ["violations", "incomplete"],
        "rules": {rule: {"enabled": False} for rule in options.disabled_rules},
    }
    context = {"exclude": [[selector] for selector in options.exclude]} if options.exclude else {}
    return f"""
(function() {{
  {_read(AXE_PATH)}
  var context = {json.dumps(context) or "document"};
  return axe.run(Object.keys(context).length ? context : document, {json.dumps(config)})
    .then(function(results) {{
      var pack = function(nodes, bucket) {{
        return (nodes || []).map(function(v) {{
          return {{
            bucket: bucket,
            id: v.id,
            impact: v.impact,
            help: v.help,
            description: v.description,
            helpUrl: v.helpUrl,
            tags: v.tags,
            nodes: (v.nodes || []).slice(0, 20).map(function(n) {{
              return {{
                target: (n.target || []).join(' '),
                html: (n.html || '').slice(0, 300),
                failureSummary: (n.failureSummary || '').slice(0, 600)
              }};
            }})
          }};
        }});
      }};
      return JSON.stringify({{
        violations: pack(results.violations, 'violation'),
        incomplete: pack(results.incomplete, 'incomplete')
      }});
    }})
    .catch(function(err) {{ return JSON.stringify({{error: String(err)}}); }});
}})()
"""


def htmlcs_script(standard: str = "WCAG2AA") -> str:
    """HTML_CodeSniffer, which reports through a callback rather than a
    promise — hence the collector array."""
    return f"""
(function() {{
  {_read(HTMLCS_PATH)}
  return new Promise(function(resolve) {{
    var found = [];
    try {{
      HTMLCS.process({json.dumps(standard)}, document, function() {{
        (HTMLCS.getMessages() || []).forEach(function(m) {{
          found.push({{
            type: m.type,
            code: m.code,
            msg: (m.msg || '').slice(0, 600),
            html: (m.element && m.element.outerHTML || '').slice(0, 300),
            tag: (m.element && m.element.tagName || '').toLowerCase()
          }});
        }});
        resolve(JSON.stringify({{messages: found.slice(0, 400)}}));
      }});
    }} catch (err) {{
      resolve(JSON.stringify({{error: String(err)}}));
    }}
  }});
}})()
"""


MEASUREMENT_SCRIPT = """
(function() {
  var nav = (performance.getEntriesByType('navigation') || [])[0] || {};
  var paints = {};
  (performance.getEntriesByType('paint') || []).forEach(function(p) {
    paints[p.name] = Math.round(p.startTime);
  });
  var resources = performance.getEntriesByType('resource') || [];
  var byType = {};
  var totalBytes = 0;
  resources.forEach(function(r) {
    var kind = r.initiatorType || 'other';
    var size = r.transferSize || r.encodedBodySize || 0;
    byType[kind] = byType[kind] || {count: 0, bytes: 0};
    byType[kind].count += 1;
    byType[kind].bytes += size;
    totalBytes += size;
  });
  var slowest = resources.slice()
    .sort(function(a, b) { return b.duration - a.duration; })
    .slice(0, 5)
    .map(function(r) {
      return {name: String(r.name).slice(0, 160), ms: Math.round(r.duration),
              bytes: r.transferSize || r.encodedBodySize || 0};
    });
  return JSON.stringify({
    domContentLoaded: Math.round(nav.domContentLoadedEventEnd || 0),
    loadComplete: Math.round(nav.loadEventEnd || 0),
    firstPaint: paints['first-paint'] || 0,
    firstContentfulPaint: paints['first-contentful-paint'] || 0,
    transferBytes: totalBytes,
    requestCount: resources.length,
    byType: byType,
    slowest: slowest,
    domNodes: document.getElementsByTagName('*').length
  });
})()
"""


# ------------------------------------------------------------- normalisation

def issues_from_axe(payload: str, source: str, exclude_rules=()) -> list:
    """axe results -> our `Issue`s.

    `incomplete` becomes a finding marked `NEEDS_BROWSER` rather than being
    dropped or promoted: axe puts things there precisely when it cannot
    decide, and that is the same honest state our own rules use.
    """
    data = _load(payload)
    if "error" in data:
        return [Issue(rule_id="axe", severity=MODERATE, category=ACCESSIBILITY,
                      source=source, engine="axe",
                      details={"engine_error": data["error"]})]

    issues = []
    for bucket, entries in (("violation", data.get("violations", [])),
                            ("incomplete", data.get("incomplete", []))):
        for entry in entries:
            if entry.get("id") in exclude_rules:
                continue
            severity = _AXE_IMPACT.get(entry.get("impact") or "", MODERATE)
            for node in entry.get("nodes", []):
                issues.append(Issue(
                    rule_id=f"axe:{entry.get('id')}",
                    severity=severity,
                    category=ACCESSIBILITY,
                    selector=node.get("target", ""),
                    snippet=node.get("html", ""),
                    source=source,
                    engine="axe",
                    confidence=NEEDS_BROWSER if bucket == "incomplete" else "exact",
                    details={
                        "engine": "axe-core",
                        "rule": entry.get("id"),
                        "help": entry.get("help", ""),
                        "description": entry.get("description", ""),
                        "why": node.get("failureSummary", ""),
                        "url": entry.get("helpUrl", ""),
                        "tags": entry.get("tags", []),
                        "bucket": bucket,
                    },
                ))
    return issues


def issues_from_htmlcs(payload: str, source: str) -> list:
    data = _load(payload)
    if "error" in data:
        return [Issue(rule_id="htmlcs", severity=MODERATE, category=ACCESSIBILITY,
                      source=source, engine="htmlcs",
                      details={"engine_error": data["error"]})]
    issues = []
    for message in data.get("messages", []):
        severity = _HTMLCS_TYPE.get(message.get("type"))
        if severity is None:
            continue  # Notice: a manual-check prompt, not a finding
        code = message.get("code", "")
        issues.append(Issue(
            rule_id=f"htmlcs:{_short_code(code)}",
            severity=severity,
            category=ACCESSIBILITY,
            snippet=message.get("html", ""),
            source=source,
            engine="htmlcs",
            details={"engine": "HTML_CodeSniffer", "code": code,
                     "why": message.get("msg", ""), "element": message.get("tag", "")},
        ))
    return issues


def issues_from_measurements(payload: str, source: str, budgets=None) -> list:
    """Measurements become findings only where they cross a budget.

    The numbers themselves are kept on the result for the report; turning
    every timing into a "problem" would produce a page of rows that say
    nothing is wrong.
    """
    data = _load(payload)
    if not data or "error" in data:
        return []
    budgets = budgets or DEFAULT_BUDGETS

    issues = []
    for key, (limit, severity, rule) in budgets.items():
        value = data.get(key)
        if not isinstance(value, (int, float)) or value <= limit:
            continue
        issues.append(Issue(
            rule_id=rule, severity=severity, category=PERFORMANCE,
            source=source, engine="browser",
            details={"metric": key, "value": value, "budget": limit,
                     "measurements": data},
        ))
    return issues


#: metric -> (budget, severity, rule id). Chosen to match the thresholds the
#: field generally treats as "good": 1.8s first contentful paint, ~1.6 MB of
#: transfer, 50 requests, 1500 DOM nodes.
DEFAULT_BUDGETS = {
    "firstContentfulPaint": (1800, SERIOUS, "perf-first-paint"),
    "loadComplete": (5000, MODERATE, "perf-load-time"),
    "transferBytes": (1_600_000, MODERATE, "perf-page-weight"),
    "requestCount": (50, MINOR, "perf-request-count"),
    "domNodes": (1500, MODERATE, "perf-dom-size"),
}


def deduplicate(issues: list) -> list:
    """Collapse the same problem found by more than one engine.

    Two engines on the same element and the same underlying rule is one
    problem, and showing it twice teaches people that the report is padded.
    The kept copy records who else found it, which is useful signal: a
    finding both engines agree on is not one to argue with.

    Matching cannot go through the selector, which is the obvious key and the
    wrong one: our own rules emit a full `html:nth-of-type(1) > body... > img`
    path, axe emits `img`, and HTML_CodeSniffer emits nothing at all. Three
    spellings of one element look like three elements, and the collapse
    silently never happens. So elements are compared by what they *are* —
    tag name plus attributes, recovered from the snippet each engine carries
    — and the selector is only a fallback for findings that have no element
    (a missing canonical link is about the page, not about a node).

    Cross-engine only. Within one engine the selectors are consistent and two
    findings on `<button></button>` really are two buttons; merging those
    would hide a genuine second problem, which is worse than a duplicate row.
    """
    from .base import SEVERITY_ORDER

    kept: dict = {}
    order = []
    #: (source, family, element key) -> the issue already kept for it, used
    #: only to match findings that came from a *different* engine.
    by_element: dict = {}

    for issue in issues:
        family = _rule_family(issue.rule_id)
        element = _element_key(issue)

        existing = None
        if element:
            candidate = by_element.get((issue.source, family, element))
            if candidate is not None and candidate.engine != issue.engine:
                existing = candidate

        signature = (issue.source, family, issue.selector or issue.snippet)
        if existing is None:
            existing = kept.get(signature)

        if existing is None:
            kept[signature] = issue
            order.append(signature)
            if element:
                by_element.setdefault((issue.source, family, element), issue)
            continue

        confirmations = set(existing.details.get("also_found_by", []))
        confirmations.add(issue.engine)
        existing.details["also_found_by"] = sorted(confirmations)
        # Keep the more severe reading of the same problem.
        if SEVERITY_ORDER.index(issue.severity) < SEVERITY_ORDER.index(existing.severity):
            existing.severity = issue.severity
    return [kept[signature] for signature in order]


#: The opening tag of a snippet: name, then everything up to the `>`.
_OPEN_TAG = re.compile(r"<\s*([a-zA-Z][a-zA-Z0-9-]*)((?:\s+[^>]*?)?)/?\s*>")
_ATTRIBUTE = re.compile(r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)")


def _element_key(issue) -> str:
    """A spelling-independent identity for the element a finding is about.

    Built from the snippet rather than the selector because every engine
    serialises the element it found, and none of them agree on how to address
    it. `<img src="a.png"/>` and `<img src="a.png">` are the same image, and
    this is what makes them compare equal.
    """
    match = _OPEN_TAG.search(issue.snippet or "")
    if not match:
        return ""
    tag = match.group(1).lower()
    attributes = sorted(
        (name.lower(), value.strip("\"'"))
        for name, value in _ATTRIBUTE.findall(match.group(2) or "")
    )
    rendered = ";".join(f"{name}={value}" for name, value in attributes)
    return f"{tag}|{rendered}"


#: Rules that mean the same thing across engines, so the deduplicator can
#: tell that `image-alt`, `axe:image-alt` and an HTMLCS 1_1_1 message about a
#: missing alt are one finding rather than three.
_RULE_FAMILIES = {
    "image-alt": "alt", "axe:image-alt": "alt", "htmlcs:1_1_1": "alt",
    "control-name": "name", "axe:button-name": "name", "axe:link-name": "name",
    "axe:input-button-name": "name", "axe:aria-input-field-name": "name",
    "axe:label": "name",
    "html-lang": "lang", "axe:html-has-lang": "lang", "axe:html-lang-valid": "lang",
    "document-title": "title", "axe:document-title": "title",
    "duplicate-id": "id", "axe:duplicate-id": "id", "axe:duplicate-id-active": "id",
    "heading-order": "heading-order", "axe:heading-order": "heading-order",
    "contrast-inline": "contrast", "axe:color-contrast": "contrast",
    "table-headers": "table", "axe:th-has-data-cells": "table",
    "viewport-zoom": "zoom", "axe:meta-viewport": "zoom",
    "tabindex-positive": "tabindex", "axe:tabindex": "tabindex",
    "link-text-vague": "link-text", "axe:link-in-text-block": "link-text",
    # HTML_CodeSniffer names success criteria, not rules, so its codes have to
    # be mapped by hand: 1.1.1 is text alternatives, 4.1.2 is name/role/value,
    # 1.4.3 is contrast.
    "htmlcs:4_1_2": "name", "htmlcs:1_4_3": "contrast",
}


def _rule_family(rule_id: str) -> str:
    return _RULE_FAMILIES.get(rule_id, rule_id)


def _short_code(code: str) -> str:
    """HTML_CodeSniffer codes are long dotted paths; the middle part is the
    success criterion, which is the useful half."""
    parts = (code or "").split(".")
    for part in parts:
        if part and part[0].isdigit():
            return part
    return parts[-1] if parts else code


def _load(payload) -> dict:
    if isinstance(payload, dict):
        return payload
    if not payload:
        return {}
    try:
        return json.loads(payload)
    except (TypeError, ValueError):
        return {"error": "engine returned a non-JSON result"}
