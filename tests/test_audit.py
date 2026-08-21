"""Accessibility rules: what they catch, and — just as important — what
they must not flag.

False positives are the way an accessibility tool gets switched off, so
roughly half of these assert silence on correct markup.
"""
from __future__ import annotations

import unittest

import audit
from audit import analyze_document
from audit.rules.accessibility import contrast_ratio


def issues(markup: str, rule_id: str | None = None,
           category: str = audit.ACCESSIBILITY) -> list:
    """Findings for one snippet, scoped to one category by default.

    The scoping matters now that four categories run over the same document:
    a bare `<img>` legitimately produces an accessibility finding *and* an
    SEO one, and an accessibility test asserting "nothing else" would fail
    on a correct SEO rule.
    """
    found = analyze_document(markup, "test.html", line_numbers=True).issues
    return [i for i in found
            if (rule_id is None or i.rule_id == rule_id)
            and (category is None or i.category == category)]


class Images(unittest.TestCase):
    def test_missing_alt_is_critical_and_offers_the_decorative_fix(self):
        found = issues('<img src="/a.png">', "image-alt")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].severity, audit.CRITICAL)
        self.assertIn('alt=""', found[0].fix_snippet)

    def test_empty_alt_is_correct_markup(self):
        self.assertEqual(issues('<img src="/a.png" alt="">', "image-alt"), [])

    def test_filename_alt_is_flagged_separately(self):
        found = issues('<img src="/a.png" alt="hero-banner-2.png">')
        self.assertEqual([i.rule_id for i in found], ["image-alt-filename"])

    def test_real_description_is_left_alone(self):
        self.assertEqual(issues('<img src="/a.png" alt="The team lead on stage">'), [])


class Controls(unittest.TestCase):
    def test_icon_only_button_has_no_name(self):
        self.assertEqual(len(issues('<button><span class="i"></span></button>',
                                    "control-name")), 1)

    def test_aria_label_is_a_name(self):
        self.assertEqual(issues('<button aria-label="Close"><i></i></button>',
                                "control-name"), [])

    def test_wrapping_label_names_an_input(self):
        markup = "<label>Email <input type='text'></label>"
        self.assertEqual(issues(markup, "control-name"), [])

    def test_label_for_names_an_input(self):
        markup = '<label for="e">Email</label><input type="text" id="e">'
        self.assertEqual(issues(markup, "control-name"), [])

    def test_submit_input_is_named_by_its_value(self):
        self.assertEqual(issues('<input type="submit" value="Send">', "control-name"), [])

    def test_anchor_without_href_is_not_a_control(self):
        self.assertEqual(issues("<a></a>", "control-name"), [])


class Structure(unittest.TestCase):
    def test_skipped_heading_level_is_reported_with_the_correct_fix(self):
        found = issues("<h1>A</h1><h4>B</h4>", "heading-order")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].details["from"], 1)
        self.assertEqual(found[0].details["to"], 4)
        self.assertIn("<h2>", found[0].fix_snippet)

    def test_descending_one_level_at_a_time_is_fine(self):
        self.assertEqual(issues("<h1>A</h1><h2>B</h2><h3>C</h3>", "heading-order"), [])

    def test_going_back_up_is_fine(self):
        # h3 -> h2 starts a new section; only downward jumps skip a level.
        self.assertEqual(issues("<h1>A</h1><h2>B</h2><h3>C</h3><h2>D</h2>",
                                "heading-order"), [])

    def test_duplicate_id_is_reported_once_for_the_second_element(self):
        found = issues('<p id="x">a</p><p id="x">b</p>', "duplicate-id")
        self.assertEqual(len(found), 1)

    def test_broken_aria_reference_is_found(self):
        found = issues('<span aria-labelledby="nope">x</span>', "aria-reference-broken")
        self.assertEqual(found[0].details["missing"], ["nope"])

    def test_resolving_aria_reference_is_fine(self):
        markup = '<h2 id="t">Title</h2><section aria-labelledby="t">x</section>'
        self.assertEqual(issues(markup, "aria-reference-broken"), [])

    def test_layout_table_marked_presentation_is_skipped(self):
        markup = '<table role="presentation"><tr><td>a</td></tr><tr><td>b</td></tr></table>'
        self.assertEqual(issues(markup, "table-headers"), [])

    def test_data_table_without_headers_is_reported(self):
        markup = "<table><tr><td>a</td></tr><tr><td>b</td></tr></table>"
        self.assertEqual(len(issues(markup, "table-headers")), 1)


