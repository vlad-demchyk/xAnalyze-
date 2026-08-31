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

    #: The languages this backend is *calibrated on*, or None when the
    #: question does not apply to it.
    #:
    #: This used to be a copied-out `("uk", "it", "en")` on all eleven
    #: detector classes and was read by no line of code - which is why the
    #: question it was supposed to answer stayed open. A backend whose answer
    #: comes out of a per-language word list or a per-language reference set
    #: names those languages here and is silenced outside them by
    #: `supports_language`. A backend that reads characters, or hands the text
    #: to a general model, says None: it is not more right on Italian than on
    #: Polish, and pretending otherwise would suppress a finding that is
    #: perfectly good.
    supported_languages: tuple[str, ...] | None = None

    @classmethod
    def supports_language(cls, language: str | None) -> bool:
        """Whether this backend has anything calibrated to say about `language`.

        `None` is a yes: it means the passage was too short to read, and the
        callers that see it check every list rather than guess one.
        `lang_detect.UNSUPPORTED` is a no - it is a reading, not a fallback,
        and it is the whole reason this method exists.
        """
        if cls.supported_languages is None or language is None:
            return True
        return language in cls.supported_languages

    #: Whether this backend already reports non-keyboard characters itself.
    #: Declared here rather than checked by name at the call site: callers
    #: run that pass alongside whichever detector was chosen (it is free and
    #: answers a different question), and the one thing they must not do is
    #: run it twice over a detector that contains it - which is what listing
    #: the names in `ui/worker.py` did until a second such detector existed.
    includes_character_pass: bool = False

    #: Whether this backend's answer depends on `corpus/labelled.jsonl`.
    #:
    #: A detector that says True cannot be scored against the whole corpus:
    #: every entry would be matched against itself, and a nearest-neighbour
    #: margin against a set containing the text is ±1 by construction. Measured
    #: 2026-08-31: run that way the embedding detector separates the corpus
    #: almost perfectly - model entries 0.73-0.79, human entries around 0.16 -
    #: and the separation is entirely self-recognition. Declared here so the
    #: calibration script can refuse the tautology instead of printing it.
    uses_corpus_as_reference: bool = False

    @classmethod
    def calibration_config(cls) -> dict:
        """Config for scoring a labelled corpus rather than a live page.

        One thing differs from a run: no score may be suppressed, because a
        threshold sweep cannot see below a cut-off the detector already applied.
        A backend with no threshold of its own returns the empty dict and is
        built exactly as it runs.
        """
        return {}

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
        """A block the detector could not judge.

        Stamped in `details` rather than recognised by its low confidence:
        callers drop low-confidence spans, so a failure that only looked like
        a weak finding was dropped with them, and a scan whose every batch
        failed printed "No findings". A block nobody read is not a clean
        block, and the difference has to survive that filter.
        """
        from models import Confidence
        return TextSpan(
            block_id=block.block_id,
            start=0,
            end=len(block.text),
            score=0.0,
            confidence=Confidence.LOW,
            detector_name=self.name,
            explanation=f"detector error: {exc}",
            details={"error": str(exc)},
        )


class DetectorUnavailable(RuntimeError):
    """Raised by a detector that is registered but not currently usable
    (e.g. missing API key, or — for the official watermark API — not yet
    published by the vendor)."""
