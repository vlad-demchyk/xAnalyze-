"""A failed PDF is not a failed report.

Printing is the last step of a run. By the time it can fail, the findings are
complete and the Markdown report is already on disk - so treating the failure
as the run's failure was the wrong reading: it stopped a run whose work was
done, and left the person with no PDF and nothing saying the Markdown was
sitting right next to it.

What has to happen instead is that the file they expected still appears, and
opening it redirects them in one line.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from report import export, notice
from report.model import ReportFinding, ReportMeta, ReportModel


def _model():
    return ReportModel(
        meta=ReportMeta(target="https://example.com", mode="web"),
        findings=[
            ReportFinding(title="Image without alt", category="accessibility",
                          severity="critical", location="a.html",
                          snippet="<img>"),
            ReportFinding(title="Image without alt", category="accessibility",
                          severity="critical", location="b.html",
                          snippet="<img>"),
        ],
        pages=[{"source": "a.html"}, {"source": "b.html"}],
        ai_patterns={"total": 7},
        typography={"total": 3})


class NoticeContent(unittest.TestCase):
    """Tested without Qt: the wording is the part that has to be right."""

    def test_it_names_the_report_to_read_instead(self):
        page = notice.notice_html("the printer did not answer",
                                  markdown_path="/runs/report.md")
        self.assertIn("/runs/report.md", page)

    def test_it_says_the_findings_are_complete(self):
        page = notice.notice_html("boom", lang="en")
        self.assertIn("complete", page)

    def test_it_carries_the_reason(self):
        page = notice.notice_html("the render process ended (exit code 139)")
        self.assertIn("exit code 139", page)

    def test_it_is_a_summary_not_an_apology(self):
        """A page of regret helps nobody; the numbers make it worth opening."""
        page = notice.notice_html("boom", model=_model())
        self.assertIn("2 findings", page)
        self.assertIn("1 distinct problems", page)
        self.assertIn("2 pages or files examined", page)
        self.assertIn("7 AI patterns", page)

    def test_it_falls_back_to_the_folder_when_no_path_is_known(self):
        page = notice.notice_html("boom", lang="en")
        self.assertIn("same folder", page)

    def test_every_language_says_something(self):
        for lang in ("uk", "it", "en"):
            page = notice.notice_html("boom", markdown_path="/r.md", lang=lang)
            self.assertIn("/r.md", page)
            self.assertGreater(len(page), 400)

    def test_an_unknown_language_is_english_rather_than_empty(self):
        self.assertIn("could not be printed", notice.notice_html("x", lang="de"))

    def test_the_reason_is_escaped(self):
        """A reason is a message from Qt, and it goes into a document."""
        page = notice.notice_html("<script>alert(1)</script>")
        self.assertNotIn("<script>", page)

    def test_a_model_that_raises_does_not_take_the_notice_down(self):
        """This runs on the failure path.

        A stand-in that raised while explaining a failure would leave the
        caller with nothing at all - the exact outcome it exists to prevent.
        """
        class Hostile:
            @property
            def findings(self):
                raise RuntimeError("no")

        page = notice.notice_html("boom", model=Hostile())
        self.assertIn("could not be printed", page)


class WhenTheRenderFails(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.target = Path(self.tmp.name) / "report.pdf"
        self.markdown = Path(self.tmp.name) / "report.md"
        self.markdown.write_text("# the real report", encoding="utf-8")
        self._real = None

    def tearDown(self):
        self.tmp.cleanup()

    def _break_render(self, exc):
        import report.pdf

        self._real = report.pdf.render_pdf

        def fail(html, base_url=""):
            # The notice is rendered through the same function, so only the
            # big document fails - which is the real shape of the failure:
            # a 31 MB page defeats the renderer and a one-page notice does not.
            if len(html) > 3000:
                raise exc
            return self._real(html, base_url)

        report.pdf.render_pdf = fail
        self.addCleanup(setattr, report.pdf, "render_pdf", self._real)

    def test_the_expected_file_still_appears(self):
        self._break_render(RuntimeError("the printer did not answer"))
        export.write_styled_report(self.target, _model(), "en",
                                   markdown_path=self.markdown)
        self.assertTrue(self.target.exists())
        self.assertTrue(self.target.read_bytes().startswith(b"%PDF-"))

    def test_a_dead_render_process_produces_a_notice_rather_than_a_stop(self):
        self._break_render(RuntimeError(
            "the render process ended while printing "
            "(CrashTermination, exit code 139)"))
        export.write_styled_report(self.target, _model(), "en",
                                   markdown_path=self.markdown)
        self.assertTrue(self.target.exists())

    def test_the_failure_does_not_reach_the_caller(self):
        """The run is finished by this point; raising would undo that."""
        self._break_render(RuntimeError("boom"))
        html = export.write_styled_report(self.target, _model(), "en",
                                          markdown_path=self.markdown)
        self.assertIn("<html", html.lower())

    def test_a_working_render_is_untouched(self):
        export.write_styled_report(self.target, _model(), "en",
                                   markdown_path=self.markdown)
        data = self.target.read_bytes()
        self.assertTrue(data.startswith(b"%PDF-"))
        # The full report, not the stand-in: a one-page notice is far smaller
        # than a rendered report with findings in it.
        self.assertGreater(len(data), 20_000)

    def test_html_output_is_untouched_by_any_of_this(self):
        target = Path(self.tmp.name) / "report.html"
        export.write_styled_report(target, _model(), "en")
        self.assertIn("<html", target.read_text(encoding="utf-8").lower())


class WhenEvenTheNoticeFails(unittest.TestCase):
    """The fallback has a fallback: a browser opens HTML, nothing opens a
    zero-byte PDF."""

    def test_the_notice_is_written_as_html_beside_it(self):
        import report.pdf

        real = report.pdf.render_pdf
        report.pdf.render_pdf = lambda *a, **k: (_ for _ in ()).throw(
            RuntimeError("no renderer at all"))
        self.addCleanup(setattr, report.pdf, "render_pdf", real)
        with tempfile.TemporaryDirectory() as tmp:
            written = notice.write_notice_pdf(
                Path(tmp) / "report.pdf", "no renderer at all",
                markdown_path="/r.md")
            self.assertEqual(written.suffix, ".html")
            self.assertIn("/r.md", written.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
