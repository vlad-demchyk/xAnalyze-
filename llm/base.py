"""Abstract LLM provider interface + registry.

Same shape as `detectors/` — one interface, a factory, and concrete
backends that register themselves. Rewriting a passage goes through
`LLMProvider.rewrite()` no matter whether the tokens are billed to the
user's own Anthropic key or to their app.xformat.net subscription, so the
UI and the bulk-rewrite worker never branch on provider.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class LLMUnavailable(RuntimeError):
    """Provider is selected but not currently usable — not signed in, no
    API key, subscription expired, network down. The message is shown to
    the user verbatim, so it should say what to do about it."""


class LLMAuthError(LLMUnavailable):
    """Credentials were rejected (bad password, expired/revoked token).
    Separate from LLMUnavailable so the UI can prompt for a fresh sign-in
    rather than just reporting a generic failure."""


class LLMAppNotPermitted(LLMUnavailable):
    """The account is fine; *this application* is not allowed to use it.

    Separate from LLMAuthError because signing in again fixes nothing: the user
    has to grant this app access to their account (or an admin has to re-enable
    it). Prompting for a password here would send someone round a loop that
    cannot resolve. Only the xFormat provider raises it - a personal API key
    and a local Claude Code session have no concept of a third-party app.
    """


@dataclass
class AuthStatus:
    signed_in: bool
    detail: str = ""          # e.g. account email, plan name, or why not
    quota_remaining: int | None = None


class LLMProvider(ABC):
    #: short machine name, e.g. "anthropic", "xformat"
    name: str = "base"
    #: human-readable label for the settings dialog
    display_name: str = "Base provider"
    #: True when this provider signs in with credentials rather than a key
    uses_account: bool = False

    def __init__(self, **config):
        self.config = config

    @abstractmethod
    def rewrite(self, text: str, language: str | None = None) -> str:
        """Return a human-sounding rewrite of `text`, or raise
        LLMUnavailable / LLMAuthError."""
        raise NotImplementedError

    @abstractmethod
    def auth_status(self) -> AuthStatus:
        """Cheap, non-billing check used by the settings dialog to show
        whether this provider is ready to use."""
        raise NotImplementedError

    def rewrite_batch(self, items: list[tuple[str, str | None]]) -> list[str]:
        """Rewrite several passages. Default is sequential; a provider that
        supports real batching should override this."""
        return [self.rewrite(text, lang) for text, lang in items]


class LLMProviderFactory:
    _registry: dict[str, type[LLMProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_cls: type[LLMProvider]) -> None:
        cls._registry[name] = provider_cls

    @classmethod
    def available(cls) -> list[str]:
        return sorted(cls._registry.keys())

    @classmethod
    def create(cls, name: str, **config) -> LLMProvider:
        if name not in cls._registry:
            raise KeyError(
                f"Unknown LLM provider '{name}'. Available: {', '.join(cls.available()) or '(none)'}"
            )
        return cls._registry[name](**config)


# Shared instruction used by every provider so switching backends doesn't
# quietly change the writing style of the output.
REWRITE_SYSTEM_PROMPT = (
    "You rewrite short pieces of UI/website copy so they read as natural, "
    "human-written text instead of AI-generated text. Keep the same "
    "language, the same approximate length and meaning, and the same tone "
    "(don't make marketing copy sound like a diary entry). Remove clichés, "
    "vary sentence rhythm, cut filler transitions. Return ONLY the "
    "rewritten text, nothing else — no quotes, no explanation."
)
