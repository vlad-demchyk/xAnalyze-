"""What a run says it is about to leave undone.

Two of the most useful things this tool can do were never defaults and were
never mentioned: pairing a site with the repository behind it (`--repo`), so
a finding names a file instead of a page, and letting a repository serve
itself (`--devserver`), so the rules that need a rendered page can run at
all. A person who does not know the flag exists gets the shallow answer and
no reason to suspect a deeper one.

So the run says so before it starts. A notice and not a prompt: a scan that
blocks on a question cannot be put in a pipeline, and an agent driving the
CLI needs a line it can match on rather than an interactive dialogue.
"""
import argparse
import io
import tempfile
import unittest
from pathlib import Path

from cli_impl import prerun


def _args(**kwargs):
    base = dict(repo=None, devserver=False, url=False, no_browser=False,
                breakpoints=None, no_hints=False)
    base.update(kwargs)
    return argparse.Namespace(**base)


class ASiteWithNoRepositoryBehindIt(unittest.TestCase):

    def test_the_missing_pairing_is_named_with_the_flag_that_fixes_it(self):
        lines = prerun.hints("fullscan", "https://x.test/", _args(),
                             is_url=True)
        self.assertTrue(any("--repo" in line for line in lines))
        self.assertTrue(all(line.startswith(prerun.PREFIX) for line in lines))

    def test_a_run_that_already_has_one_is_not_told_about_it(self):
        lines = prerun.hints("fullscan", "https://x.test/",
                             _args(repo="/repo"), is_url=True)
        self.assertFalse(any("--repo" in line for line in lines))


class ARepositoryThatCouldServeItself(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_a_node_project_is_told_it_can_be_rendered(self):
        (self.root / "package.json").write_text("{}", encoding="utf-8")
        lines = prerun.hints("scan", str(self.root), _args(), is_url=False)
        self.assertTrue(any("--devserver" in line for line in lines))
        self.assertTrue(any("node" in line for line in lines))

    def test_the_hint_says_which_way_round_the_dependencies_are(self):
        (self.root / "package.json").write_text("{}", encoding="utf-8")
        without = prerun.hints("scan", str(self.root), _args(), is_url=False)
        (self.root / "node_modules").mkdir()
        with_deps = prerun.hints("scan", str(self.root), _args(), is_url=False)
        self.assertIn("--devserver --yes", without[0])
        self.assertNotIn("--yes", with_deps[0])

    def test_a_folder_that_serves_nothing_is_left_alone(self):
        (self.root / "notes.md").write_text("x", encoding="utf-8")
        self.assertEqual(prerun.hints("scan", str(self.root), _args(),
                                      is_url=False), [])

    def test_a_run_that_already_asked_for_it_is_not_told(self):
        (self.root / "package.json").write_text("{}", encoding="utf-8")
        self.assertEqual(
            prerun.hints("scan", str(self.root), _args(devserver=True),
                         is_url=False), [])


class WhatTheAuditIsAboutToSkip(unittest.TestCase):

    def test_no_browser_is_said_out_loud(self):
        lines = prerun.hints("audit", "https://x.test/",
                             _args(no_browser=True, repo="/repo"), is_url=True)
        self.assertTrue(any("axe" in line for line in lines))

    def test_the_default_single_width_is_said_too(self):
        lines = prerun.hints("audit", "https://x.test/", _args(repo="/repo"),
                             is_url=True)
        self.assertTrue(any("--breakpoints all" in line for line in lines))

    def test_a_run_at_every_width_is_not_told_about_widths(self):
        lines = prerun.hints("audit", "https://x.test/",
                             _args(repo="/repo", breakpoints="all"),
                             is_url=True)
        self.assertEqual(lines, [])

    def test_a_plain_scan_is_not_told_about_a_browser_it_never_had(self):
        with tempfile.TemporaryDirectory() as tmp:
            lines = prerun.hints("scan", tmp, _args(no_browser=True),
                                 is_url=False)
        self.assertFalse(any("axe" in line for line in lines))


class Silence(unittest.TestCase):

    def test_no_hints_means_no_hints(self):
        self.assertEqual(
            prerun.hints("fullscan", "https://x.test/", _args(no_hints=True),
                         is_url=True), [])

    def test_announce_writes_what_it_returns(self):
        out = io.StringIO()
        lines = prerun.announce("fullscan", "https://x.test/", _args(),
                                is_url=True, out=out)
        self.assertEqual(out.getvalue().count(prerun.PREFIX), len(lines))


if __name__ == "__main__":
    unittest.main()
