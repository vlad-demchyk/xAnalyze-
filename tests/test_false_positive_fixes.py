"""Findings that were wrong, measured on a run over sixteen real targets.

Ten live sites and six repositories produced 3348 findings, and reading the
top rules by volume is what turned four of them into defects rather than
opinions. Each test here is the failing case that measurement found.
"""
import subprocess
import unittest
from pathlib import Path

import audit.rules  # noqa: F401 - registers the rules
from audit import repo_facts
from audit.engine import SKIP_AUDIT_DIRS, analyze_document


def _rules_of(markup: str, source: str = "https://example.test/page") -> list:
    return [i.rule_id for i in analyze_document(markup, source).issues]


class AbbreviationsAreWordsNotSubstrings(unittest.TestCase):
    """446 findings, and the words were not abbreviations.

    `"UI" in text` matched "building" and "guide", `PR` matched "PRODUCT",
    `HR` matched "THROUGH". The rule also carried a comment promising one
    finding per page per abbreviation and had never done it.
    """

    def test_a_word_that_merely_contains_the_letters_is_not_an_abbreviation(self):
        markup = ("<html><body><p>We are building a guide through PRODUCT "
                  "pages for our users.</p></body></html>")
        self.assertNotIn("abbreviation-expansion", _rules_of(markup))

    def test_a_real_abbreviation_still_reports(self):
        markup = "<html><body><p>The API is documented.</p></body></html>"
        self.assertIn("abbreviation-expansion", _rules_of(markup))

    def test_the_same_abbreviation_reports_once_per_document(self):
        markup = ("<html><body><p>The API is here.</p><p>The API is there.</p>"
                  "<p>And the API again.</p></body></html>")
        found = [r for r in _rules_of(markup) if r == "abbreviation-expansion"]
        self.assertEqual(len(found), 1)


class TargetBlankIsAboutSomebodyElsesPage(unittest.TestCase):
    """325 findings, 144 of them at the page's own host.

    The risk is that the opened page steers the tab that opened it. A page
    opening its own site cannot be that attacker without already being one.
    """

    def test_a_link_to_the_same_host_is_not_a_finding(self):
        markup = ('<html><body><a href="https://example.test/about" '
                  'target="_blank">About</a></body></html>')
        self.assertNotIn("bp-target-blank", _rules_of(markup))

    def test_a_relative_link_is_not_a_finding(self):
        markup = '<html><body><a href="/about" target="_blank">About</a></body></html>'
        self.assertNotIn("bp-target-blank", _rules_of(markup))

    def test_a_cross_origin_link_still_reports(self):
        markup = ('<html><body><a href="https://elsewhere.test/x" '
                  'target="_blank">Out</a></body></html>')
        self.assertIn("bp-target-blank", _rules_of(markup))

    def test_rel_noopener_answers_it(self):
        markup = ('<html><body><a href="https://elsewhere.test/x" target="_blank" '
                  'rel="noopener">Out</a></body></html>')
        self.assertNotIn("bp-target-blank", _rules_of(markup))


class IntegrityIsAboutSomebodyElsesScript(unittest.TestCase):
    """61 of 162 findings were the site's own asset subdomain."""

    def test_an_asset_subdomain_of_the_page_is_the_page(self):
        markup = ('<html><head><script src="https://assets.example.test/a.js">'
                  '</script></head></html>')
        self.assertNotIn("sec-script-integrity",
                         _rules_of(markup, "https://www.example.test/"))

    def test_a_genuinely_foreign_script_still_reports(self):
        markup = ('<html><head><script src="https://cdn.other.test/a.js">'
                  '</script></head></html>')
        self.assertIn("sec-script-integrity",
                      _rules_of(markup, "https://www.example.test/"))


class FixturesAreNotTheProject(unittest.TestCase):
    def test_the_two_modules_agree_on_what_a_fixture_directory_is(self):
        import project_profile

        for name in ("fixtures", "__fixtures__", "testdata"):
            self.assertIn(name, SKIP_AUDIT_DIRS)
            self.assertIn(name, project_profile._MARKER_BLIND)


class GitCouldNotLookIsNotAnAnswer(unittest.TestCase):
    """A `serious` credential finding produced by a race.

    An audit that ran while a commit held `index.lock` reported this
    repository's ignored `.env.e2e.local` as unignored, and the next run did
    not. `git check-ignore` speaks through its exit code - 0 ignored, 1 not
    ignored, anything else "I could not look" - and the third was being read
    as the second.
    """

    def _repo(self) -> Path:
        import tempfile

        root = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init", "-q", str(root)], check=True,
                       capture_output=True)
        (root / ".gitignore").write_text(".env.*\n", encoding="utf-8")
        (root / ".env.local").write_text("SECRET=1\n", encoding="utf-8")
        return root

    def test_an_ignored_env_file_is_not_reported(self):
        facts = repo_facts.read_facts(self._repo())
        self.assertEqual(facts.exposed_env, [])

    def test_the_exit_codes_are_what_the_fix_rests_on(self):
        root = self._repo()
        self.assertEqual(
            repo_facts._git_status(root, "check-ignore", "-q", "--", ".env.local"), 0)
        self.assertEqual(
            repo_facts._git_status(root, "check-ignore", "-q", "--", "README.md"), 1)
        # No path at all: git refuses, and that must not read as "not ignored".
        self.assertNotIn(
            repo_facts._git_status(root, "check-ignore", "-q", "--"), (0, 1))

    def test_an_unanswerable_check_stays_quiet_and_says_why(self):
        facts = repo_facts.RepoFacts()
        facts.is_git = True
        quiet = repo_facts._git_ignores(Path("/nonexistent-repo-xyz"),
                                        ".env.local", facts)
        self.assertTrue(quiet)
        self.assertTrue(facts.git_unavailable)


if __name__ == "__main__":
    unittest.main()
