"""Turns an xFormat design-system palette into a Qt style sheet.

`ui/tokens.py` reads the colours, radii and type scale out of the frontend's
`tokens.css`; this module is what paints with them. The two are kept apart
because they fail differently: parsing can find nothing (and falls back to
the palette defaults), while this file always produces a complete style
sheet from whatever palette it is handed.

Where the web app and the desktop app deliberately differ:

* Qt style sheets have no cascade and no custom properties, so every value
  is expanded here rather than referenced. That is why this is generated
  from tokens instead of hand-written — a token change stays a one-line
  change upstream.
* `box-shadow` doesn't exist in QSS. The web app's monolithic-card-on-soft-
  shadow look is approximated with a hairline border in `--border`, which
  reads as the same "surface floating on the canvas" separation without
  drawing fake shadows into the pixmap. The desktop design draws no borders
  at all, so the surfaces it introduces (`CLASS_SURFACE`, `CLASS_INSET`)
  take a real `QGraphicsDropShadowEffect` from `soft_shadow` instead - see
  the note there for why one effect stands in for the design's two layers.
* Qt needs an explicit widget-by-widget selector list where CSS would
  inherit; the shape of this file follows Qt's needs, the values follow the
  design system's.
"""
from __future__ import annotations

import re

from ui.tokens import Palette, palettes

#: Class names set with `widget.setProperty("class", ...)` and matched below.
CLASS_CARD = "card"
CLASS_HEADING = "heading"
CLASS_MUTED = "muted"
CLASS_PRIMARY = "primary"
CLASS_TOOLBAR = "toolbar"
CLASS_BADGE_HIGH = "badge-high"
CLASS_BADGE_MEDIUM = "badge-medium"
CLASS_BADGE_LOW = "badge-low"
CLASS_EMPTY = "empty"
#: A zone of the window with its own surface: the toolbar, a column, a panel
#: inside the detail column. The design the web app uses is one of monolithic
#: cards on a warm canvas, and a Qt window that paints everything on one flat
#: sheet reads as a different product entirely.
CLASS_PANEL = "panel"
#: The header strip of a panel: its name, and whatever belongs on the same
#: line. Separated by a hairline rather than by whitespace so the eye finds
#: the boundary of each zone without the layout having to grow.
CLASS_PANEL_HEAD = "panel-head"
#: A small labelled block inside a panel - "what was found", "why it matters".
CLASS_FIELD = "field"
CLASS_FIELD_LABEL = "field-label"
#: A quiet pill: the rule id, the engine that found it, the file position.
CLASS_CHIP = "chip"
#: The accent-filled variant, for the one action a panel exists to offer.
CLASS_ACCENT = "accent"
#: A button that reads as a link: secondary, never the thing to press first.
CLASS_QUIET = "quiet"
#: A hairline. A QFrame with this class draws the divider between zones.
CLASS_DIVIDER = "divider"
#: Monospaced markup shown as evidence, not as something to edit.
CLASS_CODE = "code"
#: The window's own header: the mark, the product name, the mode.
CLASS_BRAND = "brand"

#: The desktop design's three surface levels. The canvas is the window
#: itself; `CLASS_SURFACE` is a section sitting on it, `CLASS_INSET` a block
#: nested inside a section. Separated by tone and by `soft_shadow` rather
#: than by a border - which is the whole difference from `CLASS_CARD` above,
#: and why they are separate classes instead of a change to that one: the
#: two coexist while the window is migrated screen by screen.
CLASS_SURFACE = "surface"
CLASS_INSET = "inset"
#: The top controls row. A surface like any other, plus the compact button
#: metrics the design draws it with - stated here rather than on every
#: button in the window, because a 28px button is right in a one-line row
#: and wrong in a panel where it stands on its own.
CLASS_TOP_ROW = "top-row"

