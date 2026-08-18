"""Auditing one HTML file that is a whole page.

A site built or exported into a single self-contained file is a finished
document, not a piece of a project. Repo mode reads it the wrong way round:
that mode exists for fragments inside a codebase and skips whatever has no
elements, so the `<head>` of a packed page - canonical, description, Open
Graph, charset - would never be examined at all.
"""
import os
import tempfile
import unittest

import audit

PACKED_PAGE = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Packed</title>
<style>.a { color: #eee; background: #fff }</style></head>
<body>
<h1>Packed page</h1>
<img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=">
<button></button>
<script>document.title = "Packed";</script>
</body></html>
"""


class PageFileModeTests(unittest.TestCase):

    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".html")
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(PACKED_PAGE)
        self.addCleanup(os.unlink, self.path)

    def test_the_file_is_audited_as_a_page_not_as_source(self):
        result = audit.analyze_page_file(self.path)
        self.assertEqual(result.mode, "file")
        self.assertEqual(len(result.documents), 1)
        self.assertEqual(result.documents[0].source, self.path)

    def test_head_level_rules_run_on_it(self):
        """The reason repo mode is the wrong reading: a packed page has a real
        `<head>`, and SEO rules have something to say about it."""
        result = audit.analyze_page_file(self.path)
        rules = {issue.rule_id for issue in result.issues()}
        self.assertTrue(any(rule.startswith("seo-") for rule in rules), rules)

    def test_findings_carry_line_numbers(self):
        """The user has the file open, so a line is actionable in a way a CSS
        path into a one-file build is not."""
        result = audit.analyze_page_file(self.path)
        self.assertTrue(any(issue.line for issue in result.issues()))

    def test_an_unreadable_file_is_a_reported_error_not_a_crash(self):
        result = audit.analyze_page_file(self.path + ".missing")
        self.assertEqual(len(result.documents), 1)
        self.assertTrue(result.documents[0].error)
        self.assertEqual(result.issues(), [])


class BrowserUrlTests(unittest.TestCase):
    """The browser needs an absolute `file://` URL; `file://page.html` is not
    something it can resolve."""

    def test_a_path_becomes_an_absolute_file_url(self):
        import cli
        url = cli._browser_url("tests/test_page_file_mode.py")
        self.assertTrue(url.startswith("file:///"), url)

    def test_a_url_is_left_alone(self):
        import cli
        self.assertEqual(cli._browser_url("https://example.test/a"),
                         "https://example.test/a")


if __name__ == "__main__":
    unittest.main()
