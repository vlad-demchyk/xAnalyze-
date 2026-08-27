"""The report's severity chart draws four steps in four colours.

The chart is CSS bars on purpose - `printToPdf` is the consumer, and a chart
that needs a script or an image is one that sometimes prints blank. What was
wrong was the palette: ranks 1 and 2 were both `palette.amber`, so "serious"
and "moderate" drew identically and a four-step chart read as three. That is
the same collapse `P-11` describes on a 16-colour terminal, except here it
happened on every screen and every printed page, in the one artifact whose
job is to show where the weight is.
"""
from __future__ import annotations

import re
import unittest

from report.template import render_html
from report.model import ReportFinding, ReportMeta, ReportModel


def _model() -> ReportModel:
    findings = []
    for severity, count in (("critical", 1), ("serious", 8),
                            ("moderate", 5), ("minor", 3)):
        for number in range(count):
            findings.append(ReportFinding(
                category="accessibility", severity=severity,
                title=f"{severity} {number}", found="", why="", fix="",
                snippet=f"<i>{severity}{number}</i>", location="p1"))
    return ReportModel(meta=ReportMeta(target="https://site", mode="audit-web"),
                       findings=findings)


def _bar_colours(html: str) -> list:
    chart = re.search(r'<div class="charts">.*?</div></div>', html, re.S)
    block = chart.group(0) if chart else html
    return re.findall(r'class="bar-fill" style="width:[^;]+;background:([^"]+)"',
                      block)


class TheSeverityChart(unittest.TestCase):
    def test_the_chart_is_rendered_at_all(self):
        html = render_html(_model(), "en")
        self.assertIn('class="bar-fill"', html)

    def test_four_severities_get_four_distinct_colours(self):
        colours = _bar_colours(render_html(_model(), "en"))[:4]
        self.assertEqual(len(colours), 4)
        self.assertEqual(len(set(colours)), 4,
                         f"two severity bars share a colour: {colours}")

    def test_it_needs_no_script_or_image(self):
        """A chart that depends on either prints blank in the PDF."""
        html = render_html(_model(), "en")
        chart = re.search(r'<div class="charts">.*?</div></div>', html, re.S)
        self.assertIsNotNone(chart)
        for forbidden in ("<script", "<canvas", "<img"):
            with self.subTest(element=forbidden):
                self.assertNotIn(forbidden, chart.group(0))


if __name__ == "__main__":
    unittest.main()
