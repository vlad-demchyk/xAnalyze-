"""WCAG 2.5.8 Target Size (Minimum), measured in the browser (T-2226).

axe-core ships `target-size` switched off. The browser pass never turned it
on, and the static `viewport-touch-target` reads only sizes written into a
`style` attribute - so an icon button sized by a CSS class, the commonest
2.5.8 failure there is, produced nothing at all, and a clean report read as
"checked".
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from audit.base import ADVISORY, EXACT, MINOR, NEEDS_BROWSER

PAGE = """<!DOCTYPE html>
<html lang="en"><head><title>Targets</title><style>
  body { font: 16px sans-serif; margin: 40px; }
  .icon { display: inline-block; width: 16px; height: 16px; padding: 0;
          border: 0; background: #333; }
  .pair a { display: inline-block; width: 20px; height: 20px; margin: 0;
            background: #555; }
  .spaced { display: inline-block; width: 20px; height: 20px; margin: 0 6px;
            background: #555; }
  .roomy { display: block; margin: 40px 0; }
</style></head><body><main>
  <h1>Targets</h1>
  <!-- Side by side with no gap: the 24 px circles of two 16 px buttons
       overlap, so the spacing exception does not save them. With a few
       pixels between them it would, and axe would be right to pass them. -->
  <div class="roomy"><button class="icon" id="tiny" aria-label="Close"></button><button class="icon" id="tiny2" aria-label="Open"></button></div>
  <div class="roomy pair"><a href="/a" id="left" aria-label="A"></a><a href="/b" id="right" aria-label="B"></a></div>
  <p class="roomy">Read <a href="/inline" id="inline">the full story</a> in this paragraph.</p>
  <div class="roomy"><select id="native"><option>One</option></select>
    <input type="checkbox" id="check" aria-label="Agree"></div>
  <div class="roomy"><a class="spaced" href="/c" id="spaced1" aria-label="C"></a></div>
</main></body></html>"""


def _audit(page: str) -> list:
    from audit import browser, driver

    with TemporaryDirectory() as folder:
        path = Path(folder) / "targets.html"
        path.write_text(page, encoding="utf-8")
        options = browser.BrowserAuditOptions(
            run_axe=True, run_htmlcs=False, run_states=False,
            run_measurements=False, allow_local_files=True, settle_ms=200)
        driver.ensure_headless_application()
        runner = driver.BrowserAuditRunner(options)
        try:
            return runner.audit(path.resolve().as_uri()).issues
        finally:
            runner.close()


class InARealBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from audit import driver

        usable, reason = driver.available()
        if not usable:
            raise unittest.SkipTest(reason)
        cls.found = [i for i in _audit(PAGE) if i.rule_id == "axe:target-size"]

    def selectors(self) -> set:
        return {i.selector for i in self.found}

    def test_an_icon_button_sized_by_a_class_is_found(self):
        self.assertTrue({"#tiny", "#tiny2"} & self.selectors(), self.selectors())

    def test_two_small_links_side_by_side_are_found(self):
        self.assertTrue({"#left", "#right"} & self.selectors(), self.selectors())

    def test_the_exceptions_are_left_alone(self):
        for selector in ("#inline", "#native", "#check", "#spaced1"):
            with self.subTest(selector=selector):
                self.assertNotIn(selector, self.selectors())

    def test_the_finding_says_what_was_measured(self):
        tiny = [i for i in self.found if i.selector in ("#tiny", "#tiny2")]
        self.assertTrue(tiny)
        details = tiny[0].details
        self.assertEqual(details.get("min_size"), 24)
        self.assertTrue(details.get("width") or details.get("closest_offset"))


def _payload(bucket: str, data: dict, related=()) -> str:
    node = {"target": "#x", "html": "<button></button>", "failureSummary": "…",
            "data": data, "related": list(related)}
    entry = {"id": "target-size", "impact": "serious", "help": "…",
             "description": "…", "helpUrl": "", "tags": ["wcag22aa", "wcag258"],
             "nodes": [node]}
    key = "violations" if bucket == "violation" else "incomplete"
    return json.dumps({"violations": [], "incomplete": [], key: [entry]})


class Parsing(unittest.TestCase):
    def test_a_violation_carries_the_measured_size_and_neighbour(self):
        from audit.browser import issues_from_axe

        issue = issues_from_axe(_payload(
            "violation", {"minSize": 24, "width": 16, "height": 16,
                          "closestOffset": 18, "minOffset": 24},
            related=["#tiny2"]), "https://site/")[0]
        self.assertEqual(issue.confidence, EXACT)
        self.assertEqual(issue.details["width"], 16)
        self.assertEqual(issue.details["height"], 16)
        self.assertEqual(issue.details["closest_offset"], 18)
        self.assertEqual(issue.details["neighbour"], "#tiny2")
        self.assertIn("2.5.8", issue.details["wcag"])

    def test_an_undecided_target_is_a_note(self):
        from audit.browser import issues_from_axe

        issue = issues_from_axe(_payload("incomplete", {"minSize": 24}),
                                "https://site/")[0]
        self.assertEqual(issue.severity, MINOR)
        self.assertIn(issue.confidence, (NEEDS_BROWSER, ADVISORY))


class OneElementOneRow(unittest.TestCase):
    def test_the_static_reading_and_the_measurement_collapse(self):
        from audit.base import Issue, ACCESSIBILITY
        from audit.browser import deduplicate, issues_from_axe

        snippet = '<button class="icon" style="width:16px">x</button>'
        static = Issue(rule_id="viewport-touch-target", severity=MINOR,
                       category=ACCESSIBILITY, confidence=NEEDS_BROWSER,
                       selector="html > body > button", snippet=snippet,
                       source="https://site/", engine="static",
                       details={"declared": "width=16px"})
        payload = json.loads(_payload("violation", {"minSize": 24, "width": 16,
                                                    "height": 16}))
        payload["violations"][0]["nodes"][0]["html"] = snippet
        measured = issues_from_axe(json.dumps(payload), "https://site/")
        kept = deduplicate([static, *measured], markup=f"<body>{snippet}</body>")
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0].confidence, EXACT)
        self.assertEqual(kept[0].details["width"], 16)
        self.assertIn("axe", kept[0].details["also_found_by"])


class Explanation(unittest.TestCase):
    def test_every_language_names_the_measured_numbers(self):
        from audit.browser import issues_from_axe
        from audit.explanations import render

        issue = issues_from_axe(_payload(
            "violation", {"minSize": 24, "width": 16, "height": 16,
                          "closestOffset": 8, "minOffset": 24},
            related=["#tiny2"]), "https://site/")[0]
        for lang in ("uk", "it", "en"):
            with self.subTest(lang=lang):
                text = render(issue, lang)
                self.assertFalse(text.title.startswith("a11y_"))
                self.assertIn("16×16", text.found)
                self.assertIn("#tiny2", text.found)
                self.assertIn("2.5.8", text.why)
                self.assertTrue(text.fix)


if __name__ == "__main__":
    unittest.main()
