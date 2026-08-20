"""Ukrainian grammatical number, and the strings that needed it.

`a11y_summary` used to give "на 1 документах" - a plural noun after a count
of one - because the template had exactly one substitution slot for a
concept ("documents") that Ukrainian spells three different ways depending
on the count. `plural()` is the shared mechanism; the rest of this file pins
the three sentences that actually needed it.
"""
from __future__ import annotations

import unittest

from i18n.translations import plural, t
from audit.explanations import summary_line, render
from audit.engine import AccessibilityResult, DocumentReport
from audit.base import Issue


def _result(n: int) -> AccessibilityResult:
    docs = [DocumentReport(source=f"doc{i}.html",
                           issues=[Issue(rule_id="image-alt", severity="critical",
                                        source=f"doc{i}.html")])
            for i in range(n)]
    return AccessibilityResult(root="x", mode="repo", documents=docs)


class PluralHelperTests(unittest.TestCase):
    def test_ukrainian_one_few_many(self):
        forms = dict(one="файл", few="файли", many="файлів")
        self.assertEqual(plural(1, "uk", **forms), "файл")
        self.assertEqual(plural(2, "uk", **forms), "файли")
        self.assertEqual(plural(4, "uk", **forms), "файли")
        self.assertEqual(plural(5, "uk", **forms), "файлів")
        self.assertEqual(plural(0, "uk", **forms), "файлів")

    def test_the_11_to_14_exception(self):
        """11-14 end in 1-4 but still take the "many" form - the one detail
        every naive `n % 10` implementation gets wrong."""
        forms = dict(one="файл", few="файли", many="файлів")
        for n in (11, 12, 13, 14):
            self.assertEqual(plural(n, "uk", **forms), "файлів", n)
        self.assertEqual(plural(21, "uk", **forms), "файл")
        self.assertEqual(plural(101, "uk", **forms), "файл")
        self.assertEqual(plural(114, "uk", **forms), "файлів")

    def test_few_and_many_may_share_one_word(self):
        """Locative and genitive-after-preposition contexts often have no
        distinct few/many form; passing the same string for both is valid."""
        forms = dict(one="документі", few="документах", many="документах")
        self.assertEqual(plural(2, "uk", **forms), "документах")
        self.assertEqual(plural(11, "uk", **forms), "документах")

    def test_italian_and_english_only_distinguish_one_from_the_rest(self):
        self.assertEqual(plural(1, "en", one="document", few="documents"), "document")
        self.assertEqual(plural(0, "en", one="document", few="documents"), "documents")
        self.assertEqual(plural(5, "en", one="document", few="documents"), "documents")
        self.assertEqual(plural(1, "it", one="documento", few="documenti"), "documento")
        self.assertEqual(plural(2, "it", one="documento", few="documenti"), "documenti")


class SummaryLineAgreementTests(unittest.TestCase):
    """The bug as reported: "на 1 документах" for a single-document run."""

    def test_one_document_takes_the_singular(self):
        self.assertIn("1 документі", summary_line(_result(1), "uk"))
        self.assertNotIn("документах", summary_line(_result(1), "uk"))

    def test_several_documents_take_the_plural(self):
        self.assertIn("2 документах", summary_line(_result(2), "uk"))

    def test_eleven_documents_still_take_the_plural(self):
        self.assertIn("11 документах", summary_line(_result(11), "uk"))

    def test_english_and_italian_pick_the_right_form_too(self):
        self.assertIn("1 document", summary_line(_result(1), "en"))
        self.assertIn("2 documents", summary_line(_result(2), "en"))
        self.assertIn("1 documento", summary_line(_result(1), "it"))
        self.assertIn("2 documenti", summary_line(_result(2), "it"))


class RuleLevelAgreementTests(unittest.TestCase):
    """The same defect, found in two more sentences that put a count in
    front of a noun: blocking files in <head>, and third-party hosts."""

    def _issue(self, rule_id, count, **extra):
        return Issue(rule_id=rule_id, severity="moderate", source="page.html",
                    details={"count": count, **extra})

    def test_one_blocking_file_is_singular(self):
        found = render(self._issue("perf-render-blocking", 1, budget=4), "uk").found
        self.assertIn("1 блокувальний файл ", found)

    def test_several_blocking_files_are_plural(self):
        found = render(self._issue("perf-render-blocking", 6, budget=4), "uk").found
        self.assertIn("6 блокувальних файлів", found)

    def test_one_external_host_is_singular(self):
        found = render(self._issue("perf-preconnect", 1, hosts="cdn.example.com"), "uk").found
        self.assertIn("1 чужого домену", found)

    def test_several_external_hosts_share_the_plural_form(self):
        found = render(self._issue("perf-preconnect", 3, hosts="a.com, b.com"), "uk").found
        self.assertIn("3 чужих доменів", found)


if __name__ == "__main__":
    unittest.main()
