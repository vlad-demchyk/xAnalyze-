"""The bridge to xFormat's design system.

The web app, the landing page and the admin console all take their colours,
radii, spacing and type scale from one file — `apps/web/src/styles/tokens.css`
in the `XFormat` repository. This module reads that same file and turns it
into plain Python values, so the desktop app is styled from the design
system rather than from a second, drifting copy of it.

Where the file is looked for, in order:

1. `$XFORMAT_TOKENS_CSS`, when set — point it anywhere.
2. The sibling checkout: `../XFormat/apps/web/src/styles/tokens.css`
   relative to this repository. This is the live file, so a token changed
   in the frontend shows up in the desktop app on the next launch.
3. `ui/design/xformat-tokens.css` — a vendored snapshot, so the app still
   starts (and still looks like xFormat) on a machine that only has this
   repository checked out.

Only the parts of CSS that actually appear in the token file are supported:
custom properties, `var(--x)` references (resolved recursively, with the
fallback form `var(--x, y)`), `rem` lengths, and the two theme scopes
(`:root` for light, `[data-theme="dark"]` for dark). `color-mix()` is
computed for the `in srgb` form used by the file; anything else that can't
be resolved is dropped rather than guessed, and every consumer below reads
tokens through `Palette`, which has a hard-coded fallback for each value it
needs. A malformed or missing token file therefore degrades to a plain but
correct theme instead of failing to start.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

#: Checked in order; the first one that exists wins.
TOKEN_SEARCH_PATHS = (
    _REPO_ROOT.parent / "XFormat" / "apps" / "web" / "src" / "styles" / "tokens.css",
    _REPO_ROOT / "ui" / "design" / "xformat-tokens.css",
)

# Stop at the first closing brace rather than requiring one at the start of a
# line: the shipped file happens to be formatted that way, but a hand-edited
# or minified copy is not, and silently parsing nothing out of it would leave
# the app on fallback colours with no indication why.
_ROOT_BLOCK_RE = re.compile(r":root\s*\{([^{}]*)\}", re.DOTALL)
_DARK_BLOCK_RE = re.compile(r'\[data-theme="dark"\]\s*\{([^{}]*)\}', re.DOTALL)
_DECL_RE = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")
_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_VAR_RE = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*(?:\([^()]*\)[^()]*)*))?\)")
_COLOR_MIX_RE = re.compile(
    r"color-mix\(\s*in\s+srgb\s*,\s*([^,]+?)\s+(\d+)%\s*,\s*([^,)]+?)(?:\s+(\d+)%)?\s*\)"
)


def token_file() -> Path | None:
    """The token file actually in use, or None when none was found."""
    override = os.environ.get("XFORMAT_TOKENS_CSS")
    if override:
        path = Path(override).expanduser()
        return path if path.is_file() else None
    for candidate in TOKEN_SEARCH_PATHS:
        if candidate.is_file():
            return candidate
    return None


# ------------------------------------------------------------------ parsing

def _declarations(block: str) -> dict:
    return {name: value.strip() for name, value in _DECL_RE.findall(block)}


def _parse_css(text: str) -> tuple[dict, dict]:
    """Return (light, dark) raw declaration maps, comments stripped."""
    text = _COMMENT_RE.sub("", text)
    light: dict = {}
    for block in _ROOT_BLOCK_RE.findall(text):
        light.update(_declarations(block))
    dark = dict(light)
    for block in _DARK_BLOCK_RE.findall(text):
        dark.update(_declarations(block))
    return light, dark


def _resolve(value: str, table: dict, depth: int = 0) -> str | None:
    """Expand var() references and color-mix() into a literal value."""
    if depth > 12:  # a cycle in the token file; refuse rather than recurse
        return None
    value = value.strip()

    def substitute(match) -> str:
        name, fallback = match.group(1), match.group(2)
        if name in table:
            resolved = _resolve(table[name], table, depth + 1)
            if resolved is not None:
                return resolved
        return (fallback or "").strip()

    expanded = _VAR_RE.sub(substitute, value).strip()
    if not expanded:
        return None
    if "var(" in expanded:  # an unresolved reference is not a usable value
        return None

    mixed = _COLOR_MIX_RE.sub(lambda m: _mix_srgb(m, table, depth), expanded)
    if "color-mix(" in mixed:
        return None
    return mixed.strip() or None


def _mix_srgb(match, table: dict, depth: int) -> str:
    left = _resolve(match.group(1), table, depth + 1)
    right = _resolve(match.group(3), table, depth + 1)
    weight = int(match.group(2)) / 100.0
    left_rgb, right_rgb = _to_rgb(left or ""), _to_rgb(right or "")
    if left_rgb is None or right_rgb is None:
        return match.group(0)  # left unresolved; caller drops the token
    blended = tuple(
        round(a * weight + b * (1 - weight)) for a, b in zip(left_rgb, right_rgb)
    )
    return "#%02x%02x%02x" % blended


def _to_rgb(value: str) -> tuple | None:
    value = value.strip()
    if value == "transparent":
        return (0, 0, 0)
    if value.startswith("#"):
        digits = value[1:]
        if len(digits) == 3:
            digits = "".join(ch * 2 for ch in digits)
        if len(digits) in (6, 8):
            try:
                return tuple(int(digits[i:i + 2], 16) for i in (0, 2, 4))
            except ValueError:
                return None
        return None
    match = re.match(r"rgba?\(([^)]+)\)", value)
    if match:
        parts = [p.strip() for p in match.group(1).replace("/", " ").split(",")]
        try:
            return tuple(int(float(p)) for p in parts[:3])
        except ValueError:
            return None
    return {"white": (255, 255, 255), "black": (0, 0, 0)}.get(value)


def load_tokens(path: Path | None = None) -> dict:
    """Return {"light": {...}, "dark": {...}} of fully resolved tokens."""
    path = path or token_file()
    if path is None:
        return {"light": {}, "dark": {}}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {"light": {}, "dark": {}}

    out = {}
    for theme, table in zip(("light", "dark"), _parse_css(text)):
        resolved = {}
        for name, raw in table.items():
            value = _resolve(raw, table)
            if value is not None:
                resolved[name] = value
        out[theme] = resolved
    return out


# ------------------------------------------------------------------ palette

def px(value: str | None, fallback: int) -> int:
    """CSS length -> whole pixels. Qt style sheets have no rem unit, so the
    root font size the web app uses (16px, the browser default it never
    overrides) is applied here instead."""
    if not value:
        return fallback
    match = re.match(r"^(-?[\d.]+)(rem|px|em)?$", value.strip())
    if not match:
        return fallback
    number = float(match.group(1))
    unit = match.group(2) or "px"
    return int(round(number * 16)) if unit in ("rem", "em") else int(round(number))


def first_font_family(value: str | None, fallback: str) -> str:
    """The first family in a CSS font stack, unquoted. Qt resolves its own
    fallbacks, so passing the whole stack through would just give Qt a
    family name it can never match."""
    if not value:
        return fallback
    first = value.split(",")[0].strip()
    return first.strip('"\'') or fallback


@dataclass
class Palette:
    """The subset of the design system the desktop UI actually paints with.

    Every field has a fallback that is applied when the token is missing, so
    this object is always complete and no caller needs to handle None.
    """
    name: str = "light"

    page_bg: str = "#f4f3f0"
    bg: str = "#ffffff"
    bg_card: str = "#ffffff"
    bg_muted: str = "#f6f5f2"
    bg_hover: str = "#eceae6"
    text: str = "#141416"
    text_muted: str = "#6f6d68"
    border: str = "#e9e7e2"
    border_strong: str = "#d9d6d0"
    primary: str = "#000000"
    primary_hover: str = "#262626"
    on_primary: str = "#ffffff"
    accent: str = "#4c43e8"
    on_accent: str = "#ffffff"
    accent_muted: str = "rgba(76, 67, 232, 0.06)"
    success: str = "#17a06d"
    error: str = "#e5484d"
    amber: str = "#f59e0b"
    scrollbar: str = "#cfcdc7"
    scrollbar_hover: str = "#b4b2ab"

    font: str = "Geist"
    font_mono: str = "Geist Mono"
    font_size: int = 14
    font_size_sm: int = 12
    font_size_lg: int = 17
    font_size_xl: int = 21

    radius: int = 14
    radius_sm: int = 6
    radius_md: int = 8
    radius_lg: int = 10

    space_sm: int = 8
    space_md: int = 12
    space_lg: int = 16

    @property
    def is_dark(self) -> bool:
        return self.name == "dark"

    @classmethod
    def from_tokens(cls, tokens: dict, name: str = "light") -> "Palette":
        defaults = cls()

        def color(key: str, fallback: str) -> str:
            value = tokens.get(key)
            return value if value else fallback

        return cls(
            name=name,
            page_bg=color("--page-bg", defaults.page_bg),
            bg=color("--bg", defaults.bg),
            bg_card=color("--bg-card", defaults.bg_card),
            bg_muted=color("--bg-muted", defaults.bg_muted),
            bg_hover=color("--bg-hover", defaults.bg_hover),
            text=color("--text", defaults.text),
            text_muted=color("--text-muted", defaults.text_muted),
            border=color("--border", defaults.border),
            border_strong=color("--border-strong", defaults.border_strong),
            primary=color("--primary", defaults.primary),
            primary_hover=color("--primary-hover", defaults.primary_hover),
            on_primary=color("--on-primary", defaults.on_primary),
            accent=color("--brand-accent", defaults.accent),
            on_accent=color("--on-accent", defaults.on_accent),
            accent_muted=color("--bg-brand-muted", defaults.accent_muted),
            success=color("--success", defaults.success),
            error=color("--error", defaults.error),
            amber=color("--amber", defaults.amber),
            scrollbar=color("--sb-thumb", defaults.scrollbar),
            scrollbar_hover=color("--sb-thumb-hover", defaults.scrollbar_hover),
            font=first_font_family(tokens.get("--font"), defaults.font),
            font_mono=first_font_family(tokens.get("--font-mono"), defaults.font_mono),
            font_size=px(tokens.get("--font-size-base"), defaults.font_size),
            font_size_sm=px(tokens.get("--font-size-sm"), defaults.font_size_sm),
            font_size_lg=px(tokens.get("--font-size-lg"), defaults.font_size_lg),
            font_size_xl=px(tokens.get("--font-size-xl"), defaults.font_size_xl),
            radius=px(tokens.get("--radius"), defaults.radius),
            radius_sm=px(tokens.get("--radius-sm"), defaults.radius_sm),
            radius_md=px(tokens.get("--radius-md"), defaults.radius_md),
            radius_lg=px(tokens.get("--radius-lg"), defaults.radius_lg),
            space_sm=px(tokens.get("--space-sm"), defaults.space_sm),
            space_md=px(tokens.get("--space-md"), defaults.space_md),
            space_lg=px(tokens.get("--space-lg"), defaults.space_lg),
        )


def palettes() -> dict:
    """Both themes, ready to use."""
    tokens = load_tokens()
    return {
        "light": Palette.from_tokens(tokens.get("light", {}), "light"),
        "dark": Palette.from_tokens(tokens.get("dark", {}), "dark"),
    }