#: The parts of an inline selector: the word that names the setting, the
#: value itself, and the small caret that says the value can be changed.
#: Three classes rather than one because they are three different inks -
#: muted, full, and subtle - and that difference is what makes the row read
#: as a sentence instead of as a form.
CLASS_INLINE_LABEL = "inline-label"
CLASS_INLINE_VALUE = "inline-value"
CLASS_INLINE_CARET = "inline-caret"
#: The hairline standing between two inline values.
CLASS_HAIRLINE = "hairline"
#: The whole selector, which is what takes keyboard focus.
CLASS_INLINE_FIELD = "inline-field"
#: The fillable area of a `panel()`, under its head.
CLASS_PANEL_BODY = "panel-body"


def qcolor(value: str):
    """A palette colour as a `QColor`, alpha included.

    `qss_color` exists to hand colours to a *style sheet*; this hands one to
    a widget API, which needs the alpha as a number rather than as text.
    Accepts what the token file actually contains: `#rgb`, `#rrggbb`,
    `#rrggbbaa` and `rgba(r, g, b, a)`.
    """
    from PySide6.QtGui import QColor

    text = (value or "").strip()
    # `#rrggbbaa` first, and by hand: Qt reads an 8-digit hex as `#aarrggbb`,
    # alpha *first*, which is the opposite of the CSS form the token file is
    # written in. Handing xFormat's `--sb-thumb: #d8d6d0a3` straight to
    # QColor yields alpha 0xd8 and a colour shifted a channel over - wrong
    # in a way that still renders, which is the kind that survives review.
    match = re.fullmatch(r"#([0-9a-fA-F]{8})", text)
    if match:
        from PySide6.QtGui import QColor

        digits = match.group(1)
        r, g, b, a = (int(digits[i:i + 2], 16) for i in (0, 2, 4, 6))
        return QColor(r, g, b, a)

    match = re.fullmatch(r"rgba?\(([^)]+)\)", text)
    if match:
        parts = [p.strip() for p in match.group(1).split(",")]
        try:
            r, g, b = (int(float(p)) for p in parts[:3])
            alpha = float(parts[3]) if len(parts) > 3 else 1.0
        except (ValueError, IndexError):
            return QColor(0, 0, 0, 0)
        # CSS writes alpha 0..1; Qt wants 0..255.
        return QColor(r, g, b, max(0, min(255, round(alpha * 255))))
    colour = QColor(text)
    return colour if colour.isValid() else QColor(0, 0, 0, 0)


def soft_shadow(widget, p: Palette):
    """Give `widget` the design's surface shadow, or take it away.

    The bundle stacks two shadows on every surface - a 1px contact shadow and
    a wide ambient one. `QGraphicsDropShadowEffect` draws exactly one, so the
    palette carries a single blur/offset/colour tuned to stand in for both,
    and this applies it. A palette with `shadow_blur == 0` (any token file
    without the desktop overlay) clears the effect instead, which leaves the
    widget on the hairline-border look the rest of the window still uses.

    Returns the effect, or None when none was applied. Qt takes ownership of
    the effect, and setting a new one deletes the old, so this is safe to
    call again on every theme change - which `MainWindow.apply_palette` does,
    because the shadow colour differs between the two sheets.
    """
    from PySide6.QtWidgets import QGraphicsDropShadowEffect

    if p.shadow_blur <= 0:
        widget.setGraphicsEffect(None)
        return None
    # No parent. `setGraphicsEffect` takes ownership on its own, and giving
    # the effect the widget as a parent as well hands the same object to two
    # owners - which Qt frees twice when the window goes away. It survived
    # every test that built one window and segfaulted in the full suite,
    # where windows are built and destroyed in the dozens.
    effect = QGraphicsDropShadowEffect()
    effect.setBlurRadius(p.shadow_blur)
    effect.setXOffset(0)
    effect.setYOffset(p.shadow_y)
    effect.setColor(qcolor(p.shadow_color))
    widget.setGraphicsEffect(effect)
    return effect


