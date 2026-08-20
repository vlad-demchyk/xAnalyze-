"""Which judge detector bills which account.

Lives here rather than in `cli.py` because the window needs the same answer
the CLI already had. It used to exist only as `cli.JUDGE_BY_PROVIDER`, and
the window, having no access to it, asked its own question instead: it let
the user pick a detector *by name* in a dropdown. Two vocabularies for one
decision — "which account pays" in the CLI, "which backend class" in the
window — and the window's version was the one that quietly dropped the
user's choice of method on the floor.
"""
from __future__ import annotations

#: Detector names that say "ask a model" without saying whose account pays.
#: Written because that is the question a user has - the answer belongs to
#: the provider, and having to know a backend's name to ask a model at all is
#: what made `scan` demand an Anthropic key on a machine that had a perfectly
#: good Claude Code session.
JUDGE_ALIASES = ("llm-judge", "judge", "ai")

#: The judge that bills each account.
JUDGE_BY_PROVIDER = {
    "anthropic": "claude-llm-judge",
    "xformat": "xformat-llm-judge",
    "claude-code": "claude-code-llm-judge",
}

#: Every name that means "a live model reads the text", alias or concrete.
JUDGE_NAMES = frozenset(JUDGE_BY_PROVIDER.values()) | frozenset(JUDGE_ALIASES)

#: The order the providers are offered in. Anthropic first because it is the
#: default in `config.Settings`; the other two need an account or a session
#: that may not exist on this machine.
PROVIDER_ORDER = ("anthropic", "xformat", "claude-code")


def judge_for_provider(provider: str) -> str:
    """The judge detector for `provider`, falling back to the Anthropic one.

    A fallback rather than a raise: an unknown provider string can only come
    from a hand-edited settings file, and refusing to scan at all would be a
    harsher answer than running the default judge and letting its own error
    say what is missing.
    """
    return JUDGE_BY_PROVIDER.get(provider, JUDGE_BY_PROVIDER["anthropic"])
