"""The second column's action row, and what a click on a finding does.

Three fixes are pinned here, all of the same shape: a control that appeared
to work and quietly did nothing.

* A finding about the document as a whole (no h1, no canonical, no meta
  description) has no selector and no line, so clicking it highlighted
  nothing and said nothing.
* In repository mode the same finding did not even open its file.
* The two export buttons became one, and the one has to stay identifiable
  once its label is replaced by an icon.

Headless: Qt runs on the offscreen platform.
"""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from ui.main_window import MainWindow
    from ui import icons as icon_set, theme
    from audit.base import Issue, MINOR, BEST_PRACTICES
    from analysis_modes import SOURCE_REPO
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None


def issue(**kwargs):
    base = dict(rule_id="seo-canonical", severity=MINOR, category=BEST_PRACTICES,
                selector="", line=None, snippet="", source="x.html")
    base.update(kwargs)
    return Issue(**base)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class AuditClickTargets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.window = MainWindow()

    def test_a_selector_is_used_as_it_is(self):
        found = issue(selector="html > body > img:nth-of-type(1)")
        self.assertEqual(self.window._audit_target(found), found.selector)

    def test_a_document_finding_falls_back_to_the_element_it_names(self):
        self.assertEqual(
            self.window._audit_target(issue(snippet="<body>…</body>")), "body")

    def test_nothing_is_pointed_at_when_nothing_can_be(self):
        """`<head>` has no box on screen and `<html>` is the whole page, so
        both are "no target" rather than a highlight of everything."""
        for snippet in ("<head>…</head>", "<html>…</html>", ""):
            with self.subTest(snippet=snippet):
                self.assertEqual(self.window._audit_target(issue(snippet=snippet)), "")

    def test_a_repository_finding_without_a_line_still_opens_its_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "page.html"
            path.write_text("<html><body><p>текст</p></body></html>", encoding="utf-8")
            self.window.source = SOURCE_REPO
            self.window.current_preview_path = None
            self.window._show_audit_issue_in_code(
                issue(source=str(path), line=None, snippet="<head>…</head>"))
            self.assertEqual(self.window.current_preview_path, str(path))
            self.assertIn("текст", self.window.code_view.toPlainText())

    def test_an_unreadable_source_says_so_instead_of_returning_quietly(self):
        self.window.source = SOURCE_REPO
        self.window.status_bar.clearMessage()
        self.window._show_audit_issue_in_code(
            issue(source="/no/such/file.html", line=3))
        self.assertTrue(self.window.status_bar.currentMessage())


@unittest.skipIf(QApplication is None, "PySide6 not available")
class ActionRow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.window = MainWindow()

    @unittest.skipUnless(icon_set.available() if QApplication else False,
                         "icon files not present")
    def test_every_action_is_an_icon_that_can_still_be_identified(self):
        for attribute, _name in MainWindow._ACTION_ICONS:
            button = getattr(self.window, attribute)
            with self.subTest(button=attribute):
                self.assertFalse(button.icon().isNull())
                # An icon with no tooltip is a button nobody can name.
                self.assertTrue(button.toolTip())

    @unittest.skipUnless(icon_set.available() if QApplication else False,
                         "icon files not present")
    def test_icons_are_redrawn_for_the_other_theme(self):
        """They are rasterised in one colour, so the ink has to be redrawn -
        the light theme's is invisible on the dark sheet."""
        light = theme.current_palette("light")
        dark = theme.current_palette("dark")
        self.assertNotEqual(light.text, dark.text)
        first = icon_set.icon("download", light.text)
        second = icon_set.icon("download", dark.text)
        self.assertIsNot(first, second)

    def test_one_download_button_replaces_the_two_exports(self):
        self.assertFalse(hasattr(self.window, "export_report_btn"))
        self.assertFalse(hasattr(self.window, "styled_report_btn"))
        self.assertTrue(hasattr(self.window, "download_btn"))

    def test_download_is_dead_until_there_is_something_to_write(self):
        self.window.result = None
        self.window.audit_result = None
        self.window._update_repo_buttons_enabled()
        self.assertFalse(self.window.download_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
