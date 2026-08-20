"""The one call both `cli.py` and `ui/main_window.py` make: model in, a
file on disk out, `.pdf` or anything else decided by the path's suffix.

Kept as one function here rather than duplicated in the CLI and the window
— each of those call sites is meant to stay a "minimal hook", and "write
HTML, or render it to PDF first" is exactly the kind of one-line decision
that drifts apart if it is written twice.
"""
from __future__ import annotations

from pathlib import Path

from report.model import ReportModel
from report.template import render_html


def write_styled_report(path, model: ReportModel, lang: str = "en") -> str:
    """Render `model` and write it to `path`. Returns the HTML actually used
    (handy for a caller — a test, `--dry-run`-style tooling — that wants to
    inspect it without opening the file back up).

    `.pdf` (case-insensitive) renders through `report.pdf.render_pdf`;
    anything else is written as the HTML document as-is, which already
    opens correctly in a browser with no further step.
    """
    target = Path(path)
    html = render_html(model, lang)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() == ".pdf":
        from report.pdf import render_pdf

        # No `base_url`: everything the template needs (the logo, the
        # colours, the type) is already inlined, so there is nothing for a
        # base URL to resolve relative to.
        pdf_bytes = render_pdf(html)
        target.write_bytes(pdf_bytes)
    else:
        target.write_text(html, encoding="utf-8")
    return html
