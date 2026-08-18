"""Writing an audit correction back into a file.

This is the one part of the tool that changes someone's source, so the tests
below are less about "does it work" than about the three ways it could quietly
do harm: editing the wrong element, writing a value nobody chose, and leaving
a file it cannot put back.
"""
import os
import tempfile
import unittest

import audit
from audit import fixer


class FixerTestCase(unittest.TestCase):

    def write(self, markup: str) -> str:
        handle, path = tempfile.mkstemp(suffix=".html")
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            out.write(markup)
        self.addCleanup(self._cleanup, path)
        return path

    def _cleanup(self, path):
        for candidate in (path, path + ".bak"):
            if os.path.exists(candidate):
                os.unlink(candidate)

    def plan(self, markup: str):
        path = self.write(markup)
        result = audit.analyze_page_file(path)
        ready, pending, skipped = fixer.plan_fixes(result.documents)
        return path, ready, pending, skipped

    def read(self, path: str) -> str:
        with open(path, encoding="utf-8") as handle:
            return handle.read()


class TargetingTests(FixerTestCase):

    def test_the_right_image_is_corrected_when_a_line_holds_several(self):
        """The finding's line narrows the search; its attributes decide it.
        Without the second step, three images on one line would all resolve to
        the first."""
        path, ready, _pending, _skipped = self.plan(
            '<html lang="en"><head><meta charset="utf-8"><title>Three images here</title>'
            '</head><body><h1>x</h1>'
            '<img src="a.png" alt="a"><img src="b.png"><img src="c.png" alt="c">'
            '</body></html>')
        plans = [p for p in ready if p.rule_id == "bp-target-blank"]
        self.assertEqual(plans, [])  # nothing to do here; the point is below
        result = audit.analyze_page_file(path)
        issues = [i for i in result.issues() if i.rule_id == "image-alt"]
        self.assertEqual(len(issues), 1)
        _r, pending, _s = fixer.plan_fixes(result.documents)
        plan = next(p for p in pending if p.rule_id == "image-alt")
        self.assertEqual(plan.original, '<img src="b.png">')

    def test_an_element_that_moved_since_the_audit_is_refused(self):
        path, ready, _p, _s = self.plan(
            '<html lang="en"><head><title>A page about nothing at all</title></head>'
            '<body><h1>x</h1><a href="http://x.test" target="_blank">l</a></body></html>')
        plan = next(p for p in ready if p.rule_id == "bp-target-blank")
        with open(path, "w", encoding="utf-8") as out:
            out.write("<html><body>completely different</body></html>")
        outcome = fixer.apply_fixes([plan])
        self.assertEqual(outcome.applied, [])
        self.assertTrue(any("changed after the audit" in s.reason
                            for s in outcome.skipped))


class WhatMayBeWrittenTests(FixerTestCase):

    def test_a_decision_is_never_written_unattended(self):
        """`alt=""` says the image is decorative. Applying that to a
        photograph hides its meaning, and hides it from the next audit too."""
        _path, ready, pending, _skipped = self.plan(
            '<html lang="en"><head><meta charset="utf-8">'
            '<title>A page with one picture on it</title></head>'
            '<body><h1>x</h1><img src="hero.jpg"></body></html>')
        self.assertNotIn("image-alt", [p.rule_id for p in ready])
        held = next(p for p in pending if p.rule_id == "image-alt")
        self.assertIn("decorative", held.needs_input)

    def test_a_placeholder_is_never_written_unattended(self):
        _path, ready, pending, _skipped = self.plan(
            '<html lang="en"><head><meta charset="utf-8"><title>Short page here</title>'
            '</head><body><h1>x</h1><p>Words.</p></body></html>')
        self.assertNotIn("seo-meta-description", [p.rule_id for p in ready])
        held = next(p for p in pending if p.rule_id == "seo-meta-description")
        self.assertIn("placeholder", held.needs_input)

    def test_apply_refuses_a_plan_that_still_needs_input(self):
        """A last line of defence, not a check the caller can forget."""
        plan = fixer.FixPlan(path="x.html", start=0, end=0, original="",
                             replacement='<meta content="…">', rule_id="r",
                             needs_input="needs real text")
        outcome = fixer.apply_fixes([plan])
        self.assertEqual(outcome.applied, [])
        self.assertEqual(len(outcome.skipped), 1)

    def test_a_page_on_the_web_has_no_file_to_write(self):
        from audit.engine import AccessibilityResult, DocumentReport

        result = AccessibilityResult(root="https://x.test", mode="web")
        result.documents.append(DocumentReport(source="https://x.test/a"))
        result.documents[0].issues = audit.analyze_document(
            "<html><body><img src='a.png'></body></html>", "https://x.test/a").issues
        ready, pending, skipped = fixer.plan_fixes(result.documents)
        self.assertEqual(ready + pending, [])
        self.assertTrue(all("not a file on disk" in s.reason for s in skipped))


class WritingTests(FixerTestCase):

    MARKUP = ('<html>\n<head>\n<title>A page that needs a little work</title>\n'
              '</head>\n<body>\n<h1>Title</h1>\n<h3>Jumped</h3>\n'
              '<a href="http://x.test" target="_blank">l</a>\n</body>\n</html>\n')

    def test_corrections_are_written_and_the_findings_go_away(self):
        path, ready, _pending, _skipped = self.plan(self.MARKUP)
        before = audit.analyze_page_file(path).counts()
        fixer.apply_fixes(ready)
        after = audit.analyze_page_file(path).counts()
        self.assertLess(sum(after.values()), sum(before.values()))
        self.assertIn("<!DOCTYPE html>", self.read(path))
        self.assertIn("<h2>Jumped</h2>", self.read(path))
        self.assertIn('rel="noopener noreferrer"', self.read(path))

    def test_an_insert_and_a_replace_at_the_same_offset_both_survive(self):
        """A missing doctype and an `<html>` without a language both start at
        byte zero. Applied in the wrong order, one silently loses."""
        path, ready, _pending, _skipped = self.plan(self.MARKUP)
        from audit import fix_ai

        filled, _left = fix_ai.fill_locally(
            [p for p in _pending if p.rule_id == "html-lang"], "English words here")
        fixer.apply_fixes(ready + filled)
        text = self.read(path)
        self.assertTrue(text.startswith("<!DOCTYPE html>"))
        self.assertIn("<html lang=", text)

    def test_the_first_backup_is_the_one_kept(self):
        """Two runs must still be able to return to the original file, not to
        the state between them."""
        path, ready, _p, _s = self.plan(self.MARKUP)
        original = self.read(path)
        fixer.apply_fixes(ready)
        _r2, _p2, _s2 = fixer.plan_fixes(audit.analyze_page_file(path).documents)
        fixer.apply_fixes(_r2)
        self.assertEqual(self.read(path + ".bak"), original)

    def test_undo_returns_the_file_exactly(self):
        path, ready, _p, _s = self.plan(self.MARKUP)
        original = self.read(path)
        fixer.apply_fixes(ready)
        self.assertNotEqual(self.read(path), original)
        restored, problems = fixer.restore([path])
        self.assertEqual(restored, [path])
        self.assertEqual(problems, [])
        self.assertEqual(self.read(path), original)

    def test_undo_says_so_when_there_is_nothing_to_go_back_to(self):
        path = self.write(self.MARKUP)
        restored, problems = fixer.restore([path])
        self.assertEqual(restored, [])
        self.assertIn("no backup", problems[0])


if __name__ == "__main__":
    unittest.main()
