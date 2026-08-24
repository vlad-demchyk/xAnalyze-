"""The one-page PDF written when the full report cannot be printed.

Printing the PDF is the *last* step of a run. By the time it fails the work is
finished and `report.md` is already on disk - so a failure here is not a failed
run, it is a failed conversion of a report that exists. Treating it as a
failure was the wrong reading of the problem: it stopped a run whose findings
were complete, and it left the person with no PDF and nothing telling them the
markdown was sitting next to it.

So the failure produces a PDF anyway, at the path the caller asked for, and
that PDF does two things:

* says where the real report is, in one line, at the top; and
* carries the headline numbers, so it is a usable summary on its own rather
  than a page of apology.

The notice is deliberately tiny - no findings, no snippets, no logo pipeline.
Whatever defeated the full render (a 31 MB document, a wedged compositor) has
no purchase on a page this small, which is what makes the fallback worth
attempting at all.
"""
from __future__ import annotations

import html
from pathlib import Path

#: Strings live here rather than in `i18n/translations.py` because this page is
#: written into a document, not into the interface: it has to read correctly in
#: a file someone opens next week, in the language the report itself was
#: generated in, whatever the interface is set to now.
_TEXT = {
    "en": {
        "title": "The report could not be printed",
        "lead": "The findings are complete. Only the conversion to PDF "
                "failed, so read the Markdown report instead:",
        "why": "What went wrong",
        "summary": "What the run found",
        "no_path": "The Markdown report is in the same folder as this file.",
        "findings": "findings",
        "problems": "distinct problems",
        "pages": "pages or files examined",
        "footer": "This page is a stand-in. Nothing was lost: every finding "
                  "is in the Markdown report and in the JSON beside it.",
    },
    "uk": {
        "title": "Звіт не вдалось надрукувати",
        "lead": "Знахідки повні. Не вдалась лише конвертація в PDF, тому "
                "читайте Markdown-звіт:",
        "why": "Що саме сталось",
        "summary": "Що знайшов прогін",
        "no_path": "Markdown-звіт лежить у тій самій теці, що й цей файл.",
        "findings": "знахідок",
        "problems": "окремих проблем",
        "pages": "сторінок або файлів перевірено",
        "footer": "Ця сторінка є замінником. Нічого не втрачено: кожна "
                  "знахідка є в Markdown-звіті і в JSON поруч із ним.",
    },
    "it": {
        "title": "Non è stato possibile stampare il report",
        "lead": "I rilievi sono completi. È fallita solo la conversione in "
                "PDF, quindi leggi il report Markdown:",
        "why": "Che cosa è andato storto",
        "summary": "Che cosa ha trovato l'esecuzione",
        "no_path": "Il report Markdown è nella stessa cartella di questo file.",
        "findings": "rilievi",
        "problems": "problemi distinti",
        "pages": "pagine o file esaminati",
        "footer": "Questa pagina è un sostituto. Nulla è andato perso: ogni "
                  "rilievo è nel report Markdown e nel JSON accanto.",
    },
}


def _words(lang: str) -> dict:
    return _TEXT.get(lang) or _TEXT["en"]


def notice_html(reason: str, *, markdown_path=None, model=None,
                lang: str = "en") -> str:
    """The stand-in page, as HTML.

    Separate from the rendering so it can be tested without Qt, and so the
    same page can be written as `.html` when even this will not print.
    """
    words = _words(lang)
    parts = [
        "<style>",
        "body{font:16px/1.6 -apple-system,Segoe UI,Roboto,sans-serif;"
        "margin:48px;color:#1a1a1a}",
        "h1{font-size:24px;margin:0 0 8px}",
        "h2{font-size:15px;text-transform:uppercase;letter-spacing:.06em;"
        "color:#666;margin:28px 0 8px}",
        ".path{font-family:ui-monospace,Menlo,monospace;font-size:15px;"
        "background:#f4f4f5;padding:12px 14px;border-radius:6px;"
        "word-break:break-all;display:block}",
        ".why{color:#7a2e2e;background:#fdf3f3;padding:12px 14px;"
        "border-radius:6px}",
        "ul{margin:0;padding-left:20px}",
        "footer{margin-top:36px;color:#666;font-size:14px}",
        "</style>",
        f"<h1>{html.escape(words['title'])}</h1>",
        f"<p>{html.escape(words['lead'])}</p>",
    ]
    if markdown_path:
        parts.append(f"<span class='path'>{html.escape(str(markdown_path))}</span>")
    else:
        parts.append(f"<p>{html.escape(words['no_path'])}</p>")

    parts.append(f"<h2>{html.escape(words['why'])}</h2>")
    parts.append(f"<p class='why'>{html.escape(reason or '')}</p>")

    rows = _summary_rows(model, words)
    if rows:
        parts.append(f"<h2>{html.escape(words['summary'])}</h2><ul>")
        parts += [f"<li>{html.escape(row)}</li>" for row in rows]
        parts.append("</ul>")

    parts.append(f"<footer>{html.escape(words['footer'])}</footer>")
    return "".join(parts)


def _summary_rows(model, words) -> list:
    """The headline numbers, if a model was handed over.

    Guarded throughout: this runs on the failure path, and a stand-in page
    that raises while explaining a failure would leave the caller with nothing
    at all - which is the exact outcome this module exists to prevent.
    """
    if model is None:
        return []
    rows = []
    try:
        findings = list(getattr(model, "findings", ()) or ())
        if findings:
            rows.append(f"{len(findings)} {words['findings']}")
            try:
                grouped = model.grouped_findings()
                if len(grouped) != len(findings):
                    rows.append(f"{len(grouped)} {words['problems']}")
            except Exception:  # noqa: BLE001 - a number is optional here
                pass
        pages = list(getattr(model, "pages", ()) or ())
        if pages:
            rows.append(f"{len(pages)} {words['pages']}")
        for label, data in (("AI patterns", getattr(model, "ai_patterns", None)),
                            ("typography", getattr(model, "typography", None))):
            total = (data or {}).get("total") if isinstance(data, dict) else None
            if total:
                rows.append(f"{total} {label}")
    except Exception:  # noqa: BLE001
        return rows
    return rows


def write_notice_pdf(path, reason: str, *, markdown_path=None, model=None,
                     lang: str = "en") -> Path:
    """Write the stand-in to `path`. Returns what was actually written.

    A PDF if one can still be produced - the point is that the file the person
    opens is the file they expected. If even a page this small will not print,
    the same notice is written as HTML beside it rather than lost, because a
    browser opens that and nothing opens a zero-byte PDF.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    page = notice_html(reason, markdown_path=markdown_path, model=model,
                       lang=lang)
    try:
        from report.pdf import render_pdf

        target.write_bytes(render_pdf(page))
        return target
    except Exception:  # noqa: BLE001 - the fallback has its own fallback
        beside = target.with_suffix(".html")
        beside.write_text(page, encoding="utf-8")
        return beside
