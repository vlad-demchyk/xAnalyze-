"""Two small lies the tool used to tell.

One about progress ("8 findings, now 0 - down" comparing two different
targets), one about a site's shape (an apex and its `www` counted as two
sites, so a crawl that began at the apex followed nothing).
"""
from __future__ import annotations

import unittest

import cli
from crawler import _same_domain


class PreviousRunTests(unittest.TestCase):
    def _payload(self, root, mode, history):
        return {"root": root, "mode": mode, "history": history}

    def test_a_run_over_another_target_is_not_this_target_history(self):
        payload = self._payload("page.html", "audit", [
            {"at": "1", "root": "live.html", "mode": "audit", "counts": {"serious": 8}},
            {"at": "2", "root": "page.html", "mode": "audit", "counts": {"serious": 0}},
        ])
        self.assertIsNone(cli._previous_run(payload))

    def test_the_previous_run_of_the_same_target_is_found_past_others(self):
        payload = self._payload("page.html", "audit", [
            {"at": "1", "root": "page.html", "mode": "audit", "counts": {"serious": 5}},
            {"at": "2", "root": "live.html", "mode": "audit", "counts": {"serious": 8}},
            {"at": "3", "root": "page.html", "mode": "audit", "counts": {"serious": 2}},
        ])
        previous = cli._previous_run(payload)
        self.assertIsNotNone(previous)
        self.assertEqual(previous["at"], "1")

    def test_two_modes_over_one_root_are_not_each_other_history(self):
        """An audit counts accessibility, a scan counts copy. Comparing them
        would report a change that never happened."""
        payload = self._payload("~/repo", "scan", [
            {"at": "1", "root": "~/repo", "mode": "audit", "counts": {"serious": 314}},
            {"at": "2", "root": "~/repo", "mode": "scan", "counts": {"serious": 4}},
        ])
        self.assertIsNone(cli._previous_run(payload))

    def test_the_first_run_of_a_target_has_no_history(self):
        self.assertIsNone(cli._previous_run(self._payload("a", "scan", [])))


class SameDomainTests(unittest.TestCase):
    def test_www_and_apex_are_one_site(self):
        self.assertTrue(_same_domain("https://xformat.net/a",
                                     "https://www.xformat.net/b"))

    def test_case_and_default_port_are_noise(self):
        self.assertTrue(_same_domain("https://XFormat.net:443/a",
                                     "https://xformat.net/b"))

    def test_a_different_host_is_still_a_different_site(self):
        self.assertFalse(_same_domain("https://xformat.net/a",
                                      "https://api.xformat.net/b"))

    def test_a_non_default_port_still_separates(self):
        self.assertFalse(_same_domain("http://localhost:8000/a",
                                      "http://localhost:9000/b"))

    def test_a_subdomain_is_not_swallowed_by_the_www_rule(self):
        self.assertFalse(_same_domain("https://www.xformat.net/a",
                                      "https://docs.xformat.net/b"))


if __name__ == "__main__":
    unittest.main()
