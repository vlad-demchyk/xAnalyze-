"""LLM-as-judge billed to the user's xFormat subscription.

Same prompt, same JSON contract and the same span mapping as
`claude_llm_judge.py` — only the transport differs: the request goes to
`POST /api/ai/document_analysis` on the xFormat backend with the session
token the user already signed in with, and the tokens come out of their
plan instead of a personal Anthropic key.

Why this exists rather than "just use the Anthropic detector": the two
halves of this tool cost money in different places. Detection runs over
every block on a site; rewriting runs over the flagged ones. If only the
rewrite could be billed to the subscription, then anyone without a personal
API key could pay for the cheap half and not the expensive one, which is
backwards. With this, one xFormat sign-in covers the whole loop and nothing
else in the app has to know which account paid.

The model is not chosen here. The backend maps each feature to a model per
plan (`featureModelMap.ts`), so what runs is whatever the subscription is
entitled to — which is also why the response is parsed leniently: a model
routed by that catalog may not honour a JSON-schema constraint the way the
Anthropic path does.
"""
from __future__ import annotations

from models import TextBlock, TextSpan
from .base import DetectorUnavailable
from .claude_llm_judge import (
    DEFAULT_BATCH_SIZE, ClaudeLLMJudgeDetector, _SYSTEM_PROMPT,
    _parse_json_relaxed,
)
from .factory import DetectorFactory

# The backend has no schema-enforcement parameter, so the shape is asked for
# in words. `_parse_json_relaxed` handles a model that wraps it in prose.
_JSON_INSTRUCTION = (
    "\n\nRespond with ONLY JSON, no prose, in exactly this shape:\n"
    '{"results": [{"block_index": 0, "flags": '
    '[{"quote": "...", "score": 0.8, "reason": "..."}]}]}'
)


class XFormatLLMJudgeDetector(ClaudeLLMJudgeDetector):
    name = "xformat-llm-judge"
    display_name = "xFormat subscription — LLM-as-judge (billed to your plan)"
    supported_languages = ("uk", "it", "en")

    def __init__(self, base_url: str | None = None, endpoints: dict | None = None,
                 batch_size: int = DEFAULT_BATCH_SIZE, **config):
        # Deliberately not calling ClaudeLLMJudgeDetector.__init__: it looks
        # for an Anthropic key, which this path never uses.
        from .base import Detector
        Detector.__init__(self, **config)
        self.batch_size = batch_size
        self.model = "(chosen by the xFormat plan)"
        self._base_url = base_url
        self._endpoints = endpoints
        self._provider = None

    def _get_provider(self):
        if self._provider is not None:
            return self._provider
        from llm.base import LLMProviderFactory
        import llm  # noqa: F401 - registers the providers

        kwargs = {}
        if self._base_url:
            kwargs["base_url"] = self._base_url
        if self._endpoints:
            kwargs["endpoints"] = self._endpoints
        provider = LLMProviderFactory.create("xformat", **kwargs)
        status = provider.auth_status()
        if not status.signed_in:
            # Checked once, before the first of N batches, so a signed-out
            # user is told immediately instead of after a long scan that
            # produced one identical error per block.
            raise DetectorUnavailable(
                f"Not signed in to xFormat ({status.detail}). Sign in under "
                "Settings → Rewriting, or pick a different detector."
            )
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
            raw = provider.analyze(_SYSTEM_PROMPT + _JSON_INSTRUCTION, numbered)
            data = _parse_json_relaxed(raw)
        except Exception as exc:  # noqa: BLE001 - one failed batch, not a failed scan
            return [self._error_span(b, exc) for b in batch]
        return self._spans_from_payload(data, batch)


DetectorFactory.register(XFormatLLMJudgeDetector.name, XFormatLLMJudgeDetector)
