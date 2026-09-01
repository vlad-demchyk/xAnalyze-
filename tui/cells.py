"""A table cell that wraps instead of losing its end.

Textual's `DataTable` draws one line per row and clips whatever does not
fit, so four screens in this interface were slicing their own values with
`[:34]`, `[:80]` and `[-46:]` before handing them over. Each slice looked
harmless and each one removed the part a person was reading for:

* a log detail cut at 80 characters ends mid `key=value`, and the pair that
  was cut is usually the one that explains the line;
* a run target cut to its last 46 characters keeps the path and drops the
  **domain**, so a list of runs against three different sites read as three
  rows that all begin with `...`.

The fix is not a longer slice. A cell folded at the column's own width and a
row that grows to fit shows the whole value and costs a line, and Textual
supports both directly - `Text(overflow="fold")` and `add_row(height=None)`.

`height=None` is the second half and it is not optional: a folded `Text` in
a row fixed at one line is a clipped cell with extra steps.
"""
from __future__ import annotations

from rich.text import Text

#: What `add_row` is given so the row grows to the tallest cell in it.
AUTO_HEIGHT = None


def folded(value, style: str = "") -> Text:
    """One cell, wrapped at the column width rather than cut off."""
    return Text(str(value if value is not None else ""),
                overflow="fold", no_wrap=False,
                style=style or "")
