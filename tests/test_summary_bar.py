"""The run summary strip: what was scanned, and how bad it is.

The design puts a severity bar beside the finding count because the count
alone cannot answer the question people actually ask of it - 27 findings
that are all minor and 27 that are all critical are the same number and a
different afternoon.

Two things are worth holding still here. The strip must not appear before
there is a run to summarise, and its total must agree with the list
underneath it: the window does not treat a `LOW` span as a finding anywhere
else, so a summary that counted them would put a number on screen that
nothing else in the window matches.

Headless: Qt runs on the offscreen platform, like the other widget tests.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    from models import AnalysisResult, Confidence, PageResult, TextSpan
    from ui import theme
    from ui.main_window import MainWindow
    from ui.widgets import SeverityBar
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None


def span(confidence) -> "TextSpan":
    """One flagged passage at the given confidence."""
    return TextSpan(block_id="b", start=0, end=1, score=0.9,
                    confidence=confidence, detector_name="test")


@unittest.skipIf(QApplication is None, "PySide6 not available")
class Bar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.palette = theme.current_palette("light")

    def bar(self) -> SeverityBar:
        widget = SeverityBar(self.palette)
        self._alive = getattr(self, "_alive", [])
        self._alive.append(widget)
        return widget

    def colour_at(self, widget: SeverityBar, x: int) -> str:
        image = widget.grab().toImage()
        colour = image.pixelColor(x, widget.height() // 2)
        return "#%02x%02x%02x" % (colour.red(), colour.green(), colour.blue())

    def test_the_segments_run_worst_first(self):
        """Fixed order, not sorted by size: a bar whose colours moved between
        runs would say nothing about whether things got better."""
        widget = self.bar()
        widget.set_counts({"critical": 6, "serious": 8, "moderate": 9, "minor": 4})
        self.assertEqual(
            [self.colour_at(widget, x) for x in (10, 60, 120, 180)],
            [self.palette.sev_critical, self.palette.sev_high,
             self.palette.sev_medium, self.palette.sev_none])

    def test_a_level_with_no_findings_takes_no_room(self):
        """A sliver for a severity nobody hit is a lie told in one pixel."""
        widget = self.bar()
        widget.set_counts({"critical": 1, "minor": 1})
        painted = {self.colour_at(widget, x) for x in range(2, 188, 4)}
        self.assertNotIn(self.palette.sev_high, painted)
        self.assertNotIn(self.palette.sev_medium, painted)

    def test_an_empty_run_is_the_bare_track(self):
        widget = self.bar()
        widget.set_counts({})
        self.assertEqual(widget.total(), 0)
        self.assertEqual(self.colour_at(widget, 95), self.palette.bg_muted)

    def test_it_totals_what_it_was_given(self):
        widget = self.bar()
        widget.set_counts({"critical": 2, "serious": 3, "moderate": 0, "minor": 1})
        self.assertEqual(widget.total(), 6)

    def test_unknown_levels_are_dropped_not_lumped_in(self):
        """A fifth severity added upstream must not silently become part of
        an existing segment."""
        widget = self.bar()
        widget.set_counts({"critical": 1, "catastrophic": 99})
        self.assertEqual(widget.total(), 1)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class StripInTheWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.addCleanup(self.window.deleteLater)
        self.addCleanup(self.window.close)

    def test_it_is_not_there_before_a_run(self):
        """An empty bar beside "0 findings" is furniture that says nothing."""
        self.assertTrue(self.window.summary_bar.isHidden())

    def test_a_scan_brings_it_out(self):
        self.window.result = AnalysisResult(
            root_url="https://example.com",
            pages=[PageResult(url="https://example.com", depth=0)],
            spans=[span(Confidence.HIGH), span(Confidence.MEDIUM)])
        self.window._refresh_summary()
        self.assertFalse(self.window.summary_bar.isHidden())
        self.assertEqual(self.window.severity_bar.total(), 2)

    def test_low_confidence_is_not_counted_as_a_finding(self):
        """The status line does not count it and the list does not show it,
        so a summary that did would disagree with everything around it."""
        self.window.result = AnalysisResult(
            root_url="https://example.com",
            pages=[PageResult(url="https://example.com", depth=0)],
            spans=[span(Confidence.HIGH), span(Confidence.LOW),
                   span(Confidence.LOW)])
        self.window._refresh_summary()
        self.assertEqual(self.window.severity_bar.total(), 1)

    def test_confidence_lands_on_the_ramp_by_consequence(self):
        """High is the one to act on first, so it takes the worst segment."""
        self.window.result = AnalysisResult(
            root_url="https://example.com",
            pages=[PageResult(url="https://example.com", depth=0)],
            spans=[span(Confidence.HIGH), span(Confidence.MEDIUM)])
        self.window._refresh_summary()
        counts = self.window.severity_bar._counts
        self.assertEqual(counts["critical"], 1)
        self.assertEqual(counts["serious"], 1)
        self.assertEqual(counts["moderate"], 0)

    def test_the_line_says_what_was_scanned(self):
        self.window.url_edit.setText("https://example.com")
        self.window.result = AnalysisResult(
            root_url="https://example.com",
            pages=[PageResult(url="https://example.com", depth=0)],
            spans=[span(Confidence.HIGH)])
        self.window._refresh_summary()
        self.assertIn("example.com", self.window.summary_label.text())

    def test_the_count_reaches_the_label(self):
        self.window.result = AnalysisResult(
            root_url="https://example.com",
            pages=[PageResult(url="https://example.com", depth=0)],
            spans=[span(Confidence.HIGH), span(Confidence.HIGH)])
        self.window._refresh_summary()
        self.assertIn("2", self.window.summary_count.text())


if __name__ == "__main__":
    unittest.main()
