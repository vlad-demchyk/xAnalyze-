"""Four TUI tables were slicing their own values before drawing them.

`DataTable` draws one line per row and clips the overflow, so each screen
had taken to cutting the value itself - `[:34]`, `[:80]`, `[-46:]`. Every
slice looked harmless and every one removed the part a person reads for:

* a log detail cut at 80 characters ends inside a `key=value`, and the pair
  it cuts is usually the one that explains the line;
* a run target kept as its *last* 46 characters drops the **domain**, so
  three runs against three different sites read as three rows beginning
  "...".

Two halves, and both are needed: a folded cell in a row fixed at one line is
a clipped cell with extra steps.
"""
import os
import re
import unittest
from pathlib import Path

os.environ.setdefault("TEXTUAL_HEADLESS", "1")

from tui.cells import AUTO_HEIGHT, folded

SCREENS = Path(__file__).resolve().parent.parent / "tui" / "screens"


class ACellWraps(unittest.TestCase):

    def test_it_folds_rather_than_truncating(self):
        cell = folded("x" * 500)
        self.assertEqual(cell.overflow, "fold")
        self.assertFalse(cell.no_wrap)
        self.assertEqual(len(cell.plain), 500)

    def test_none_becomes_empty_rather_than_the_word_none(self):
        self.assertEqual(folded(None).plain, "")

    def test_a_number_is_accepted_without_the_caller_stringifying_it(self):
        self.assertEqual(folded(7).plain, "7")

    def test_auto_height_is_what_datatable_understands_as_fit(self):
        self.assertIsNone(AUTO_HEIGHT)


class TheTablesUseIt(unittest.TestCase):

    #: The two that carry a value long enough to need it. The other two
    #: (`settings`, `results`) hold short labels and a count.
    WRAPPING = ("logs.py", "reports.py")

    def test_the_long_valued_tables_fold_and_grow(self):
        for name in self.WRAPPING:
            source = (SCREENS / name).read_text(encoding="utf-8")
            with self.subTest(screen=name):
                self.assertIn("folded(", source)
                self.assertIn("height=AUTO_HEIGHT", source)

    def test_no_table_slices_its_own_value_any_more(self):
        """The slices that were there, by shape: a cell built with `[:n]` or
        `[-n:]` inside an `add_row`."""
        for name in self.WRAPPING:
            source = (SCREENS / name).read_text(encoding="utf-8")
            rows = re.findall(r"table\.add_row\((.*?)\n\s*\)", source, re.S)
            rows += re.findall(r"table\.add_row\((.*?)height=", source, re.S)
            for row in rows:
                with self.subTest(screen=name):
                    self.assertNotRegex(row, r"\[-?\d+:\]")
                    self.assertNotRegex(row, r"\[:\d+\]")


if __name__ == "__main__":
    unittest.main()
