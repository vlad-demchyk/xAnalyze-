"""Entry point: python main.py

Thin on purpose. This file used to carry a second, simplified `MainWindow`
of its own - a redesign that became the entry point in `31fe7f2` and left
`ui/main_window.py` orphaned. The consequences were not cosmetic: that
window drove the analysis workers directly instead of going through
`ui.view_model`, so the accessibility audit never ran (it computed
`wants_audit` and never read it), the scope and method chosen in its sidebar
never reached the scan, and report export, fix-on-disk, undo, bulk rewrite
and the preview highlight did not exist. Every UI test in the suite was
meanwhile exercising the window nobody launched.

There is one window again, it is the complete one, and its controls now live
in a left-hand column - the shape the redesign was reaching for. See
`ui.main_window.SIDEBAR_WIDTH`.
"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

import config
import detectors  # noqa: F401 -- side effect: registers built-in detectors
from ui import theme
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("XAnalyze")
    app.setOrganizationName("xFormat")

    # Styled before the window is built, so every widget is created with the
    # palette already in place — applying it afterwards makes the window
    # flash in the default Qt grey on slower machines. The palette is
    # returned and handed to the window because a few things QSS cannot
    # reach (the delegate that paints the findings list, the injected
    # preview stylesheet) need the same colour values.
    settings = config.Settings.load()
    palette = theme.apply_theme(app, settings.theme)

    window = MainWindow(palette=palette)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
