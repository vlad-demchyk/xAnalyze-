"""One run context joins acquisition, static checks and browser checks."""
from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import mock

import config
import diagnosis
from analysis_modes import (
    CHECK_AI_PATTERNS,
    AnalysisRequest,
    ExtractionSnapshot,
    RunContext,
)
from audit import browser, responsive
from audit.driver import PageAudit
from audit.engine import AccessibilityResult, DocumentReport
from models import CrawlDiagnostics

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class SnapshotEvidence(unittest.TestCase):
    def request(self, depth=2):
        return AnalysisRequest(target="https://example.test", depth=depth)

    def test_a_shallower_view_does_not_receive_deeper_pages(self):
        original = self.request(depth=3)
        pages = tuple(SimpleNamespace(depth=depth) for depth in range(4))
        snapshot = ExtractionSnapshot(request=original, pages=pages)

        selected = snapshot.pages_for(self.request(depth=1))

        self.assertEqual([page.depth for page in selected], [0, 1])

    def test_the_crawl_diagnostics_survive_reuse(self):
        walk = CrawlDiagnostics(pages_read=3, limit=3, queued_when_stopped=5)
        snapshot = ExtractionSnapshot(
            request=self.request(), pages=(SimpleNamespace(depth=0),),
            crawl=walk)

        revised = snapshot.updated(session_host="example.test")

        self.assertIs(revised.crawl, walk)
        self.assertTrue(revised.crawl.truncated)
        self.assertNotEqual(snapshot.snapshot_id, "")

    def test_cancellation_is_shared_by_the_whole_context(self):
        context = RunContext(self.request())
        self.assertFalse(context.cancellation())
        context.cancellation.cancel()
        self.assertTrue(context.cancellation())


