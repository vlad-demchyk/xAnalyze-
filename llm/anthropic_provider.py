"""Direct-to-Anthropic provider: tokens are billed to the user's own key."""
from __future__ import annotations

import os

from .base import (
    REWRITE_SYSTEM_PROMPT, AuthStatus, LLMProvider, LLMProviderFactory,
    LLMAuthError, LLMUnavailable,
)

DEFAULT_MODEL = "claude-opus-5"


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    display_name = "Anthropic API (your own key)"
    uses_account = False

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL, **config):
        super().__init__(**config)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self._client = None  # built once and reused across a bulk rewrite

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.api_key:
            raise LLMUnavailable(
                "No Anthropic API key. Set ANTHROPIC_API_KEY, or enter one in "
                "Settings, or switch to the xformat.net subscription."
            )
        try:
            import anthropic
        except ImportError as exc:
            raise LLMUnavailable("The 'anthropic' package is not installed.") from exc
        self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def auth_status(self) -> AuthStatus:
        if not self.api_key:
            return AuthStatus(signed_in=False, detail="no API key configured")
        masked = f"…{self.api_key[-4:]}" if len(self.api_key) > 4 else "set"
        return AuthStatus(signed_in=True, detail=f"key {masked}")

    def rewrite(self, text: str, language: str | None = None) -> str:
        client = self._get_client()
        lang_hint = f" (language: {language})" if language else ""
        try:
            response = client.messages.create(
                model=self.model,
                # A rewrite is one short passage of UI copy, so a small cap
                # is a real constraint here rather than a cost shortcut: the
                # output is meant to be about as long as the input, and a
                # reply that runs far past it is a failed rewrite anyway.
                max_tokens=4000,
                system=REWRITE_SYSTEM_PROMPT,
                # Rewriting a sentence is not a reasoning task, and a bulk
                # rewrite runs this once per flagged passage on the user's
                # bill. The cheapest tier is the right default.
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": text + lang_hint}],
            )
        except Exception as exc:  # noqa: BLE001
            if _looks_like_auth_error(exc):
                raise LLMAuthError(f"Anthropic rejected the API key: {exc}") from exc
            raise LLMUnavailable(f"Anthropic request failed: {exc}") from exc
        if getattr(response, "stop_reason", None) == "refusal":
            # A decline is a 200 with an empty-looking body; without this
            # check the caller would silently get the original text back and
            # believe the rewrite succeeded.
            raise LLMUnavailable(
                "The model declined to rewrite this passage. Edit it by hand, "
                "or use the offline suggestion."
            )
        # `content` can also hold thinking blocks; only text is the answer.
        parts = [p.text for p in response.content if getattr(p, "type", "") == "text"]
        return "".join(parts).strip() or text


def _looks_like_auth_error(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status in (401, 403):
        return True
    return "authentication" in str(exc).lower() or "api key" in str(exc).lower()


LLMProviderFactory.register(AnthropicProvider.name, AnthropicProvider)