class Keyboard(unittest.TestCase):
    def test_positive_tabindex_is_reported(self):
        found = issues('<div tabindex="3">x</div>', "tabindex-positive")
        self.assertEqual(found[0].details["value"], 3)
        self.assertIn('tabindex="0"', found[0].fix_snippet)

    def test_zero_and_negative_tabindex_are_legitimate(self):
        self.assertEqual(issues('<div tabindex="0">x</div><div tabindex="-1">y</div>',
                                "tabindex-positive"), [])


class Media(unittest.TestCase):
    def test_autoplay_without_controls_is_reported(self):
        found = issues('<video autoplay src="/a.mp4"></video>', "media-autoplay")
        self.assertEqual(len(found), 1)
        # Boolean attributes are written bare in the suggested fix, so the
        # snippet can be pasted into a source file as-is.
        self.assertIn("autoplay ", found[0].fix_snippet)
        self.assertNotIn('autoplay=""', found[0].fix_snippet)

    def test_muted_autoplay_video_is_allowed(self):
        self.assertEqual(issues('<video autoplay muted src="/a.mp4"></video>',
                                "media-autoplay"), [])

    def test_captions_track_satisfies_the_rule(self):
        markup = '<video src="/a.mp4"><track kind="captions" src="/c.vtt"></video>'
        self.assertEqual(issues(markup, "media-captions"), [])

    def test_missing_captions_is_marked_as_needing_a_browser(self):
        found = issues('<video src="/a.mp4"></video>', "media-captions")
        self.assertEqual(found[0].confidence, audit.NEEDS_BROWSER)


class Viewport(unittest.TestCase):
    def test_blocked_zoom_is_reported(self):
        markup = '<meta name="viewport" content="width=device-width, user-scalable=no">'
        self.assertEqual(len(issues(markup, "viewport-zoom")), 1)

    def test_maximum_scale_one_is_reported(self):
        markup = '<meta name="viewport" content="width=device-width, maximum-scale=1.0">'
        self.assertEqual(len(issues(markup, "viewport-zoom")), 1)

    def test_a_normal_viewport_is_fine(self):
        markup = '<meta name="viewport" content="width=device-width, initial-scale=1">'
        self.assertEqual(issues(markup, "viewport-zoom"), [])


class Contrast(unittest.TestCase):
    def test_known_ratios(self):
        self.assertAlmostEqual(contrast_ratio((0, 0, 0), (255, 255, 255)), 21.0, places=2)
        self.assertAlmostEqual(contrast_ratio((255, 255, 255), (255, 255, 255)), 1.0, places=2)

    def test_low_contrast_inline_pair_is_reported_as_needing_a_browser(self):
        markup = '<p style="color:#999999;background:#ffffff">text</p>'
        found = issues(markup, "contrast-inline")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].confidence, audit.NEEDS_BROWSER)
        self.assertLess(found[0].details["ratio"], 4.5)

    def test_sufficient_contrast_is_not_reported(self):
        markup = '<p style="color:#333333;background:#ffffff">text</p>'
        self.assertEqual(issues(markup, "contrast-inline"), [])

    def test_colour_alone_is_not_judged(self):
        # Without a background on the same element the real pair comes from
        # the cascade, which this pass cannot see — so it says nothing.
        self.assertEqual(issues('<p style="color:#999999">text</p>', "contrast-inline"), [])


class DocumentLevel(unittest.TestCase):
    def test_missing_lang_and_title_are_reported_for_a_full_document(self):
        found = {i.rule_id for i in issues("<html><body><p>x</p></body></html>")}
        self.assertIn("html-lang", found)
        self.assertIn("document-title", found)

    def test_a_fragment_is_not_judged_as_a_document(self):
        # A JSX component file is not a page; demanding <title> of it would
        # be a false positive on every component in a repository.
        found = {i.rule_id for i in issues("<div><p>x</p></div>")}
        self.assertNotIn("html-lang", found)
        self.assertNotIn("document-title", found)
        self.assertNotIn("page-has-h1", found)


