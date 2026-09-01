"""A signed-in run, and the rules that make one acceptable to ship.

Half of what is worth auditing is behind a login. The way in that does not
involve this tool handling credentials is the obvious one: a person signs in
themselves in a real browser window, and the run reuses what that browser was
given. Everything below is about the other half of that bargain - the session
is per host, it can be seen, it can be removed, and nothing about its
contents ever leaves the machine's own storage.
"""
from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path


class _Isolated(unittest.TestCase):
    """Every case runs against its own config directory, never the
    developer's - a test that writes a session into the real one is a test
    that hands the next run somebody's account."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._previous = os.environ.get("XDG_CONFIG_HOME")
        os.environ["XDG_CONFIG_HOME"] = self._tmp.name
        self.addCleanup(self._restore)

    def _restore(self):
        if self._previous is None:
            os.environ.pop("XDG_CONFIG_HOME", None)
        else:
            os.environ["XDG_CONFIG_HOME"] = self._previous


class WhichSessionBelongsToWhom(_Isolated):
    def test_the_port_is_part_of_the_host(self):
        import site_session as ss

        self.assertEqual(ss.host_of("http://localhost:3000/admin"), "localhost:3000")
        self.assertNotEqual(ss.host_of("http://localhost:3000/"),
                            ss.host_of("http://localhost:8080/"))

    def test_a_bare_hostname_is_read_as_one(self):
        import site_session as ss

        self.assertEqual(ss.host_of("staging.example.com/admin"),
                         "staging.example.com")

    def test_nothing_is_not_a_host(self):
        import site_session as ss

        self.assertEqual(ss.host_of(""), "")
        self.assertEqual(ss.host_of("   "), "")

    def test_a_session_for_one_host_is_not_a_session_for_another(self):
        import site_session as ss

        ss.save_cookies("staging.example.com", {"sid": "x"})
        self.assertTrue(ss.has_session("staging.example.com"))
        self.assertFalse(ss.has_session("example.com"))
        self.assertEqual(ss.load_cookies("example.com"), {})

    def test_an_empty_directory_is_not_a_session(self):
        """The profile directory is created when the sign-in window opens.
        Somebody who closed that window without signing in must not be told
        they are signed in."""
        import site_session as ss

        ss.profile_dir("example.com", create=True)
        self.assertFalse(ss.has_session("example.com"))


class ItCanBeSeenAndRemoved(_Isolated):
    def test_the_hosts_are_listable(self):
        import site_session as ss

        ss.save_cookies("a.example", {"s": "1"})
        ss.save_cookies("b.example", {"s": "1"})
        self.assertEqual(ss.known_hosts(), ["a.example", "b.example"])

    def test_forgetting_one_host_leaves_the_other(self):
        import site_session as ss

        ss.save_cookies("a.example", {"s": "1"})
        ss.save_cookies("b.example", {"s": "1"})
        self.assertTrue(ss.forget("a.example"))
        self.assertEqual(ss.known_hosts(), ["b.example"])

    def test_forgetting_removes_the_cookies_too_and_not_only_the_profile(self):
        import site_session as ss

        ss.save_cookies("a.example", {"s": "1"})
        path = ss.cookies_path("a.example")
        ss.forget("a.example")
        self.assertFalse(path.exists())
        self.assertEqual(ss.load_cookies("a.example"), {})

    def test_forgetting_everything_reports_how_much_there_was(self):
        import site_session as ss

        ss.save_cookies("a.example", {"s": "1"})
        ss.save_cookies("b.example", {"s": "1"})
        self.assertEqual(ss.forget_all(), 2)
        self.assertEqual(ss.known_hosts(), [])

    def test_forgetting_a_host_that_has_nothing_says_so(self):
        import site_session as ss

        self.assertFalse(ss.forget("nobody.example"))


class NothingLeaksOut(_Isolated):
    def test_the_cookie_file_is_readable_by_its_owner_only(self):
        import site_session as ss

        ss.save_cookies("a.example", {"sid": "secret"})
        mode = stat.S_IMODE(ss.cookies_path("a.example").stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_the_description_carries_the_fact_and_not_the_session(self):
        import site_session as ss

        ss.save_cookies("a.example", {"sid": "secret"})
        described = ss.describe("a.example")
        self.assertIn("a.example", described)
        self.assertNotIn("secret", described)
        self.assertNotIn("sid", described)

    def test_a_host_with_no_session_describes_as_nothing(self):
        import site_session as ss

        self.assertEqual(ss.describe("a.example"), "")

    def test_an_unreadable_store_is_a_run_without_a_session(self):
        """Never an exception: a session that cannot be read is one the run
        does not have, and a scan that raises over it has thrown away work
        it already did."""
        import site_session as ss

        path = ss.profile_dir("a.example", create=True) / "cookies.json"
        path.write_text("{ this is not json", encoding="utf-8")
        self.assertEqual(ss.load_cookies("a.example"), {})


class BothClientsOrNeither(_Isolated):
    """`requests` fetches the pages and QtWebEngine renders them, and they
    share no storage. Handing the session to one produces a run where the
    browser sees the account and the fetch sees the login form."""

    def config(self):
        from crawler import CrawlConfig

        return CrawlConfig(max_depth=0, max_pages=1)

    def test_applying_a_session_fills_the_fetchers_cookies(self):
        import site_session as ss

        ss.save_cookies("a.example", {"sid": "x", "csrf": "y"})
        config = self.config()
        host, count = ss.apply_to(config, "https://a.example/admin")
        self.assertEqual((host, count), ("a.example", 2))
        self.assertEqual(config.cookies, {"sid": "x", "csrf": "y"})

    def test_no_session_changes_nothing(self):
        import site_session as ss

        config = self.config()
        self.assertEqual(ss.apply_to(config, "https://a.example/"), ("", 0))
        self.assertEqual(config.cookies, {})

    def test_the_crawler_sends_what_it_was_given(self):
        """Set on the session rather than as a header, so redirects and the
        site's own Set-Cookie behave the way a browser makes them behave."""
        import crawler

        captured = {}

        class _FakeSession:
            def __init__(self):
                self.headers = {}
                self.cookies = self

            def set(self, name, value):
                captured[name] = value

            def get(self, *_args, **_kwargs):
                raise RuntimeError("stop here")

        original = crawler.requests.Session
        crawler.requests.Session = _FakeSession
        try:
            crawler.crawl("https://a.example/",
                          crawler.CrawlConfig(max_depth=0, max_pages=1,
                                              cookies={"sid": "x"}))
        except Exception:  # noqa: BLE001 - the fake stops the walk on purpose
            pass
        finally:
            crawler.requests.Session = original
        self.assertEqual(captured, {"sid": "x"})


class TheCommandLine(_Isolated):
    def test_listing_says_so_when_there_is_nothing(self):
        import cli

        args = type("A", (), {"list": True, "forget": False, "url": ""})()
        self.assertEqual(cli.cmd_login(args), 0)

    def test_forgetting_without_a_url_forgets_everything(self):
        import cli
        import site_session as ss

        ss.save_cookies("a.example", {"s": "1"})
        args = type("A", (), {"list": False, "forget": True, "url": ""})()
        self.assertEqual(cli.cmd_login(args), 0)
        self.assertEqual(ss.known_hosts(), [])

    def test_forgetting_one_host_by_url(self):
        import cli
        import site_session as ss

        ss.save_cookies("a.example", {"s": "1"})
        ss.save_cookies("b.example", {"s": "1"})
        args = type("A", (), {"list": False, "forget": True,
                              "url": "https://a.example/x"})()
        cli.cmd_login(args)
        self.assertEqual(ss.known_hosts(), ["b.example"])

    def test_signing_in_needs_an_address(self):
        import cli

        args = type("A", (), {"list": False, "forget": False, "url": ""})()
        self.assertEqual(cli.cmd_login(args), 2)


if __name__ == "__main__":
    unittest.main()
