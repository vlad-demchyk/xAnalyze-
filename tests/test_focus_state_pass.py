"""The focus pass reports nothing when it cannot see focus.

A document that does not itself have focus never matches `:focus` in
Chromium. `el.focus()` still sets `activeElement`, so the check believed it
had focused the element - but no focus rule applied, no computed style
changed, and every focusable element on the page came back with a missing
indicator.

Measured against `https://www.gov.uk/`, whose focus state is among the most
tested on the web: 588 serious findings across ten pages, one for very nearly
every element examined. Confirmed in a live browser - `document.hasFocus()`
was `false` and `el.matches(':focus')` was `false` immediately after
`el.focus()`.

Two rules follow, and this file pins both in the script's source, since the
script itself only runs inside a browser:

* the pass must establish that it *can* see focus before reporting that a
  ring is missing;
* what counts as an indicator is any visible change, not an outline - GOV.UK
  draws a yellow background, and 83 rules in its stylesheet set `background`
  on `:focus`.
"""
from __future__ import annotations

import unittest

from audit.states import STATE_SCRIPT


class TheScriptChecksItCanMeasure(unittest.TestCase):
    def test_it_asks_whether_the_document_has_focus(self):
        self.assertIn("document.hasFocus()", STATE_SCRIPT)

    def test_it_confirms_the_probe_actually_matches_focus(self):
        self.assertIn("matches(':focus')", STATE_SCRIPT)

    def test_the_report_says_whether_focus_was_measurable(self):
        self.assertIn("focusMeasured", STATE_SCRIPT)

    def test_nothing_is_recorded_when_it_cannot_see_focus(self):
        self.assertIn("if (!canSeeFocus) return;", STATE_SCRIPT)


class WhatCountsAsAnIndicator(unittest.TestCase):
    def test_background_and_colour_count_too(self):
        for name in ("gainedBackground", "gainedColor"):
            with self.subTest(property=name):
                self.assertIn(name, STATE_SCRIPT)

    def test_the_original_three_are_still_there(self):
        for name in ("gainedOutline", "gainedShadow", "gainedBorder"):
            with self.subTest(property=name):
                self.assertIn(name, STATE_SCRIPT)


class OffCanvasIsNotBelowTheFold(unittest.TestCase):
    """`focus-outside-viewport` measured how long the page was.

    On `https://www.gov.uk/` it reported 151 `govuk-footer__link` elements -
    the ordinary footer - as focusable content outside the viewport. Content
    further down a page is reached by scrolling.
    """

    def test_the_page_length_condition_is_gone(self):
        self.assertNotIn("window.innerHeight + window.scrollY + 2000",
                         STATE_SCRIPT)

    def test_a_negative_edge_still_counts(self):
        self.assertIn("rect.bottom < 0 || rect.right < 0", STATE_SCRIPT)


if __name__ == "__main__":
    unittest.main()
