"""What a repository reveals about itself.

Three questions, one method: none of them judges anything. Each reads a fact
that is either present or absent, the way `unicode_rules` reads a zero-width
character - which is the whole argument for this module existing next to a
pile of classifiers.

The distinctions that have to survive:

**Written with an assistant is not a defect.** It is reported as provenance,
MINOR, with an explanation that says so, because a tool that files it as a
problem is telling people how to work. The reason to report it at all is
that the repository has been keeping an exact answer to "who wrote this" in
plain text the whole time, while every detector in this project is guessing
at it.

**A published secret and an unpublished one need opposite advice.** A `.env`
git already tracks is in every clone: deleting it changes nothing, and the
only useful sentence is "rotate those credentials". One that is merely
sitting there unignored has not leaked yet, and `.gitignore` still helps.
Filing both as one finding would give half of them advice that leaves the
secret where it is.

**Silence beats a guess.** A folder that is not a git repository produces no
commit findings, because "no assistant commits found" and "no history to
look at" are opposite statements and only one of them is true.
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

import audit
from audit import repo_facts
from audit.explanations import render


def git(root: Path, *args: str) -> None:
    subprocess.run(("git", "-C", str(root)) + args, capture_output=True,
                   check=False, timeout=30)


class Repo(unittest.TestCase):
    """A real git repository per test - the thing under test is what git
    says, so a fake would be testing the fake."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def make_git(self) -> None:
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@example.test")
        git(self.root, "config", "user.name", "T")

    def write(self, rel: str, text: str = "x") -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def commit(self, message: str, *paths: str) -> None:
        for rel in paths or ("-A",):
            git(self.root, "add", "-f", rel)
        git(self.root, "commit", "-q", "-m", message)

    def facts(self):
        return repo_facts.read_facts(self.root)

    def findings(self):
        return [doc.issues[0]
                for doc in repo_facts.as_documents(self.facts(), str(self.root))]

    def rules(self) -> list:
        return [issue.rule_id for issue in self.findings()]


class WhoWroteIt(Repo):
    def test_a_co_authored_commit_is_recorded(self):
        self.make_git()
        self.write("a.txt")
        self.commit("feat: a\n\nCo-Authored-By: Claude <noreply@anthropic.com>")
        facts = self.facts()
        self.assertEqual(len(facts.assistant_commits), 1)

    def test_an_ordinary_commit_is_not(self):
        self.make_git()
        self.write("a.txt")
        self.commit("feat: a")
        self.assertEqual(self.facts().assistant_commits, [])

    def test_a_person_mentioning_a_tool_in_prose_is_not_a_co_author(self):
        """"reviewed claude's suggestion" is a sentence about somebody's
        process and nobody else's business."""
        self.make_git()
        self.write("a.txt")
        self.commit("fix: reviewed claude's suggestion and kept ours")
        self.assertEqual(self.facts().assistant_commits, [])

    def test_it_is_reported_as_provenance_and_not_as_a_problem(self):
        self.make_git()
        self.write("a.txt")
        self.commit("feat: a\n\nCo-Authored-By: Claude <noreply@anthropic.com>")
        issue = next(i for i in self.findings()
                     if i.rule_id == repo_facts.RULE_ASSISTANT_COMMITS)
        self.assertEqual(issue.severity, "minor")
        self.assertEqual(issue.category, "best-practices")
        self.assertIn("not a defect", render(issue, "en").why.lower())

    def test_a_folder_with_no_history_says_nothing_about_commits(self):
        """"No assistant commits found" and "no history to look at" are
        opposite statements, and reporting the second as the first is how a
        tool comes to sound certain about something it never looked at."""
        self.write("a.txt")
        facts = self.facts()
        self.assertFalse(facts.is_git)
        self.assertEqual(facts.assistant_commits, [])
        self.assertTrue(facts.git_unavailable)
        self.assertNotIn(repo_facts.RULE_ASSISTANT_COMMITS, self.rules())


class WhatTheAssistantsLeftBehind(Repo):
    def test_a_claude_file_is_found(self):
        self.write("CLAUDE.md", "context")
        self.assertIn("CLAUDE.md", self.facts().tool_artifacts)

    def test_a_tool_folder_is_found(self):
        self.write(".cursor/rules", "x")
        self.assertIn(".cursor/", self.facts().tool_artifacts)

    def test_a_project_with_none_reports_none(self):
        self.write("src/main.py", "print(1)")
        self.assertEqual(self.facts().tool_artifacts, [])
        self.assertNotIn(repo_facts.RULE_TOOL_ARTIFACTS, self.rules())

    def test_the_reason_given_is_the_one_that_matters(self):
        """Not "you have AI files" - they are harmless and often useful. The
        reason to look is that they hold project context written for a tool
        and not for a reader."""
        self.write("CLAUDE.md", "context")
        issue = next(i for i in self.findings()
                     if i.rule_id == repo_facts.RULE_TOOL_ARTIFACTS)
        self.assertIn("published", render(issue, "en").fix.lower())


