"""LLM-as-judge over whichever account is paying.

The prompt, the JSON contract and the span mapping all come from
`claude_llm_judge.py`; what changes here is only the transport. That split
exists because "which model reads the text" and "whose account is billed for
it" are two questions, and the tool already knows how to answer the second
one: `rewriter.effective_provider_name` decides it for every other AI call
in the CLI, including the rule that a run inside a Claude Code session bills
that session rather than a second subscription.

Before this, `scan --detector claude-llm-judge` answered the second question
by itself, and answered it with "an Anthropic API key or nothing" - so a
machine with a signed-in Claude Code session and an xFormat subscription was
told `No Anthropic API key configured` while `audit --ai` on the same machine
ran fine. One decision in two places is how two commands come to disagree.
"""
from __future__ import annotations

from models import TextBlock, TextSpan
from .base import Detector, DetectorUnavailable
from .claude_llm_judge import (
    DEFAULT_BATCH_SIZE, ClaudeLLMJudgeDetector, _SYSTEM_PROMPT,
    _parse_json_relaxed,
)

# Providers reached through this path have no schema-enforcement parameter,
# so the shape is asked for in words. `_parse_json_relaxed` handles a model
# that wraps it in prose.
JSON_INSTRUCTION = (
    "\n\nRespond with ONLY JSON, no prose, in exactly this shape:\n"
    '{"results": [{"block_index": 0, "flags": '
    '[{"quote": "...", "score": 0.8, "reason": "..."}]}]}'
    "\n\nUse ALL detection rules from the system prompt: statistical signals "
    "(uniformity, repetition, dash density), structural patterns, and cliché "
    "phrases. Do NOT dismiss dash density as typography."
)


class ProviderLLMJudgeDetector(ClaudeLLMJudgeDetector):
    """Judge whose calls go through an `llm.base.LLMProvider`.

    Subclasses name the provider; everything else is shared.
    """

    #: Which provider in `LLMProviderFactory` pays for this.
    provider_name = ""
    #: How to name the account in an error. "Not signed in to xFormat" is
    #: actionable in a way that "not signed in" is not, when three accounts
    #: could each have been the one meant.
    account_name = "the AI account"
    #: What to tell someone whose account is not usable yet. Provider-specific
    #: because the way out differs: sign in here, or sign in there.
    unavailable_hint = "Pick a different detector, or sign in."

    def __init__(self, batch_size: int = DEFAULT_BATCH_SIZE,
                 provider=None, **config):
        # Deliberately not calling ClaudeLLMJudgeDetector.__init__: it looks
        # for an Anthropic key, which this path never uses.
        Detector.__init__(self, **config)
        self.batch_size = batch_size
        self.model = "(chosen by the account that pays)"
        self._provider = provider

    def _build_provider(self):
        """Make the provider this judge bills. Overridden where the provider
        needs configuration the settings hold."""
        import rewriter

        return rewriter.build_provider(force=self.provider_name)

    def _get_provider(self):
        if self._provider is not None:
            return self._provider
        import llm  # noqa: F401 - registers the providers

        provider = self._build_provider()
        status = provider.auth_status()
        if not status.signed_in:
            # Checked once, before the first of N batches, so an unusable
            # account is reported immediately instead of producing one
            # identical error per block at the end of a long scan.
            raise DetectorUnavailable(
                f"Not signed in to {self.account_name} ({status.detail}). "
                f"{self.unavailable_hint}")
        self._provider = provider
        return provider

    def analyze_blocks(self, blocks: list[TextBlock]) -> list[TextSpan]:
        provider = self._get_provider()
        spans: list[TextSpan] = []
        for i in range(0, len(blocks), self.batch_size):
            batch = blocks[i:i + self.batch_size]
            spans.extend(self._analyze_batch(provider, batch))
        return spans

    def _analyze_batch(self, provider, batch: list[TextBlock]) -> list[TextSpan]:
        numbered = "\n\n".join(f"[{idx}] {b.text}" for idx, b in enumerate(batch))
        try:
            raw = provider.analyze(_SYSTEM_PROMPT + JSON_INSTRUCTION, numbered)
            data = _parse_json_relaxed(raw)
        except Exception as exc:  # noqa: BLE001 - one failed batch, not a failed scan
            return [self._error_span(b, exc) for b in batch]
        return self._spans_from_payload(data, batch)
