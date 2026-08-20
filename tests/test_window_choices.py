"""The window's four controls, checked against what they are supposed to mean.

Headless: Qt runs on the offscreen platform, so this asserts about widget
state, never about pixels.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
    from ui.main_window import MainWindow
    from analysis_modes import (
        CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS, METHOD_AI, METHOD_LOCAL,
        READER_BROWSER, READER_CODE, SOURCE_FILE, SOURCE_REPO, SOURCE_SITE,
    )
    from i18n.translations import t
except Exception as exc:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None
    _reason = str(exc)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class Choices(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.window = MainWindow()

    def _select(self, combo, value):
        """Pick a choice combo's entry by the choices it stands for."""
        self._select_raw(combo, MainWindow.choice_key(value))

    def _select_raw(self, combo, value):
        index = combo.findData(value)
        self.assertGreaterEqual(index, 0, f"{value} is not offered")
        combo.setCurrentIndex(index)

    def test_the_source_combo_offers_sources_only(self):
        offered = [self.window.mode_combo.itemData(i)
                   for i in range(self.window.mode_combo.count())]
        self.assertEqual(offered, [SOURCE_SITE, SOURCE_REPO, SOURCE_FILE])

    def test_a_repository_offers_no_browser_reading(self):
        self._select_raw(self.window.mode_combo, SOURCE_REPO)
        offered = [self.window.reader_combo.itemData(i)
                   for i in range(self.window.reader_combo.count())]
        self.assertEqual(offered, [MainWindow.choice_key((READER_CODE,))])
        self.assertFalse(self.window.reader_combo.isEnabled())

    def test_a_site_offers_code_browser_and_both(self):
        self._select_raw(self.window.mode_combo, SOURCE_SITE)
        offered = [self.window.reader_combo.itemData(i)
                   for i in range(self.window.reader_combo.count())]
        self.assertIn(MainWindow.choice_key((READER_CODE, READER_BROWSER)), offered)

    def test_both_questions_are_the_default(self):
        window = MainWindow()
        self.assertEqual(set(window.current_request().checks),
                         {CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS})

    def test_the_account_is_offered_when_a_model_judges_copy(self):
        """Two conditions, not one. The combo beside the method used to name
        a detector class and appeared for every copy run; it names the
        account now, and an offline-only run has no account question. Which
        engine judges the copy is the method's answer - see
        `test_method_reaches_the_run.py`."""
        self.window._ai_available = lambda: True
        self.window._retranslate_choices()
        self._select_raw(self.window.mode_combo, SOURCE_SITE)
        self._select(self.window.checks_combo, (CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS))
        self._select(self.window.method_combo, (METHOD_LOCAL, METHOD_AI))
        self.assertFalse(self.window.provider_combo.isHidden())
        # The regression this replaces: choosing an audit hid the control, so
        # a run that also judged copy had no way to say who judged it.
        self._select(self.window.checks_combo, (CHECK_ACCESSIBILITY,))
        self.assertTrue(self.window.provider_combo.isHidden())

    def test_a_copy_row_is_never_tagged_as_an_audit_row(self):
        self._select_raw(self.window.mode_combo, SOURCE_SITE)
        self._select(self.window.checks_combo, (CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS))
        self.assertNotEqual(self.window._text_row_kind(), "audit")

    def test_changing_the_question_reuses_the_fetched_pages(self):
        self._select_raw(self.window.mode_combo, SOURCE_SITE)
        self.window.url_edit.setText("https://example.com")
        self._select(self.window.checks_combo, (CHECK_ACCESSIBILITY,))
        first = self.window.current_request()
        self.window._remember_extraction(first, pages=["one", "two"])
        # Same site, different question: nothing to fetch again.
        self._select(self.window.checks_combo, (CHECK_AI_PATTERNS,))
        self.assertEqual(self.window._reusable_pages(), ["one", "two"])

    def test_a_new_target_does_not_reuse_them(self):
        self._select_raw(self.window.mode_combo, SOURCE_SITE)
        self.window.url_edit.setText("https://example.com")
        self.window._remember_extraction(self.window.current_request(),
                                         pages=["one"])
        self.window.url_edit.setText("https://other.example")
        self.assertIsNone(self.window._reusable_pages())

    def test_a_deeper_crawl_does_not_reuse_them(self):
        self._select_raw(self.window.mode_combo, SOURCE_SITE)
        self.window.url_edit.setText("https://example.com")
        self.window.depth_spin.setValue(0)
        self.window._remember_extraction(self.window.current_request(),
                                         pages=["one"])
        self.window.depth_spin.setValue(2)
        self.assertIsNone(self.window._reusable_pages())

    def test_changing_the_source_forgets_them(self):
        self._select_raw(self.window.mode_combo, SOURCE_SITE)
        self.window.url_edit.setText("https://example.com")
        self.window._remember_extraction(self.window.current_request(),
                                         pages=["one"])
        self._select_raw(self.window.mode_combo, SOURCE_REPO)
        self._select_raw(self.window.mode_combo, SOURCE_SITE)
        self.assertIsNone(self.window._reusable_pages())

    def test_the_file_source_reads_the_file_field(self):
        self._select_raw(self.window.mode_combo, SOURCE_FILE)
        self.window.file_path_edit.setText("/tmp/page.html")
        self.assertEqual(self.window.current_request().target, "/tmp/page.html")


@unittest.skipIf(QApplication is None, "PySide6 not available")
class AccountControl(unittest.TestCase):
    """The header states who pays, and signing in changes who does."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window(self, signed_in_detail=None):
        window = MainWindow()
        # Patched, not asked: the real answer is a network round trip, and the
        # question here is what the window does with each answer.
        status = None
        if signed_in_detail is not None:
            status = type("Status", (), {"signed_in": True,
                                         "detail": signed_in_detail})()
        window._account_cache = status
        window._refresh_account_control()
        return window

    def test_signed_out_offers_signing_in(self):
        window = self._window()
        self.assertEqual(window.account_btn.text(), t("settings_sign_in", window.lang))
        self.assertEqual(window.account_label.text(), "")

    def test_signed_in_shows_the_account_and_offers_signing_out(self):
        window = self._window("someone@example.com · pro")
        self.assertEqual(window.account_btn.text(), t("settings_sign_out", window.lang))
        self.assertEqual(window.account_label.text(), "someone@example.com · pro")

    def test_the_status_is_not_asked_twice(self):
        window = self._window()
        calls = []
        window._xformat_provider = lambda: calls.append(1)
        window._account_status()
        window._account_status()
        self.assertEqual(calls, [], "a cached answer must not be re-asked")

    def test_signing_in_selects_the_ai_method_alongside_the_local_one(self):
        window = self._window("someone@example.com · pro")
        window._ai_available = lambda: True
        window._select_ai_method()
        self.assertEqual(set(window.current_request().methods),
                         {METHOD_LOCAL, METHOD_AI})


if __name__ == "__main__":
    unittest.main()