class WhatIsAboutToLeak(Repo):
    def test_an_unignored_env_is_serious(self):
        self.make_git()
        self.write(".env", "SECRET=1")
        issue = next(i for i in self.findings()
                     if i.rule_id == repo_facts.RULE_ENV_EXPOSED)
        self.assertEqual(issue.severity, "serious")
        self.assertEqual(issue.category, "security")

    def test_a_tracked_env_is_critical_and_says_to_rotate(self):
        """It is in every clone. Deleting the file changes nothing, and a
        finding that said "remove it" would leave the secret where it is."""
        self.make_git()
        self.write(".env", "SECRET=1")
        self.commit("oops", ".env")
        issue = next(i for i in self.findings()
                     if i.rule_id == repo_facts.RULE_ENV_TRACKED)
        self.assertEqual(issue.severity, "critical")
        self.assertIn("rotate", render(issue, "en").fix.lower())

    def test_an_ignored_env_is_the_correct_arrangement_and_says_nothing(self):
        self.make_git()
        self.write(".gitignore", ".env\n")
        self.write(".env", "SECRET=1")
        self.assertEqual(self.facts().exposed_env, [])
        self.assertEqual(self.rules(), [])

    def test_an_example_file_is_the_convention_for_not_carrying_secrets(self):
        self.make_git()
        for rel in (".env.example", ".env.sample", ".env.template"):
            self.write(rel, "SECRET=")
        self.assertEqual(self.facts().exposed_env, [])

    def test_a_nested_env_is_found_too(self):
        self.make_git()
        self.write("services/api/.env.local", "K=1")
        self.assertIn("services/api/.env.local", self.facts().exposed_env)

    def test_a_file_merely_named_like_one_is_not_a_secret(self):
        self.make_git()
        self.write("environment.md", "notes")
        self.write("src/env.py", "x")
        self.assertEqual(self.facts().exposed_env, [])

    def test_the_projects_own_ignore_rules_are_honoured_too(self):
        """`repo_scanner`'s defaults keep the walk out of `node_modules/`,
        and a dependency's own `.env.example` is not this project's news."""
        self.make_git()
        self.write("node_modules/pkg/.env", "K=1")
        self.assertEqual(self.facts().exposed_env, [])


class GitNotAnswering(Repo):
    def test_a_git_that_cannot_run_is_absence_not_a_crash(self):
        from unittest import mock

        self.make_git()
        self.write(".env", "SECRET=1")
        with mock.patch("audit.repo_facts.subprocess.run",
                        side_effect=OSError("git is not installed")):
            facts = self.facts()
        self.assertFalse(facts.is_git)
        self.assertEqual(facts.assistant_commits, [])
        # The `.env` is still found: that part never needed git.
        self.assertEqual(facts.exposed_env, [".env"])

    def test_a_git_that_times_out_is_the_same_answer(self):
        from unittest import mock

        self.make_git()
        with mock.patch("audit.repo_facts.subprocess.run",
                        side_effect=subprocess.TimeoutExpired("git", 1)):
            self.assertFalse(self.facts().is_git)


class InTheAudit(Repo):
    def test_a_repository_audit_reads_them(self):
        self.make_git()
        self.write(".env", "SECRET=1")
        self.write("CLAUDE.md", "context")
        result = audit.analyze_files([], str(self.root), media=False)
        rules = {issue.rule_id for doc in result.documents for issue in doc.issues}
        self.assertIn(repo_facts.RULE_ENV_EXPOSED, rules)
        self.assertIn(repo_facts.RULE_TOOL_ARTIFACTS, rules)

    def test_a_caller_can_ask_for_the_markup_only(self):
        self.make_git()
        self.write(".env", "SECRET=1")
        result = audit.analyze_files([], str(self.root), media=False,
                                     repo_facts=False)
        self.assertEqual(result.documents, [])
        self.assertIsNone(result.repo)

    def test_the_result_carries_why_git_was_silent(self):
        """The difference between "no assistant commits" and "nothing to
        read" has to survive as far as the reader."""
        self.write(".env", "SECRET=1")
        result = audit.analyze_files([], str(self.root), media=False)
        self.assertTrue(result.repo.git_unavailable)

    def test_security_is_a_category_of_its_own(self):
        """A credential about to be published is not a best practice anyone
        departed from, and filing it as one states it too quietly."""
        from audit.base import CATEGORIES, SECURITY

        self.assertIn(SECURITY, CATEGORIES)
        self.make_git()
        self.write(".env", "SECRET=1")
        result = audit.analyze_files([], str(self.root), media=False)
        found = {i.category for d in result.documents for i in d.issues}
        self.assertIn(SECURITY, found)

    def test_every_finding_reads_as_a_sentence_in_every_language(self):
        self.make_git()
        self.write(".env", "SECRET=1")
        self.write("CLAUDE.md", "context")
        self.commit("feat: a\n\nCo-Authored-By: Claude <noreply@anthropic.com>",
                    "CLAUDE.md")
        for issue in self.findings():
            for lang in ("uk", "it", "en"):
                with self.subTest(rule=issue.rule_id, lang=lang):
                    explained = render(issue, lang)
                    for part in (explained.title, explained.found,
                                 explained.why, explained.fix):
                        self.assertNotIn("a11y_", part)
                        self.assertNotIn("{", part)


if __name__ == "__main__":
    unittest.main()
