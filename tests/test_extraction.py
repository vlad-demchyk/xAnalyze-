"""What the extractors take, what they leave, and what they say when they
take nothing.

The crawler cases are all "why is the result empty" scenarios, because that
is the question the diagnostics exist to answer and the one an empty list
cannot answer by itself.
"""
from __future__ import annotations

import unittest

import crawler
from crawler import _diagnose, _extract_text_blocks
from models import KIND_INJECTED, KIND_MARKUP, KIND_TECHNICAL, PageDiagnostics
from repo_scanner import (SCOPE_BOTH, SCOPE_CONTENT, SCOPE_TECHNICAL,
                          _extract_blocks, mask_code_comments)


def extract(html: str):
    diagnostics = PageDiagnostics()
    blocks = _extract_text_blocks(html, "http://x/", diagnostics)
    _diagnose(diagnostics, "http://x/", html, blocks)
    return blocks, diagnostics


class CrawlerExtraction(unittest.TestCase):
    def test_paragraph_is_taken(self):
        blocks, _ = extract("<html><body><p>This paragraph has quite enough "
                            "visible text in it.</p></body></html>")
        self.assertEqual(len(blocks), 1)

    def test_copy_directly_inside_a_div_is_taken(self):
        # Regression: div/section aren't candidate tags, so copy written
        # straight into one used to be missed entirely.
        blocks, _ = extract("<html><body><div>This text sits directly in a div "
                            "with no paragraph tag.</div></body></html>")
        self.assertEqual(len(blocks), 1)

    def test_a_wrapper_does_not_duplicate_its_child(self):
        blocks, _ = extract("<html><body><div class='wrap'><p>This paragraph has "
                            "quite enough visible text.</p></div></body></html>")
        self.assertEqual(len(blocks), 1)

    def test_script_bodies_are_never_content(self):
        blocks, _ = extract("<html><body><script>const message = 'This string is "
                            "long enough to look like copy';</script></body></html>")
        self.assertEqual(blocks, [])


class CrawlerDiagnostics(unittest.TestCase):
    def test_application_shell_is_reported_as_js_rendered(self):
        blocks, diagnostics = extract(
            '<html><body><div id="root"></div>'
            '<script src="/_next/static/x.js"></script></body></html>'
        )
        self.assertEqual(blocks, [])
        self.assertIn(crawler.EMPTY_JS_RENDERED, diagnostics.reasons)
        self.assertEqual(diagnostics.js_framework, "next")

    def test_navigation_only_page_is_reported_as_too_short(self):
        blocks, diagnostics = extract(
            "<html><body><p>Hi</p><h1>Home</h1><a href='/x'>Next</a></body></html>")
        self.assertEqual(blocks, [])
        self.assertIn(crawler.EMPTY_TOO_SHORT, diagnostics.reasons)
        self.assertEqual(diagnostics.dropped_too_short, 3)

    def test_empty_markup_is_reported_as_no_text(self):
        _blocks, diagnostics = extract("<html><body></body></html>")
        self.assertIn(crawler.EMPTY_NO_TEXT, diagnostics.reasons)

    def test_a_page_with_text_gets_no_reason(self):
        _blocks, diagnostics = extract("<html><body><p>This paragraph has quite "
                                       "enough visible text in it.</p></body></html>")
        self.assertEqual(diagnostics.reasons, [])

    def test_measurements_are_recorded_either_way(self):
        _blocks, diagnostics = extract("<html><body><p>This paragraph has quite "
                                       "enough visible text in it.</p></body></html>")
        self.assertGreater(diagnostics.html_bytes, 0)
        self.assertGreater(diagnostics.text_ratio, 0.1)
        self.assertEqual(diagnostics.blocks_kept, 1)


SAMPLE = '''// This comprehensive helper will streamline the way you delve into the data.
import React from "react";

/**
 * In today's fast-paced world it is important to note that this component
 * unlocks the potential of your dashboard.
 */
export function Panel() {
  const config = { title: "Unlock the potential of your team", icon: "star" };
  return (
    <div>
      <h1>Welcome back to the dashboard</h1>
      <input placeholder="Search across your comprehensive archive" />
      <p>{t("It is important to note that we saved your work")}</p>
    </div>
  );
}
'''


