"""Who a finding belongs to, when a platform served the page.

A report that lists a platform's own bundles beside the author's markup is
technically right and practically useless: it asks a person to triage work
they cannot do. These check the split is drawn on evidence - a literal path
the platform emits - and that nothing is removed by drawing it.
"""
import unittest

import project_profile
from audit import engine
from audit.base import Issue
from audit.engine import AccessibilityResult, DocumentReport

WORDPRESS = '<html><head><meta name="generator" content="WordPress 7.1"></head><body></body></html>'
HUGO = '<html><head><meta name="generator" content="Hugo 0.165.0"></head><body></body></html>'


def _result(markup: str, snippets: list) -> AccessibilityResult:
    result = AccessibilityResult(root="https://example.test/", mode="web")
    result.markup_sample = markup
    result.documents.append(DocumentReport(
        source="https://example.test/",
        issues=[Issue(rule_id="perf-render-blocking", severity="serious",
                      snippet=snippet) for snippet in snippets]))
    return result


class Ownership(unittest.TestCase):
    def test_a_core_asset_belongs_to_the_platform(self):
        result = _result(WORDPRESS, [
            "<link rel='stylesheet' href='/wp-includes/blocks/navigation/style.min.css'>"])
        counts = engine.attribute_ownership(result)
        self.assertEqual(counts, {"wordpress": 1})
        self.assertEqual(result.issues()[0].owner, "wordpress")

    def test_a_theme_file_stays_with_the_author(self):
        # A theme is chosen and can be changed, so its markup is the owner's
        # responsibility even when they did not type it.
        result = _result(WORDPRESS, [
            "<link rel='stylesheet' href='/wp-content/themes/mine/style.css'>"])
        self.assertEqual(engine.attribute_ownership(result), {})
        self.assertEqual(result.issues()[0].owner, "")

    def test_an_element_with_no_address_belongs_to_whoever_wrote_the_page(self):
        result = _result(WORDPRESS, ["<h2 style='color:#eee'>Latest</h2>"])
        self.assertEqual(engine.attribute_ownership(result), {})

    def test_a_generator_owns_nothing_it_did_not_serve(self):
        # Hugo is detected from the same kind of evidence and still owns
        # nothing: its output is what the author wrote.
        result = _result(HUGO, ["<link rel='stylesheet' href='/css/main.css'>"])
        self.assertEqual(engine.attribute_ownership(result), {})

    def test_an_undetected_page_attributes_nothing(self):
        # The path alone is not enough: without a detected platform there is
        # nothing to attribute to, and guessing from a path is how a wrong
        # answer gets stated confidently.
        result = _result("<html><body></body></html>", [
            "<link rel='stylesheet' href='/wp-includes/blocks/style.min.css'>"])
        self.assertEqual(engine.attribute_ownership(result), {})

    def test_nothing_is_suppressed(self):
        result = _result(WORDPRESS, [
            "<link rel='stylesheet' href='/wp-includes/a.css'>",
            "<h2>Latest</h2>"])
        before = len(result.issues())
        engine.attribute_ownership(result)
        self.assertEqual(len(result.issues()), before)
        self.assertEqual(result.counts()["serious"], 2)


class TheMap(unittest.TestCase):
    def test_every_owning_platform_is_a_stack_that_exists(self):
        names = {stack.name for stack in project_profile.STACKS}
        for name in project_profile.PLATFORM_ASSETS:
            self.assertIn(name, names, f"{name} owns paths but is not a stack")

    def test_a_framework_build_is_not_the_platform(self):
        # `/_next/static/` is the author's own code compiled. Measured on
        # vercel.com, treating it as Next.js's turned a render-blocking
        # script the site owns into somebody else's problem.
        for name in ("nextjs", "nuxt", "sveltekit", "hugo", "jekyll", "astro",
                     "vite", "eleventy", "gatsby"):
            self.assertNotIn(name, project_profile.PLATFORM_ASSETS,
                             f"{name} builds the author's code; it owns nothing")

    def test_a_platform_only_claims_paths_it_serves(self):
        # Every fragment has to be specific enough that no author would type
        # it by hand into their own site. A bare "/assets/" here would take
        # half the web with it.
        for name, fragments in project_profile.PLATFORM_ASSETS.items():
            for fragment in fragments:
                self.assertGreater(len(fragment), 6, f"{name}: {fragment}")
                self.assertNotIn(fragment, ("/assets/", "/static/", "/css/"))


if __name__ == "__main__":
    unittest.main()


class SkipLinkIsOneProblem(unittest.TestCase):
    """Three engines answer "can the keyboard bypass the navigation".

    None of them was mapped to the others, so a page with no skip link was
    reported three times under three names, with nothing saying they agreed -
    on the one finding where agreement is the whole signal.
    """

    def test_three_engines_collapse_into_one_row(self):
        from audit.browser import deduplicate

        def issue(rule, engine, selector, snippet, severity):
            return Issue(rule_id=rule, severity=severity, category="accessibility",
                         source="https://x/", snippet=snippet, selector=selector,
                         engine=engine, details={})

        out = deduplicate([
            issue("skip-link", "static", "", "", "moderate"),
            issue("state:no-skip-link", "browser", "nav", "<nav>…</nav>", "moderate"),
            issue("axe:bypass", "axe", "html", "<html>", "serious"),
        ], markup="<html><body><nav>x</nav></body></html>")

        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].details["agreement"], 3)
        # The worst severity survives: two engines calling it moderate does
        # not make the third one's serious wrong.
        self.assertEqual(out[0].severity, "serious")
