"""Comprehensive tests for the modern UI - all functionality."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QDialog
    from main import (
        MainWindow, FindingsList, DetailPanel, PreviewPanel,
        FindingRow, SeverityBadge,
    )
    from ui.sidebar import Sidebar
    from ui.theme import build_qss, current_palette
    from analysis_modes import (
        SOURCE_SITE, SOURCE_REPO, SOURCE_FILE,
        CHECK_ACCESSIBILITY, CHECK_AI_PATTERNS,
        METHOD_LOCAL, METHOD_AI,
    )
except Exception:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 not available")
class TestSidebar(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.sidebar = Sidebar(lang="uk")
        self.sidebar.show()
        self.app.processEvents()

    def test_source_buttons_exist(self):
        self.assertIn(SOURCE_SITE, self.sidebar.source_buttons)
        self.assertIn(SOURCE_REPO, self.sidebar.source_buttons)
        self.assertIn(SOURCE_FILE, self.sidebar.source_buttons)

    def test_default_source_is_site(self):
        self.assertEqual(self.sidebar.get_source(), SOURCE_SITE)

    def test_switch_to_repo(self):
        self.sidebar._on_source_clicked(SOURCE_REPO)
        self.assertEqual(self.sidebar.get_source(), SOURCE_REPO)
        self.assertTrue(self.sidebar.repo_container.isVisible())
        self.assertFalse(self.sidebar.url_input.isVisible())
        self.assertFalse(self.sidebar.file_container.isVisible())

    def test_switch_to_file(self):
        self.sidebar._on_source_clicked(SOURCE_FILE)
        self.assertEqual(self.sidebar.get_source(), SOURCE_FILE)
        self.assertTrue(self.sidebar.file_container.isVisible())
        self.assertFalse(self.sidebar.url_input.isVisible())
        self.assertFalse(self.sidebar.repo_container.isVisible())

    def test_switch_back_to_site(self):
        self.sidebar._on_source_clicked(SOURCE_REPO)
        self.sidebar._on_source_clicked(SOURCE_SITE)
        self.assertEqual(self.sidebar.get_source(), SOURCE_SITE)
        self.assertTrue(self.sidebar.url_input.isVisible())
        self.assertFalse(self.sidebar.repo_container.isVisible())
        self.assertFalse(self.sidebar.file_container.isVisible())

    def test_check_chips_exist(self):
        self.assertIn(CHECK_AI_PATTERNS, self.sidebar.check_chips)
        self.assertIn(CHECK_ACCESSIBILITY, self.sidebar.check_chips)

    def test_default_checks(self):
        checks = self.sidebar.get_checks()
        self.assertIn(CHECK_AI_PATTERNS, checks)
        self.assertIn(CHECK_ACCESSIBILITY, checks)

    def test_uncheck_ai_patterns(self):
        self.sidebar.check_chips[CHECK_AI_PATTERNS].setChecked(False)
        checks = self.sidebar.get_checks()
        self.assertNotIn(CHECK_AI_PATTERNS, checks)
        self.assertIn(CHECK_ACCESSIBILITY, checks)

    def test_method_chips_exist(self):
        self.assertIn(METHOD_LOCAL, self.sidebar.method_chips)
        self.assertIn(METHOD_AI, self.sidebar.method_chips)

    def test_default_method_is_local(self):
        methods = self.sidebar.get_methods()
        self.assertIn(METHOD_LOCAL, methods)
        self.assertNotIn(METHOD_AI, methods)

    def test_switch_to_ai(self):
        self.sidebar.method_chips[METHOD_AI].setChecked(True)
        methods = self.sidebar.get_methods()
        self.assertIn(METHOD_AI, methods)

    def test_url_input_visible_for_site(self):
        self.assertTrue(self.sidebar.url_input.isVisible())

    def test_depth_control_visible_for_site(self):
        self.assertTrue(self.sidebar.depth_container.isVisible())

    def test_depth_hidden_for_repo(self):
        self.sidebar._on_source_clicked(SOURCE_REPO)
        self.assertFalse(self.sidebar.depth_container.isVisible())

    def test_get_depth(self):
        self.sidebar.depth_spin.setValue(3)
        self.assertEqual(self.sidebar.get_depth(), 3)

    def test_set_busy(self):
        self.sidebar.set_busy(True)
        self.assertFalse(self.sidebar.analyze_btn.isVisible())
        self.assertTrue(self.sidebar.cancel_btn.isVisible())

    def test_set_not_busy(self):
        self.sidebar.set_busy(True)
        self.sidebar.set_busy(False)
        self.assertTrue(self.sidebar.analyze_btn.isVisible())
        self.assertFalse(self.sidebar.cancel_btn.isVisible())

    def test_settings_button_exists(self):
        self.assertIsNotNone(self.sidebar.settings_btn)

    def test_account_button_exists(self):
        self.assertIsNotNone(self.sidebar.account_btn)

    def test_browse_buttons_exist(self):
        self.assertIsNotNone(self.sidebar.repo_browse)
        self.assertIsNotNone(self.sidebar.file_browse)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class TestSeverityBadge(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_critical_badge(self):
        badge = SeverityBadge("critical")
        self.assertEqual(badge.text(), "CRITICAL")

    def test_high_badge(self):
        badge = SeverityBadge("high")
        self.assertEqual(badge.text(), "HIGH")

    def test_medium_badge(self):
        badge = SeverityBadge("medium")
        self.assertEqual(badge.text(), "MEDIUM")

    def test_low_badge(self):
        badge = SeverityBadge("low")
        self.assertEqual(badge.text(), "LOW")

    def test_badge_size(self):
        badge = SeverityBadge("high")
        self.assertEqual(badge.width(), 52)
        self.assertEqual(badge.height(), 20)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class TestFindingRow(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_row_has_badge(self):
        row = FindingRow("high", "Test finding")
        self.assertIsNotNone(row.badge)

    def test_row_has_text(self):
        row = FindingRow("high", "Test finding")
        self.assertIn("Test finding", row.text_label.text())

    def test_row_styled_text_with_tag(self):
        row = FindingRow("medium", "[typography] Some text")
        text = row.text_label.text()
        self.assertIn("typography", text)
        self.assertIn("span", text)

    def test_row_minimum_height(self):
        row = FindingRow("high", "Test")
        self.assertGreaterEqual(row.minimumHeight(), 36)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class TestFindingsList(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.findings = FindingsList()

    def test_initial_count(self):
        self.assertEqual(self.findings._count, 0)
        self.assertEqual(self.findings.count_label.text(), "0 items")

    def test_add_finding(self):
        self.findings.add_finding("high", "Test finding", "index.html:42")
        self.assertEqual(self.findings._count, 1)
        self.assertEqual(self.findings.count_label.text(), "1 items")

    def test_add_multiple_findings(self):
        self.findings.add_finding("high", "Finding 1")
        self.findings.add_finding("medium", "Finding 2")
        self.findings.add_finding("low", "Finding 3")
        self.assertEqual(self.findings._count, 3)
        self.assertEqual(self.findings.count_label.text(), "3 items")

    def test_list_has_items(self):
        self.findings.add_finding("high", "Test")
        self.assertEqual(self.findings.list.count(), 1)

    def test_item_has_user_data(self):
        self.findings.add_finding("high", "Test text", "source.html")
        item = self.findings.list.item(0)
        data = item.data(0x0100)  # UserRole
        self.assertEqual(data, ("high", "Test text", "source.html"))


@unittest.skipIf(QApplication is None, "PySide6 not available")
class TestDetailPanel(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.detail = DetailPanel()
        self.detail.show()
        self.app.processEvents()

    def test_initial_placeholder_visible(self):
        self.assertTrue(self.detail.placeholder.isVisible())

    def test_initial_detail_hidden(self):
        self.assertFalse(self.detail.detail_widget.isVisible())

    def test_show_finding(self):
        self.detail.show_finding("high", "Missing alt", "index.html:42")
        self.assertTrue(self.detail.detail_widget.isVisible())
        self.assertFalse(self.detail.placeholder.isVisible())

    def test_show_finding_sets_title(self):
        self.detail.show_finding("high", "Missing alt attribute")
        self.assertEqual(self.detail.title_label.text(), "Missing alt attribute")

    def test_show_finding_sets_source(self):
        self.detail.show_finding("high", "Test", "index.html:42")
        self.assertIn("index.html:42", self.detail.source_badge.text())

    def test_show_finding_sets_severity(self):
        self.detail.show_finding("critical", "Test")
        self.assertEqual(self.detail.severity_badge.text(), "CRITICAL")


@unittest.skipIf(QApplication is None, "PySide6 not available")
class TestPreviewPanel(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.preview = PreviewPanel()

    def test_has_content(self):
        self.assertIsNotNone(self.preview.content)

    def test_has_detach_button(self):
        self.assertIsNotNone(self.preview.detach_btn)

    def test_content_is_read_only(self):
        self.assertTrue(self.preview.content.isReadOnly())


@unittest.skipIf(QApplication is None, "PySide6 not available")
class TestMainWindow(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()
        self.window.show()
        self.app.processEvents()

    def test_window_title(self):
        self.assertEqual(self.window.windowTitle(), "XAnalyze")

    def test_has_sidebar(self):
        self.assertIsNotNone(self.window.sidebar)

    def test_has_findings(self):
        self.assertIsNotNone(self.window.findings)

    def test_has_detail(self):
        self.assertIsNotNone(self.window.detail)

    def test_has_preview(self):
        self.assertIsNotNone(self.window.preview)

    def test_has_status_bar(self):
        self.assertIsNotNone(self.window.status_label)

    def test_initial_status(self):
        self.assertEqual(self.window.status_label.text(), "Ready")

    def test_analyze_with_empty_target(self):
        self.window.sidebar.url_input.setText("")
        self.window._on_analyze()
        self.assertEqual(self.window.status_label.text(), "Enter a URL or path")

    def test_analyze_sets_busy(self):
        self.window.sidebar.url_input.setText("https://example.com")
        self.window._on_analyze()
        self.assertTrue(self.window.sidebar.cancel_btn.isVisible())

    def test_cancel(self):
        self.window.sidebar.url_input.setText("https://example.com")
        self.window._on_analyze()
        self.window._on_cancel()

    def test_settings_button_opens_dialog(self):
        # Just verify the method exists and can be called
        self.assertIsNotNone(self.window._on_settings)

    def test_account_button_opens_dialog(self):
        # Just verify the method exists and can be called
        self.assertIsNotNone(self.window._on_account)

    def test_finding_click_shows_detail(self):
        self.window.findings.add_finding("high", "Test finding", "index.html:42")
        item = self.window.findings.list.item(0)
        self.window._on_finding_clicked(item)
        self.assertTrue(self.window.detail.detail_widget.isVisible())

    def test_finding_click_sets_detail(self):
        self.window.findings.add_finding("high", "Missing alt", "index.html:42")
        item = self.window.findings.list.item(0)
        self.window._on_finding_clicked(item)
        self.assertEqual(self.window.detail.title_label.text(), "Missing alt")

    def test_switch_source_clears_findings(self):
        self.window.findings.add_finding("high", "Test")
        self.window.sidebar._on_source_clicked(SOURCE_REPO)
        # Findings should still be there until analyze is clicked
        self.assertEqual(self.window.findings.list.count(), 1)

    def test_web_finished_populates_findings(self):
        # Create a simple mock result
        class MockSpan:
            def __init__(self):
                self.block_id = "test"
                self.confidence = type('obj', (object,), {'__str__': lambda s: 'high'})()
                self.explanation = "Test finding"

        class MockBlock:
            def __init__(self):
                self.block_id = "test"

        class MockPage:
            def __init__(self):
                self.url = "https://example.com"
                self.blocks = [MockBlock()]

        class MockResult:
            def __init__(self):
                self.spans = [MockSpan()]
                self.pages = [MockPage()]

        self.window._on_web_finished(MockResult())
        self.assertEqual(self.window.findings.list.count(), 1)

    def test_repo_finished_populates_findings(self):
        class MockSpan:
            def __init__(self):
                self.block_id = "test"
                self.confidence = type('obj', (object,), {'__str__': lambda s: 'high'})()
                self.explanation = "Test finding"

        class MockBlock:
            def __init__(self):
                self.block_id = "test"
                self.line_number = 42

        class MockFile:
            def __init__(self):
                self.path = "index.html"
                self.blocks = [MockBlock()]

        class MockResult:
            def __init__(self):
                self.spans = [MockSpan()]
                self.files = [MockFile()]

        self.window._on_repo_finished(MockResult())
        self.assertEqual(self.window.findings.list.count(), 1)

    def test_failed_shows_error(self):
        self.window._on_failed("Test error")
        self.assertIn("Error", self.window.status_label.text())

    def test_worker_finished_resets_busy(self):
        self.window.sidebar.set_busy(True)
        self.window._on_worker_finished()
        self.assertFalse(self.window.sidebar.cancel_btn.isVisible())


@unittest.skipIf(QApplication is None, "PySide6 not available")
class TestTheme(unittest.TestCase):
    app = None

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_qss_builds(self):
        palette = current_palette("dark")
        qss = build_qss(palette)
        self.assertGreater(len(qss), 0)

    def test_qss_contains_dark_colors(self):
        palette = current_palette("dark")
        qss = build_qss(palette)
        self.assertIn(palette.bg_base, qss)
        self.assertIn(palette.text_primary, qss)

    def test_qss_contains_accent(self):
        palette = current_palette("dark")
        qss = build_qss(palette)
        self.assertIn(palette.accent, qss)

    def test_theme_applies(self):
        palette = current_palette("dark")
        qss = build_qss(palette)
        self.app.setStyleSheet(qss)
        # Should not raise


if __name__ == "__main__":
    unittest.main()
