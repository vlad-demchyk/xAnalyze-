"""Placeholder for Anthropic's OFFICIAL text-watermark detector.

Status, re-checked against Anthropic's own pages on 18 August 2026:

* The watermark itself is **live**. Claude models launched on or after
  2 August 2026 mark their text output with an imperceptible watermark
  (an approach derived from SynthID-Text), across the API, Claude, Claude
  Code and the rest of the surfaces.
* Detection is **not shipped**. Anthropic says it is "working to enable
  users and other third parties to detect Claude's embedded watermarks and
  provenance metadata" and will "share details on detection mechanisms in
  forthcoming technical documentation", and separately that a watermark
  detection API is coming but its implementation is still being worked out.
  No endpoint, no auth scheme, no request or response format has been
  published.
* What *is* verifiable today is C2PA signed provenance metadata — but only
  on generated **files** (.svg, .png, .jpg), not on text. This tool reads
  page copy and source files, so that path does not apply to it.

The practical consequence: nobody can honestly ship text-watermark
detection today, and any tool that claims to is running a classifier under
a name that isn't one. That is precisely what `claude_llm_judge.py` and
`heuristic.py` are — labelled as classifiers, because that is what they
are.

This class exists purely as the wiring point: registered in the factory so
it appears in the detector dropdown, and failing fast with an explanation
rather than returning fabricated results. When Anthropic publishes the real
docs, fill in `_call_official_api` below (base URL, auth header,
request/response parsing) — nothing else in the app needs to change.
"""
from __future__ import annotations

import os

from models import TextBlock, TextSpan
from .base import Detector, DetectorUnavailable
from .factory import DetectorFactory


class ClaudeOfficialWatermarkDetector(Detector):
    name = "claude-official-watermark"
    display_name = "Claude — official watermark API (not yet published by Anthropic)"
    #: A vendor signature, if it is ever published, will not be per-language.

    def __init__(self, api_key: str | None = None, base_url: str | None = None, **config):
        super().__init__(**config)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.base_url = base_url or os.environ.get("ANTHROPIC_WATERMARK_API_BASE_URL")
        # Raised here, not in `analyze_block`. It was raised there, and
        # `Detector.analyze_blocks` turns an exception into an error span per
        # block - so choosing this detector produced one identical
        # "unavailable" finding for every passage on the site, at the end of a
        # full crawl, instead of one sentence before the crawl started. The
        # same reasoning as `ProviderLLMJudgeDetector._get_provider`: an
        # unusable backend is reported once, up front.
        self._unavailable()

    def analyze_block(self, block: TextBlock) -> list[TextSpan]:
        return self._call_official_api(block)

    def _call_official_api(self, block: TextBlock) -> list[TextSpan]:
        self._unavailable()
        return []  # unreachable; kept so the signature stays honest

    @staticmethod
    def _unavailable() -> None:
        raise DetectorUnavailable(
            "Anthropic watermarks Claude's text output, but has not published "
            "any way to read that mark: as of 18 August 2026 detection is "
            "still 'forthcoming technical documentation', with no endpoint, "
            "auth scheme or payload format released. When that changes: set "
            "ANTHROPIC_WATERMARK_API_BASE_URL (or pass base_url=) and "
            "implement the request/response handling in "
            "detectors/claude_watermark_stub.py::_call_official_api. "
            "Until then use the 'offline' detector, or one of the "
            "LLM-as-judge detectors — and read their results as opinions, "
            "not as proof of origin."
        )


DetectorFactory.register(ClaudeOfficialWatermarkDetector.name, ClaudeOfficialWatermarkDetector)
