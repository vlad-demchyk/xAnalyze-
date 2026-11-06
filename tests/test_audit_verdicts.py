"""The audit rules agree with the checked verdicts in corpus/ (T-1963).

A true verdict must be reported at the rule's own weight; a false one must
stay silent or come out lowered to a note. A rule change that moves either
fails here, by name, before a crawl finds it.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from audit import verdicts as V


class TheRulesAgreeWithTheVerdicts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verdicts = V.load()

    def test_every_verdict_holds(self):
        for verdict in self.verdicts:
            with self.subTest(verdict.id):
                got = [(i.severity, i.confidence) for i in V.findings(verdict)]
                self.assertTrue(
                    V.holds(verdict),
                    f"{verdict.id}: verdict {verdict.verdict} ({verdict.reason}), "
                    f"rule gave {got or 'nothing'}")

    def test_every_weighty_rule_has_a_true_and_a_false_example(self):
        """Serious and critical rules cost most when wrong, in either
        direction - so each is held to both a real defect and a near miss."""
        cover = V.coverage(self.verdicts)
        for rule in V.weighty_rules():
            with self.subTest(rule):
                counts = cover.get(rule, {"true": 0, "false": 0})
                self.assertGreaterEqual(counts["true"], 1, f"{rule}: no true example")
                self.assertGreaterEqual(counts["false"], 1, f"{rule}: no false example")

    def test_every_verdict_names_a_rule_that_exists(self):
        import audit.engine  # noqa: F401 - registers every rule
        from audit.base import RuleRegistry

        known = set(RuleRegistry.available())
        for verdict in self.verdicts:
            if verdict.engine == V.STATIC:
                with self.subTest(verdict.id):
                    self.assertIn(verdict.rule, known)

    def test_the_corpus_carries_no_secrets_or_contact_data(self):
        """Markup shapes only: a verdict never needs a client's data."""
        import re

        text = V.CORPUS.read_text(encoding="utf-8")
        for pattern in (r"[\w.+-]+@(?!example\.)[\w-]+\.[a-z]{2,}",  # email
                        r"\bsk_live_\w+", r"\bAKIA[0-9A-Z]{16}\b",
                        r"Bearer\s+[\w.-]{20,}", r"\+?\d[\d ]{8,}\d"):
            with self.subTest(pattern):
                self.assertIsNone(re.search(pattern, text))


class TheFileFormat(unittest.TestCase):
    def _load(self, *records):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False,
                                         encoding="utf-8") as handle:
            for record in records:
                handle.write((record if isinstance(record, str)
                              else json.dumps(record)) + "\n")
        self.addCleanup(Path(handle.name).unlink)
        return V.load(Path(handle.name))

    BASE = {"id": "a", "rule": "image-alt", "engine": "static", "verdict": True,
            "reason": "r", "source": "s", "date": "2026-11-06", "html": "<img>"}

    def test_comments_and_blank_lines_are_skipped(self):
        self.assertEqual(len(self._load("// note", "", self.BASE)), 1)

    def test_a_missing_field_is_refused(self):
        record = dict(self.BASE)
        del record["reason"]
        with self.assertRaisesRegex(ValueError, "missing reason"):
            self._load(record)

    def test_a_duplicate_id_is_refused(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self._load(self.BASE, self.BASE)

    def test_a_verdict_must_be_a_boolean(self):
        with self.assertRaisesRegex(ValueError, "true or false"):
            self._load(dict(self.BASE, verdict="yes"))

    def test_a_lowered_finding_counts_as_not_reported(self):
        """The weight is the rule's own: lowered to advisory is a note."""
        verdict = V.Verdict(id="x", rule="image-alt-filename", engine="static",
                            verdict=False, reason="", source="", date="",
                            html='<img src="/a/hero-banner-big.jpg" alt="hero-banner-big-two">')
        found = V.findings(verdict)
        self.assertTrue(found and all(i.confidence == "advisory" for i in found))
        self.assertFalse(V.reported(verdict))


if __name__ == "__main__":
    unittest.main()
