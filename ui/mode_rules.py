"""Validation rules for source/reader/check/method combinations.

The toolbar offers four independent choices: what to look at (source),
how to read it (reader), what to look for (check), and who judges
(method). Not every combination is meaningful - a repository has no
browser to render in, and an AI pass needs a signed-in account.

This module is pure logic: no Qt, no side effects, no state. Every
function answers one question about what is allowed, and every rule
is testable in isolation.
"""
from __future__ import annotations

from analysis_modes import (
    AVAILABLE_READERS,
    CHECK_ACCESSIBILITY,
    CHECK_AI_PATTERNS,
    METHOD_AI,
    METHOD_EMBEDDING,
    METHOD_LOCAL,
    READER_BROWSER,
    READER_CODE,
    SOURCE_FILE,
    SOURCE_REPO,
    SOURCE_SITE,
)


def available_readers_for(source: str) -> tuple[str, ...]:
    """Which readers make sense for this source."""
    return AVAILABLE_READERS.get(source, (READER_CODE,))


def auto_readers(source: str) -> tuple[str, ...]:
    """The readers the tool should use for this source, chosen automatically.

    The user no longer picks a reader: a site is always read both ways
    (HTTP fetch + browser render) because the comparison itself is a
    finding — copy that only exists after JavaScript hydration. A
    repository has no server, so it is read from disk only.
    """
    return AVAILABLE_READERS.get(source, (READER_CODE,))


def reader_available(source: str, reader: str) -> bool:
    """Can this reader be used with this source?"""
    return reader in available_readers_for(source)


def method_available(method: str, *, ai_available: bool) -> bool:
    """Can this method be used given the current account state?"""
    if method == METHOD_AI:
        return ai_available
    return True


def provider_visible(checks: tuple[str, ...], methods: tuple[str, ...]) -> bool:
    """The provider combo is only relevant when AI is actually judging."""
    wants_ai_patterns = CHECK_AI_PATTERNS in checks
    wants_ai_method = METHOD_AI in methods
    return wants_ai_patterns and wants_ai_method


# The seven `*_visible` policies that used to live here are gone. They had no
# callers - `main_window._apply_mode_visibility` decides all of it inline -
# and that on its own would only be clutter. What made them worth deleting is
# that they had drifted: `fix_unicode_visible()` returned True
# unconditionally while the window shows that button only for a copy run, and
# `download_visible(checks)` answered "any check at all" where the window asks
# for copy or audit findings. A module named for the rules, stating rules the
# application does not follow, is worse than no module: the next person to fix
# a visibility bug fixes it here and nothing changes.
#
# If these come back, they come back with the window calling them.


def col1_stack_index(source: str) -> int:
    """Which preview to show: 0=web view, 1=code view."""
    return 1 if source == SOURCE_REPO else 0


def source_controls_index(source: str) -> int:
    """Which input controls to show: 0=URL, 1=repo path, 2=file path."""
    if source == SOURCE_FILE:
        return 2
    if source == SOURCE_REPO:
        return 1
    return 0


def derive_mode(source: str, checks: tuple[str, ...]) -> str:
    """The effective run mode, derived from source + checks.

    Downstream code (preview, buttons, dispatch) still uses these names.
    """
    if source == SOURCE_REPO:
        return "repo"
    if source == SOURCE_FILE:
        return "file"
    return "audit" if checks == (CHECK_ACCESSIBILITY,) else "web"


def normalize_reader_choice(source: str, current: tuple[str, ...]) -> tuple[str, ...]:
    """Keep only readers that are valid for this source."""
    allowed = available_readers_for(source)
    result = tuple(r for r in current if r in allowed)
    return result if result else (allowed[0],)


def normalize_method_choice(
    current: tuple[str, ...], *, ai_available: bool
) -> tuple[str, ...]:
    """Drop AI method if no account is available."""
    result = tuple(m for m in current if method_available(m, ai_available=ai_available))
    return result if result else (METHOD_LOCAL,)
