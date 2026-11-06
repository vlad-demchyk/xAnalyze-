"""What a TUI run screen starts from: the person's Settings (P-31).

The Settings screen stores a default method, crawl depth, page ceiling and
repository scope, and the window already reads them. The run screens used to
type their own numbers instead, so a saved setting changed nothing in the
terminal. One reader here, so the three screens cannot drift apart again.
"""
from __future__ import annotations

from dataclasses import dataclass

import config

#: `Settings.default_method` -> the scan screen's detector choice. The same
#: split the window makes in `ViewModel._detector_for_request`.
METHOD_TO_DETECTOR = {
    "local": "offline",
    "ai": "llm-judge",
    "local+ai": "hybrid",
}

#: The depths the run screens offer. A stored value outside them would leave
#: a `Select` with nothing chosen, so it falls back to the shipped default.
DEPTHS = ("0", "1", "2", "3")
SCOPES = ("content", "technical", "both")


@dataclass(frozen=True)
class RunDefaults:
    depth: str = "1"
    max_pages: int = 30
    scope: str = "content"
    detector: str = "offline"


def from_settings(settings) -> RunDefaults:
    shipped = RunDefaults()
    depth = str(getattr(settings, "crawl_depth", shipped.depth))
    try:
        max_pages = int(getattr(settings, "max_pages", shipped.max_pages))
    except (TypeError, ValueError):
        max_pages = shipped.max_pages
    scope = getattr(settings, "repo_scope", shipped.scope)
    method = getattr(settings, "default_method", "local")
    return RunDefaults(
        depth=depth if depth in DEPTHS else shipped.depth,
        max_pages=max_pages if max_pages >= 0 else shipped.max_pages,
        scope=scope if scope in SCOPES else shipped.scope,
        detector=METHOD_TO_DETECTOR.get(method, shipped.detector),
    )


def load() -> RunDefaults:
    """The stored settings as run defaults; the shipped ones if unreadable."""
    try:
        settings = config.Settings.load()
    except Exception:  # noqa: BLE001 - a form must still draw
        return RunDefaults()
    return from_settings(settings)
