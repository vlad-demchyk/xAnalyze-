"""One finding, five surfaces, and the same claim on all of them.

This project's most expensive class of defect is a fact with more than one
owner. The cheaper twin is a fact with *no* owner on some surface: something
the run established, that one surface shows and another quietly drops. It
looks like nothing at all, because every surface is individually plausible.

Two of them were live when this file was written, and both were about the
part of a finding that says how much to trust it:

* **`confidence`.** The window and the terminal have shown `advisory` and
  `needs-browser` since they existed. The styled report and the agent
  briefing - the two artefacts a person actually hands to somebody else -
  printed an editorial judgement and a measured fact in identical type.
* **`caveat`.** `audit.explanations.render` writes the sentence that says
  what a finding is *not* ("nothing will check this for you"). The terminal
  printed it, the window's detail panel printed it, and both report adapters
  dropped it on the floor.

So this file walks the whole path - `Issue` -> explanation -> each surface -
for each level of certainty, and asserts the claim survives it.
"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from audit.base import ADVISORY, EXACT, NEEDS_BROWSER, Issue
from audit.engine import AccessibilityResult, DocumentReport
from audit.explanations import render
from cli_impl.reports import _problem_map, _problems_section
from report.model import from_accessibility
from report.template import render_html

LEVELS = (EXACT, ADVISORY, NEEDS_BROWSER)


def _issue(confidence: str) -> Issue:
    return Issue(
        rule_id="geo-article-schema", severity="moderate", category="geo",
        confidence=confidence, source="https://example.com/",
        selector="article", snippet="<article>x</article>", details={},
    )


def _result(confidence: str) -> AccessibilityResult:
    result = AccessibilityResult(root="https://example.com", mode="web")
    document = DocumentReport(source="https://example.com/", elements_checked=400)
    document.issues.append(_issue(confidence))
    result.documents.append(document)
    return result


class TheExplanationSaysIt(unittest.TestCase):
    """The source of both facts. If this stops being true the rest is moot."""

    def test_the_two_uncertain_levels_carry_a_caveat_and_exact_does_not(self):
        self.assertEqual(render(_issue(EXACT), "en").caveat, "")
        for level in (ADVISORY, NEEDS_BROWSER):
            with self.subTest(level=level):
                self.assertTrue(render(_issue(level), "en").caveat)

    def test_the_two_caveats_are_different_sentences(self):
        """"Go and check this in a browser" and "nothing will check this for
        you" send a reader to two different places. They shared one sentence
        once, and people went looking for an answer that did not exist."""
        self.assertNotEqual(render(_issue(ADVISORY), "en").caveat,
                            render(_issue(NEEDS_BROWSER), "en").caveat)


class TheReportModelCarriesIt(unittest.TestCase):

    def test_both_facts_survive_the_adapter(self):
        for level in LEVELS:
            finding = from_accessibility(_result(level), "en").findings[0]
            with self.subTest(level=level):
                self.assertEqual(finding.confidence, level)
                self.assertEqual(finding.caveat, render(_issue(level), "en").caveat)

    def test_two_certainties_are_two_findings_not_one(self):
        """A group prints one certainty over all its occurrences, so merging
        an advisory row with an exact one would print a claim that is wrong
        for half of them."""
        from report.model import ReportModel, ReportMeta

        model = ReportModel(meta=ReportMeta(target="t", mode="audit-web"),
                            findings=[from_accessibility(_result(EXACT), "en").findings[0],
                                      from_accessibility(_result(ADVISORY), "en").findings[0]])
        model.findings[1].location = "https://example.com/other"
        self.assertEqual(len(model.grouped_findings()), 2)


class TheStyledReportShowsIt(unittest.TestCase):

    def test_an_uncertain_finding_is_badged_and_an_exact_one_is_not(self):
        """`exact` deliberately gets no badge: a document where most rows
        carry one teaches the reader to ignore it."""
        # The body only: the class is always *defined* in the style sheet,
        # and what matters is whether a card wears it.
        exact = render_html(from_accessibility(_result(EXACT), "en"),
                            lang="en").split("<body>")[1]
        self.assertNotIn("badge-cert", exact)
        for level in (ADVISORY, NEEDS_BROWSER):
            with self.subTest(level=level):
                body = render_html(from_accessibility(_result(level), "en"),
                                   lang="en").split("<body>")[1]
                self.assertIn(f"cert-{level}", body)

    def test_the_caveat_is_printed_where_the_finding_is(self):
        for level in (ADVISORY, NEEDS_BROWSER):
            html = render_html(from_accessibility(_result(level), "en"), lang="en")
            sentence = render(_issue(level), "en").caveat
            with self.subTest(level=level):
                self.assertIn('class="caveat"', html)
                self.assertIn(sentence.split(".")[0][:40], html)

    def test_the_badge_is_named_in_all_three_languages(self):
        for lang in ("en", "uk", "it"):
            body = render_html(from_accessibility(_result(ADVISORY), lang),
                               lang=lang).split("<body>")[1]
            with self.subTest(lang=lang):
                self.assertIn("badge-cert", body)


class TheAgentBriefingCarriesIt(unittest.TestCase):

    def _problems(self, level):
        return _problem_map(_result(level), render, "en")

    def test_the_json_names_the_certainty_and_the_caveat(self):
        for level in LEVELS:
            problem = self._problems(level)[0]
            with self.subTest(level=level):
                self.assertEqual(problem["confidence"], level)
                self.assertEqual(problem["caveat"],
                                 render(_issue(level), "en").caveat)
                # It has to survive being written out, not only being built.
                json.dumps(problem)

    def test_the_markdown_says_it_only_when_it_is_not_settled(self):
        settled = "\n".join(_problems_section({"problems": self._problems(EXACT)}))
        self.assertNotIn("certainty", settled)
        self.assertNotIn("- note:", settled)
        for level in (ADVISORY, NEEDS_BROWSER):
            text = "\n".join(_problems_section({"problems": self._problems(level)}))
            with self.subTest(level=level):
                self.assertIn(f"certainty {level}", text)
                self.assertIn("- note:", text)


class TheWindowShowsIt(unittest.TestCase):
    """Already true when this file was written; pinned so it stays true."""

    def test_the_detail_panel_has_a_row_for_the_caveat(self):
        # Read, not imported. The assertion is about a line of source, and
        # importing `ui.window_parts.audit_panel` to reach it drags in Qt -
        # so on a machine with no working PySide6 a text check failed as if
        # the row had been removed. The file is the evidence either way.
        source = (Path(__file__).resolve().parent.parent
                  / "ui" / "window_parts" / "audit_panel.py"
                  ).read_text(encoding="utf-8")
        self.assertIn('("audit_caveat", explanation.caveat)', source)

    def test_the_terminal_prints_it(self):
        import inspect

        import cli

        self.assertIn("explanation.caveat", inspect.getsource(cli.cmd_audit))


if __name__ == "__main__":
    unittest.main()