class RepositoryScopes(unittest.TestCase):
    def kinds(self, scope):
        return [b.kind for b in _extract_blocks(SAMPLE, "app.jsx", scope)]

    def texts(self, scope):
        return [b.text for b in _extract_blocks(SAMPLE, "app.jsx", scope)]

    def test_content_scope_excludes_comments(self):
        self.assertNotIn(KIND_TECHNICAL, self.kinds(SCOPE_CONTENT))

    def test_content_scope_takes_markup_and_injected_copy(self):
        kinds = set(self.kinds(SCOPE_CONTENT))
        self.assertEqual(kinds, {KIND_MARKUP, KIND_INJECTED})

    def test_injected_copy_covers_attributes_keys_and_translations(self):
        texts = self.texts(SCOPE_CONTENT)
        self.assertIn("Search across your comprehensive archive", texts)   # attribute
        self.assertIn("Unlock the potential of your team", texts)          # object key
        self.assertIn("It is important to note that we saved your work", texts)  # t()

    def test_technical_scope_takes_only_comments(self):
        self.assertEqual(set(self.kinds(SCOPE_TECHNICAL)), {KIND_TECHNICAL})

    def test_both_scope_takes_everything(self):
        self.assertEqual(
            set(self.kinds(SCOPE_BOTH)),
            {KIND_MARKUP, KIND_INJECTED, KIND_TECHNICAL},
        )

    def test_offsets_always_match_the_source_file(self):
        # file_writer re-checks this before writing; if it were ever false,
        # a replacement would splice text into the wrong place.
        for scope in (SCOPE_CONTENT, SCOPE_TECHNICAL, SCOPE_BOTH):
            for b in _extract_blocks(SAMPLE, "app.jsx", scope):
                self.assertEqual(SAMPLE[b.start:b.end], b.text, scope)

    def test_directives_and_task_markers_are_not_prose(self):
        source = ("// eslint-disable-next-line no-console\n"
                  "// TODO: rewrite this whole thing at some point soon please\n"
                  "# noqa: E501 this line is long but that is fine really\n")
        self.assertEqual(_extract_blocks(source, "x.js", SCOPE_TECHNICAL), [])

    def test_a_url_is_not_mistaken_for_a_comment(self):
        source = 'const endpoint = "https://example.com/some/fairly/long/path";\n'
        self.assertEqual(_extract_blocks(source, "x.js", SCOPE_TECHNICAL), [])

    def test_commented_out_copy_is_not_live_content(self):
        source = '<!-- <input placeholder="This copy is commented out entirely"> -->\n'
        texts = [b.text for b in _extract_blocks(source, "x.html", SCOPE_CONTENT)]
        self.assertNotIn("This copy is commented out entirely", texts)


class DesignTokens(unittest.TestCase):
    def test_palette_is_complete_even_with_no_token_file(self):
        from ui.tokens import Palette

        palette = Palette.from_tokens({}, "light")
        # Every field falls back, so a missing or malformed token file
        # degrades to a plain theme rather than to a crash on startup.
        self.assertTrue(palette.page_bg.startswith("#"))
        self.assertGreater(palette.font_size, 0)

    def test_var_references_and_rem_lengths_resolve(self):
        from ui.tokens import Palette, _parse_css, _resolve, px

        light, dark = _parse_css(
            ':root { --a: #123456; --b: var(--a); --r: 0.875rem; }\n'
            '[data-theme="dark"] { --b: #000000; }\n'
        )
        self.assertEqual(_resolve(light["--b"], light), "#123456")
        self.assertEqual(_resolve(dark["--b"], dark), "#000000")
        self.assertEqual(px(_resolve(light["--r"], light), 0), 14)

    def test_eight_digit_hex_is_converted_for_qt(self):
        from ui.theme import qss_color

        # Qt style sheets reject #rrggbbaa, and xFormat's scrollbar tokens
        # use it — dropping the token would lose the colour silently.
        self.assertTrue(qss_color("#d8d6d0a3").startswith("rgba("))
        self.assertEqual(qss_color("#123456"), "#123456")

    def test_generated_stylesheet_carries_the_palette(self):
        from ui.theme import build_qss
        from ui.tokens import Palette

        palette = Palette.from_tokens({}, "light")
        qss = build_qss(palette)
        self.assertIn(palette.page_bg, qss)
        self.assertIn(palette.font, qss)


if __name__ == "__main__":
    unittest.main()


class MarkdownMasking(unittest.TestCase):
    """Markdown quotes code in backticks, and quoted markup is not shipped
    markup. Measured on 596 real `.md` files: every finding above `minor`
    the audit produced on them came from a backticked example, and all of
    them were false.
    """

    DOC = ('# Title\n\n'
           'Real markup ships here: <img src="x.png">\n\n'
           '`<img src="quoted.png">` is only mentioned.\n\n'
           '```html\n'
           '<img src="fenced.png">\n'
           '```\n\n'
           'After the fence: <audio controls></audio>.\n')

    def masked(self) -> str:
        return mask_code_comments(self.DOC, "docs/guide.md")

    def test_quoted_markup_is_blanked(self):
        masked = self.masked()
        self.assertNotIn("quoted.png", masked)
        self.assertNotIn("fenced.png", masked)

    def test_markup_outside_a_code_span_survives(self):
        # A `.md` really can ship markup, and silencing the whole file would
        # trade false findings for missing ones.
        masked = self.masked()
        self.assertIn('<img src="x.png">', masked)
        self.assertIn("<audio controls>", masked)

    def test_offsets_and_lines_are_preserved(self):
        # Every finding's line number indexes into the original file.
        masked = self.masked()
        self.assertEqual(len(masked), len(self.DOC))
        self.assertEqual(masked.count("\n"), self.DOC.count("\n"))

    def test_backticks_in_other_file_types_are_left_alone(self):
        source = 'const sql = `SELECT * FROM t`;\n'
        self.assertEqual(mask_code_comments(source, "db.ts"), source)
