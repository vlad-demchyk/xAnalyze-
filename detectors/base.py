"""Abstract detector interface + registry (the "abstract factory").

Every detection backend (heuristic, Claude-as-judge, a future official
watermark API, or anything else you plug in later — OpenAI, a local model,
your own backend) implements the same `Detector` interface. The UI and the
analysis pipeline only ever talk to this interface, never to a concrete
backend directly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from models import TextBlock, TextSpan


class Detector(ABC):
    """Common interface every detection backend must implement."""

    #: short machine name, e.g. "heuristic", "claude-llm-judge"
    name: str = "base"

    #: human-readable label for the UI
    display_name: str = "Base detector"

    #: languages this backend claims to support well
    supported_languages: tuple[str, ...] = ("uk", "it", "en")

    def __init__(self, **config):
        self.config = config

    @abstractmethod
    def analyze_block(self, block: TextBlock) -> list[TextSpan]:
        """Return zero or more TextSpans (may cover the whole block or
        sub-ranges of it) describing where AI-generated content is
        suspected, with a 0..1 score each.
        """
        raise NotImplementedError

    def analyze_blocks(self, blocks: list[TextBlock]) -> list[TextSpan]:
        """Default implementation: analyze one block at a time.
        Override for backends that batch requests (e.g. a remote API).
        """
        spans: list[TextSpan] = []
        for block in blocks:
            try:
                spans.extend(self.analyze_block(block))
            except Exception as exc:  # noqa: BLE001 - surface, don't crash the whole scan
                spans.append(self._error_span(block, exc))
        return spans

    def _error_span(self, block: TextBlock, exc: Exception) -> TextSpan:
        from models import Confidence
        return TextSpan(
            block_id=block.block_id,
            start=0,
            end=len(block.text),
            score=0.0,
            confidence=Confidence.LOW,
            detector_name=self.name,
            explanation=f"detector error: {exc}",
        )


class DetectorUnavailable(RuntimeError):
    """Raised by a detector that is registered but not currently usable
    (e.g. missing API key, or — for the official watermark API — not yet
    published by the vendor)."""
