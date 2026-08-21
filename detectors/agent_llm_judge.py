"""Agent-as-judge detector: the CLI agent itself acts as the LLM judge.

When running in agent mode (e.g., from Claude Code, Cursor, or any coding
agent), this detector sends the text to the agent for judgment instead of
requiring an API key. The agent analyzes the text and returns a score.

This is the third option alongside:
1. claude-llm-judge (Anthropic API key)
2. xformat-llm-judge (xFormat subscription)
3. agent-llm-judge (the agent itself)

Usage:
    xanalyze scan ./src --detector agent-llm-judge
    xanalyze fullscan https://example.com --detector agent-llm-judge
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
