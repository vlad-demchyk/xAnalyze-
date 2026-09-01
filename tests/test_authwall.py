"""Whether what was audited is the site, or the door in front of it.

The failure this pass exists for is not a crash and not a wrong finding: it
is a *confident* report about a login form. A crawl that walks into a wall
fetches the sign-in page, finds three things wrong with it, and says "40
pages, 3 findings" - which reads as a verdict on the application behind the
wall, and is a verdict on its front door.
"""
from __future__ import annotations

import unittest

import audit
import diagnosis as dx
from audit import authwall
from models import PageDiagnostics, PageResult
from report.model import from_accessibility
from report.template import render_html


def page(url="https://x.test/", html="", status=None, headers=None, final=""):
    return PageResult(
        url=url, depth=0, raw_html=html,
        diagnostics=PageDiagnostics(status_code=status, final_url=final,
                                    headers=headers or {}))


class WhatCountsAsADoor(unittest.TestCase):
    def test_401_names_its_own_scheme(self):
        wall = authwall.inspect(page(
            status=401, headers={"www-authenticate": 'Basic realm="staging"'}))
        self.assertEqual(wall.signal, authwall.HTTP_401)
        self.assertEqual(wall.detail, "Basic")
        self.assertTrue(wall.certain)

    def test_403_is_recorded_as_the_weaker_signal_it_is(self):
        """No `WWW-Authenticate`: the server declined without saying how to
        get in, which may be a wall and may be a permission."""
        wall = authwall.inspect(page(status=403))
        self.assertEqual(wall.signal, authwall.HTTP_403)
        self.assertFalse(wall.certain)

    def test_a_password_field_is_the_page_saying_what_it_is(self):
        wall = authwall.inspect(page(
            html='<form action="/session"><input type="password"></form>'))
        self.assertEqual(wall.signal, authwall.PASSWORD_FORM)
        self.assertTrue(wall.certain)

    def test_current_password_autocomplete_counts_too(self):
        wall = authwall.inspect(page(
            html='<input autocomplete="current-password">'))
        self.assertEqual(wall.signal, authwall.PASSWORD_FORM)

    def test_a_redirect_to_a_sign_in_address_is_a_wall(self):
        wall = authwall.inspect(page(
            url="https://x.test/admin",
            final="https://x.test/login?returnUrl=%2Fadmin"))
        self.assertEqual(wall.signal, authwall.LOGIN_REDIRECT)

    def test_an_ordinary_page_is_not_a_wall(self):
        self.assertIsNone(authwall.inspect(page(html="<h1>Pricing</h1>")))

    def test_a_page_about_logging_in_is_not_a_login_page(self):
        """`/why-login-matters` is a marketing page. The path is only asked
        about when the body gave nothing away."""
        self.assertIsNone(authwall.inspect(
            page(url="https://x.test/blog/why-login-matters",
                 html="<h1>Why login matters</h1>")))


class OneWallNotFortyPages(unittest.TestCase):
    def test_the_run_counts_what_it_read_alongside_what_was_walled(self):
        report = authwall.scan([
            page(url="https://x.test/a", html="<input type=password>"),
            page(url="https://x.test/b", html="<input type=password>"),
            page(url="https://x.test/c", html="<h1>Public</h1>"),
        ])
        self.assertEqual((report.blocked, report.pages_read), (2, 3))
        self.assertFalse(report.whole_site)
        self.assertEqual(list(report.by_signal()), [authwall.PASSWORD_FORM])

    def test_a_crawl_that_read_nothing_but_doors_says_exactly_that(self):
        report = authwall.scan([
            page(url=f"https://x.test/{n}", html="<input type=password>")
            for n in range(4)])
        self.assertTrue(report.whole_site)


class ItReachesTheRun(unittest.TestCase):
    def result(self, pages):
        return audit.analyze_pages(pages, "https://x.test", media=False)

    def test_an_audit_carries_the_wall_report(self):
        result = self.result([page(html="<input type=password>")])
        self.assertEqual(result.auth.blocked, 1)

    def test_a_clean_site_carries_an_empty_one(self):
        result = self.result([page(html="<html><body><h1>Hi</h1></body></html>")])
        self.assertEqual(result.auth.blocked, 0)

    def test_the_window_gets_one_notice_per_crawl_not_per_address(self):
        result = self.result([
            page(url=f"https://x.test/{n}", html="<input type=password>")
            for n in range(5)])
        notices = dx.diagnose_auth_wall(result)
        self.assertEqual(len(notices), 1)
        self.assertEqual(notices[0].kind, dx.AUTH_WALL_WHOLE)
        self.assertEqual(notices[0].fields["blocked"], 5)

    def test_a_partly_walled_crawl_is_the_milder_notice(self):
        result = self.result([
            page(url="https://x.test/a", html="<input type=password>"),
            page(url="https://x.test/b", html="<html><body><h1>Hi</h1></body></html>"),
        ])
        self.assertEqual([n.kind for n in dx.diagnose_auth_wall(result)],
                         [dx.AUTH_WALL])

    def test_a_clean_crawl_produces_no_notice(self):
        result = self.result([page(html="<html><body><h1>Hi</h1></body></html>")])
        self.assertEqual(dx.diagnose_auth_wall(result), [])

    def test_both_notices_read_as_sentences_in_every_language(self):
        from i18n.translations import t

        result = self.result([page(html="<input type=password>")])
        for notice in dx.diagnose_auth_wall(result):
            for lang in ("uk", "it", "en"):
                for key in (notice.title_key, notice.body_key):
                    self.assertNotEqual(t(key, lang, **notice.fields), key)


class TheReportSaysItFirst(unittest.TestCase):
    """The report is the artefact somebody hands to somebody else, and "40
    pages, 3 findings" over a login form is the one sentence in it that
    would be a lie."""

    def model(self, pages):
        return from_accessibility(
            audit.analyze_pages(pages, "https://x.test", media=False), "en")

    def test_a_walled_run_carries_the_section(self):
        model = self.model([page(html="<input type=password>")])
        self.assertEqual(model.auth["blocked"], 1)
        html = render_html(model, "en")
        self.assertIn('<section class="authwall">', html)
        self.assertIn("What was behind a login", html)

    def test_a_clean_run_has_no_section_at_all(self):
        model = self.model([page(html="<html><body><h1>Hi</h1></body></html>")])
        self.assertEqual(model.auth, {})
        self.assertNotIn('<section class="authwall">',
                         render_html(model, "en"))

    def test_the_section_is_written_in_every_language(self):
        model = self.model([page(html="<input type=password>")])
        for lang, heading in (("uk", "Що було за логіном"),
                              ("it", "Che cosa stava dietro un accesso"),
                              ("en", "What was behind a login")):
            self.assertIn(heading, render_html(model, lang))


if __name__ == "__main__":
    unittest.main()
