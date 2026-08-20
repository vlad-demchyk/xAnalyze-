"""A styled, brandable export of a scan: the same findings the window and
`cli.py --report` already show, laid out as a document instead of a list.

Three files, one direction of dependency:

* `model.py` — the shape every renderer draws from (`ReportModel`), plus the
  two adapters that build one from `AnalysisResult`/`RepoAnalysisResult`
  (text mode) or from `AccessibilityResult` (audit mode). Nothing downstream
  of this module ever looks at those source types again.
* `template.py` — `ReportModel` -> a self-contained HTML string (print CSS,
  logo, everything inlined).
* `pdf.py` — that same HTML -> PDF bytes, via `QWebEnginePage.printToPdf`.

Kept as one small package rather than a function each in `cli.py` or
`ui/main_window.py` because a report is a real intermediate artifact: the
model is unit-testable with no Qt, and the HTML is byte-for-byte what a
browser would show, independent of whether it is ever turned into a PDF.
"""
