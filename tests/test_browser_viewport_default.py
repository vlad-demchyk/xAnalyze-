"""A browser pass with no viewport was auditing a 0x0 page.

`BrowserAuditOptions.viewport` defaulted to `None`, documented as "whatever
the engine defaults to". There is no such default: a `QWebEnginePage` with no
widget behind it is 0x0, `innerWidth` and `innerHeight` both report 0, and
nothing on the page has a layout box.

Measured 2026-08-31, the same page audited both ways:

    https://www.python.org/              151 findings unsized -> 244 sized
    https://en.wikipedia.org/wiki/Rome   3 state:focus-outside-viewport only unsized
    https://www.gov.uk/                  17 -> 18, state finding changed identity

The unsized pass lost real findings and invented false ones, which is the
worst of both directions.
"""
from __future__ import annotations

import unittest

from audit import browser, responsive


class TheDefaultIsARealSize(unittest.TestCase):
    def test_a_pass_nobody_configured_still_has_a_viewport(self):
        width, height = browser.BrowserAuditOptions().viewport
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)

    def test_the_default_matches_the_desktop_breakpoint(self):
        """One owner for the numbers.

        A plain `--browser` run and `--breakpoints desktop` must answer the
        same, or the same page audited two ways gives two answers for a
        reason nobody typed.
        """
        name, width, height = responsive.BREAKPOINTS[0]
        self.assertEqual(name, "desktop")
        self.assertEqual((width, height), browser.DEFAULT_VIEWPORT)

    def test_none_still_means_unsized_for_a_caller_who_asks_for_it(self):
        # Not removed: "no viewport" is a legitimate thing to request, and
        # the driver only attaches a widget when a size was given.
        self.assertIsNone(browser.BrowserAuditOptions(viewport=None).viewport)

    def test_an_explicit_size_is_not_overridden(self):
        self.assertEqual(
            browser.BrowserAuditOptions(viewport=(390, 844)).viewport, (390, 844))


if __name__ == "__main__":
    unittest.main()
