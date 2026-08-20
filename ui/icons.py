"""Line icons for the action row, in the colour the theme is currently using.

The set is Lucide (ISC, vendored under `design/assets/icons/` with its
licence), which is the same set xFormat's own web app uses - so the desktop
app's buttons are drawn from the same alphabet as the product they belong to,
rather than from whatever Qt happens to ship on this machine.

One thing has to happen in code rather than in the files: Lucide draws with
`stroke="currentColor"`, which means "inherit the text colour" - a rule the
web understands and `QIcon` does not. Loaded as-is, every icon renders black,
which is invisible in the dark theme. So the colour is substituted into the
SVG source before rendering, and the rendered result is cached per
(name, colour, size): the same six icons are re-requested on every theme
change and every relayout, and re-rasterising them each time is work nobody
asked for.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

ICONS = Path(__file__).resolve().parent / "design" / "assets" / "icons"

#: Rendered icons, keyed by what makes them different.
_CACHE: dict = {}

#: Icons are square and sized in logical pixels; the device pixel ratio is
#: applied on top so the line work stays crisp on a Retina display.
DEFAULT_SIZE = 18


def available() -> bool:
    """Whether the icon files are present.

    Asked rather than assumed because the answer differs between a checkout
    and a frozen bundle, and a missing icon must degrade to a text button
    instead of raising in the middle of building the window.
    """
    return ICONS.is_dir()


def icon(name: str, color: str, size: int = DEFAULT_SIZE,
         ratio: float = 1.0) -> QIcon | None:
    """The named Lucide icon, stroked in `color`, or None if it is missing."""
    key = (name, color, size, round(ratio, 2))
    if key in _CACHE:
        return _CACHE[key]

    path = ICONS / f"{name}.svg"
    if not path.is_file():
        return None
    source = path.read_text(encoding="utf-8").replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(source.encode("utf-8")))
    if not renderer.isValid():
        return None

    pixels = max(1, int(size * max(ratio, 1.0)))
    pixmap = QPixmap(QSize(pixels, pixels))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(max(ratio, 1.0))

    built = QIcon(pixmap)
    _CACHE[key] = built
    return built
