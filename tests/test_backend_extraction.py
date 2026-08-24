"""Backend-language content extraction, technical-string filtering, and the
Vue bound-prop / template-literal leaks these were paired with.

Three problems, one file each section:
  1. Server-side languages (Python/PHP/Ruby, minimally Go/Java/C#) are read
     for content, but only through pattern-based sites — never markup rules.
  2. Technical-shaped strings (keys, URLs, paths, MIME types, CSS selectors,
     date formats, unresolved template substitutions) are filtered out
     everywhere content is judged, not just in one code path.
  3. Vue's `:attr="expr"` / `v-bind:attr="expr"` no longer leak the bound
     expression as if it were a plain attribute value.
"""
from __future__ import annotations

import unittest

from models import KIND_INJECTED
from repo_scanner import (
    SCOPE_CONTENT,
    _extract_blocks,
    _is_probably_content,
    _looks_technical,
)


def content_texts(src: str, path: str) -> list[str]:
    return [b.text for b in _extract_blocks(src, path, SCOPE_CONTENT)]


class PythonExtraction(unittest.TestCase):
    def test_render_context_title_is_content(self):
        src = (
            "def view(request):\n"
            "    return render(request, 'home.html', "
            "{'title': 'Welcome back to your dashboard'})\n"
        )
        self.assertIn("Welcome back to your dashboard", content_texts(src, "views.py"))

    def test_json_response_detail_is_content(self):
        src = "return JsonResponse({'detail': 'Your session has expired'}, status=401)\n"
        self.assertIn("Your session has expired", content_texts(src, "views.py"))

    def test_gettext_call_is_content(self):
        src = "message = gettext('Your changes have been saved')\n"
        self.assertIn("Your changes have been saved", content_texts(src, "forms.py"))

    def test_underscore_gettext_shorthand_is_content(self):
        src = "raise ValidationError(_('Please enter a valid email address'))\n"
        self.assertIn("Please enter a valid email address", content_texts(src, "forms.py"))

    def test_uppercase_string_constant_is_content(self):
        src = 'WELCOME_MESSAGE = "Welcome back, we missed you"\n'
        self.assertIn("Welcome back, we missed you", content_texts(src, "constants.py"))

    def test_technical_identifier_is_not_content(self):
        # A dotted/uppercase identifier is a key, not copy.
        src = 'code = "user_not_found"\nSTATUS = "PENDING_REVIEW"\n'
        self.assertEqual(content_texts(src, "views.py"), [])

    def test_python_comment_is_not_content(self):
        src = (
            "# This explains something to another developer, not a user\n"
            "context = {'message': 'Password updated successfully'}\n"
        )
        texts = content_texts(src, "views.py")
        self.assertIn("Password updated successfully", texts)
        self.assertNotIn(
            "This explains something to another developer, not a user", texts
        )

    def test_no_markup_rules_applied_to_python(self):
        # `<` here is a comparison, not a tag; the tag walk must not fire.
        src = "if a < b:\n    x = 'this text sits between comparisons < and >'\n"
        # Should not crash and should not produce a KIND_MARKUP block.
        blocks = _extract_blocks(src, "logic.py", SCOPE_CONTENT)
        self.assertTrue(all(b.kind == KIND_INJECTED for b in blocks))


class PhpExtraction(unittest.TestCase):
    def test_laravel_translation_helper_is_content(self):
        src = "$msg = __('Your order has been shipped');\n"
        self.assertIn("Your order has been shipped", content_texts(src, "OrderController.php"))

    def test_trans_helper_is_content(self):
        src = "$msg = trans('We could not find that page');\n"
        self.assertIn("We could not find that page", content_texts(src, "helpers.php"))

    def test_echo_string_is_content(self):
        src = "echo 'Thank you for signing up';\n"
        self.assertIn("Thank you for signing up", content_texts(src, "welcome.php"))

    def test_blade_literal_interpolation_is_content(self):
        src = "<div>{{ 'Your cart is currently empty' }}</div>\n"
        self.assertIn("Your cart is currently empty", content_texts(src, "cart.blade.php"))

    def test_blade_variable_interpolation_is_not_content(self):
        # No quotes: this is a variable, not literal text.
        src = "<div>{{ $cartMessage }}</div>\n"
        self.assertEqual(content_texts(src, "cart.blade.php"), [])


class WordPressExtraction(unittest.TestCase):
    """The WordPress i18n family beyond `__()`.

    Measured on real theme copy: five calls in, one found - `_e`,
    `esc_html__`, `esc_html_e` and `_x` were silently missing, so a theme's
    visible text (written almost entirely through these) came back looking
    clean while the scan had found almost nothing.
    """

    def test_e_is_content(self):
        src = "<?php _e('Immerso in un paesaggio unico', 'theme'); ?>\n"
        self.assertIn("Immerso in un paesaggio unico", content_texts(src, "header.php"))

    def test_esc_html_underscore_underscore_is_content(self):
        src = "<?php echo esc_html__('Prenota ora la tua vacanza', 'theme'); ?>\n"
        self.assertIn("Prenota ora la tua vacanza", content_texts(src, "cta.php"))

    def test_esc_html_e_is_content(self):
        src = "<?php esc_html_e('Un soggiorno indimenticabile', 'theme'); ?>\n"
        self.assertIn("Un soggiorno indimenticabile", content_texts(src, "cta.php"))

    def test_esc_attr_e_is_content(self):
        src = "<input placeholder=\"<?php esc_attr_e('Cerca nel sito', 'theme'); ?>\">\n"
        self.assertIn("Cerca nel sito", content_texts(src, "search.php"))

    def test_x_with_context_is_content(self):
        src = "<?php echo _x('Prenota adesso', 'button label', 'theme'); ?>\n"
        self.assertIn("Prenota adesso", content_texts(src, "cta.php"))

    def test_n_plural_singular_form_is_content(self):
        # The plural argument is not captured - one quoted string per call
        # site is what the pattern-based extractor does everywhere else -
        # but the singular is real copy and must not be lost either.
        src = "<?php echo _n('Un ospite', 'Piu ospiti', $count, 'theme'); ?>\n"
        self.assertIn("Un ospite", content_texts(src, "booking.php"))


