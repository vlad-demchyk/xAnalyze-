"""Finding the element a finding is about.

Two separate questions: does the generated script look for the right thing, and
does a source-file finding land on the right line.
"""
import json
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.site_preview import build_highlight_js

try:
    from PySide6.QtWidgets import QApplication, QPlainTextEdit
    from ui.code_preview import highlight_line
except Exception:  # noqa: BLE001
    QApplication = None


class TheScript(unittest.TestCase):
    def test_it_scrolls_as_well_as_outlines(self):
        js = build_highlight_js("body > p:nth-of-type(2)")
        self.assertIn("scrollIntoView", js)
        self.assertIn("__ai_scanner_highlight", js)

    def test_the_selector_is_passed_as_data_not_as_code(self):
        # A selector arriving from a parsed document must not be able to end the
        # string it sits in. Checked by looking for the properly quoted form,
        # not by stripping backslashes - stripping them is what would make an
        # escaped payload look like an executable one.
        selector = "p[data-x=\"'); alert(1); ('\"]"
        js = build_highlight_js(selector)
        self.assertIn(json.dumps(selector), js)
        self.assertNotIn('alert(1); (\'"]");', js)

    def test_an_opening_tag_gives_it_something_to_fall_back_on(self):
        js = build_highlight_js("body > img:nth-of-type(9)", '<img src="/logo.svg"/>')
        self.assertIn("getElementsByTagName", js)
        self.assertIn("logo.svg", js)

    def test_without_a_fallback_it_does_not_invent_one(self):
        js = build_highlight_js("body > img:nth-of-type(9)")
        self.assertIn('var opening = ""', js)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class TheLine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_the_named_line_is_the_one_selected(self):
        edit = QPlainTextEdit()
        edit.setPlainText("one\ntwo\nthree\nfour")
        highlight_line(edit, 3)
        self.assertEqual(edit.textCursor().selectedText(), "three")

    def test_a_line_past_the_end_is_ignored_rather_than_clamped(self):
        edit = QPlainTextEdit()
        edit.setPlainText("one\ntwo")
        highlight_line(edit, 99)
        self.assertEqual(edit.textCursor().selectedText(), "")


if __name__ == "__main__":
    unittest.main()
