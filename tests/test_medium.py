"""An email and a page are the same file format and almost nothing else.

`_document_kind` answers "page or fragment". This is the other question a
scan has to get right before it opens its mouth: a complete HTML document may
be a page a browser serves or an email a mail client renders.

Measured on `~/repositories/VSC`, a workspace of Ghost, Beehiiv, Carrd and
ClickFunnels deliverables: 1074 findings over 144 documents, and the six
loudest rules were all browser concepts - `seo-canonical` 93,
`seo-structured-data` 93, `seo-open-graph` 91, `seo-meta-description` 83,
`landmark-regions` 80, `skip-link` 67. An email has no canonical URL, is never
crawled, is not shared to Open Graph, and lands in clients that implement
neither landmarks nor skip links.

Detection is deliberately asymmetric. `web` is the default and needs no
evidence; `email` has to prove itself, because being wrong in that direction
*hides* findings - the failure nobody can see in a report.
"""
from __future__ import annotations

import unittest

from audit import medium
from audit.base import RuleRegistry


class EmailHasToProveItself(unittest.TestCase):
    def test_the_outlook_namespace_is_decisive(self):
        found = medium.detect(
            '<html xmlns:v="urn:schemas-microsoft-com:vml"><body>x</body></html>')
        self.assertTrue(found.is_email)
        self.assertIn("Outlook", found.evidence)

    def test_a_merge_tag_is_decisive(self):
        for tag in ("{{unsubscribe_url}}", "*|UNSUB|*", "%%unsubscribe%%",
                    "{{ subscriber.first_name }}"):
            with self.subTest(tag=tag):
                self.assertTrue(medium.detect(f"<body><a>{tag}</a></body>").is_email)

    def test_two_corroborating_signals_are_enough(self):
        markup = ('<meta name="supported-color-schemes" content="light">'
                  + '<table role="presentation"></table>' * 3)
        self.assertTrue(medium.detect(markup).is_email)

    def test_one_corroborating_signal_is_not(self):
        """Being wrong here hides findings, so one weak signal is not enough."""
        self.assertFalse(medium.detect(
            '<meta name="supported-color-schemes" content="light">').is_email)
        self.assertFalse(medium.detect(
            '<table role="presentation"></table>' * 3).is_email)

    def test_a_table_layout_with_an_email_attribute_settles_it(self):
        """Measured 2026-09-01 over 324 HTML files: seventeen lay out in
        three or more presentation tables, all seventeen are email
        deliverables, and every one carries a fixed narrow table width, a
        `bgcolor` or a `<td align>`. Asking for the colour-schemes meta as
        well left twelve of them audited as web pages."""
        for attribute in ('<table role="presentation" width="600">',
                          '<tr bgcolor="#131317">',
                          '<td align="center">'):
            with self.subTest(attribute):
                markup = ('<table role="presentation"></table>' * 3) + attribute
                found = medium.detect(markup)
                self.assertTrue(found.is_email, found.evidence)
                self.assertIn("presentation tables", found.evidence)

    def test_a_modern_page_with_tables_is_still_a_page(self):
        """The other side of the trade: presentation tables alone, with no
        attribute a browser stopped needing in 1999, stay web."""
        markup = ('<div class="grid">'
                  + '<table role="presentation"><tr><td>x</td></tr></table>' * 4
                  + '</div>')
        self.assertFalse(medium.detect(markup).is_email)

    def test_an_ordinary_page_is_web(self):
        found = medium.detect(
            '<!DOCTYPE html><html lang="en"><head><title>x</title></head>'
            '<body><main><h1>x</h1></main></body></html>')
        self.assertEqual(found.name, medium.WEB)
        self.assertEqual(found.evidence, "")

    def test_a_real_newsletter_is_recognised(self):
        """The file that started this: a Beehiiv welcome email."""
        markup = ('<!DOCTYPE html>\n<html lang="en" '
                  'xmlns:v="urn:schemas-microsoft-com:vml" '
                  'xmlns:o="urn:schemas-microsoft-com:office:office">\n'
                  '<head><meta charset="utf-8"></head><body></body></html>')
        self.assertTrue(medium.detect(markup).is_email)


class WhatAnEmailIsNotAskedFor(unittest.TestCase):
    def test_the_browser_only_rules_are_marked(self):
        expected = {"seo-canonical", "seo-open-graph", "seo-structured-data",
                    "seo-meta-description", "seo-title-length", "seo-noindex",
                    "geo-article-schema", "geo-article-provenance",
                    "skip-link", "landmark-regions", "hreflang-links",
                    "perf-preconnect", "perf-render-blocking",
                    "perf-font-display", "image-modern-format"}
        marked = {r.id for r in RuleRegistry.all_rules()
                  if getattr(r, "web_only", False)}
        self.assertEqual(marked, expected)

    def test_accessibility_is_not_web_only(self):
        """`alt`, control names, table headers and contrast are as real in a
        mail client as in a browser. Marking any of them would trade a
        category error for a blind spot."""
        for rule_id in ("image-alt", "control-name", "table-headers",
                        "contrast-inline", "html-lang", "image-alt-filename"):
            with self.subTest(rule=rule_id):
                self.assertFalse(getattr(RuleRegistry.create(rule_id),
                                         "web_only", False))


class TheMediumReachesTheRules(unittest.TestCase):
    def _rules_fired(self, markup: str, forced=None) -> set:
        from audit.engine import analyze_document

        report = analyze_document(markup, "a.html", force_medium=forced)
        return {issue.rule_id for issue in report.issues}

    _EMAIL = ('<!DOCTYPE html><html lang="en" '
              'xmlns:v="urn:schemas-microsoft-com:vml">'
              '<head><meta charset="utf-8"><title>A newsletter issue</title>'
              '</head><body><table role="presentation"><tr><td>'
              '<img src="a.png"><p>Hello</p></td></tr></table></body></html>')

    def test_an_email_is_not_asked_for_a_canonical(self):
        self.assertNotIn("seo-canonical", self._rules_fired(self._EMAIL))

    def test_an_email_is_still_asked_for_alt_text(self):
        self.assertIn("image-alt", self._rules_fired(self._EMAIL))

    def test_the_same_markup_as_a_page_is_asked_for_both(self):
        page = self._EMAIL.replace(
            ' xmlns:v="urn:schemas-microsoft-com:vml"', "")
        fired = self._rules_fired(page)
        self.assertIn("seo-canonical", fired)
        self.assertIn("image-alt", fired)

    def test_a_declared_medium_overrides_the_markup(self):
        """For a deliverable that carries neither namespace nor merge tag."""
        page = self._EMAIL.replace(
            ' xmlns:v="urn:schemas-microsoft-com:vml"', "")
        self.assertNotIn("seo-canonical",
                         self._rules_fired(page, forced=medium.EMAIL))


if __name__ == "__main__":
    unittest.main()
