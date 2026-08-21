"""Agent-as-judge detector: offline heuristic fallback.

For the REAL agent-as-judge workflow (where the agent's LLM judges text),
use the two-step CLI workflow instead:

    # Step 1: scan → candidate blocks as JSON
    xanalyze agent-scan ./src --json > candidates.json

    # Step 2: agent judges each candidate (the agent reads candidates,
    # examines each block, and writes judgments)

    # Step 3: merge agent's judgments with offline scan → final report
    xanalyze agent-scan ./src | xanalyze agent-judge ./src --judgments -

This detector is a FALLBACK that runs offline heuristics when called
directly (e.g., `--detector agent-llm-judge`). It does NOT call any LLM.
The name is kept for backward compatibility with existing scripts.

The three judge options:
1. claude-llm-judge      — Anthropic API key, real LLM call
2. xformat-llm-judge     — xFormat subscription, real LLM call
3. agent-scan + agent-judge — the agent itself judges (no API key needed)
"""
from __future__ import annotations

import json
import sys
from typing import Any

from models import TextBlock, TextSpan, Confidence, score_to_confidence
from .base import Detector, DetectorUnavailable
from .factory import DetectorFactory


class AgentLLMJudgeDetector(Detector):
    """Uses the agent itself as the LLM judge.

    This detector uses the offline heuristic detector for analysis,
    which provides comprehensive pattern matching for all supported
    languages (uk, it, en).
    """

    name = "agent-llm-judge"
    display_name = "Agent — LLM-as-judge (the agent itself)"
    supported_languages = ("uk", "it", "en")

    def __init__(self, **config):
        super().__init__(**config)
        self._cache: dict[str, float] = {}
        # Use the offline detector for comprehensive analysis
        from .offline import OfflineDetector
        self._offline = OfflineDetector(**config)

    def analyze_block(self, block: TextBlock) -> list[TextSpan]:
        """Analyze a single text block using offline detector."""
        text = block.text
        if not text.strip() or len(text.split()) < 5:
            return []

        # Use offline detector for comprehensive analysis
        spans = self._offline.analyze_block(block)
        
        # Filter to only high-confidence findings
        return [s for s in spans if s.score >= 0.33]

    def analyze_blocks(self, blocks: list) -> list[TextSpan]:
        """Analyze multiple blocks."""
        spans: list[TextSpan] = []
        for block in blocks:
            try:
                spans.extend(self.analyze_block(block))
            except Exception as exc:
                # One bad block can't stop the scan
                spans.append(self._error_span(block, exc))
        return spans


# Register the detector
DetectorFactory.register(AgentLLMJudgeDetector.name, AgentLLMJudgeDetector)
