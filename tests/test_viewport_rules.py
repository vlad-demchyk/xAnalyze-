"""The static viewport rules: what the markup alone proves about how a
page behaves at phone width.

Inline styles and <style> blocks are checked; stylesheet files need the
browser pass, so these rules carry NEEDS_BROWSER confidence and say "found
in the markup" rather than claiming the rendered page fails.
"""
import unittest

from bs4 import BeautifulSoup

from audit.base import ACCESSIBILITY, RuleRegistry, Issue
from audit.explanations import render


class _Context:
    source = "test"

    def locate(self, tag):
        return (tag.name, None)


def _check(rule_id: str, html: str):
    rule = next(r for r in RuleRegistry.all_rules() if r.id == rule_id)
    document = BeautifulSoup(html, "html.parser")
    return rule.check(document, _Context())


class FixedPixelWidthTests(unittest.TestCase):

    def test_inline_width_over_600_is_flagged(self):
        issues = _check("viewport-fixed-width",
                        '<div style="width: 1200px">wide</div>')
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].details["width_px"], 1200)

    def test_style_block_declarations_are_checked(self):
        issues = _check("viewport-fixed-width", """<style>
            .container { width: 1200px; }
            .fixed { width: 800px; }
        </style><div class="container"></div>""")
        widths = sorted(i.details["width_px"] for i in issues)
        self.assertEqual(widths, [800, 1200])

    def test_narrow_widths_pass(self):
        issues = _check("viewport-fixed-width",
                        '<div style="width: 300px"></div>')
        self.assertEqual(issues, [])

    def test_max_and_min_width_are_not_the_bug(self):
        issues = _check("viewport-fixed-width",
                        '<div style="max-width: 1200px; min-width: 900px"></div>')
        self.assertEqual(issues, [])

    def test_mobile_media_query_overrides_are_not_flagged(self):
        html = ("<style>@media (max-width: 768px) { .c { width: 1200px; } }</style>")
        self.assertEqual(_check("viewport-fixed-width", html), [])

    def test_desktop_media_query_still_counts(self):
        html = ("<style>@media (min-width: 1024px) { .d { width: 1400px; } }</style>")
        self.assertEqual([i.details["width_px"]
                          for i in _check("viewport-fixed-width", html)], [1400])


class TinyFontTests(unittest.TestCase):

    def test_sub_10px_inline_font(self):
        issues = _check("viewport-tiny-font",
                        '<p style="font-size: 8px">tiny</p>')
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].details["font_px"], 8.0)

    def test_style_block_fonts(self):
        issues = _check("viewport-tiny-font",
                        "<style>.tiny-text { font-size: 8px; }</style>")
        self.assertEqual(len(issues), 1)

    def test_ten_px_exactly_passes(self):
        issues = _check("viewport-tiny-font",
                        '<p style="font-size: 10px">edge</p>')
        self.assertEqual(issues, [])

    def test_pt_rem_em_converted_to_px(self):
        issues = _check("viewport-tiny-font",
                        '<p style="font-size: 6pt">pt</p>'
                        '<p style="font-size: 0.5rem">rem</p>')
        values = sorted(i.details["font_px"] for i in issues)
        self.assertEqual(values, [8.0, 8.0])

    def test_normal_sizes_silent(self):
        issues = _check("viewport-tiny-font",
                        '<p style="font-size: 16px">ok</p>')
        self.assertEqual(issues, [])


class SmallTouchTargetTests(unittest.TestCase):

    def test_tiny_button_flagged(self):
        issues = _check("viewport-touch-target",
                        '<button style="width:20px;height:20px">go</button>')
        self.assertEqual(len(issues), 1)
        self.assertIn("height=20px", issues[0].details["declared"])

    def test_non_interactive_elements_are_not_targets(self):
        issues = _check("viewport-touch-target",
                        '<span style="width:20px;height:20px">x</span>')
        self.assertEqual(issues, [])

    def test_reasonably_sized_link_silent(self):
        issues = _check("viewport-touch-target",
                        '<a href="/" style="width:44px;height:44px;display:block">home</a>')
        self.assertEqual(issues, [])


class ExplanationShapeTests(unittest.TestCase):
    """Every new finding must reach the screen as words, not keys."""

    def test_findings_render_readably_in_all_languages(self):
        samples = {
            "viewport-fixed-width": {"width_px": 1200, "mobile_viewport": 390},
            "viewport-tiny-font": {"font_px": 8.0, "minimum_recommended": 10},
            "viewport-touch-target": {"declared": "height=20px",
                                      "wcag_minimum": 24, "recommended": 44},
        }
        for lang in ("uk", "it", "en"):
            for rule_id, details in samples.items():
                with self.subTest(lang=lang, rule=rule_id):
                    explanation = render(Issue(
                        rule_id=rule_id, severity="moderate",
                        category=ACCESSIBILITY, source="x", details=details), lang)
                    for field in ("title", "found", "why", "fix"):
                        value = getattr(explanation, field)
                        self.assertTrue(value and not value.startswith("a11y_"),
                                        f"{rule_id}/{field}/{lang} raw key")


if __name__ == "__main__":
    unittest.main()