class ViewModelRunBoundary(unittest.TestCase):
    def setUp(self):
        try:
            from ui.app_state import AppState
            from ui.view_model import MainViewModel
        except Exception as exc:  # noqa: BLE001
            self.skipTest(str(exc))
        self.state = AppState()
        self.state.set_target("https://example.test")
        self.state.set_checks((CHECK_AI_PATTERNS,))
        self.model = MainViewModel(self.state, config.Settings())

    def test_analyze_starts_fresh_and_acquires_off_the_gui_thread(self):
        old_request = self.model.current_request()
        self.model._remember_extraction(
            old_request, pages=[SimpleNamespace(depth=0, marker="old")])

        with mock.patch.object(self.model, "_render_for_request") as render, \
                mock.patch.object(self.model, "_start_audit") as audit:
            self.assertIsNone(self.model.analyze())

        render.assert_not_called()
        audit.assert_called_once_with()
        self.assertIsNone(self.model._cached_pages)

    def test_cancel_reaches_the_worker_and_the_run_token(self):
        self.model._begin_run(self.model.current_request())
        self.model._worker = mock.Mock()

        self.model.cancel()

        self.model._worker.cancel.assert_called_once_with()
        self.model._worker.requestInterruption.assert_called_once_with()
        self.assertTrue(self.model.cancellation_requested)

    def test_finishing_first_pass_does_not_release_the_second_worker(self):
        first = mock.Mock()
        second = mock.Mock()
        self.model._active_workers = [first, second]
        self.model._worker = second

        self.model._on_worker_finished(first)

        self.assertIs(self.model._worker, second)
        self.assertNotIn(first, self.model._active_workers)

    def test_rendered_crawl_uses_one_session_for_http_and_browser(self):
        self.model._begin_run(self.model.current_request())
        captured = {}

        def apply_to(crawl_config, target):
            crawl_config.cookies = {"sid": "secret"}
            captured["http"] = (target, dict(crawl_config.cookies))
            return "example.test", 1

        @contextmanager
        def renderer(*, session_host="", **_kwargs):
            captured["browser"] = session_host
            yield lambda _url: "<html><body>rendered</body></html>"

        def crawl(_url, crawl_config, **kwargs):
            captured["crawl_cookies"] = dict(crawl_config.cookies)
            captured["cancelled"] = kwargs.get("cancelled")
            kwargs["walk"].pages_read = 1
            return [SimpleNamespace(depth=0)]

        with mock.patch("audit.driver.available", return_value=(True, "")), \
                mock.patch("audit.driver.html_renderer", renderer), \
                mock.patch("site_session.apply_to", side_effect=apply_to), \
                mock.patch("crawler.crawl", side_effect=crawl):
            pages = self.model._render_crawl("https://example.test/private")

        self.assertEqual(len(pages), 1)
        self.assertEqual(captured["crawl_cookies"], {"sid": "secret"})
        self.assertEqual(captured["browser"], "example.test")
        self.assertIs(captured["cancelled"],
                      self.model._run_context.cancellation)
        self.assertEqual(self.model._acquired_crawl.pages_read, 1)

    def test_audit_acquisition_is_reused_by_the_copy_pass(self):
        pages = [SimpleNamespace(depth=0)]
        walk = CrawlDiagnostics(pages_read=1, limit=30)
        worker = SimpleNamespace(
            acquired_pages=pages, crawl=walk,
            session_host="example.test", session_values=1)
        self.model._begin_run(self.model.current_request())
        self.model._last_request = self.model.current_request()
        self.model._worker = worker
        self.model._pending_copy_pass = True

        with mock.patch.object(self.model, "_report_session"), \
                mock.patch.object(self.model, "_start_copy_pass") as copy:
            self.model._on_audit_finished(
                AccessibilityResult(root="https://example.test"))

        copy.assert_called_once_with()
        self.assertEqual(self.model._reusable_pages(), pages)
        self.assertIs(self.model._snapshot.crawl, walk)

    def test_browser_dom_is_remembered_with_the_static_crawl_depth(self):
        from models import PageDiagnostics, PageResult

        request = self.model.current_request()
        self.model._last_request = request
        self.model._begin_run(request)
        self.model._remember_extraction(
            request, pages=[PageResult(
                url="https://example.test/child", depth=2,
                diagnostics=PageDiagnostics(
                    status_code=200, content_type="text/html",
                    headers={"content-security-policy": "default-src 'self'"}))])

        self.model.remember_browser_html({
            "https://example.test/child":
                "<html><body><p>Rendered copy long enough to keep.</p></body></html>"
        })

        self.assertEqual(len(self.model._cached_pages), 1)
        self.assertEqual(self.model._cached_pages[0].depth, 2)
        self.assertIn("Rendered copy", self.model._cached_pages[0].raw_html)
        self.assertEqual(self.model._cached_pages[0].diagnostics.status_code, 200)
        self.assertIn("content-security-policy",
                      self.model._cached_pages[0].diagnostics.headers)

    def test_rendered_dom_replaces_response_shell_for_static_rules(self):
        import audit
        from crawler import page_from_html

        request = self.model.current_request()
        self.model._last_request = request
        self.model._begin_run(request)
        raw = page_from_html(
            "<html lang='en'><head><title>Page</title></head>"
            "<body><main><img src='logo.png'></main></body></html>",
            "https://example.test")
        self.model._remember_extraction(request, pages=[raw])
        self.model.audit_result = audit.analyze_pages(
            [raw], request.target, media=False)
        self.assertIn("image-alt",
                      {issue.rule_id for issue in self.model.audit_result.issues()})

        self.model.remember_browser_html({
            "https://example.test":
                "<html lang='en'><head><title>Page</title></head>"
                "<body><main><img src='logo.png' alt='Logo'></main></body></html>"
        })

        self.assertNotIn(
            "image-alt",
            {issue.rule_id for issue in self.model.audit_result.issues()})


class OneBrowserNavigation(unittest.TestCase):
    def test_breakpoints_resize_one_loaded_page(self):
        calls = []

        class Runner:
            def set_viewport(self, width, height):
                calls.append(("viewport", width, height))

            def audit(self, url):
                calls.append(("load", url))
                return PageAudit(url=url, html="<html>one revision</html>")

            def audit_loaded(self, url, options):
                calls.append(("probe", url, options.run_htmlcs,
                              options.capture_html))
                return PageAudit(url=url)

        answer = responsive.audit_responsive(
            "https://example.test", responsive.BREAKPOINTS,
            browser.BrowserAuditOptions(), runner=Runner())

        self.assertEqual([call for call in calls if call[0] == "load"],
                         [("load", "https://example.test")])
        probes = [call for call in calls if call[0] == "probe"]
        self.assertEqual(len(probes), len(responsive.BREAKPOINTS) - 1)
        self.assertTrue(all(call[2:] == (False, False) for call in probes))
        self.assertEqual(answer.html, "<html>one revision</html>")

    def test_cli_browser_runner_receives_the_session_profile(self):
        from cli_impl import auditpass

        seen = {}
        profile = object()

        class Runner:
            def __init__(self, _options, profile=None, cancelled=None):
                seen["profile"] = profile

            def audit(self, url):
                return PageAudit(url=url)

            def close(self):
                pass

        with mock.patch("audit.driver.BrowserAuditRunner", Runner), \
                mock.patch("audit.driver.ensure_headless_application"):
            auditpass._audit_at_widths(
                ["https://example.test"], browser.BrowserAuditOptions(), (),
                profile=profile)

        self.assertIs(seen["profile"], profile)


