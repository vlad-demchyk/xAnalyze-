"""The two groupings must count the same problems.

There are two of them, and they are read by different people. The audit
payload groups with `duplicates.issue_identity`; the branded report - the PDF
or HTML a person opens - groups with `report.model.Finding.identity`. Both
walk the same findings, so a run that answers "how many distinct problems"
twice must answer it the same way.

It did not. On a three-page crawl of a real WordPress site the styled report
counted 374 problems and the audit payload 369, over the same 552
occurrences, because only `issue_identity` masked generated identifiers. The
inflation was in the half a person reads, and the docstring warning against
it had been sitting in the other half since it was written.
"""
from __future__ import annotations

import unittest

import duplicates
from audit.base import Issue
from audit.engine import AccessibilityResult, DocumentReport
from report.model import from_accessibility

#: What a WordPress theme stamps into one component on every page it renders.
_GENERATED_IDS = ("6a8c2c05ce8bd", "b71f0e4a2c913", "0d4e77ab19c2f")


def _result(snippets) -> AccessibilityResult:
    result = AccessibilityResult(root="https://site", mode="web")
    for number, snippet in enumerate(snippets):
        source = f"https://site/page{number}"
        document = DocumentReport(source=source)
        document.issues = [Issue(
            rule_id="aria-reference-broken", severity="critical",
            category="accessibility", source=source, snippet=snippet,
            details={},
        )]
        result.documents.append(document)
    return result


def _both(result) -> tuple:
    issues = [issue for document in result.documents for issue in document.issues]
    return (len(duplicates.group_issues(issues)),
            len(from_accessibility(result, "en").grouped_findings()))


class OneTemplateIsOneProblem(unittest.TestCase):
    def test_a_generated_id_does_not_split_one_bug_into_three(self):
        result = _result([
            f'<button aria-controls="page-toc-panel-{gen}">Indice</button>'
            for gen in _GENERATED_IDS
        ])
        audit_count, report_count = _both(result)
        self.assertEqual(audit_count, 1)
        self.assertEqual(report_count, 1,
                         "the branded report still counts one template bug "
                         "once per page it renders on")

    def test_the_two_groupings_agree(self):
        """The property, stated directly: one run, one number."""
        result = _result([
            f'<button aria-controls="page-toc-panel-{gen}">Indice</button>'
            for gen in _GENERATED_IDS
        ])
        audit_count, report_count = _both(result)
        self.assertEqual(audit_count, report_count)

    def test_genuinely_different_elements_stay_apart(self):
        """Masking must not merge two real problems into one.

        The risk in the other direction, and the more expensive one: a
        wrongly merged problem hides a real one.
        """
        result = _result([
            '<button aria-controls="search-panel">Cerca</button>',
            '<button aria-controls="menu-panel">Menu</button>',
            '<button aria-controls="toc-panel">Indice</button>',
        ])
        audit_count, report_count = _both(result)
        self.assertEqual(audit_count, 3)
        self.assertEqual(report_count, 3)

    def test_reindented_markup_is_judged_the_same_way_by_both(self):
        """Parity holds where the answer is arguable, too.

        Neither grouping merges these: collapsing runs of whitespace turns
        `>\n  Cerca` into `> Cerca`, which is still not `>Cerca`. Whether
        that is the right answer is a separate question - what this pins is
        that both halves give the *same* answer, so the two reports from one
        run never disagree about how many problems there are.
        """
        result = _result([
            '<button aria-controls="search-panel">Cerca</button>',
            '<button   aria-controls="search-panel">\n  Cerca</button>',
        ])
        audit_count, report_count = _both(result)
        self.assertEqual(audit_count, report_count)


if __name__ == "__main__":
    unittest.main()
