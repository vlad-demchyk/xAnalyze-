"""Centralized application state with change notifications.

AppState holds every user-facing choice (source, reader, check, method,
provider) and emits Qt signals when any of them change. The toolbar
combos write to this object; the UI subscribes to its signals to
update visibility, enabled state, and combo contents.

This replaces the scattered ``self.source``, ``self._chosen_checks()``,
``self._chosen_methods()`` etc. that lived directly on MainWindow.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QObject, Signal

from analysis_modes import (
    CHECK_AI_PATTERNS,
    METHOD_AI,
    METHOD_LOCAL,
    SOURCE_SITE,
)
from ui.mode_rules import (
    auto_readers,
    derive_mode,
    normalize_method_choice,
    provider_visible,
)


class AppState(QObject):
    """Observable state for the entire application.

    Every setter validates the new value, normalises it, and emits the
    appropriate changed signal only when the value actually differs.
    The UI connects to these signals once, at startup.
    """

    # -- signals -----------------------------------------------------------
    source_changed = Signal(str)          # new source
    checks_changed = Signal(tuple)        # new checks tuple
    method_changed = Signal(tuple)        # new methods tuple
    provider_changed = Signal(str)        # new provider key
    ai_available_changed = Signal(bool)   # account state changed
    mode_changed = Signal(str)            # derived mode changed

    # Fired after any axis changes, in addition to the specific signal.
    # Listeners that care about the combined state (e.g. button visibility)
    # connect to this one signal instead of all five.
    any_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._source: str = SOURCE_SITE
        self._checks: tuple[str, ...] = (CHECK_AI_PATTERNS,)
        self._methods: tuple[str, ...] = (METHOD_LOCAL,)
        self._provider: str = ""
        self._ai_available: bool = False
        self._target: str = ""
        self._depth: int = 0

    # -- source ------------------------------------------------------------
    @property
    def source(self) -> str:
        return self._source

    def set_source(self, value: str) -> None:
        if value == self._source:
            return
        old_mode = self.mode
        self._source = value
        self.source_changed.emit(value)
        self._emit_mode_if_changed(old_mode)
        self.any_changed.emit()

    # -- readers (auto-determined from source) -----------------------------
    @property
    def readers(self) -> tuple[str, ...]:
        """The readers for the current source, determined automatically."""
        return auto_readers(self._source)

    # -- checks ------------------------------------------------------------
    @property
    def checks(self) -> tuple[str, ...]:
        return self._checks

    def set_checks(self, value: tuple[str, ...]) -> None:
        if value == self._checks:
            return
        old_mode = self.mode
        self._checks = value
        self.checks_changed.emit(value)
        self._emit_mode_if_changed(old_mode)
        self.any_changed.emit()

    # -- methods -----------------------------------------------------------
    @property
    def methods(self) -> tuple[str, ...]:
        return self._methods

    def set_methods(self, value: tuple[str, ...]) -> None:
        normalised = normalize_method_choice(value, ai_available=self._ai_available)
        if normalised == self._methods:
            return
        self._methods = normalised
        self.method_changed.emit(normalised)
        self.any_changed.emit()

    # -- provider ----------------------------------------------------------
    @property
    def provider(self) -> str:
        return self._provider

    def set_provider(self, value: str) -> None:
        if value == self._provider:
            return
        self._provider = value
        self.provider_changed.emit(value)
        self.any_changed.emit()

    # -- ai_available ------------------------------------------------------
    @property
    def ai_available(self) -> bool:
        return self._ai_available

    def set_ai_available(self, value: bool) -> None:
        if value == self._ai_available:
            return
        self._ai_available = value
        if not value:
            self._methods = normalize_method_choice(self._methods, ai_available=False)
            self.method_changed.emit(self._methods)
        self.ai_available_changed.emit(value)
        self.any_changed.emit()

    # -- target / depth (no signals, read by ViewModel) --------------------
    @property
    def target(self) -> str:
        return self._target

    def set_target(self, value: str) -> None:
        self._target = value

    @property
    def depth(self) -> int:
        return self._depth

    def set_depth(self, value: int) -> None:
        self._depth = max(0, value)

    # -- derived -----------------------------------------------------------
    @property
    def mode(self) -> str:
        return derive_mode(self._source, self._checks)

    @property
    def wants_provider(self) -> bool:
        return provider_visible(self._checks, self._methods)

    def _emit_mode_if_changed(self, old_mode: str) -> None:
        new_mode = self.mode
        if new_mode != old_mode:
            self.mode_changed.emit(new_mode)