def qss_color(value: str) -> str:
    """Qt style sheets accept `#rgb`/`#rrggbb` and `rgba(...)`, but not the
    8-digit `#rrggbbaa` form CSS allows — and xFormat's scrollbar tokens use
    it. Convert rather than drop, so the token still lands."""
    value = (value or "").strip()
    match = re.fullmatch(r"#([0-9a-fA-F]{8})", value)
    if not match:
        return value
    digits = match.group(1)
    r, g, b, a = (int(digits[i:i + 2], 16) for i in (0, 2, 4, 6))
    return f"rgba({r}, {g}, {b}, {a / 255:.3f})"


def build_qss(p: Palette) -> str:
    c = qss_color
    # Selection colours: the accent at full strength is too loud behind body
    # text, so selections use the muted brand fill the web app uses for the
    # same job (rows, chips) and keep the normal text colour on top.
    selection_bg = c(p.accent_muted) if p.accent_muted.startswith("rgba") else c(p.bg_hover)

    return f"""
/* Generated from xFormat design tokens — edit tokens.css, not this string. */

/* No background here on purpose. A blanket fill on `QWidget` paints every
   plain container in the window with the canvas colour - including the
   unnamed wrappers inside a panel, which then cover the surface the panel
   just painted. That is what flattened the three surface levels back into
   one: the panel drew #fbfaf8 and an anonymous child drew #efece7 straight
   over it. The canvas belongs to the window; everything above it is either
   transparent or declares a surface of its own. */
QWidget {{
    color: {c(p.text)};
    font-family: "{p.font}";
    font-size: {p.font_size}px;
}}

QMainWindow, QDialog, QMainWindow > QWidget {{
    background-color: {c(p.page_bg)};
}}

/* ---------------------------------------------------------------- surfaces */

QWidget[class="{CLASS_CARD}"] {{
    background-color: {c(p.bg_card)};
    border: 1px solid {c(p.border)};
    border-radius: {p.radius}px;
}}

QWidget[class="{CLASS_TOOLBAR}"] {{
    background-color: {c(p.bg_card)};
    border: 1px solid {c(p.border)};
    border-radius: {p.radius}px;
}}

/* The desktop design's surfaces. No border on purpose: the separation is
   tone plus `soft_shadow`, and a hairline on top of both reads as a seam. */
QWidget[class="{CLASS_SURFACE}"] {{
    background-color: {c(p.bg)};
    border: none;
    border-radius: {p.radius}px;
}}

QWidget[class="{CLASS_TOP_ROW}"] {{
    background-color: {c(p.bg)};
    border: none;
    border-radius: {p.radius}px;
}}

QWidget[class="{CLASS_TOP_ROW}"] QPushButton {{
    padding: 5px 13px;
    border-radius: {p.radius_md}px;
}}

QWidget[class="{CLASS_INSET}"] {{
    background-color: {c(p.bg_muted)};
    border: none;
    border-radius: {p.radius_lg - 1}px;
}}

/* Controls inside the strip lose their own box. In the design the scanned
   address is text sitting in the filled strip, not a field drawn on top of
   one - a bordered input inside a bordered block is two nested boxes saying
   the same thing, and it is what made the row 68px tall against the 44px
   the design draws. The focus ring below is what still says which control
   the keyboard is on, since the border no longer can. */
QWidget[class="{CLASS_INSET}"] QLineEdit,
QWidget[class="{CLASS_INSET}"] QSpinBox {{
    background: transparent;
    border: none;
    border-radius: {p.radius_sm}px;
    padding: 1px 3px;
}}

QWidget[class="{CLASS_INSET}"] QLineEdit:focus,
QWidget[class="{CLASS_INSET}"] QSpinBox:focus {{
    background-color: {c(p.bg)};
    border: none;
}}

/* ------------------------------------------------------- inline selectors */

QLabel[class="{CLASS_INLINE_LABEL}"] {{
    color: {c(p.text_muted)};
    font-size: {p.font_size_sm}px;
}}

QLabel[class="{CLASS_INLINE_VALUE}"] {{
    color: {c(p.text)};
    font-weight: 500;
}}

QLabel[class="{CLASS_INLINE_CARET}"] {{
    color: {c(p.text_subtle)};
    font-size: {max(9, p.font_size_sm - 3)}px;
}}

QFrame[class="{CLASS_HAIRLINE}"] {{
    background-color: {c(p.divider)};
    border: none;
}}

/* The focus ring. An inline selector has no box of its own, so without this
   there is nothing at all to say which one the keyboard is on - and this
   window is the one that reports missing focus indicators on other people's
   pages. */
QWidget[class="{CLASS_INLINE_FIELD}"]:focus {{
    background-color: {c(p.bg_hover)};
    border-radius: {p.radius_sm}px;
}}

QLabel {{
    background: transparent;
}}

QLabel[class="{CLASS_HEADING}"] {{
    font-size: {p.font_size_lg}px;
    font-weight: 600;
    color: {c(p.text)};
}}

QLabel[class="{CLASS_MUTED}"] {{
    color: {c(p.text_muted)};
    font-size: {p.font_size_sm}px;
}}

QLabel[class="{CLASS_EMPTY}"] {{
    color: {c(p.text_muted)};
    font-size: {p.font_size}px;
    padding: {p.space_lg}px;
}}

/* Confidence badges. Colour alone never carries the meaning — the label
   spells out the level — so these stay readable for colour-blind users and
   in a screenshot printed in grayscale. */
QLabel[class="{CLASS_BADGE_HIGH}"],
QLabel[class="{CLASS_BADGE_MEDIUM}"],
QLabel[class="{CLASS_BADGE_LOW}"] {{
    border-radius: {p.radius_sm}px;
    padding: 2px {p.space_sm}px;
    font-size: {p.font_size_sm}px;
    font-weight: 600;
}}
QLabel[class="{CLASS_BADGE_HIGH}"] {{
    background-color: {c(p.error_strong)};
    color: {c(p.on_error)};
}}
QLabel[class="{CLASS_BADGE_MEDIUM}"] {{
    background-color: {c(p.amber)};
    color: {c(p.on_amber)};
}}
QLabel[class="{CLASS_BADGE_LOW}"] {{
    background-color: {c(p.bg_muted)};
    color: {c(p.text_muted)};
}}

/* ----------------------------------------------------------------- inputs */

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox {{
    background-color: {c(p.bg_muted)};
    border: 1px solid {c(p.border)};
    border-radius: {p.radius_lg}px;
    padding: {p.space_sm}px {p.space_md}px;
    color: {c(p.text)};
    selection-background-color: {c(p.accent)};
    selection-color: {c(p.on_accent)};
}}

QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {c(p.accent)};
}}

QLineEdit:disabled, QPlainTextEdit:disabled, QTextEdit:disabled,
QSpinBox:disabled, QComboBox:disabled {{
    color: {c(p.text_muted)};
    background-color: {c(p.bg_muted)};
}}

QLineEdit[class="field-error"] {{
    border: 1px solid {c(p.error)};
}}

QLabel[class="field-error"] {{
    color: {c(p.error)};
    font-size: {p.font_size_sm}px;
}}

QComboBox::drop-down {{
    border: none;
    width: 22px;
}}

QComboBox QAbstractItemView {{
    background-color: {c(p.bg_card)};
    border: 1px solid {c(p.border)};
    border-radius: {p.radius_md}px;
    padding: {p.space_sm // 2}px;
    selection-background-color: {c(p.bg_hover)};
    selection-color: {c(p.text)};
    outline: none;
}}

QSpinBox::up-button, QSpinBox::down-button {{
    width: 16px;
    border: none;
    background: transparent;
}}

/* ---------------------------------------------------------------- buttons */

QPushButton {{
    background-color: {c(p.bg_card)};
    border: 1px solid {c(p.border_strong)};
    border-radius: {p.radius_lg}px;
    padding: {p.space_sm}px {p.space_lg}px;
    color: {c(p.text)};
    font-weight: 500;
}}

QPushButton:hover {{
    background-color: {c(p.bg_hover)};
}}

QPushButton:pressed {{
    background-color: {c(p.bg_muted)};
}}

QPushButton:disabled {{
    color: {c(p.text_muted)};
    border-color: {c(p.border)};
    background-color: {c(p.bg_muted)};
}}

QPushButton[class="{CLASS_PRIMARY}"] {{
    background-color: {c(p.primary)};
    color: {c(p.on_primary)};
    border: 1px solid {c(p.primary)};
}}

QPushButton[class="{CLASS_PRIMARY}"]:hover {{
    background-color: {c(p.primary_hover)};
    border-color: {c(p.primary_hover)};
}}

QPushButton[class="{CLASS_PRIMARY}"]:disabled {{
    background-color: {c(p.bg_muted)};
    border-color: {c(p.border)};
    color: {c(p.text_muted)};
}}

/* ------------------------------------------------------------------ zones */

/* Every zone is a surface on the canvas rather than a region of one flat
   sheet. This is the single largest difference between a Qt window that looks
   like a Qt window and one that looks like the rest of the product. */
QWidget[class="{CLASS_PANEL}"] {{
    background-color: {c(p.bg_card)};
    border: 1px solid {c(p.border)};
    border-radius: {p.radius}px;
}}

/* Transparent, so the panel's own surface shows through it. Without this
   the blanket `QWidget` rule at the top of this sheet paints the canvas
   colour over the panel that contains it, and the three surface levels
   collapse into one flat sheet - which is exactly what a screenshot of the
   rebuilt window showed: canvas #efece7 where the panel had painted its
   #fbfaf8. The head below keeps its own fill and is matched after this. */
QWidget[class="{CLASS_PANEL_BODY}"] {{
    background: transparent;
}}

QWidget[class="{CLASS_PANEL_HEAD}"] {{
    background-color: {c(p.bg_muted)};
    border: none;
    border-bottom: 1px solid {c(p.border)};
    border-top-left-radius: {p.radius}px;
    border-top-right-radius: {p.radius}px;
}}

QFrame[class="{CLASS_DIVIDER}"] {{
    background-color: {c(p.border)};
    border: none;
    max-height: 1px;
    min-height: 1px;
}}

QWidget[class="{CLASS_FIELD}"] {{
    background-color: {c(p.bg_muted)};
    border: 1px solid {c(p.border)};
    border-radius: {p.radius_md}px;
}}

QLabel[class="{CLASS_FIELD_LABEL}"] {{
    color: {c(p.text_muted)};
    font-size: {p.font_size_sm}px;
    font-weight: 600;
    /* Small caps by spacing rather than by font: the label is a signpost, and
       at this size letter-spacing separates it from the sentence under it
       more reliably than weight alone. */
    letter-spacing: 1px;
}}

QLabel[class="{CLASS_CHIP}"] {{
    background-color: {c(p.bg_muted)};
    border: 1px solid {c(p.border_strong)};
    border-radius: {p.radius_sm}px;
    padding: 2px {p.space_sm}px;
    color: {c(p.text_muted)};
    font-size: {p.font_size_sm}px;
}}

QPlainTextEdit[class="{CLASS_CODE}"], QTextEdit[class="{CLASS_CODE}"] {{
    background-color: {c(p.bg_muted)};
    border: 1px solid {c(p.border)};
    border-radius: {p.radius_md}px;
    font-family: "{p.font_mono}";
    font-size: {p.font_size_sm}px;
    color: {c(p.text)};
}}

QWidget[class="{CLASS_BRAND}"] {{
    background: transparent;
}}

QPushButton[class="{CLASS_ACCENT}"] {{
    background-color: {c(p.accent)};
    color: {c(p.on_accent)};
    border: 1px solid {c(p.accent)};
    font-weight: 600;
}}

QPushButton[class="{CLASS_ACCENT}"]:hover {{
    background-color: {c(p.accent_hover)};
    border-color: {c(p.accent_hover)};
}}

QPushButton[class="{CLASS_ACCENT}"]:disabled {{
    background-color: {c(p.bg_muted)};
    border-color: {c(p.border)};
    color: {c(p.text_muted)};
}}

QPushButton[class="{CLASS_QUIET}"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {c(p.text_muted)};
    padding: {p.space_sm // 2}px {p.space_sm}px;
    font-weight: 500;
}}

QPushButton[class="{CLASS_QUIET}"]:hover {{
    background-color: {c(p.bg_hover)};
    color: {c(p.text)};
}}

QScrollArea, QScrollArea > QWidget > QWidget {{
    background: transparent;
    border: none;
}}

QSplitter::handle {{
    background: transparent;
}}

/* ------------------------------------------------------------------ lists */

QListWidget {{
    background-color: {c(p.bg_card)};
    /* No border: the list lives inside a panel that already has one, and two
       concentric rounded rectangles a pixel apart look like a mistake. */
    border: none;
    border-radius: 0;
    padding: {p.space_sm // 2}px;
    outline: none;
}}

QListWidget::item {{
    border-radius: {p.radius_md}px;
    padding: {p.space_sm}px;
    margin: 1px 0;
    color: {c(p.text)};
}}

QListWidget::item:hover {{
    background-color: {c(p.bg_hover)};
}}

QListWidget::item:selected {{
    background-color: {selection_bg};
    color: {c(p.text)};
}}

/* --------------------------------------------------------------- chrome */

QSplitter::handle {{
    background: transparent;
    width: {p.space_md}px;
}}

QStatusBar {{
    background-color: {c(p.page_bg)};
    color: {c(p.text_muted)};
    border-top: 1px solid {c(p.border)};
}}

QStatusBar::item {{
    border: none;
}}

QToolTip {{
    background-color: {c(p.bg_card)};
    color: {c(p.text)};
    border: 1px solid {c(p.border_strong)};
    border-radius: {p.radius_md}px;
    padding: {p.space_sm}px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background: {c(p.scrollbar)};
    border-radius: 5px;
    min-height: 28px;
}}

QScrollBar::handle:vertical:hover {{
    background: {c(p.scrollbar_hover)};
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background: {c(p.scrollbar)};
    border-radius: 5px;
    min-width: 28px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {c(p.scrollbar_hover)};
}}

QScrollBar::add-line, QScrollBar::sub-line,
QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
    border: none;
    height: 0;
    width: 0;
}}

QProgressBar {{
    background-color: {c(p.bg_muted)};
    border: none;
    border-radius: {p.radius_sm}px;
    height: 6px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {c(p.accent)};
    border-radius: {p.radius_sm}px;
}}

QCheckBox {{
    spacing: {p.space_sm}px;
}}

QMessageBox, QFileDialog {{
    background-color: {c(p.bg_card)};
}}
"""


def resolve_mode(mode: str) -> str:
    """'auto' follows the OS; anything else is taken literally."""
    if mode in ("light", "dark"):
        return mode
    try:
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtCore import Qt

        scheme = QGuiApplication.styleHints().colorScheme()
        return "dark" if scheme == Qt.ColorScheme.Dark else "light"
    except Exception:  # noqa: BLE001 - old Qt, or no GUI; light is the safe answer
        return "light"


def current_palette(mode: str = "auto") -> Palette:
    return palettes()[resolve_mode(mode)]


def apply_theme(app, mode: str = "auto") -> Palette:
    """Style the whole application and return the palette that was used, so
    callers can paint the few things QSS can't reach (web-preview HTML, a
    syntax highlighter's colours) with the same values."""
    palette = current_palette(mode)
    app.setStyleSheet(build_qss(palette))
    return palette
