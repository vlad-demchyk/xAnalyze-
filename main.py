"""Entry point: python main.py"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

import config
import detectors  # noqa: F401 -- side effect: registers built-in detectors
from ui import theme
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("AI Content Scanner")

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
