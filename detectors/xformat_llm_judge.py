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

The transport itself now lives in `provider_llm_judge.py`, shared with the
Claude Code judge: what is specific to xFormat is the endpoint configuration
the settings carry, and nothing else.
"""
from __future__ import annotations

from .claude_llm_judge import DEFAULT_BATCH_SIZE
from .factory import DetectorFactory
from .provider_llm_judge import ProviderLLMJudgeDetector

# Kept importable from here: it was part of this module's surface before the
# transport moved.
from .provider_llm_judge import JSON_INSTRUCTION as _JSON_INSTRUCTION  # noqa: F401


class XFormatLLMJudgeDetector(ProviderLLMJudgeDetector):
    name = "xformat-llm-judge"
    display_name = "xFormat subscription — LLM-as-judge (billed to your plan)"
    #: A general model, not a word list: no language is out of scope.
    provider_name = "xformat"
    account_name = "xFormat"
    unavailable_hint = ("Sign in under Settings → Rewriting, or pick a "
                        "different detector.")

    def __init__(self, base_url: str | None = None, endpoints: dict | None = None,
                 batch_size: int = DEFAULT_BATCH_SIZE, **config):
        super().__init__(batch_size=batch_size, **config)
        self.model = "(chosen by the xFormat plan)"
        self._base_url = base_url
        self._endpoints = endpoints

    def _build_provider(self):
        """Built directly rather than through `rewriter` when the caller passed
        an endpoint override: the desktop app lets the backend shape be
        corrected in the field, and that override has to survive the trip."""
        if not (self._base_url or self._endpoints):
            return super()._build_provider()
        from llm.base import LLMProviderFactory

        kwargs = {}
        if self._base_url:
            kwargs["base_url"] = self._base_url
        if self._endpoints:
            kwargs["endpoints"] = self._endpoints
        return LLMProviderFactory.create("xformat", **kwargs)


DetectorFactory.register(XFormatLLMJudgeDetector.name, XFormatLLMJudgeDetector)
