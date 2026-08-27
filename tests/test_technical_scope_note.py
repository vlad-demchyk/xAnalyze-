"""The technical scan says what it did not measure.

`P-09` was written as "the technical mode judges comments with a dictionary
built for copy", and the measurement changed the answer. Over 7225 comment
blocks in `~/repositories/XFormat` and 55756 in this repository, the offline
pass produced **zero** cliche or statistical findings - not noisy, silent.
`CLICHE_PHRASES` is a marketing list and `heuristic.py` pins any
statistics-only score to 0.32, below reporting, so the stylistic half of this
mode cannot speak about comments at all.

Building a second dictionary would mean inventing one from examples, with no
corpus of comments whose author is known - the exact mistake `corpus/README.md`
exists to prevent. So the mode says so instead, and this is the case that
keeps it saying it.
"""
from __future__ import annotations

import unittest

from cli_impl.output import TECHNICAL_STYLE_CAVEAT, technical_scope_note


def _character_finding():
    return {"detector": "offline", "details": {"source": "characters"}}


def _style_finding():
    return {"detector": "offline", "details": {"cliches": ["unlock the potential"]}}


class TheCaveat(unittest.TestCase):
    def test_a_silent_technical_scan_says_it_did_not_measure(self):
        self.assertEqual(technical_scope_note("technical", []), TECHNICAL_STYLE_CAVEAT)

    def test_character_findings_alone_do_not_count_as_style(self):
        """The case that actually happens: everything reported is a dash."""
        note = technical_scope_note("technical", [_character_finding()] * 81)
        self.assertEqual(note, TECHNICAL_STYLE_CAVEAT)

    def test_a_real_style_finding_silences_it(self):
        """With something to judge, the reader is better served by the finding."""
        self.assertEqual(technical_scope_note("technical", [_style_finding()]), "")

    def test_a_content_scan_is_not_caveated(self):
        """The phrase list *is* calibrated for copy; that is what it is for."""
        self.assertEqual(technical_scope_note("content", []), "")

    def test_both_carries_the_caveat_too(self):
        """`both` includes the technical pass, so the same limit applies."""
        self.assertEqual(technical_scope_note("both", []), TECHNICAL_STYLE_CAVEAT)

    def test_the_wording_does_not_call_a_quiet_result_clean(self):
        self.assertIn("not measured", TECHNICAL_STYLE_CAVEAT)
        self.assertNotIn("no issues", TECHNICAL_STYLE_CAVEAT.lower())


if __name__ == "__main__":
    unittest.main()
