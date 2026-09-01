"""The check that would have caught the last four false-positive classes.

Every one of them looked different in the code and identical in the numbers:
the rule fired on almost every candidate it had, on almost every document.
`focus-not-visible` produced 588 findings across ten pages of GOV.UK;
`control-name` produced 455 across one WordPress project. A real defect is
uneven - some pages have it, most elements are fine.

These cases pin both directions. Saturation has to be recognised, and normal
unevenness has to be left alone: a check that cries wolf about ordinary
findings is worth less than no check.
"""
from __future__ import annotations

import unittest

from audit.base import Issue
from audit.engine import AccessibilityResult, DocumentReport
from audit.saturation import saturated_rules


def _result(shape: dict, documents: int = 10) -> AccessibilityResult:
    """`{rule: findings-per-document}` over `documents` documents."""
    result = AccessibilityResult(root="https://site", mode="web")
    for number in range(documents):
        report = DocumentReport(source=f"https://site/page{number}")
        for rule, per in shape.items():
            for index in range(per):
                report.issues.append(Issue(
                    rule_id=rule, severity="serious",
                    source=report.source, snippet=f"<i>{index}</i>", details={}))
        result.documents.append(report)
    return result


class TheShapeOfABrokenMeasurement(unittest.TestCase):
    def test_the_gov_uk_focus_pass_is_caught(self):
        """588 findings over ten pages, one per element examined."""
        found = saturated_rules(_result({"state:focus-not-visible": 59}))
        self.assertEqual([s.rule for s in found], ["state:focus-not-visible"])
        self.assertEqual(found[0].findings, 590)
        self.assertEqual(found[0].documents, 10)

    def test_the_note_says_what_to_do_about_it(self):
        note = saturated_rules(_result({"control-name": 46}))[0].message()
        self.assertIn("measuring the scan, not the page", note)
        self.assertIn("control-name", note)

    def test_the_worst_rule_comes_first(self):
        found = saturated_rules(_result({"a": 12, "b": 40, "c": 25}))
        self.assertEqual([s.rule for s in found], ["b", "c", "a"])


class ThePopulationIsPagesNotDocuments(unittest.TestCase):
    """One page is audited as several documents.

    Its own rules are one, its response headers another, its crawl facts a
    third, the provenance of an image on it a fourth. Counting those as the
    denominator diluted the share past the point where this guard can fire:
    measured 2026-09-01 on a 250-page site, `htmlcs:1_4_3` reached 251 of
    283 pages - the shape this exists to name - and 251 of 879 documents,
    which is 0.29 and under every threshold here.
    """

    def _result(self, extra_documents_per_page: int):
        result = AccessibilityResult(root="https://site", mode="web")
        for number in range(10):
            source = f"https://site/page{number}"
            page = DocumentReport(source=source)
            for index in range(12):
                page.issues.append(Issue(rule_id="noisy", severity="serious",
                                         source=source, snippet=f"<i>{index}</i>",
                                         details={}))
            result.documents.append(page)
            for extra in range(extra_documents_per_page):
                # A header document for the same address: one finding, and
                # it must not become a page in the denominator.
                headers = DocumentReport(source=source)
                headers.issues.append(Issue(rule_id="sec-no-csp",
                                            severity="moderate", source=source,
                                            snippet="", details={}))
                result.documents.append(headers)
        return result

    def test_extra_documents_for_one_page_do_not_dilute_the_share(self):
        for extra in (0, 1, 3):
            with self.subTest(extra_documents=extra):
                found = saturated_rules(self._result(extra))
                self.assertEqual([s.rule for s in found], ["noisy"])
                self.assertEqual(found[0].documents_total, 10)
                self.assertEqual(found[0].documents, 10)
                self.assertEqual(found[0].findings, 120)


class OrdinaryFindingsAreLeftAlone(unittest.TestCase):
    def test_a_few_findings_everywhere_is_a_real_site_wide_defect(self):
        """A missing skip link on every page is one problem, not a false one."""
        self.assertEqual(saturated_rules(_result({"skip-link": 1})), [])

    def test_many_findings_on_one_page_is_not_saturation(self):
        result = _result({}, documents=10)
        for index in range(40):
            result.documents[0].issues.append(Issue(
                rule_id="image-alt", severity="serious",
                source=result.documents[0].source, details={}))
        self.assertEqual(saturated_rules(result), [])

    def test_a_small_run_is_not_judged(self):
        """One file with twelve missing `alt` attributes is a normal Tuesday."""
        self.assertEqual(saturated_rules(_result({"image-alt": 30}, documents=2)), [])

    def test_a_count_smaller_than_the_findings_is_not_a_population(self):
        """Measured on a real run of python.org, where it printed "20
        findings on 1 elements (2000% of what was examined)".

        Several passes report `elements_checked=1` meaning "one thing was
        examined" - a response's headers, a site's link graph, a file's
        provenance. Dividing by it makes a percentage out of a number that
        was never a population, and the resulting warning accused a rule
        that had done nothing wrong."""
        result = AccessibilityResult(root="https://site", mode="web")
        report = DocumentReport(source="https://site/", elements_checked=1)
        for index in range(20):
            report.issues.append(Issue(
                rule_id="axe:listitem", severity="serious",
                source=report.source, snippet=f"<li>{index}</li>", details={}))
        result.documents.append(report)
        self.assertEqual(saturated_rules(result), [])

    def test_a_real_single_page_share_is_still_caught(self):
        """The fix must not close the eye it opened: a page with a real
        element count and a rule taking half of it is still saturated."""
        result = AccessibilityResult(root="https://site", mode="web")
        report = DocumentReport(source="https://site/", elements_checked=120)
        for index in range(59):
            report.issues.append(Issue(
                rule_id="state:focus-not-visible", severity="serious",
                source=report.source, snippet=f"<a>{index}</a>", details={}))
        result.documents.append(report)
        self.assertEqual([s.rule for s in saturated_rules(result)],
                         ["state:focus-not-visible"])

    def test_a_clean_run_says_nothing(self):
        self.assertEqual(saturated_rules(_result({}, documents=10)), [])

    def test_a_document_that_errored_is_not_counted(self):
        result = _result({"image-alt": 30}, documents=3)
        for report in result.documents:
            report.error = "unreadable"
        self.assertEqual(saturated_rules(result), [])


class ItReachesTheReport(unittest.TestCase):
    def test_the_payload_carries_the_warning(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace

        from cli_impl.reports import _write_report

        result = _result({"state:focus-not-visible": 59})
        with tempfile.TemporaryDirectory() as folder:
            args = SimpleNamespace(report=str(Path(folder, "r.json")))
            payload = _write_report(result, args, "en")

        rules = [row["rule"] for row in payload["saturated_rules"]]
        self.assertIn("state:focus-not-visible", rules)

    def test_a_normal_run_carries_an_empty_list(self):
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace

        from cli_impl.reports import _write_report

        with tempfile.TemporaryDirectory() as folder:
            args = SimpleNamespace(report=str(Path(folder, "r.json")))
            payload = _write_report(_result({"skip-link": 1}), args, "en")

        self.assertEqual(payload["saturated_rules"], [])


if __name__ == "__main__":
    unittest.main()
