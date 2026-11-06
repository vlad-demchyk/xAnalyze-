"""Precision per audit rule from a person's labels (T-1963)."""
from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from audit import precision as P
from audit.base import Issue


def _issue(rule, source="https://s.test/", snippet="<img>", **kw):
    return asdict(Issue(rule_id=rule, severity=kw.pop("severity", "serious"),
                        source=source, snippet=snippet, **kw))


def _audit(*issues, pages=()):
    return {"issues": list(issues),
            "coverage": {"documents": [{"source": p, "kind": "page", "reason": ""}
                                       for p in pages]}}


class TheFingerprintIsTheIgnoreFilesOne(unittest.TestCase):
    def test_a_label_and_an_ignore_entry_name_the_same_finding(self):
        import suppression

        issue = Issue(rule_id="image-alt", severity="critical",
                      source="https://s.test/a", snippet='<img  src="x">')
        self.assertEqual(P.finding_fingerprint(asdict(issue)),
                         suppression.issue_fingerprint(issue))


class Measuring(unittest.TestCase):
    def test_precision_needs_enough_labels_to_be_a_number(self):
        issues = [_issue("image-alt", snippet=f"<img id={i}>") for i in range(4)]
        labels = {P.finding_fingerprint(i): True for i in issues}
        row, = P.measure([_audit(*issues)], labels)
        self.assertEqual((row.found, row.labelled), (4, 4))
        self.assertIsNone(row.precision)
        self.assertIn("not measured (n=4", P.render([row]))

    def test_true_over_labelled(self):
        issues = [_issue("image-alt", snippet=f"<img id={i}>") for i in range(10)]
        labels = {P.finding_fingerprint(i): n < 6 for n, i in enumerate(issues[:8])}
        row, = P.measure([_audit(*issues)], labels)
        self.assertEqual((row.found, row.true, row.false), (10, 6, 2))
        self.assertAlmostEqual(row.precision, 0.75)
        self.assertIn("75% (n=8)", P.render([row]))

    def test_the_same_finding_in_two_audits_counts_once(self):
        one = _issue("image-alt")
        row, = P.measure([_audit(one), _audit(dict(one))], {})
        self.assertEqual(row.found, 1)

    def test_the_least_precise_measured_rule_comes_first(self):
        good = [_issue("a-good", snippet=f"<i {n}>") for n in range(5)]
        bad = [_issue("b-bad", snippet=f"<i {n}>") for n in range(5)]
        labels = {P.finding_fingerprint(i): True for i in good}
        labels.update({P.finding_fingerprint(i): False for i in bad})
        rows = P.measure([_audit(*good, *bad, _issue("c-unlabelled"))], labels)
        self.assertEqual([r.rule for r in rows], ["b-bad", "a-good", "c-unlabelled"])

    def test_a_rule_on_every_page_is_pointed_out(self):
        pages = ["https://s.test/a", "https://s.test/b", "https://s.test/c"]
        rows = P.measure([_audit(*[_issue("skip-link", source=p) for p in pages],
                                 pages=pages)], {})
        self.assertIn("fires on every one of 3 pages", P.render(rows, pages=3))


class TheLabelFile(unittest.TestCase):
    def test_the_template_keeps_labels_already_given(self):
        first, second = _issue("image-alt"), _issue("control-name", snippet="<button>")
        labels = {P.finding_fingerprint(first): False}
        records = P.template_records([_audit(first, second)], labels)
        self.assertEqual([r["verdict"] for r in records], [False, None])

    def test_unlabelled_lines_are_skipped_and_bad_ones_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "labels.jsonl"
            path.write_text("\n".join([
                json.dumps({"fingerprint": "a", "verdict": True}),
                json.dumps({"fingerprint": "b", "verdict": None}),
                "// a comment",
            ]), encoding="utf-8")
            self.assertEqual(P.load_labels(path), {"a": True})
            path.write_text(json.dumps({"fingerprint": "a", "verdict": "yes"}),
                            encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "true, false or null"):
                P.load_labels(path)

    def test_the_command_writes_a_template_then_measures(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "a.json"
            audit.write_text(json.dumps(_audit(_issue("image-alt"))), encoding="utf-8")
            labels = Path(tmp) / "labels.jsonl"
            self.assertEqual(P.main([str(audit), "--template", str(labels)]), 0)
            record = json.loads(labels.read_text(encoding="utf-8"))
            self.assertIsNone(record["verdict"])
            self.assertEqual(P.main([str(audit), "--labels", str(labels)]), 0)


if __name__ == "__main__":
    unittest.main()
