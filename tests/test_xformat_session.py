"""The refresh-token half of the xFormat session.

Written from a live run against `api.xformat.net` on 2026-08-19, which is
where the defect these tests pin down was found: sign-in and the first
refresh both worked, and the token stored for the *next* process was
already spent. Nothing here talks to the network - the shapes are the ones
the live API actually returned.
"""
from __future__ import annotations

import unittest
from unittest import mock

import requests

from llm import credentials
from llm.base import LLMAppNotPermitted, LLMAuthError, LLMUnavailable
from llm.xformat_provider import REFRESH_COOKIE, XFormatProvider


class FakeResponse:
    def __init__(self, status_code=200, body=None, cookies=None):
        self.status_code = status_code
        self._body = body if body is not None else {}
        self.text = ""
        self.cookies = requests.cookies.RequestsCookieJar()
        for name, value in (cookies or {}).items():
            # Path and domain as the backend sets them: this is what makes a
            # primed cookie and an issued one two different jar entries.
            self.cookies.set(name, value, domain=".xformat.net", path="/api/auth")

    def json(self):
        return self._body


class FakeSession:
    """Enough of `requests.Session` for the auth flow, with a real cookie jar
    so that duplicate-cookie behaviour is the real one."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.headers = {}
        self.cookies = requests.cookies.RequestsCookieJar()

    def request(self, method, url, json=None, headers=None, timeout=None, verify=None):
        self.requests.append({"method": method, "url": url, "json": json})
        resp = self.responses.pop(0)
        for cookie in resp.cookies:
            self.cookies.set(cookie.name, cookie.value,
                             domain=cookie.domain, path=cookie.path)
        return resp


class SecretStore:
    def __init__(self):
        self.data = {}


class RefreshTokenTests(unittest.TestCase):
    def setUp(self):
        self.store = SecretStore()
        patches = [
            mock.patch.object(credentials, "save_secret",
                              side_effect=lambda k, v: self.store.data.__setitem__(k, v)),
            mock.patch.object(credentials, "load_secret",
                              side_effect=lambda k: self.store.data.get(k)),
            mock.patch.object(credentials, "delete_secret",
                              side_effect=lambda k: self.store.data.pop(k, None)),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _provider(self, responses):
        provider = XFormatProvider()
        provider._session = FakeSession(responses)
        provider._session.headers.update({})
        return provider

    def test_sign_in_takes_the_refresh_token_from_the_cookie(self):
        """Login answers with no `refreshToken` in the body - the cookie is the
        only carrier, and that is the live shape."""
        provider = self._provider([FakeResponse(
            body={"user": {"id": "u", "email": "a@b.c"},
                  "accessToken": "access-1", "accessTokenExpiresAt": 1},
            cookies={REFRESH_COOKIE: "refresh-1"},
        ), FakeResponse(body={"profile": {"email": "a@b.c", "plan": "free"}})])

        provider.sign_in("a@b.c", "secret")

        self.assertEqual(provider._refresh_token, "refresh-1")
        self.assertEqual(self.store.data["xformat_refresh_token"], "refresh-1")

    def test_refresh_stores_the_newly_issued_token(self):
        """The defect: the jar holds the primed cookie *and* the issued one, so
        reading the token back from the jar kept the spent value."""
        provider = self._provider([FakeResponse(
            body={"accessToken": "access-2", "accessTokenExpiresAt": 2},
            cookies={REFRESH_COOKIE: "refresh-2"},
        )])
        provider._refresh_token = "refresh-1"
        provider._prime_refresh_cookie()

        self.assertTrue(provider._refresh_access_token())
        self.assertEqual(provider._refresh_token, "refresh-2")
        self.assertEqual(self.store.data["xformat_refresh_token"], "refresh-2")

    def test_the_spent_token_is_not_replayed_on_the_next_refresh(self):
        """Two refreshes in a row must send two different tokens, because the
        backend answers `Already Used` to the first one twice."""
        provider = self._provider([
            FakeResponse(body={"accessToken": "access-2", "accessTokenExpiresAt": 2},
                         cookies={REFRESH_COOKIE: "refresh-2"}),
            FakeResponse(body={"accessToken": "access-3", "accessTokenExpiresAt": 3},
                         cookies={REFRESH_COOKIE: "refresh-3"}),
        ])
        provider._refresh_token = "refresh-1"
        provider._prime_refresh_cookie()

        provider._refresh_access_token()
        provider._refresh_access_token()

        sent = [r["json"].get("refreshToken") for r in provider._session.requests]
        self.assertEqual(sent, ["refresh-1", "refresh-2"])

    def test_priming_leaves_one_cookie_not_two(self):
        provider = self._provider([])
        provider._refresh_token = "refresh-1"
        provider._prime_refresh_cookie()
        provider._refresh_token = "refresh-2"
        provider._prime_refresh_cookie()

        names = [c.value for c in provider._session.cookies if c.name == REFRESH_COOKIE]
        self.assertEqual(names, ["refresh-2"])

    def test_a_rejected_refresh_token_is_forgotten(self):
        """401 here is final: the token is single-use and now spent. Keeping it
        would mean every later call retries a token that can never work."""
        provider = self._provider([FakeResponse(status_code=401, body={"error": "refresh_failed"})])
        provider._refresh_token = "refresh-1"
        provider._prime_refresh_cookie()

        self.assertFalse(provider._refresh_access_token())
        self.assertIsNone(provider._refresh_token)
        self.assertNotIn("xformat_refresh_token", self.store.data)

    def test_an_unreachable_backend_keeps_the_token(self):
        """Offline says nothing about whether the token is still good."""
        provider = XFormatProvider()
        provider._refresh_token = "refresh-1"
        provider._session = mock.Mock()
        provider._session.headers = {}
        provider._session.cookies = requests.cookies.RequestsCookieJar()
        provider._session.request.side_effect = OSError("no route to host")

        self.assertFalse(provider._refresh_access_token())
        self.assertEqual(provider._refresh_token, "refresh-1")


class BackendErrorTests(unittest.TestCase):
    """What the user is told when the backend says no.

    Every shape here was returned by the live API on 2026-08-19.
    """

    def _raise(self, status, body):
        return XFormatProvider._handle_response(FakeResponse(status_code=status, body=body))

    def test_a_weekly_limit_is_not_reported_as_try_again_shortly(self):
        with self.assertRaises(LLMUnavailable) as caught:
            self._raise(429, {"error": "weekly_limit_exceeded",
                              "message": "Weekly usage limit reached - resets next week, "
                                         "or upgrade your plan for a higher limit."})
        message = str(caught.exception)
        self.assertIn("weekly", message.lower())
        self.assertNotIn("shortly", message.lower())

    def test_an_unknown_limit_code_falls_back_to_the_backend_sentence(self):
        with self.assertRaises(LLMUnavailable) as caught:
            self._raise(429, {"error": "monthly_limit_exceeded",
                              "message": "Monthly usage limit reached."})
        self.assertIn("Monthly usage limit reached.", str(caught.exception))

    def test_an_app_that_was_never_allowed_says_how_to_allow_it(self):
        with self.assertRaises(LLMAppNotPermitted) as caught:
            self._raise(403, {"error": "client_app_grant_required"})
        self.assertIn("grant", str(caught.exception))

    def test_an_unknown_failure_still_carries_the_backend_sentence(self):
        with self.assertRaises(LLMUnavailable) as caught:
            self._raise(500, {"error": "internal", "message": "Something broke."})
        self.assertIn("Something broke.", str(caught.exception))


class AuthStatusTests(unittest.TestCase):
    def test_no_token_is_not_signed_in(self):
        with mock.patch.object(credentials, "load_secret", return_value=None):
            provider = XFormatProvider()
        status = provider.auth_status()
        self.assertFalse(status.signed_in)

    def test_a_rejected_session_reports_signed_out(self):
        with mock.patch.object(credentials, "load_secret", return_value=None):
            provider = XFormatProvider()
        provider._access_token = "dead"
        provider._session = FakeSession([FakeResponse(status_code=401, body={})])
        with mock.patch.object(provider, "_refresh_access_token", return_value=False):
            status = provider.auth_status()
        self.assertFalse(status.signed_in)
        self.assertIsInstance(LLMAuthError("x"), Exception)


if __name__ == "__main__":
    unittest.main()
