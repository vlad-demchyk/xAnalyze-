"""An address left in the source language on a site that translates addresses.

The signal is the site's own inconsistency, not the identical path. Keeping
one set of slugs across languages is a legitimate strategy, and a rule that
reported it would be arguing with a decision rather than finding a defect.
What a human reviewer actually had to list by hand was the other shape: a
site whose addresses were translated except for seven pages.
"""
import unittest

from audit import crosspage

RULE = "seo-slug-not-translated"


class _Page:
    def __init__(self, url, html=""):
        self.url = url
        self.raw_html = html
        self.error = None
        self.diagnostics = None


def alternates(lang, *pairs) -> str:
    links = "".join(
        f'<link rel="alternate" hreflang="{code}" href="{url}">'
        for code, url in pairs)
    return (f'<html lang="{lang}"><head>{links}</head>'
            f"<body><p>x</p></body></html>")


def pair(slug_it, slug_de, lang_de="de"):
    """One page in two languages, cross-linked as hreflang alternates."""
    it_url = f"https://example.com{slug_it}"
    de_url = f"https://example.com/{lang_de}{slug_de}"
    head = (("it", it_url), (lang_de, de_url))
    return [_Page(it_url, alternates("it", *head)),
            _Page(de_url, alternates(lang_de, *head))]


def rules_for(pages) -> list:
    return [i for i in crosspage.issues_for(pages) if i.rule_id == RULE]


class TheSiteContradictsItself(unittest.TestCase):

    def test_the_untranslated_address_is_reported(self):
        pages = (pair("/eventi/", "/veranstaltungen/")
                 + pair("/esperienze/", "/erlebnisse/")
                 + pair("/passeggiate/", "/passeggiate/"))
        found = rules_for(pages)
        self.assertEqual(len(found), 1)
        # The finding lands on the German page: that is the address that was
        # supposed to change and did not.
        self.assertEqual(found[0].source, "https://example.com/de/passeggiate")
        self.assertEqual(found[0].details["language"], "it")

    def test_each_missed_address_is_named_once(self):
        pages = (pair("/eventi/", "/veranstaltungen/")
                 + pair("/esperienze/", "/erlebnisse/")
                 + pair("/passeggiate/", "/passeggiate/")
                 + pair("/pacchetti/", "/pacchetti/"))
        self.assertEqual(len(rules_for(pages)), 2)


class WhereItMustStaySilent(unittest.TestCase):

    def test_a_site_that_never_translates_slugs_is_a_strategy(self):
        pages = (pair("/eventi/", "/eventi/")
                 + pair("/esperienze/", "/esperienze/")
                 + pair("/passeggiate/", "/passeggiate/"))
        self.assertEqual(rules_for(pages), [])

    def test_one_translated_pair_is_not_yet_a_policy(self):
        pages = pair("/eventi/", "/veranstaltungen/") + pair("/x/", "/x/")
        self.assertEqual(rules_for(pages), [])

    def test_a_fully_translated_site_has_nothing_to_report(self):
        pages = (pair("/eventi/", "/veranstaltungen/")
                 + pair("/esperienze/", "/erlebnisse/")
                 + pair("/passeggiate/", "/spaziergaenge/"))
        self.assertEqual(rules_for(pages), [])

    def test_a_single_page_run_says_nothing(self):
        self.assertEqual(rules_for(pair("/x/", "/x/")[:1]), [])


class TheLanguagePrefixIsNotPartOfTheSlug(unittest.TestCase):
    """`/de/eventi/` against `/eventi/` differs only by the prefix, and that
    difference is the site's routing rather than a translated address."""

    def test_the_prefix_alone_does_not_count_as_a_translation(self):
        pages = (pair("/eventi/", "/eventi/")
                 + pair("/esperienze/", "/esperienze/")
                 + pair("/passeggiate/", "/passeggiate/"))
        self.assertEqual(rules_for(pages), [])

    def test_a_regional_prefix_is_still_a_prefix(self):
        pages = (pair("/eventi/", "/veranstaltungen/", lang_de="de-AT")
                 + pair("/esperienze/", "/erlebnisse/", lang_de="de-AT")
                 + pair("/passeggiate/", "/passeggiate/", lang_de="de-AT"))
        found = rules_for(pages)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].source,
                         "https://example.com/de-AT/passeggiate")


if __name__ == "__main__":
    unittest.main()
