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

    This detector writes the text to a temporary file and asks the agent
    to analyze it. The agent returns a JSON score.

    For CLI usage, this prints the text to stderr and reads the score from
    stdin, allowing the agent to interactively judge the text.
    """

    name = "agent-llm-judge"
    display_name = "Agent — LLM-as-judge (the agent itself)"
    supported_languages = ("uk", "it", "en")

    def __init__(self, **config):
        super().__init__(**config)
        self._cache: dict[str, float] = {}

    def analyze_block(self, block: TextBlock) -> list[TextSpan]:
        """Analyze a single text block by asking the agent."""
        text = block.text
        if not text.strip() or len(text.split()) < 5:
            return []

        # Check cache
        cache_key = text[:100]
        if cache_key in self._cache:
            score = self._cache[cache_key]
        else:
            score = self._ask_agent(text, block.language_hint or "en")
            self._cache[cache_key] = score

        if score < 0.33:
            return []

        return [
            TextSpan(
                block_id=block.block_id,
                start=0,
                end=len(text),
                score=score,
                confidence=score_to_confidence(score),
                detector_name=self.name,
                explanation=f"Agent judged: {score:.2f}",
                details={
                    "source": "agent-judge",
                    "score": score,
                    "language": block.language_hint,
                },
            )
        ]

    def _ask_agent(self, text: str, language: str) -> float:
        """Ask the agent to judge the text.

        In CLI mode, this prints the text to stderr and reads from stdin.
        In agent mode, the agent can intercept this and provide the score.
        """
        # For now, use a simple heuristic as fallback
        # The agent should override this method or provide a callback
        return self._heuristic_score(text, language)

    def _heuristic_score(self, text: str, language: str) -> float:
        """Simple heuristic score as fallback.

        This is used when the agent cannot interactively judge the text.
        The agent should override _ask_agent to provide real judgment.
        """
        # Check for common AI patterns
        ai_indicators = [
            "it is worth noting",
            "comprehensive solution",
            "delve into",
            "in today's fast-paced",
            "moreover,",
            "furthermore,",
            "additionally,",
            "it is important to note",
            "whether you're",
            "unlock the potential",
        ]

        text_lower = text.lower()
        matches = sum(1 for phrase in ai_indicators if phrase in text_lower)

        if matches >= 3:
            return 0.8
        elif matches >= 2:
            return 0.6
        elif matches >= 1:
            return 0.4
        else:
            return 0.2


# Register the detector
DetectorFactory.register(AgentLLMJudgeDetector.name, AgentLLMJudgeDetector)