class RubyExtraction(unittest.TestCase):
    def test_flash_notice_is_content(self):
        src = 'flash[:notice] = "Your profile has been updated"\n'
        self.assertIn("Your profile has been updated", content_texts(src, "users_controller.rb"))

    def test_rails_t_helper_is_content(self):
        src = "t('Please confirm your email address before continuing')\n"
        self.assertIn(
            "Please confirm your email address before continuing",
            content_texts(src, "app.rb"),
        )

    def test_erb_literal_output_is_content(self):
        src = "<p><%= 'Checkout is temporarily unavailable' %></p>\n"
        self.assertIn("Checkout is temporarily unavailable", content_texts(src, "index.html.erb"))

    def test_ruby_hash_comment_is_not_content_but_interpolation_survives(self):
        src = (
            "# internal note for maintainers only, never shown to a user\n"
            "flash[:notice] = \"Loaded #{count} items successfully\"\n"
        )
        blocks = _extract_blocks(src, "controller.rb", SCOPE_CONTENT)
        texts = [b.text for b in blocks]
        self.assertTrue(all("internal note" not in t for t in texts))


class TechnicalStringFiltering(unittest.TestCase):
    def test_snake_case_key_is_filtered(self):
        self.assertTrue(_looks_technical("request_failed"))
        self.assertTrue(_looks_technical("rate_limited"))
        self.assertFalse(_is_probably_content("request_failed"))

    def test_kebab_case_key_is_filtered(self):
        self.assertTrue(_looks_technical("gpt-legacy"))

    def test_capitalised_compound_word_is_not_filtered(self):
        # Real copy: "Text-to-speech", "Built-in" start uppercase.
        self.assertFalse(_looks_technical("Text-to-speech"))
        self.assertFalse(_looks_technical("Built-in"))

    def test_url_is_filtered(self):
        self.assertTrue(_looks_technical("https://example.com/docs"))
        self.assertTrue(_looks_technical("www.example.com"))

    def test_file_path_is_filtered(self):
        self.assertTrue(_looks_technical("src/components/Button.tsx"))
        self.assertTrue(_looks_technical("./assets/logo.png"))

    def test_mime_type_is_filtered(self):
        self.assertTrue(_looks_technical("application/json"))
        self.assertTrue(_looks_technical("image/png"))

    def test_css_selector_is_filtered(self):
        self.assertTrue(_looks_technical(".btn-primary"))
        self.assertTrue(_looks_technical("#header"))

    def test_date_format_is_filtered(self):
        self.assertTrue(_looks_technical("YYYY-MM-DD"))
        self.assertTrue(_looks_technical("%Y-%m-%d %H:%M:%S"))

    def test_ordinary_sentence_is_not_filtered(self):
        self.assertFalse(_looks_technical("Please enter a valid email address"))
        self.assertFalse(_looks_technical("Dashboard"))

    def test_js_template_literal_with_substitution_is_filtered(self):
        # A backtick template literal captured with its expression still
        # unresolved is source code, not text a reader ever sees.
        self.assertTrue(_looks_technical("Hello, ${name}!"))
        self.assertTrue(_looks_technical("cv.check.${check.id}"))

    def test_i18n_mustache_placeholder_is_not_filtered(self):
        # {{name}} / {{count}} is i18next's own placeholder syntax inside
        # otherwise-finished, reviewable prose — real content, not a leak.
        self.assertFalse(_looks_technical("{{count}} items left"))
        self.assertFalse(_looks_technical('Delete "{{name}}" from history?'))


class VueBoundAttributeLeak(unittest.TestCase):
    def test_static_placeholder_is_content(self):
        src = '<input placeholder="Search the docs" />\n'
        self.assertIn("Search the docs", content_texts(src, "Search.vue"))

    def test_bound_shorthand_colon_placeholder_is_not_content(self):
        src = '<input :placeholder="searchPlaceholder" />\n'
        self.assertEqual(content_texts(src, "Search.vue"), [])

    def test_v_bind_prefixed_title_is_not_content(self):
        src = '<span v-bind:title="computedTitle">x</span>\n'
        self.assertEqual(content_texts(src, "Widget.vue"), [])

    def test_static_title_is_still_content(self):
        src = '<span title="Click to expand the section">x</span>\n'
        self.assertIn("Click to expand the section", content_texts(src, "Widget.vue"))


if __name__ == "__main__":
    unittest.main()
