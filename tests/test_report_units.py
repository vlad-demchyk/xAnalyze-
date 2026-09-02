"""One name in the summary table must not carry two different numbers.

P-36, measured 2026-09-02 on a real WordPress theme. The "What was found"
table printed

    Typography                                        5
    Typography issues (non-keyboard characters)   ’   30
    Typography issues (non-keyboard characters)   —   12
    ...

and the chart beside it said `Typography 5`. Both numbers were right: 5 is
how many *distinct problems* the grouping found, 52 is how many *times* a
non-keyboard character occurs. Nothing on the page said so, the two blocks
were a dozen rows apart, and the only reading available to a person was that
the report contradicted itself.

The fix does not pick a number. It names the unit on every row and puts the
rows of one subject together, so both facts are readable at once - which is
what a summary is for.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from report.model import (CATEGORY_AI_TEXT,  # noqa: E402
                          CATEGORY_TYPOGRAPHY, ReportFinding,
                          ReportMeta, ReportModel)
from report.template import render_html  # noqa: E402

_ROW = re.compile(
    r"<tr><td>(?P<group>[^<]*)</td><td class=\"detail\">(?P<detail>[^<]*)</td>"
    r"<td class=\"num\">(?P<count>\d+)</td></tr>")


def _model() -> ReportModel:
    """Five distinct typography problems over fifty-two occurrences.

    A second category is here on purpose. With typography alone the rows are
    contiguous whether or not anything groups them, and the ordering test
    would pass over the defect it exists for: what actually happened is that
    the category block came first, the AI block after it, and the character
    tallies last - so "Typography" appeared, went away, and came back.
    """
    findings = [
        ReportFinding(title=f"Non-keyboard character {n}",
                      category=CATEGORY_TYPOGRAPHY, severity="low",
                      location=f"page-{n}.html:1", found="x", snippet=f"s{n}")
        for n in range(5)
    ]
    findings.append(
        ReportFinding(title="Reads as generated", category=CATEGORY_AI_TEXT,
                      severity="medium", location="page-0.html:9", found="x"))
    model = ReportModel(meta=ReportMeta(target="/tmp/theme", mode="text-repo"),
                        findings=findings)
    model.typography = {"total": 52, "files": 3,
                        "by_character": {"’": 30, "—": 12, "…": 10}}
    model.ai_patterns = {"total": 3, "high": 2, "medium": 1, "low": 0}
    return model


def _rows(lang: str) -> list:
    return [(m.group("group"), m.group("detail"), int(m.group("count")))
            for m in _ROW.finditer(render_html(_model(), lang))]


class EveryNumberSaysWhatItCounts(unittest.TestCase):

    def test_both_typography_numbers_are_printed(self):
        rows = _rows("en")
        counts = {detail: count for group, detail, count in rows
                  if group == "Typography"}
        self.assertEqual(counts.get("distinct problems"), 5)
        self.assertEqual(counts.get("occurrences in total"), 52)

    def test_no_row_carries_a_bare_number(self):
        """A row whose detail cell is empty is a number with no unit, which
        is the shape the defect had."""
        for group, detail, count in _rows("en"):
            with self.subTest(group=group):
                self.assertTrue(detail.strip(),
                                f"{group} prints {count} and does not say "
                                f"what it counted")

    def test_the_rows_of_one_subject_are_contiguous(self):
        """Two facts about typography a dozen rows apart read as a
        contradiction; side by side they read as two facts."""
        groups = [group for group, _d, _c in _rows("en")]
        seen: list = []
        for group in groups:
            if not seen or seen[-1] != group:
                self.assertNotIn(group, seen,
                                 f"{group!r} comes back after another group")
                seen.append(group)

    def test_the_character_tally_adds_up_to_the_total_it_prints(self):
        rows = _rows("en")
        tally = sum(count for group, detail, count in rows
                    if group == "Typography"
                    and detail not in ("distinct problems",
                                       "occurrences in total"))
        total = next(count for group, detail, count in rows
                     if group == "Typography"
                     and detail == "occurrences in total")
        self.assertEqual(tally, total)

    def test_every_language_names_both_units(self):
        """A unit named only in English is a unit half the readers do not
        have."""
        for lang in ("en", "uk", "it"):
            with self.subTest(lang=lang):
                rows = _rows(lang)
                details = {detail for _g, detail, _c in rows}
                self.assertEqual(len(details & {"", " "}), 0)
                typo = [count for group, _d, count in rows
                        if group not in ("", None)]
                self.assertTrue(typo)
                self.assertIn(52, [c for _g, _d, c in rows])
                self.assertIn(5, [c for _g, _d, c in rows])


if __name__ == "__main__":
    unittest.main()
