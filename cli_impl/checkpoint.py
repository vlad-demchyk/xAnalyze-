"""A phase's product, kept on disk so resume does not recompute it.

The expensive phases of a full scan are the crawl and the browser pass: on a
192-page site they were three minutes and forty-three minutes respectively,
against two minutes for everything that comes after. A failure in one of the
cheap late phases used to cost the whole forty-six.

What is stored is the *product*, not the process: the audit's findings rather
than the pages they came from. `AccessibilityResult`, `DocumentReport` and
`Issue` are all plain dataclasses, so this is an exact round trip rather than
a stand-in that happens to answer the attributes today's report writers read -
which is what it would have had to be if any of them held a live object.

Deliberately not stored: the crawled pages themselves. Their text runs to
tens of megabytes on a large site and nothing after the audit reads them, so
keeping them would cost far more than the phase they would save.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

AUDIT_FILE = "checkpoint-audit.json"
SCAN_FILE = "checkpoint-scan.json"


def _write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)
    return path


def save_audit(run_dir, result) -> Path | None:
    """Store an `AccessibilityResult`. Returns the file, or None if empty."""
    if result is None:
        return None
    payload = {
        "root": result.root,
        "mode": result.mode,
        "rules_run": list(getattr(result, "rules_run", ()) or ()),
        "documents": [
            {"source": doc.source, "error": doc.error,
             "elements_checked": doc.elements_checked,
             "issues": [asdict(issue) for issue in doc.issues]}
            for doc in result.documents
        ],
    }
    return _write(Path(run_dir) / AUDIT_FILE, payload)


def load_audit(run_dir):
    """Rebuild the `AccessibilityResult`, or None when there is no file.

    Unknown keys are dropped rather than passed through: a checkpoint written
    by an older build must not crash the resume that reads it, and a field
    this version does not have is a field it does not need.
    """
    path = Path(run_dir) / AUDIT_FILE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    from dataclasses import fields

    from audit.base import Issue
    from audit.engine import AccessibilityResult, DocumentReport

    known = {f.name for f in fields(Issue)}
    documents = []
    for doc in payload.get("documents", []):
        issues = [Issue(**{k: v for k, v in raw.items() if k in known})
                  for raw in doc.get("issues", [])]
        documents.append(DocumentReport(
            source=doc.get("source", ""), issues=issues,
            error=doc.get("error"),
            elements_checked=doc.get("elements_checked", 0)))
    return AccessibilityResult(
        root=payload.get("root", ""), mode=payload.get("mode", "web"),
        documents=documents, rules_run=payload.get("rules_run", []))


def save_scan(run_dir, findings: list, counts: dict | None = None) -> Path:
    """Store the AI-patterns and typography findings."""
    return _write(Path(run_dir) / SCAN_FILE,
                  {"findings": list(findings or []), "counts": counts or {}})


def load_scan(run_dir):
    """Returns `(findings, counts)`, or `(None, None)` when absent."""
    path = Path(run_dir) / SCAN_FILE
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None
    return payload.get("findings", []), payload.get("counts", {})