class PartialBrowserAnswer(unittest.TestCase):
    def result(self):
        document = DocumentReport(source="https://example.test")
        return (AccessibilityResult(
            root=document.source, documents=[document]), document)

    def test_a_page_failure_is_first_class_diagnostics(self):
        result, document = self.result()

        merged = browser.merge_page_audit(
            result, document,
            PageAudit(url=document.source, error="load timed out"))

        self.assertFalse(merged)
        self.assertEqual(result.browser_errors[0]["error"], "load timed out")
        notices = diagnosis.diagnose_audit(result)
        self.assertEqual(notices[0].kind, diagnosis.BROWSER_INCOMPLETE)

    def test_one_engine_failure_keeps_other_browser_answers(self):
        result, document = self.result()

        merged = browser.merge_page_audit(
            result, document,
            PageAudit(url=document.source, engine_errors={"axe": "timeout"}))

        self.assertTrue(merged)
        self.assertEqual(result.browser_errors[0]["engine"], "axe")


class DesktopBrowserSession(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtWidgets import QApplication

            from ui.main_window import MainWindow
        except Exception as exc:  # noqa: BLE001
            raise unittest.SkipTest(str(exc))
        cls.app = QApplication.instance() or QApplication([])
        cls.MainWindow = MainWindow

    def test_responsive_pass_uses_the_run_session_profile(self):
        window = self.MainWindow()
        self.addCleanup(window.close)
        window.app_state.set_target("https://example.test")
        request = window.view_model.current_request()
        window.view_model._remember_extraction(
            request, pages=[SimpleNamespace(depth=0)],
            session_host="example.test", session_values=1)
        result, _document = PartialBrowserAnswer().result()
        window.audit_result = result
        window.view_model.audit_result = result
        profile = object()
        seen = {}

        class Runner:
            def __init__(self, _options, profile=None, cancelled=None):
                seen["profile"] = profile
                seen["cancelled"] = cancelled

            def close(self):
                pass

        with mock.patch("audit.driver.available", return_value=(True, "")), \
                mock.patch("audit.driver.session_profile", return_value=profile), \
                mock.patch("audit.driver.BrowserAuditRunner", Runner), \
                mock.patch("audit.responsive.audit_responsive",
                           return_value=PageAudit(url="https://example.test")), \
                mock.patch("suppression.Suppressions.load",
                           return_value=SimpleNamespace(selectors=[], rules=[])), \
                mock.patch.object(window, "_populate_audit_list"), \
                mock.patch.object(window, "_refresh_summary"), \
                mock.patch.object(window, "_update_audit_buttons_enabled"), \
                mock.patch.object(window, "diagnose_finished_run"):
            window._run_browser_pass()

        self.assertIs(seen["profile"], profile)
        self.assertFalse(seen["cancelled"]())

    def test_browser_pass_targets_acquired_pages_not_media_documents(self):
        window = self.MainWindow()
        self.addCleanup(window.close)
        source = "https://example.test"
        window.app_state.set_target(source)
        request = window.view_model.current_request()
        window.view_model._remember_extraction(
            request, pages=[SimpleNamespace(url=source, depth=0)])
        result = AccessibilityResult(root=source, documents=[
            DocumentReport(source=source),
            DocumentReport(source="https://example.test/hero.jpg"),
        ])
        window.audit_result = result
        window.view_model.audit_result = result
        seen = []

        class Runner:
            def __init__(self, _options, profile=None, cancelled=None):
                pass

            def close(self):
                pass

        def responsive(address, *_args, **_kwargs):
            seen.append(address)
            return PageAudit(url=address)

        with mock.patch("audit.driver.available", return_value=(True, "")), \
                mock.patch("audit.driver.BrowserAuditRunner", Runner), \
                mock.patch("audit.responsive.audit_responsive",
                           side_effect=responsive), \
                mock.patch("suppression.Suppressions.load",
                           return_value=SimpleNamespace(selectors=[], rules=[])), \
                mock.patch.object(window, "_populate_audit_list"), \
                mock.patch.object(window, "_refresh_summary"), \
                mock.patch.object(window, "_update_audit_buttons_enabled"), \
                mock.patch.object(window, "diagnose_finished_run"):
            window._run_browser_pass()

        self.assertEqual(seen, [source])


if __name__ == "__main__":
    unittest.main()
