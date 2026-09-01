"""Work that is delivered as a piece of somebody else's site.

Two shapes, and neither is the whole thing a scan usually gets pointed at:

* a **WordPress theme or plugin**, handed over on its own. Its templates are
  fragments by construction - `<html>` opens in `header.php` and closes in
  `footer.php` - and the folder carries none of the markers of the
  installation around it. WordPress itself identifies them by a *header
  inside a file*: `Theme Name:` in `style.css`, `Plugin Name:` in the
  plugin's main PHP file.
* a **SharePoint web part**, which is one subtree of a page the tenant owns.
  Auditing the page around it reports the suite bar, the site navigation and
  the comment rail - hundreds of findings against markup the developer
  cannot reach - and buries the handful that are theirs.

The first needed a marker that reads content rather than file names; the
second needed the opposite of the suppression list, "only inside this part",
and a way to survive the identifiers the platform generates.
"""
import tempfile
import unittest
from pathlib import Path

import project_profile
from audit.engine import analyze_document
from audit.within import ScopeNotFound, narrow, stem


class WhatAWordPressDeliveryLooksLike(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_a_theme_is_recognised_by_the_header_in_its_stylesheet(self):
        (self.root / "style.css").write_text(
            "/*\nTheme Name: Palmanova\nVersion: 1.0\n*/\n", encoding="utf-8")
        profile = project_profile.detect(self.root)
        self.assertEqual([s.name for s in profile.stacks], ["wordpress-theme"])
        self.assertIn("style.css", profile.evidence["wordpress-theme"])

    def test_a_plugin_is_recognised_by_the_header_in_its_php(self):
        (self.root / "shop-widget.php").write_text(
            "<?php\n/*\nPlugin Name: Shop Widget\n*/\n", encoding="utf-8")
        profile = project_profile.detect(self.root)
        self.assertEqual([s.name for s in profile.stacks],
                         ["wordpress-plugin"])

    def test_a_stylesheet_without_the_header_is_not_a_theme(self):
        """Every project has a `style.css`. The header is the marker, and
        matching the file name alone would call half the web WordPress."""
        (self.root / "style.css").write_text("body { margin: 0 }",
                                             encoding="utf-8")
        self.assertEqual(project_profile.detect(self.root).stacks, [])

    def test_a_theme_template_is_a_fragment_and_keeps_page_rules_off(self):
        """`header.php` opens the document and `footer.php` closes it, so no
        single file is a page. Asking one for a canonical link, an `<h1>` or
        a skip link is asking a piece for a property of the whole."""
        header = self.root / "header.php"
        header.write_text(
            "<!doctype html><html <?php language_attributes(); ?>>"
            "<head><?php wp_head(); ?></head><body>"
            "<header><img src='/logo.png'></header>", encoding="utf-8")
        # Through repo mode, which is the path a theme folder takes:
        # `_is_page_file` is false for `.php`, so nobody ever declares this
        # file a page, and `_document_kind` reads it as the fragment it is.
        import audit
        from models import FileResult

        result = audit.analyze_files(
            [FileResult(path=str(header),
                        raw_text=header.read_text(encoding="utf-8"))],
            str(self.root), media=False, repo_facts=False)
        fired = {issue.rule_id for issue in result.issues()}
        self.assertIn("image-alt", fired)
        for page_level in ("seo-canonical", "seo-open-graph", "page-has-h1",
                           "landmark-regions", "skip-link"):
            with self.subTest(page_level):
                self.assertNotIn(page_level, fired)


class WhatASharePointDeliveryLooksLike(unittest.TestCase):

    PAGE = ('<!doctype html><html lang="en"><head><title>Tenant</title></head>'
            '<body>'
            '<div id="SuiteNavPlaceHolder"><img src="suite.png"><button></button></div>'
            '<nav class="ms-HorizontalNav"><img src="nav.png"></nav>'
            '<div class="CanvasZone_9f8e7d"><section id="WebPartWPQ3">'
            '<h2>Ours</h2><img src="part.png"></section></div>'
            '<footer><img src="foot.png"></footer></body></html>')

    def test_a_web_part_folder_is_recognised_without_the_solution(self):
        with tempfile.TemporaryDirectory() as tmp:
            part = Path(tmp) / "src" / "webparts" / "hello"
            part.mkdir(parents=True)
            (part / "HelloWebPart.ts").write_text("export default class {}",
                                                  encoding="utf-8")
            profile = project_profile.detect(tmp)
        self.assertEqual([s.name for s in profile.stacks], ["spfx"])

    def test_only_the_part_is_read(self):
        whole = {i.rule_id for i in analyze_document(self.PAGE, "p.html").issues}
        part = {i.rule_id for i in
                analyze_document(self.PAGE, "p.html",
                                 within="#WebPartWPQ3").issues}
        self.assertIn("image-alt", part)
        # The tenant's chrome and the page's own head are not this
        # developer's work and are not in the answer.
        self.assertTrue(whole - part)
        for page_level in ("seo-canonical", "seo-title-length", "bp-charset"):
            with self.subTest(page_level):
                self.assertNotIn(page_level, part)

    def test_the_scope_makes_it_a_fragment_not_a_small_page(self):
        """A subtree has no `<head>`, so most page rules go quiet on their
        own - but not all of them. `seo-image-dimensions` is page-level and
        fires happily on a headless document, so without the fragment
        reading a scoped run would report the web part for a property of the
        page it is embedded in."""
        from bs4 import BeautifulSoup

        subtree = str(BeautifulSoup(self.PAGE, "html.parser")
                      .select_one("#WebPartWPQ3"))
        as_page = {i.rule_id for i in
                   analyze_document(subtree, "p.html").issues}
        as_scope = {i.rule_id for i in
                    analyze_document(self.PAGE, "p.html",
                                     within="#WebPartWPQ3").issues}
        self.assertIn("seo-image-dimensions", as_page)
        self.assertNotIn("seo-image-dimensions", as_scope)

    def test_a_generated_suffix_does_not_have_to_be_typed(self):
        """`CanvasZone_9f8e7d` changes between renders and environments. The
        stem is what the developer wrote, and it is what is matched."""
        markup, how = narrow(self.PAGE, ".CanvasZone")
        self.assertEqual(how, "stem")
        self.assertIn("WebPartWPQ3", markup)

    def test_an_exact_match_is_preferred_and_named_as_such(self):
        _markup, how = narrow(self.PAGE, "#WebPartWPQ3")
        self.assertEqual(how, "exact")

    def test_a_selector_that_matches_nothing_is_an_error_not_a_clean_page(self):
        with self.assertRaises(ScopeNotFound):
            narrow(self.PAGE, "#NoSuchPart")
        report = analyze_document(self.PAGE, "p.html", within="#NoSuchPart")
        self.assertIn("matched nothing", report.error or "")
        self.assertEqual(report.issues, [])

    def test_two_web_parts_are_not_confused_by_their_stems(self):
        """`WebPartWPQ3` and `WebPartWPQ7` are two parts on one page, and a
        stem that collapsed them would audit the wrong one."""
        with self.assertRaises(ScopeNotFound):
            narrow(self.PAGE, "#WebPartWPQ7")

    def test_the_stem_strips_what_platforms_generate(self):
        for generated, wanted in (("ControlZone_1a2b3c", "ControlZone"),
                                  ("root-137", "root"),
                                  ("ms-Button", "ms-Button")):
            with self.subTest(generated):
                self.assertEqual(stem(generated), wanted)


class WhatTheBrowserPassDoesWhenScoped(unittest.TestCase):

    def test_axe_is_given_the_include_context(self):
        from audit.browser import BrowserAuditOptions, axe_script

        script = axe_script(BrowserAuditOptions(within="#WebPartWPQ3"))
        self.assertIn('"include"', script)
        self.assertIn("#WebPartWPQ3", script)

    def test_the_engines_that_read_the_whole_document_are_switched_off(self):
        """HTML_CodeSniffer walks from `document`, the state pass tabs
        through the page, and a measurement is a property of the load. Left
        on, they would answer about the tenant's page under a report the
        caller narrowed on purpose."""
        import argparse
        from unittest import mock

        from audit.engine import AccessibilityResult, DocumentReport
        from cli_impl import auditpass

        result = AccessibilityResult(root="https://x.test/", mode="web")
        result.documents = [DocumentReport(source="https://x.test/")]
        seen = {}

        def _fake(urls, options, sizes, progress=None, markup=None):
            seen["options"] = options
            return []

        args = argparse.Namespace(within="#WebPartWPQ3", breakpoints=None)
        with mock.patch("audit.driver.available", return_value=(True, "")), \
                mock.patch.object(auditpass, "_audit_at_widths", _fake), \
                mock.patch("audit.browser.merge_into_document"):
            auditpass._run_browser_pass(result,
                                        mock.Mock(selectors=[], rules=[]),
                                        args)
        options = seen["options"]
        self.assertEqual(options.within, "#WebPartWPQ3")
        self.assertTrue(options.run_axe)
        self.assertFalse(options.run_htmlcs)
        self.assertFalse(options.run_states)
        self.assertFalse(options.run_measurements)


if __name__ == "__main__":
    unittest.main()
