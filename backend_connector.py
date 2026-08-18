"""Extension point for connecting to YOUR OWN backend/AI account.

Per your notes: you already have an AI account/backend that can validate
scans and run a chat integration on top of them, but that integration is
still an open question and not built yet. Rather than guessing at your
backend's API shape, this module defines the seam the rest of the app will
call through, so wiring in the real thing later doesn't touch the crawler,
the detectors, or the UI.

When you're ready, implement `RemoteBackendConnector` for your actual
backend (auth, request/response shapes) and flip `backend_enabled = True`
in Settings (config.py). Until then this stays unused — the app runs fully
standalone (crawl + local/Claude detectors).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from models import AnalysisResult


class BackendConnector(ABC):
    """What the app expects from "your backend" once it's wired in."""

    @abstractmethod
    def validate_scan(self, result: AnalysisResult) -> AnalysisResult:
        """Send a completed scan to your backend for validation/re-scoring
        and return the (possibly annotated) result."""
        raise NotImplementedError

    @abstractmethod
    def start_chat(self, context: str) -> str:
        """Kick off a chat session on your backend seeded with `context`
        (e.g. a summary of flagged passages) and return a session id or URL."""
        raise NotImplementedError


class NullBackendConnector(BackendConnector):
    """Default no-op connector used while backend integration is undecided."""

    def validate_scan(self, result: AnalysisResult) -> AnalysisResult:
        return result

    def start_chat(self, context: str) -> str:
        raise NotImplementedError(
            "Backend chat integration isn't configured yet. Implement "
            "BackendConnector for your backend and set it up in config.py / "
            "the app's startup code when you're ready."
        )


def get_backend_connector(settings) -> BackendConnector:
    if not settings.backend_enabled or not settings.backend_url:
        return NullBackendConnector()
    # TODO: once your backend's API is defined, return a real connector here,
    # e.g. `return MyBackendConnector(base_url=settings.backend_url)`
    return NullBackendConnector()
