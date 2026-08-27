"""The severity ramp survives a terminal that cannot draw it.

`P-11`, measured rather than described. The dark palette's four steps are
`#d97a72`, `#d89874`, `#cfae66`, `#5f5a53`. Downgraded to a 16-colour
terminal they become ANSI 9, 7, 7, 8: `serious` and `moderate` land on the
same white, so the ramp reads as three steps and its two middle ones cannot
be told apart. At 256 colours all four differ.

The fix is a mark, not a different colour - the colours belong to the design
system. These cases pin both halves: the collapse is real, and the mark
appears exactly when it is needed.
"""
from __future__ import annotations

import unittest

from rich.color import Color, ColorSystem

from tui.screens.results import (
    _SEVERITY_MARK, _SEVERITY_VARIABLE, _ramp_is_legible,
)
from ui import theme


class _Console:
    def __init__(self, color_system):
        self.color_system = color_system


class _App:
    def __init__(self, color_system):
        self.console = _Console(color_system)


def _ansi16(hex_colour: str) -> int:
    return Color.parse(hex_colour).downgrade(ColorSystem.STANDARD).number


class TheCollapseIsReal(unittest.TestCase):
    """If this stops failing to separate, the mark is no longer needed."""

    def _ramp(self):
        palette = theme.current_palette("dark")
        variables = theme.build_textual_theme(palette).variables
        return [variables[_SEVERITY_VARIABLE[name]]
                for name in ("critical", "serious", "moderate", "minor")]

    def test_all_four_steps_differ_at_256_colours(self):
        self.assertEqual(len(set(self._ramp())), 4)

    def test_two_of_them_share_one_ansi16_slot(self):
        at16 = [_ansi16(colour) for colour in self._ramp()]
        self.assertLess(len(set(at16)), 4,
                        "the ramp no longer collapses; the mark may be dropped")


class TheMarkAppearsWhenItIsNeeded(unittest.TestCase):
    def test_a_rich_terminal_needs_no_mark(self):
        for system in ("256", "truecolor"):
            with self.subTest(color_system=system):
                self.assertTrue(_ramp_is_legible(_App(system)))

    def test_a_poor_terminal_does(self):
        for system in ("standard", None, ""):
            with self.subTest(color_system=system):
                self.assertFalse(_ramp_is_legible(_App(system)))

    def test_every_painted_step_has_a_mark(self):
        """A step with a colour and no mark is a step that disappears."""
        self.assertEqual(set(_SEVERITY_MARK), set(_SEVERITY_VARIABLE))

    def test_the_marks_are_distinct(self):
        self.assertEqual(len(set(_SEVERITY_MARK.values())), 4)


class TheCell(unittest.TestCase):
    def _cell(self, label, marked):
        from tui.screens.results import ResultsScreen

        palette = theme.current_palette("dark")
        variables = theme.build_textual_theme(palette).variables
        return ResultsScreen._severity_cell(label, variables, "27", marked=marked)

    def test_the_mark_is_prefixed_only_when_asked(self):
        self.assertEqual(str(self._cell("critical", False)), "27")
        self.assertEqual(str(self._cell("critical", True)), "!!! 27")

    def test_the_audit_shape_of_the_key_still_matches(self):
        """A row can read "critical" or "audit critical" for one severity."""
        self.assertEqual(str(self._cell("audit moderate", True)), "! 27")

    def test_an_unknown_row_is_left_alone(self):
        self.assertEqual(str(self._cell("files", True)), "27")


if __name__ == "__main__":
    unittest.main()
