"""The app's own palette, held to the rule the app enforces on other people.

XAnalyze reports insufficient contrast as an accessibility finding on the
pages it audits (`audit.rules.accessibility.InlineContrast`). Its own window
was never measured against the same threshold, and "the dark theme has uneven
spots" is not a defect anyone can act on - so this file turns that sentence
into numbers, using the very function the audit rule uses.

Every pair below is a foreground the window actually paints on a background
it actually paints it on, in both themes. Three of them failed when this was
first run, which is what `Palette.error_strong` / `error_text` /
`success_text` exist to fix:

    white on `error`      3.91  the HIGH badge, 12px bold - not "large text"
    `success` on `bg`     3.34  the "signed in" line in Settings
    `error` on `bg`       3.91  the same line in its failure state

WCAG AA is 4.5:1 for normal text and 3:1 for large text and for the visual
boundary of a control. Where 3:1 is the right threshold that is said per
pair, with the reason - never as a way of letting a failing pair pass.
"""
import unittest

from audit.rules.accessibility import contrast_ratio
from ui import theme

AA_TEXT = 4.5
AA_LARGE = 3.0

#: (foreground token, background token, threshold, where it is painted)
PAIRS = (
    ("text", "bg", AA_TEXT, "body text on a panel"),
    ("text", "bg_card", AA_TEXT, "text on a card: findings list, detail panel"),
    ("text", "bg_muted", AA_TEXT, "text in an input, a combo, a spin box"),
    ("text", "bg_hover", AA_TEXT, "a hovered row in the findings list"),
    ("text", "page_bg", AA_TEXT, "text on the window's own canvas"),
    ("text_muted", "bg", AA_TEXT, "the muted label class"),
    ("text_muted", "bg_card", AA_TEXT, "the empty-state body"),
    ("text_muted", "bg_muted", AA_TEXT, "a disabled button's label"),
    ("on_primary", "primary", AA_TEXT, "the Analyze button"),
    ("on_primary", "primary_hover", AA_TEXT, "the Analyze button, hovered"),
    ("on_accent", "accent", AA_TEXT, "an accent fill"),
    ("on_accent", "accent_hover", AA_TEXT, "an accent fill, hovered"),
    ("on_error", "error_strong", AA_TEXT, "the HIGH confidence badge"),
    ("on_amber", "amber", AA_TEXT, "the MEDIUM confidence badge"),
    ("text_muted", "bg_muted", AA_TEXT, "the LOW confidence badge"),
    ("success_text", "bg", AA_TEXT, "the Settings status line, signed in"),
    ("error_text", "bg", AA_TEXT, "the Settings status line, failed"),
    ("accent", "bg", AA_TEXT, "a link-coloured word"),
    # A boundary rather than a word. 3:1 is the AA threshold for visual
    # information *required* to identify a control - and this outline is the
    # only thing saying "the finding is here", so it has to meet it.
    ("error", "bg_card", AA_LARGE, "the highlight outline on a preview"),
)

#: Measured and deliberately not asserted, so that the omission is a decision
#: on the record rather than a pair nobody thought of: the button outline
#: (`border_strong` on `bg_card`) is 1.45:1 on the light sheet and 1.61:1 on
#: the dark one. It is xFormat's own `--border-strong`, and every button it
#: draws is identified by its label or its icon - both of which clear AA by a
#: wide margin above - so the outline carries no information of its own.
#: Raising it would repaint every panel edge in the app to satisfy a
#: threshold that does not apply to decoration.
UNASSERTED_BOUNDARY = ("border_strong", "bg_card")


def rgb(value: str) -> tuple:
    text = value.lstrip("#")
    return tuple(int(text[i:i + 2], 16) for i in (0, 2, 4))


class PaletteContrast(unittest.TestCase):
    def test_every_painted_pair_clears_its_threshold(self):
        for mode in ("light", "dark"):
            palette = theme.current_palette(mode)
            for foreground, background, threshold, where in PAIRS:
                with self.subTest(theme=mode, where=where):
                    ratio = contrast_ratio(rgb(getattr(palette, foreground)),
                                           rgb(getattr(palette, background)))
                    self.assertGreaterEqual(
                        round(ratio, 2), threshold,
                        f"{foreground} on {background} in the {mode} theme is "
                        f"{ratio:.2f}:1, below {threshold}:1 - {where}")

    def test_the_badge_ink_does_not_follow_the_theme(self):
        """`error` and `amber` are the same hue on both sheets, so ink that
        flipped with the theme would land near-black on a mid red."""
        light = theme.current_palette("light")
        dark = theme.current_palette("dark")
        self.assertEqual(light.on_error, dark.on_error)
        self.assertEqual(light.on_amber, dark.on_amber)
        self.assertEqual(light.error_strong, dark.error_strong)

    def test_status_words_do_follow_the_theme(self):
        """The opposite case: a word sits on a surface, and the surface is
        what changes. Darkening the hue on the dark sheet would cost contrast
        rather than buy it."""
        light = theme.current_palette("light")
        dark = theme.current_palette("dark")
        self.assertNotEqual(light.error_text, dark.error_text)
        self.assertEqual(dark.error_text, dark.error)


if __name__ == "__main__":
    unittest.main()
