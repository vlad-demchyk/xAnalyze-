"""What the response said, as findings.

Ten security rules read the markup and none of them read the response. The
headers arrived with every page the crawl fetched and were dropped on the
floor - `crawler` kept `Content-Type` and let the rest die with the response
object - so a site served with no `Content-Security-Policy` and no
`Strict-Transport-Security` was audited as if transport were not part of it.

Nothing here costs a request. The bytes were already paid for.

Two things this deliberately does not do:

* **Judge the contents of a policy.** A CSP with `unsafe-inline` is weaker
  than one without, and saying by how much is a claim this cannot support
  from one header string. Absent or present is a fact; "weak" is an opinion.
* **Run off a page that was never fetched.** A page the crawl could not read
  has no headers, and reporting "no CSP" about it would be a finding about
  our own failure.
"""
from __future__ import annotations

from .base import (
    BEST_PRACTICES, CRITICAL, EXACT, Issue, MINOR, MODERATE, SECURITY,
    SERIOUS,
)

#: header -> (rule id, severity, category). Every one of these is a header
#: whose *absence* is the finding, so a present header of any value passes.
MISSING_HEADER_RULES = {
    "content-security-policy": ("sec-no-csp", SERIOUS, SECURITY),
    "strict-transport-security": ("sec-no-hsts", SERIOUS, SECURITY),
    "x-content-type-options": ("sec-no-nosniff", MODERATE, SECURITY),
    "referrer-policy": ("sec-no-referrer-policy", MINOR, SECURITY),
    "x-frame-options": ("sec-no-frame-options", MODERATE, SECURITY),
}

#: A page served over plain HTTP cannot be fixed by a header, so HSTS is not
#: reported there - the scheme is the finding, and `bp-mixed-content` and
#: `sec-form-insecure-action` already cover what it costs.
_HTTPS_ONLY = ("sec-no-hsts",)

RULE_NO_COMPRESSION = "perf-no-compression"
RULE_NO_CACHE = "perf-no-cache-header"


def _issue(rule: str, severity: str, category: str, url: str,
           details: dict) -> Issue:
    return Issue(rule_id=rule, severity=severity, category=category,
                 confidence=EXACT, source=url, selector="", line=None,
                 snippet="", details=details, engine="headers")


#: A CSP can also be delivered in the markup, and a page that does that is
#: not a page with no policy. Checked as a literal rather than by parsing:
#: this is a substring question, and the pass runs before any soup exists.
_META_CSP = 'http-equiv="content-security-policy"'


def issues_for(url: str, headers: dict, status: int | None = None,
               markup: str = "") -> list:
    """Findings about how one page was served.

    `headers` is what the crawler recorded, lower-cased. Empty means the page
    was never fetched, and that is not evidence of anything.
    """
    if not headers:
        return []
    flat = " ".join((markup or "").lower().replace("'", '"').split())
    https = url.lower().startswith("https://")
    issues = []
    for header, (rule, severity, category) in MISSING_HEADER_RULES.items():
        if headers.get(header):
            continue
        if rule in _HTTPS_ONLY and not https:
            continue
        if header == "content-security-policy" and _META_CSP in flat:
            continue
        # A CSP with `frame-ancestors` says the same thing X-Frame-Options
        # does, and says it better. Reporting both would be reporting a
        # problem the site has already solved the modern way.
        if (header == "x-frame-options"
                and "frame-ancestors" in (headers.get("content-security-policy") or "")):
            continue
        issues.append(_issue(rule, severity, category, url, {"header": header}))

    encoding = (headers.get("content-encoding") or "").lower()
    if not encoding:
        issues.append(_issue(RULE_NO_COMPRESSION, MODERATE, "performance", url,
                             {"header": "content-encoding"}))

    cache = headers.get("cache-control") or ""
    if not cache:
        issues.append(_issue(RULE_NO_CACHE, MINOR, "performance", url,
                             {"header": "cache-control"}))
    return issues


def as_documents(pages) -> list:
    """One `DocumentReport` per page that carried headers worth reporting."""
    from .engine import DocumentReport

    documents = []
    for page in pages:
        diagnostics = getattr(page, "diagnostics", None)
        headers = dict(getattr(diagnostics, "headers", {}) or {})
        issues = issues_for(getattr(page, "url", ""), headers,
                            getattr(diagnostics, "status_code", None),
                            markup=getattr(page, "raw_html", "") or "")
        if issues:
            documents.append(DocumentReport(source=page.url, issues=issues,
                                            elements_checked=1))
    return documents
