"""Modern design system for XAnalyze.

Dark-first palette inspired by Linear, Vercel, and Sentry.
Every value is a Python constant - no CSS parsing needed.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DesignTokens:
    """Complete design system tokens."""
    name: str = "dark"

    # -- Backgrounds --
    bg_base: str = "#0d1117"        # main canvas
    bg_surface: str = "#161b22"     # sidebar, panels
    bg_elevated: str = "#1c2128"    # cards, dropdowns
    bg_hover: str = "#262c36"       # hover states
    bg_active: str = "#2d333b"      # active/selected
    bg_input: str = "#0d1117"       # input fields

    # -- Text --
    text_primary: str = "#e6edf3"   # main text
    text_secondary: str = "#8b949e" # muted text
    text_disabled: str = "#484f58"  # disabled
    text_inverse: str = "#0d1117"   # text on light fills

    # -- Borders --
    border_default: str = "#30363d"
    border_subtle: str = "#21262d"
    border_active: str = "#58a6ff"
    border_strong: str = "#444c56"  # more visible border

    # -- Status colors --
    critical: str = "#f85149"
    high: str = "#f0883e"
    medium: str = "#d29922"
    low: str = "#3fb950"
    info: str = "#58a6ff"

    # -- Accent --
    accent: str = "#58a6ff"
    accent_emphasis: str = "#1f6feb"
    accent_muted: str = "rgba(56, 139, 253, 0.15)"

    # -- Semantic --
    success: str = "#3fb950"
    error: str = "#f85149"
    warning: str = "#d29922"

    # -- Typography --
    font_family: str = "Inter, -apple-system, 'Segoe UI', sans-serif"
    font_mono: str = "'JetBrains Mono', 'Fira Code', 'SF Mono', monospace"
    font_size_xs: int = 11
    font_size_sm: int = 12
    font_size_base: int = 13
    font_size_lg: int = 15
    font_size_xl: int = 18
    font_size_xxl: int = 24

    # -- Spacing (4px grid) --
    space_1: int = 4
    space_2: int = 8
    space_3: int = 12
    space_4: int = 16
    space_5: int = 20
    space_6: int = 24
    space_8: int = 32

    # -- Radius --
    radius_sm: int = 4
    radius_md: int = 6
    radius_lg: int = 8
    radius_xl: int = 12

    # -- Shadows --
    shadow_sm: str = "0 1px 2px rgba(0, 0, 0, 0.3)"
    shadow_md: str = "0 4px 12px rgba(0, 0, 0, 0.4)"
    shadow_lg: str = "0 8px 24px rgba(0, 0, 0, 0.5)"

    # -- Layout --
    sidebar_width: int = 260
    detail_width: int = 380
    header_height: int = 48


# Singleton instance
TOKENS = DesignTokens()
