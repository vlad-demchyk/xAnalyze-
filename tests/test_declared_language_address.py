"""The declared language against what the site itself says about the page.

`html-lang-mismatch` asks the text, and a detector only knows the languages
it was taught: a German page comes back `other` and that rule stays silent by
design. So a whole site can serve every page with the wrong `lang` and no
rule notices - the case a real audit found on a three-language site, sixty-five
pages of sixty-five declaring `lang="it"`.

These tests are about the shape of the evidence rather than about German:
what the rule must say, and - the longer half - what it must stay silent
about, because a rule that guesses here is worse than no rule.
"""
import unittest

from audit.engine import analyze_document

RULE = "html-lang-contradicts-address"


def rules_for(markup: str, source: str) -> set:
    return {i.rule_id for i in analyze_document(markup, source).issues}


def page(lang: str, head: str = "") -> str:
    return (f'<html lang="{lang}"><head>{head}</head>'
            f'<body><p>Text</p></body></html>')


OG_DE = '<meta property="og:locale" content="de_DE">'


class TwoSourcesAgreeAgainstTheAttribute(unittest.TestCase):

    def test_path_prefix_and_open_graph_outvote_the_attribute(self):
        self.assertIn(RULE, rules_for(
            page("it", OG_DE), "https://example.com/de/eventi/"))

    def test_subdomain_and_open_graph_outvote_the_attribute(self):
        self.assertIn(RULE, rules_for(
            page("it", OG_DE), "https://de.example.com/eventi/"))

    def test_query_parameter_and_open_graph_outvote_the_attribute(self):
        self.assertIn(RULE, rules_for(
            page("it", OG_DE), "https://example.com/eventi/?lang=de"))

    def test_path_prefix_and_self_hreflang_outvote_the_attribute(self):
        head = ('<link rel="alternate" hreflang="de" '
                'href="https://example.com/de/eventi/">')
        self.assertIn(RULE, rules_for(
            page("it", head), "https://example.com/de/eventi/"))

    def test_the_finding_names_the_language_to_use(self):
        issues = [i for i in analyze_document(
            page("it", OG_DE), "https://example.com/de/eventi/").issues
            if i.rule_id == RULE]
        self.assertEqual(issues[0].details["expected"], "de")
        self.assertEqual(issues[0].details["declared"], "it")


class OneSourceIsNotEvidence(unittest.TestCase):
    """A single signal is a coincidence until something corroborates it."""

    def test_a_path_prefix_alone_says_nothing(self):
        # `/de/` is also a Spanish preposition and a product code.
        self.assertNotIn(RULE, rules_for(
            page("it"), "https://example.com/de/eventi/"))

    def test_open_graph_alone_says_nothing(self):
        self.assertNotIn(RULE, rules_for(
            page("it", OG_DE), "https://example.com/eventi/"))

    def test_a_prefix_under_a_matching_subdomain_is_still_one_witness(self):
        # One statement wearing two hats: the same site decided both.
        self.assertNotIn(RULE, rules_for(
            page("it"), "https://de.example.com/de/eventi/"))


class SilentWhereItHasNoVerdict(unittest.TestCase):

    def test_agreement_with_the_attribute_is_silent(self):
        self.assertNotIn(RULE, rules_for(
            page("de", OG_DE), "https://example.com/de/eventi/"))

    def test_a_regional_tag_is_the_same_language(self):
        self.assertNotIn(RULE, rules_for(
            page("de-AT", OG_DE), "https://example.com/de/eventi/"))

    def test_disagreeing_sources_produce_no_finding(self):
        head = '<meta property="og:locale" content="fr_FR">'
        self.assertNotIn(RULE, rules_for(
            page("it", head), "https://example.com/de/eventi/"))

    def test_a_missing_attribute_is_left_to_the_other_rule(self):
        markup = f'<html><head>{OG_DE}</head><body><p>Text</p></body></html>'
        self.assertNotIn(RULE, rules_for(markup, "https://example.com/de/x/"))

    def test_a_repository_path_is_not_an_address(self):
        self.assertNotIn(RULE, rules_for(page("it", OG_DE), "src/page.html"))

    def test_x_default_is_not_a_language(self):
        head = ('<link rel="alternate" hreflang="x-default" '
                'href="https://example.com/de/eventi/">')
        self.assertNotIn(RULE, rules_for(
            page("it", head), "https://example.com/de/eventi/"))

    def test_hreflang_pointing_elsewhere_is_not_a_self_entry(self):
        head = ('<link rel="alternate" hreflang="de" '
                'href="https://example.com/de/other/">')
        self.assertNotIn(RULE, rules_for(
            page("it", head), "https://example.com/de/eventi/"))


class TheSentenceCountsItsOwnWitnesses(unittest.TestCase):
    """Two is the rule's minimum, not the number it found.

    The rendered sentence used to say "two independent places" whatever it
    listed, and on a live run it listed three - a report wrong about its own
    evidence in all three languages.
    """

    SELF_DE = ('<link rel="alternate" hreflang="de" '
               'href="https://example.com/de/eventi/">')

    def issue_for(self, head: str, source: str):
        found = [i for i in analyze_document(page("it", head), source).issues
                 if i.rule_id == RULE]
        self.assertEqual(len(found), 1)
        return found[0]

    def test_two_witnesses_are_counted_as_two(self):
        issue = self.issue_for(OG_DE, "https://example.com/de/eventi/")
        self.assertEqual(issue.details["count"], 2)

    def test_three_witnesses_are_counted_as_three(self):
        issue = self.issue_for(OG_DE + self.SELF_DE,
                               "https://example.com/de/eventi/")
        self.assertEqual(issue.details["count"], 3)
        self.assertEqual(issue.details["signals"],
                         "hreflang self-entry, og:locale, path prefix")

    def test_the_sentence_names_the_number_it_listed(self):
        from audit.explanations import render

        issue = self.issue_for(OG_DE + self.SELF_DE,
                               "https://example.com/de/eventi/")
        for lang, expected in (("en", "3 independent places"),
                               ("uk", "3 незалежних місцях"),
                               ("it", "3 punti indipendenti")):
            with self.subTest(lang=lang):
                found = render(issue, lang).found
                self.assertIn(expected, found)
                self.assertNotIn("two independent", found)

    def test_two_witnesses_still_read_as_two(self):
        from audit.explanations import render

        issue = self.issue_for(OG_DE, "https://example.com/de/eventi/")
        for lang, expected in (("en", "2 independent places"),
                               ("uk", "2 незалежних місцях"),
                               ("it", "2 punti indipendenti")):
            with self.subTest(lang=lang):
                self.assertIn(expected, render(issue, lang).found)


class PathSegmentsThatAreNotLanguages(unittest.TestCase):
    """The permissive tag pattern must not turn ordinary paths into signals."""

    def test_a_long_first_segment_is_not_a_language(self):
        self.assertNotIn(RULE, rules_for(
            page("it", OG_DE), "https://example.com/eventi/de/"))

    def test_a_numeric_segment_is_not_a_language(self):
        self.assertNotIn(RULE, rules_for(
            page("it", OG_DE), "https://example.com/2026/eventi/"))


if __name__ == "__main__":
    unittest.main()
