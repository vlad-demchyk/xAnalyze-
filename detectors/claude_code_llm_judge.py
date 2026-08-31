"""LLM-as-judge through the machine's signed-in Claude Code session.

The account that is already open and already being paid for. This is the
detector `scan` reaches for by default inside a Claude Code session, for the
same reason `rewriter` routes rewrites there: the alternative is billing a
second subscription for work the current session already covers, and on a
machine with Claude Code but no API key the alternative is not working at
all.

No model is named here beyond the settings' `claude_code_model`: what runs
is whatever that session is entitled to.
"""
from __future__ import annotations

from .factory import DetectorFactory
from .provider_llm_judge import ProviderLLMJudgeDetector


class ClaudeCodeLLMJudgeDetector(ProviderLLMJudgeDetector):
    name = "claude-code-llm-judge"
    display_name = "Claude Code session — LLM-as-judge (this machine's login)"
    #: A general model, not a word list: no language is out of scope.
    provider_name = "claude-code"
    account_name = "Claude Code"
    unavailable_hint = ("Sign in with `claude login`, or pick a different "
                        "detector.")

    def __init__(self, **config):
        super().__init__(**config)
        self.model = "(chosen by the Claude Code session)"


DetectorFactory.register(ClaudeCodeLLMJudgeDetector.name, ClaudeCodeLLMJudgeDetector)
