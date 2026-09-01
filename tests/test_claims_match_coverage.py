"""What the README says it handles is what the suite proves it handles.

The rule this file exists for: *what we do not have, we do not claim.* A
support list is the easiest thing in a project to write once and never check
again, and a tool whose README names a framework it has never been measured
against is telling the reader something it does not know.

So the list is not maintained by hand in three languages. Each README's
technology list is compared against the fixture directories, and each stack
list against `project_profile.STACKS`. Adding a framework to a README without
adding the pair of fixtures that proves it fails here, in every language.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import project_profile

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "frameworks"
READMES = ("README.md", "README_ua.md", "README_it.md")

#: The heading each list sits under, per language.
_TEMPLATE_HEADINGS = {
    "README.md": "## Templates it understands",
    "README_ua.md": "## Шаблони, які він розуміє",
    "README_it.md": "## Template che comprende",
}
_STACK_HEADINGS = {
    "README.md": "## Stacks it recognises",
    "README_ua.md": "## Стеки, які він розпізнає",
    "README_it.md": "## Stack che riconosce",
}


def _covered_technologies() -> set:
    return {p.name for p in FIXTURES.iterdir() if p.is_dir()}


def _flat(text: str) -> str:
    """One line, so a phrase can be looked for without guessing where the
    markdown wrapped it."""
    return " ".join(text.split())


def _listed(readme: str, heading: str) -> set:
    text = (ROOT / readme).read_text(encoding="utf-8")
    start = text.find(heading)
    if start == -1:
        return set()
    body = text[start:start + 3000]
    # The list is the first backtick-quoted run of comma-separated names.
    # Hyphens included: a stack name can carry one (`wordpress-theme`), and
    # a pattern that stopped at the hyphen read half a name and reported the
    # README as wrong when it was right.
    match = re.search(r"`([a-z0-9-]+(?:`, `[a-z0-9-]+)+)`", body)
    return set(match.group(1).split("`, `")) if match else set()


class TheTemplateListIsMeasured(unittest.TestCase):
    def test_every_readme_lists_exactly_what_has_fixtures(self):
        covered = _covered_technologies()
        for readme in READMES:
            with self.subTest(readme=readme):
                listed = _listed(readme, _TEMPLATE_HEADINGS[readme])
                self.assertTrue(listed, f"{readme} has no template list")
                self.assertEqual(
                    listed, covered,
                    f"{readme} claims {sorted(listed - covered)} with no "
                    f"fixture, and omits {sorted(covered - listed)}")

    def test_the_claim_is_not_empty(self):
        self.assertGreaterEqual(len(_covered_technologies()), 14)


class TheStackListIsTheCode(unittest.TestCase):
    def test_every_readme_lists_exactly_the_detected_stacks(self):
        known = {stack.name for stack in project_profile.STACKS}
        for readme in READMES:
            with self.subTest(readme=readme):
                listed = _listed(readme, _STACK_HEADINGS[readme])
                self.assertTrue(listed, f"{readme} has no stack list")
                self.assertEqual(
                    listed, known,
                    f"{readme} claims {sorted(listed - known)} that nothing "
                    f"detects, and omits {sorted(known - listed)}")

    def test_no_stack_is_named_twice(self):
        names = [stack.name for stack in project_profile.STACKS]
        self.assertEqual(len(names), len(set(names)))


class ACategoryWithNoRulesIsNotACategory(unittest.TestCase):
    """The claim that would have caught `security` sitting empty.

    It was in `CATEGORIES`, it appeared in `--category`'s choices, and it had
    **zero** rules registered against it. `audit.repo_facts` filed a committed
    `.env` there and nothing else ever did, so the word in a report meant "one
    repository check ran" rather than "the markup was read for this".
    """

    def _counts(self) -> dict:
        import audit  # noqa: F401 - registers the rules
        from audit.base import RuleRegistry

        counts: dict = {}
        for rule in RuleRegistry.all_rules():
            counts[rule.category] = counts.get(rule.category, 0) + 1
        return counts

    def test_every_offered_category_has_rules_in_it(self):
        from audit.base import CATEGORIES

        counts = self._counts()
        for category in CATEGORIES:
            with self.subTest(category=category):
                self.assertGreater(
                    counts.get(category, 0), 0,
                    f"`{category}` is offered to the user and nothing checks it")

    def test_each_readme_counts_the_rules_it_claims(self):
        """A number in a README is a claim like any other."""
        counts = self._counts()
        for readme in READMES:
            with self.subTest(readme=readme):
                text = _flat((ROOT / readme).read_text(encoding="utf-8"))
                for category, number in counts.items():
                    self.assertIn(f"`{category}` ({number})", text,
                                  f"{readme} does not say {category} has "
                                  f"{number} rules")


class TheHonestyIsWrittenDown(unittest.TestCase):
    """Each list has to say what it does *not* cover, in every language.

    A list of supported things without that sentence reads as a list of all
    things, which is the claim this file exists to prevent.
    """

    _CAVEAT = {
        "README.md": "not on this list is still read",
        "README_ua.md": "поза цим списком він усе одно читає",
        "README_it.md": "non elencata viene comunque letto",
    }

    def test_each_readme_says_what_is_unmeasured(self):
        for readme, phrase in self._CAVEAT.items():
            with self.subTest(readme=readme):
                text = _flat((ROOT / readme).read_text(encoding="utf-8"))
                self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
