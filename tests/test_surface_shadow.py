"""The desktop design's surfaces, which are separated by tone and a shadow
rather than by a border.

QSS has no `box-shadow`, so the two shadows the design stacks on every
surface become one `QGraphicsDropShadowEffect` carried in the palette. The
part worth testing is not the look but the fallback: a token file without the
desktop overlay must produce `shadow_blur == 0`, and a zero blur must clear
any effect already on the widget rather than draw a blurless smudge. That is
what keeps the plain xFormat palette - which the window still starts on when
`$XANALYZE_DESKTOP_CSS` is empty - on its hairline-border look.

Headless: Qt runs on the offscreen platform, like the other widget tests.
"""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui import tokens

try:
    from PySide6.QtWidgets import QApplication, QWidget
    from ui import theme
except Exception:  # noqa: BLE001 - no Qt here is a skip, not a failure
    QApplication = None


OVERLAY = tokens.OVERLAY_PATH


class ShadowTokens(unittest.TestCase):
    def test_the_overlay_declares_a_shadow_for_both_sheets(self):
        loaded = tokens.load_tokens(overlay=OVERLAY)
        for name in ("light", "dark"):
            palette = tokens.Palette.from_tokens(loaded[name], name)
            with self.subTest(theme=name):
                self.assertGreater(palette.shadow_blur, 0)
                self.assertTrue(palette.shadow_color.startswith("rgba("))

    def test_the_two_sheets_do_not_share_a_shadow(self):
        """A shadow tuned for a near-white canvas is invisible on a near-black
        one, so the overlay states each separately."""
        loaded = tokens.load_tokens(overlay=OVERLAY)
        light = tokens.Palette.from_tokens(loaded["light"], "light")
        dark = tokens.Palette.from_tokens(loaded["dark"], "dark")
        self.assertNotEqual(light.shadow_color, dark.shadow_color)

    def test_without_the_overlay_there_is_no_shadow(self):
        """The fallback that keeps the plain xFormat palette usable."""
        palette = tokens.Palette.from_tokens(
            tokens.load_tokens(overlay=None).get("light", {}), "light")
        self.assertEqual(palette.shadow_blur, 0)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class SurfacePainting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_qcolor_keeps_the_alpha_the_css_states(self):
        # 0.07 of 255 is 18. Losing this is the failure mode that matters:
        # a shadow at full alpha is a black box, not a shadow.
        colour = theme.qcolor("rgba(28, 27, 25, 0.07)")
        self.assertEqual(
            (colour.red(), colour.green(), colour.blue(), colour.alpha()),
            (28, 27, 25, 18))

    def test_qcolor_accepts_the_other_forms_the_token_file_uses(self):
        self.assertEqual(theme.qcolor("#1c1b19").alpha(), 255)
        self.assertEqual(theme.qcolor("#d8d6d0a3").alpha(), 0xA3)

    def test_qcolor_refuses_to_guess(self):
        """An unparseable value becomes fully transparent rather than an
        arbitrary colour - an invisible shadow beats a black one."""
        self.assertEqual(theme.qcolor("not-a-colour").alpha(), 0)
        self.assertEqual(theme.qcolor("").alpha(), 0)

    def test_a_shadow_is_applied_and_then_cleared(self):
        widget = QWidget()
        shadowed = tokens.Palette(shadow_blur=18, shadow_y=3,
                                  shadow_color="rgba(28, 27, 25, 0.07)")
        effect = theme.soft_shadow(widget, shadowed)
        self.assertIsNotNone(effect)
        self.assertEqual(effect.blurRadius(), 18)
        self.assertEqual(effect.yOffset(), 3)
        self.assertIs(widget.graphicsEffect(), effect)

        # Switching to a palette with no shadow must take the old one off.
        # Qt deletes the replaced effect, so the check is on the widget.
        self.assertIsNone(theme.soft_shadow(widget, tokens.Palette()))
        self.assertIsNone(widget.graphicsEffect())

    def test_the_surfaces_are_drawn_without_a_border(self):
        """The design draws none, and a hairline on top of tone plus shadow
        reads as a seam."""
        qss = theme.build_qss(theme.current_palette("light"))
        for name in (theme.CLASS_SURFACE, theme.CLASS_INSET):
            with self.subTest(surface=name):
                block = qss.split(f'QWidget[class="{name}"] {{')[1].split("}")[0]
                self.assertIn("border: none", block)

    def test_the_three_surface_levels_are_distinct(self):
        """Tone is what separates them, so two levels sharing a colour would
        make the middle one disappear."""
        palette = theme.current_palette("light")
        levels = {palette.page_bg, palette.bg, palette.bg_muted}
        self.assertEqual(len(levels), 3)


@unittest.skipIf(QApplication is None, "PySide6 not available")
class SurfacesReachThePixels(unittest.TestCase):
    """The levels have to survive being painted, not just being declared.

    They did not, and the palette could not have told anyone: a blanket
    `QWidget { background-color: page_bg }` at the top of the style sheet
    painted every unnamed container in the window, including the wrappers
    inside a panel, straight over the surface the panel had just drawn. The
    palette held three distinct colours the whole time while the window
    rendered two. Only a rendered pixel catches that, so this renders one.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        from ui.main_window import MainWindow

        # Saved and put back in tearDownClass: `apply_theme` sets the style
        # sheet on the *application*, which outlives this class and would
        # otherwise re-style every widget test that runs after it.
        cls._sheet_before = cls.app.styleSheet()
        theme.apply_theme(cls.app, "light")
        cls.window = MainWindow()
        cls.window.resize(1300, 800)
        cls.window.show()
        cls.app.processEvents()
        cls.app.processEvents()
        cls.shot = cls.window.grab().toImage()

    @classmethod
    def tearDownClass(cls):
        cls.window.close()
        cls.window.deleteLater()
        cls.app.setStyleSheet(cls._sheet_before)

    def pixel(self, x: int, y: int) -> str:
        colour = self.shot.pixelColor(x, y)
        return "#%02x%02x%02x" % (colour.red(), colour.green(), colour.blue())

    def test_the_canvas_is_the_canvas(self):
        palette = theme.current_palette("light")
        # The left margin, beside the first column and below the top row.
        self.assertEqual(self.pixel(4, 400), palette.page_bg)

    def test_the_top_row_sits_on_a_surface(self):
        palette = theme.current_palette("light")
        self.assertEqual(self.pixel(650, 20), palette.bg)

    def test_a_column_sits_on_a_surface_not_on_the_canvas(self):
        """The failure this class exists for: the columns rendered in the
        canvas colour, so the window read as one flat sheet with lines drawn
        on it."""
        palette = theme.current_palette("light")
        for x in (700, 1100):
            with self.subTest(column_at=x):
                self.assertEqual(self.pixel(x, 300), palette.bg)

    def test_a_panel_head_is_the_level_between(self):
        palette = theme.current_palette("light")
        self.assertEqual(self.pixel(700, 90), palette.bg_muted)

    def test_the_canvas_and_the_surfaces_actually_differ_on_screen(self):
        """Stated as a rendered comparison rather than a palette one, so that
        a future change which makes them equal fails here even if the tokens
        still say they are three colours."""
        canvas = self.pixel(4, 400)
        surface = self.pixel(700, 300)
        head = self.pixel(700, 90)
        self.assertEqual(len({canvas, surface, head}), 3)


if __name__ == "__main__":
    unittest.main()
