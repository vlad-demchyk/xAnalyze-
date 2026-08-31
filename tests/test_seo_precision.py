"""SEO findings must test whether metadata is usable, not only present."""
from __future__ import annotations

import unittest

import audit
from audit import browser


def findings(markup: str, rule_id: str):
    return [issue for issue in audit.analyze_document(markup, "https://example.test/").issues
            if issue.rule_id == rule_id]


class CanonicalPrecision(unittest.TestCase):
    def test_a_fragment_is_not_a_canonical_document(self):
        found = findings('<html><head><link rel="canonical" href="#section"></head></html>',
                         "seo-canonical")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].details["reason"], "fragment")

    def test_a_relative_canonical_is_not_reported_as_invalid(self):
        self.assertEqual(findings('<html><head><link rel="canonical" href="/about"></head></html>',
                                  "seo-canonical"), [])


class StructuredDataPrecision(unittest.TestCase):
    def test_invalid_jsonld_is_reported(self):
        found = findings('<html><head><script type="application/ld+json">{bad}</script></head></html>',
                         "seo-structured-data")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].details["reason"], "invalid-json")

    def test_jsonld_without_a_type_is_not_treated_as_valid_schema(self):
        found = findings('<html><head><script type="application/ld+json">{"@context":"https://schema.org"}</script></head></html>',
                         "seo-structured-data")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].details["reason"], "missing-type")

    def test_a_typed_graph_is_accepted(self):
        markup = ('<html><head><script type="application/ld+json">'
                  '{"@context":"https://schema.org","@graph":[{"@type":"Article"}]}'
                  '</script></head></html>')
        self.assertEqual(findings(markup, "seo-structured-data"), [])


class BrowserPerformancePrecision(unittest.TestCase):
    def test_lcp_cls_and_long_tasks_have_independent_budgets(self):
        payload = {
            "largestContentfulPaint": 2700,
            "cumulativeLayoutShift": 0.12,
            "longTaskMs": 240,
        }
        found = browser.issues_from_measurements(payload, "https://example.test/")
        self.assertEqual({issue.rule_id for issue in found}, {
            "perf-largest-contentful-paint", "perf-layout-shift-browser",
            "perf-long-tasks",
        })

    def test_unavailable_long_task_api_is_not_serialised_as_zero(self):
        self.assertIn("if (longTaskObserver) result.longTaskMs = longTaskMs;",
                      browser.MEASUREMENT_SCRIPT)
