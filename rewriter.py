"""Builds the configured LLM provider and generates human-sounding
rewrites through it.

This is a thin seam over `llm/` so callers (the bulk-rewrite worker, the
detail panel, the CLI) never care which account the tokens are billed to.

One rule lives here rather than in the providers, because it is about the
environment and not about any one backend: **when the tool is running inside
Claude Code, AI calls go to Claude Code.** That session is already
authenticated and already being paid for, so sending its work to a paid
subscription would bill a second account for the same rewrite — and would
simply fail on a machine that has Claude Code but no xFormat login. The rule
applies to the CLI only, and `--provider` overrides it; the desktop app is
not launched by an agent, so there the user's choice in Settings stands.
"""
from __future__ import annotations

import config
import llm  # noqa: F401 - registers the built-in providers
from llm.base import LLMProvider, LLMProviderFactory, LLMUnavailable
from llm.claude_code_provider import find_binary, running_inside_claude_code


def effective_provider_name(settings, force: str | None = None,
                            allow_auto: bool = False) -> str:
    """Which provider will actually be used, and why it can be shown.

    Exposed rather than kept inside `build_provider` so the CLI can print the
    routing decision before spending anything on it: "auto-selected because
    this is a Claude Code session" is the difference between a surprise on
    someone's bill and an expected one.
    """
    if force:
        return force
    if (allow_auto and settings.prefer_claude_code_in_cli
            and running_inside_claude_code() and find_binary()):
        return "claude-code"
    return settings.llm_provider or "anthropic"


def build_provider(settings=None, force: str | None = None,
                   allow_auto: bool = False) -> LLMProvider:
    """Create the provider named in settings, configured and ready."""
    settings = settings or config.Settings.load()
    name = effective_provider_name(settings, force, allow_auto)
    if name == "xformat":
        return LLMProviderFactory.create(
            "xformat",
            base_url=settings.xformat_base_url,
            endpoints=settings.xformat_endpoints,
        )
    if name == "claude-code":
        return LLMProviderFactory.create(
            "claude-code", model=settings.claude_code_model,
        )
    return LLMProviderFactory.create(
        "anthropic",
        api_key=config.get_anthropic_api_key(),
        model=settings.claude_model,
    )


def generate_rewrite(text: str, language: str | None = None, settings=None,
                      provider: LLMProvider | None = None) -> str:
    """Rewrite one passage. Pass `provider` when rewriting many passages so
    the client/session (and, for xformat, the auth token) is reused instead
    of being rebuilt per call."""
    provider = provider or build_provider(settings)
    return provider.rewrite(text, language)


__all__ = [
    "build_provider", "effective_provider_name", "generate_rewrite",
    "LLMUnavailable",
]
