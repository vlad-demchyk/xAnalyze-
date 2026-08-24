"""The one call both `cli.py` and `ui/main_window.py` make: model in, a
file on disk out, `.pdf` or anything else decided by the path's suffix.

Kept as one function here rather than duplicated in the CLI and the window
— each of those call sites is meant to stay a "minimal hook", and "write
HTML, or render it to PDF first" is exactly the kind of one-line decision
that drifts apart if it is written twice.
"""
from __future__ import annotations

import sys
from pathlib import Path

from report.model import ReportModel
from report.template import render_html


def write_styled_report(path, model: ReportModel, lang: str = "en",
                        markdown_path=None) -> str:
    """Render `model` and write it to `path`. Returns the HTML actually used
    (handy for a caller — a test, `--dry-run`-style tooling — that wants to
    inspect it without opening the file back up).

    `.pdf` (case-insensitive) renders through `report.pdf.render_pdf`;
    anything else is written as the HTML document as-is, which already
    opens correctly in a browser with no further step.

    **A failed PDF is not a failed report.** Printing is the last step of a
    run, and by the time it can fail the findings are complete and the
    Markdown report is already written. So a render failure does not
    propagate: a one-page stand-in is written to `path` instead, saying where
    the Markdown report is and carrying the headline numbers. The person opens
    the file they expected and is redirected in one line, rather than finding
    no PDF and no explanation.

    `markdown_path` is what that stand-in points at. Without it the notice
    still says the report is in the same folder, which is true - but naming
    the file is the difference between a redirect and a hint.
    """
    target = Path(path)
    html = render_html(model, lang)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() == ".pdf":
        from report.notice import write_notice_pdf
        from report.pdf import render_pdf

        try:
            # No `base_url`: everything the template needs (the logo, the
            # colours, the type) is already inlined, so there is nothing for a
            # base URL to resolve relative to.
            target.write_bytes(render_pdf(html))
        except Exception as exc:  # noqa: BLE001 - redirected, not swallowed
            written = write_notice_pdf(target, str(exc), model=model,
                                       markdown_path=markdown_path, lang=lang)
            # Said out loud as well as written into the file: a caller
            # watching stderr must not have to open the PDF to learn that it
            # is a stand-in.
            print(f"# the PDF could not be printed ({exc}); wrote a one-page "
                  f"notice to {written} - the full report is the Markdown one",
                  file=sys.stderr, flush=True)
    else:
        target.write_text(html, encoding="utf-8")
    return html
