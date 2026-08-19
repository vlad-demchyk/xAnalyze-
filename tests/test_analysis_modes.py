"""The three choices stay independent, and an impossible one is adjusted, not
refused.
"""
import unittest

from analysis_modes import (
    CHECKS, CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS, METHOD_AI, METHOD_LOCAL,
    READER_BROWSER, READER_CODE, SOURCE_FILE, SOURCE_REPO, SOURCE_SITE,
    AnalysisRequest, available_readers, supports_browser,
)


class Readers(unittest.TestCase):
    def test_a_repository_cannot_be_rendered(self):
        self.assertFalse(supports_browser(SOURCE_REPO))
        self.assertEqual(available_readers(SOURCE_REPO), (READER_CODE,))

    def test_a_site_and_a_single_file_can_be_both_read_and_rendered(self):
        for source in (SOURCE_SITE, SOURCE_FILE):
            self.assertEqual(available_readers(source),
                             (READER_CODE, READER_BROWSER))

    def test_asking_to_render_a_repository_is_adjusted_and_explained(self):
        request = AnalysisRequest(source=SOURCE_REPO,
                                  readers=(READER_CODE, READER_BROWSER)).normalised()
        self.assertEqual(request.readers, (READER_CODE,))
        self.assertTrue(any("browser" in note for note in request.notes))

    def test_both_readers_survive_where_they_are_possible(self):
        request = AnalysisRequest(source=SOURCE_SITE,
                                  readers=(READER_BROWSER, READER_CODE)).normalised()
        self.assertEqual(request.readers, (READER_CODE, READER_BROWSER))
        self.assertEqual(request.notes, [])


class ChecksAndMethods(unittest.TestCase):
    def test_the_two_checks_are_independent_of_the_source(self):
        request = AnalysisRequest(source=SOURCE_REPO,
                                  checks=(CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS)).normalised()
        self.assertTrue(request.wants_accessibility)
        self.assertTrue(request.wants_ai_patterns)

    def test_an_empty_choice_means_both_rather_than_nothing(self):
        request = AnalysisRequest(checks=()).normalised()
        self.assertEqual(request.checks, CHECKS)

    def test_the_ai_method_needs_an_account(self):
        request = AnalysisRequest(methods=(METHOD_LOCAL, METHOD_AI),
                                  ai_available=False).normalised()
        self.assertEqual(request.methods, (METHOD_LOCAL,))
        self.assertTrue(request.notes)

    def test_the_ai_method_is_kept_when_an_account_is_there(self):
        request = AnalysisRequest(methods=(METHOD_LOCAL, METHOD_AI),
                                  ai_available=True).normalised()
        self.assertEqual(request.methods, (METHOD_LOCAL, METHOD_AI))
        self.assertEqual(request.notes, [])

    def test_ai_only_falls_back_to_offline_rather_than_running_nothing(self):
        request = AnalysisRequest(methods=(METHOD_AI,), ai_available=False).normalised()
        self.assertEqual(request.methods, (METHOD_LOCAL,))


class ReusingWhatWasFetched(unittest.TestCase):
    def _site(self, **kw):
        return AnalysisRequest(source=SOURCE_SITE, target="https://example.com", **kw)

    def test_changing_the_question_does_not_need_a_new_crawl(self):
        first = self._site(checks=(CHECK_ACCESSIBILITY,)).normalised()
        second = self._site(checks=(CHECK_AI_PATTERNS,)).normalised()
        self.assertTrue(second.reuses_extraction(first))

    def test_changing_the_method_does_not_need_a_new_crawl(self):
        first = self._site(methods=(METHOD_LOCAL,)).normalised()
        second = self._site(methods=(METHOD_LOCAL, METHOD_AI), ai_available=True).normalised()
        self.assertTrue(second.reuses_extraction(first))

    def test_a_different_target_does(self):
        first = self._site().normalised()
        second = AnalysisRequest(source=SOURCE_SITE, target="https://other.example").normalised()
        self.assertFalse(second.reuses_extraction(first))

    def test_asking_for_the_rendered_page_after_a_plain_fetch_does(self):
        first = self._site(readers=(READER_CODE,)).normalised()
        second = self._site(readers=(READER_CODE, READER_BROWSER)).normalised()
        self.assertFalse(second.reuses_extraction(first))

    def test_but_dropping_the_browser_afterwards_does_not(self):
        first = self._site(readers=(READER_CODE, READER_BROWSER)).normalised()
        second = self._site(readers=(READER_CODE,)).normalised()
        self.assertTrue(second.reuses_extraction(first))

    def test_nothing_to_reuse_on_the_first_run(self):
        self.assertFalse(self._site().normalised().reuses_extraction(None))


if __name__ == "__main__":
    unittest.main()
