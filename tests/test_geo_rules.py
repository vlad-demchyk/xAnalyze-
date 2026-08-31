"""GEO readiness is advisory and must never turn into a pretend ranking."""
from __future__ import annotations

import unittest

import audit
from audit.explanations import render


def findings(markup: str):
    report = audit.analyze_document(markup, "https://example.test/article")
    return [issue for issue in report.issues if issue.category == "geo"]


class ArticleGeoSignals(unittest.TestCase):
    def test_non_article_page_does_not_receive_editorial_advice(self):
        self.assertEqual(findings("<html><body><main>Product page</main></body></html>"), [])

    def test_article_without_semantic_evidence_gets_two_advisory_signals(self):
        found = findings("<html><body><article><h1>Report</h1><p>Text</p></article></body></html>")
        self.assertEqual({issue.rule_id for issue in found}, {
            "geo-article-schema", "geo-article-provenance",
        })
        self.assertTrue(all(issue.confidence == "advisory" for issue in found))

    def test_article_jsonld_with_author_and_date_satisfies_both_signals(self):
        markup = """<html><head><script type="application/ld+json">
        {"@context":"https://schema.org","@type":"Article",
         "author":{"@type":"Person","name":"Ada"},
         "datePublished":"2026-08-31"}</script></head>
        <body><article><h1>Report</h1></article></body></html>"""
        self.assertEqual(findings(markup), [])

    def test_visible_semantic_author_and_date_do_not_substitute_for_article_type(self):
        markup = ("<html><head><meta name=\"author\" content=\"Ada\"></head><body>"
                  "<article><time datetime=\"2026-08-31\">31 August</time></article>"
                  "</body></html>")
        self.assertEqual([issue.rule_id for issue in findings(markup)],
                         ["geo-article-schema"])

    def test_geo_explanations_are_readable_in_every_supported_language(self):
        for lang in ("uk", "it", "en"):
            for issue in findings("<html><body><article>Text</article></body></html>"):
                explanation = render(issue, lang)
                self.assertFalse(explanation.title.startswith("a11y_"))
                self.assertTrue(explanation.why)


if __name__ == "__main__":
    unittest.main()