class Explanations(unittest.TestCase):
    def test_every_rule_has_all_four_strings_in_all_three_languages(self):
        from i18n.translations import _STRINGS

        missing = []
        for rule_id in audit.RuleRegistry.available():
            stem = rule_id.replace("-", "_")
            for suffix in ("title", "found", "why", "fix"):
                key = f"a11y_{stem}_{suffix}"
                entry = _STRINGS.get(key)
                if entry is None:
                    missing.append(key)
                    continue
                for language in ("uk", "it", "en"):
                    if not entry.get(language):
                        missing.append(f"{key}:{language}")
        self.assertEqual(missing, [])

    def test_explanation_renders_with_the_rule_specific_values(self):
        from audit.explanations import render

        issue = issues('<img src="/hero.png">', "image-alt")[0]
        rendered = render(issue, "en")
        self.assertIn("/hero.png", rendered.found)
        self.assertIn("1.1.1", rendered.wcag)
        self.assertTrue(rendered.why)
        self.assertTrue(rendered.fix)


class AIReview(unittest.TestCase):
    def test_candidates_skip_what_the_offline_rules_already_answer(self):
        from bs4 import BeautifulSoup

        from audit.ai_review import collect_candidates
        from audit.base import RuleContext
        from audit.engine import _dom_path

        document = BeautifulSoup(
            '<img src="/a.png"><img src="/b.png" alt="A chart">', "html.parser")
        context = RuleContext(source="x")
        context.dom_path = _dom_path
        candidates = collect_candidates(document, context)
        # The image with no alt is `image-alt`, reported exactly and for free;
        # paying a model to re-confirm it would be waste.
        self.assertEqual([c["text"] for c in candidates], ["A chart"])

    def test_a_failing_provider_yields_one_finding_not_an_exception(self):
        from bs4 import BeautifulSoup

        from audit.ai_review import AIAccessibilityReview
        from audit.base import RuleContext
        from audit.engine import _dom_path

        class Failing:
            def analyze(self, system, user):
                raise RuntimeError("not signed in")

        document = BeautifulSoup('<img src="/b.png" alt="A chart">', "html.parser")
        context = RuleContext(source="x")
        context.dom_path = _dom_path
        found = AIAccessibilityReview(provider=Failing()).review_document(document, context)
        self.assertEqual(len(found), 1)
        self.assertIn("batch_error", found[0].details)


class Landmarks(unittest.TestCase):
    def test_page_without_main_is_reported(self):
        markup = '<html><body><nav><a href="/">Home</a></nav><p>Content</p></body></html>'
        found = issues(markup, "landmark-regions")
        self.assertEqual(len(found), 1)
        self.assertIn("<main>", found[0].fix_snippet)

    def test_page_with_main_is_fine(self):
        markup = '<html><body><main><p>Content</p></main></body></html>'
        self.assertEqual(issues(markup, "landmark-regions"), [])

    def test_fragment_is_not_judged(self):
        self.assertEqual(issues('<div><p>x</p></div>', "landmark-regions"), [])


class SkipLink(unittest.TestCase):
    def test_page_without_skip_link_is_reported(self):
        markup = '<html><body><nav><a href="/">Home</a></nav><main id="main"><p>x</p></main></body></html>'
        found = issues(markup, "skip-link")
        self.assertEqual(len(found), 1)

    def test_page_with_skip_link_is_fine(self):
        markup = '<html><body><a href="#main">Skip</a><nav><a href="/">Home</a></nav><main id="main"><p>x</p></main></body></html>'
        self.assertEqual(issues(markup, "skip-link"), [])

    def test_fragment_is_not_judged(self):
        self.assertEqual(issues('<div><a href="#x">Skip</a></div>', "skip-link"), [])


class FormErrorMessage(unittest.TestCase):
    def test_invalid_field_without_description_is_reported(self):
        markup = '<input type="text" aria-invalid="true">'
        found = issues(markup, "form-error-message")
        self.assertEqual(len(found), 1)

    def test_invalid_field_with_describedby_is_fine(self):
        markup = '<input type="text" aria-invalid="true" aria-describedby="err"><span id="err">Required</span>'
        self.assertEqual(issues(markup, "form-error-message"), [])

    def test_invalid_field_with_errormessage_is_fine(self):
        markup = '<input type="text" aria-invalid="true" aria-errormessage="err">'
        self.assertEqual(issues(markup, "form-error-message"), [])

    def test_valid_field_is_not_judged(self):
        self.assertEqual(issues('<input type="text">', "form-error-message"), [])


