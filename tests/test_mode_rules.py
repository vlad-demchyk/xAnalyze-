"""Tests for mode_rules - pure validation logic."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from analysis_modes import (
    CHECK_ACCESSIBILITY,
    CHECK_AI_PATTERNS,
    METHOD_AI,
    METHOD_LOCAL,
    READER_BROWSER,
    READER_CODE,
    SOURCE_FILE,
    SOURCE_REPO,
    SOURCE_SITE,
)
from ui.mode_rules import (
    auto_readers,
    available_readers_for,
    col1_stack_index,
    derive_mode,
    generate_list_visible,
    method_available,
    normalize_method_choice,
    normalize_reader_choice,
    provider_visible,
    reader_available,
    source_controls_index,
)


class TestAvailableReaders(unittest.TestCase):
    def test_site_has_both(self):
        self.assertEqual(available_readers_for(SOURCE_SITE), (READER_CODE, READER_BROWSER))

    def test_repo_has_only_code(self):
        self.assertEqual(available_readers_for(SOURCE_REPO), (READER_CODE,))

    def test_file_has_both(self):
        self.assertEqual(available_readers_for(SOURCE_FILE), (READER_CODE, READER_BROWSER))

    def test_unknown_source_defaults_to_code(self):
        self.assertEqual(available_readers_for("unknown"), (READER_CODE,))


class TestAutoReaders(unittest.TestCase):
    def test_site_uses_both(self):
        self.assertEqual(auto_readers(SOURCE_SITE), (READER_CODE, READER_BROWSER))

    def test_repo_uses_code(self):
        self.assertEqual(auto_readers(SOURCE_REPO), (READER_CODE,))

    def test_file_uses_both(self):
        self.assertEqual(auto_readers(SOURCE_FILE), (READER_CODE, READER_BROWSER))


class TestReaderAvailable(unittest.TestCase):
    def test_browser_available_for_site(self):
        self.assertTrue(reader_available(SOURCE_SITE, READER_BROWSER))

    def test_browser_not_available_for_repo(self):
        self.assertFalse(reader_available(SOURCE_REPO, READER_BROWSER))

    def test_code_always_available(self):
        for source in (SOURCE_SITE, SOURCE_REPO, SOURCE_FILE):
            self.assertTrue(reader_available(source, READER_CODE))


class TestMethodAvailable(unittest.TestCase):
    def test_local_always_available(self):
        self.assertTrue(method_available(METHOD_LOCAL, ai_available=False))
        self.assertTrue(method_available(METHOD_LOCAL, ai_available=True))

    def test_ai_needs_account(self):
        self.assertFalse(method_available(METHOD_AI, ai_available=False))
        self.assertTrue(method_available(METHOD_AI, ai_available=True))


class TestProviderVisible(unittest.TestCase):
    def test_visible_when_ai_patterns_and_ai_method(self):
        self.assertTrue(provider_visible((CHECK_AI_PATTERNS,), (METHOD_AI,)))

    def test_hidden_when_local_only(self):
        self.assertFalse(provider_visible((CHECK_AI_PATTERNS,), (METHOD_LOCAL,)))

    def test_hidden_when_accessibility_only(self):
        self.assertFalse(provider_visible((CHECK_ACCESSIBILITY,), (METHOD_AI,)))

    def test_hidden_when_both_checks_but_local(self):
        self.assertFalse(
            provider_visible((CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS), (METHOD_LOCAL,))
        )


class TestDeriveMode(unittest.TestCase):
    def test_repo_source(self):
        self.assertEqual(derive_mode(SOURCE_REPO, (CHECK_AI_PATTERNS,)), "repo")

    def test_file_source(self):
        self.assertEqual(derive_mode(SOURCE_FILE, (CHECK_AI_PATTERNS,)), "file")

    def test_site_with_accessibility_only(self):
        self.assertEqual(derive_mode(SOURCE_SITE, (CHECK_ACCESSIBILITY,)), "audit")

    def test_site_with_ai_patterns(self):
        self.assertEqual(derive_mode(SOURCE_SITE, (CHECK_AI_PATTERNS,)), "web")

    def test_site_with_both(self):
        self.assertEqual(
            derive_mode(SOURCE_SITE, (CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS)), "web"
        )


class TestNormalizeReaderChoice(unittest.TestCase):
    def test_keeps_valid_choice(self):
        self.assertEqual(
            normalize_reader_choice(SOURCE_SITE, (READER_BROWSER,)), (READER_BROWSER,)
        )

    def test_drops_invalid_choice(self):
        self.assertEqual(
            normalize_reader_choice(SOURCE_REPO, (READER_BROWSER,)), (READER_CODE,)
        )

    def test_empty_falls_back_to_first_allowed(self):
        self.assertEqual(normalize_reader_choice(SOURCE_REPO, ()), (READER_CODE,))


class TestNormalizeMethodChoice(unittest.TestCase):
    def test_keeps_local(self):
        self.assertEqual(
            normalize_method_choice((METHOD_LOCAL,), ai_available=False), (METHOD_LOCAL,)
        )

    def test_drops_ai_when_unavailable(self):
        self.assertEqual(
            normalize_method_choice((METHOD_AI,), ai_available=False), (METHOD_LOCAL,)
        )

    def test_keeps_ai_when_available(self):
        self.assertEqual(
            normalize_method_choice((METHOD_AI,), ai_available=True), (METHOD_AI,)
        )

    def test_both_when_available(self):
        result = normalize_method_choice((METHOD_LOCAL, METHOD_AI), ai_available=True)
        self.assertEqual(result, (METHOD_LOCAL, METHOD_AI))


class TestButtonVisibility(unittest.TestCase):
    def test_generate_list_repo_only(self):
        self.assertTrue(generate_list_visible(SOURCE_REPO, (CHECK_AI_PATTERNS,)))
        self.assertFalse(generate_list_visible(SOURCE_SITE, (CHECK_AI_PATTERNS,)))

    def test_generate_list_needs_ai_patterns(self):
        self.assertFalse(generate_list_visible(SOURCE_REPO, (CHECK_ACCESSIBILITY,)))

    def test_col1_stack(self):
        self.assertEqual(col1_stack_index(SOURCE_REPO), 1)
        self.assertEqual(col1_stack_index(SOURCE_SITE), 0)

    def test_source_controls(self):
        self.assertEqual(source_controls_index(SOURCE_SITE), 0)
        self.assertEqual(source_controls_index(SOURCE_REPO), 1)
        self.assertEqual(source_controls_index(SOURCE_FILE), 2)


if __name__ == "__main__":
    unittest.main()