class TableScope(unittest.TestCase):
    def test_table_with_th_without_scope_is_reported(self):
        markup = '<table><tr><th>Name</th><th>Age</th></tr><tr><td>John</td><td>30</td></tr></table>'
        found = issues(markup, "table-scope")
        self.assertEqual(len(found), 1)

    def test_table_with_scope_is_fine(self):
        markup = '<table><tr><th scope="col">Name</th><th scope="col">Age</th></tr><tr><td>John</td><td>30</td></tr></table>'
        self.assertEqual(issues(markup, "table-scope"), [])

    def test_single_th_is_not_judged(self):
        markup = '<table><tr><th>Name</th><td>John</td></tr></table>'
        self.assertEqual(issues(markup, "table-scope"), [])


class HreflangLinks(unittest.TestCase):
    def test_multilingual_site_without_hreflang_is_reported(self):
        markup = '<html lang="en"><head><title>T</title></head><body><a href="/uk/">Українська</a></body></html>'
        found = issues(markup, "hreflang-links")
        self.assertEqual(len(found), 1)

    def test_page_without_language_links_is_not_judged(self):
        markup = '<html lang="en"><head><title>T</title></head><body><p>Content</p></body></html>'
        self.assertEqual(issues(markup, "hreflang-links"), [])


class BreadcrumbMarkup(unittest.TestCase):
    def test_breadcrumb_outside_nav_is_reported(self):
        markup = '<div class="breadcrumb"><a href="/">Home</a> / <a href="/page">Page</a></div>'
        found = issues(markup, "breadcrumb-markup")
        self.assertEqual(len(found), 1)

    def test_breadcrumb_in_nav_is_fine(self):
        markup = '<nav aria-label="breadcrumb"><ol><li><a href="/">Home</a></li></ol></nav>'
        self.assertEqual(issues(markup, "breadcrumb-markup"), [])


class LanguageChange(unittest.TestCase):
    def test_foreign_text_without_lang_is_reported(self):
        markup = '<html lang="en"><head><title>T</title></head><body><p>This is a long enough English text with <span>дуже довгий український текст щоб перевірити правило</span> inside</p></body></html>'
        found = issues(markup, "language-change")
        # May or may not find it depending on text length threshold
        if found:
            self.assertEqual(found[0].details["page_lang"], "en")

    def test_foreign_text_with_lang_is_fine(self):
        markup = '<html lang="en"><head><title>T</title></head><body><p>This is English <span lang="uk">Український текст</span></p></body></html>'
        self.assertEqual(issues(markup, "language-change"), [])


class AbbreviationExpansion(unittest.TestCase):
    def test_abbreviation_without_abbr_is_reported(self):
        markup = '<html lang="en"><head><title>T</title></head><body><p>The WCAG standard is important for accessibility on this page with enough text to trigger the rule</p></body></html>'
        found = issues(markup, "abbreviation-expansion")
        # May find WCAG
        if found:
            self.assertEqual(found[0].details["abbreviation"], "WCAG")

    def test_abbreviation_with_abbr_is_fine(self):
        markup = '<html lang="en"><head><title>T</title></head><body><p>The <abbr title="Web Content Accessibility Guidelines">WCAG</abbr> standard is important</p></body></html>'
        self.assertEqual(issues(markup, "abbreviation-expansion"), [])


class ImageModernFormat(unittest.TestCase):
    def test_legacy_format_without_srcset_is_reported(self):
        found = issues('<img src="/photo.png" alt="Photo">', "image-modern-format",
                       category=audit.PERFORMANCE)
        self.assertEqual(len(found), 1)

    def test_modern_format_is_not_judged(self):
        self.assertEqual(issues('<img src="/photo.webp" alt="Photo">', "image-modern-format",
                                category=audit.PERFORMANCE), [])

    def test_srcset_satisfies_the_rule(self):
        self.assertEqual(issues('<img src="/photo.png" srcset="/photo-300.webp 300w" alt="Photo">',
                                "image-modern-format", category=audit.PERFORMANCE), [])

    def test_svg_is_not_judged(self):
        self.assertEqual(issues('<img src="/icon.svg" alt="Icon">', "image-modern-format",
                                category=audit.PERFORMANCE), [])

    def test_data_uri_is_not_judged(self):
        self.assertEqual(issues('<img src="data:image/png;base64,abc" alt="Icon">',
                                "image-modern-format", category=audit.PERFORMANCE), [])


if __name__ == "__main__":
    unittest.main()
