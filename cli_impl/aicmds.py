"""The `ai` command family: sign-in, status, consent, and the billing-path
smoke test.

Every AI-backed feature has a CLI entry point, for two reasons. The first
is that this tool is meant to run unattended in hooks and pipelines, where
there is no Settings dialog to sign in from. The second is that a feature
only reachable through a window cannot be checked without a person and a
mouse, so "does the subscription actually work" stops being an answerable
question the moment the only path to it is the UI.
"""
from __future__ import annotations

import os
import sys

import config
from cli_impl import EXIT_ERROR, EXIT_FINDINGS, EXIT_OK


def _provider_for(args):
    """Build the provider the user asked for, or the automatic one.

    `allow_auto=True` is what routes a run started inside Claude Code to the
    signed-in Claude session instead of a paid subscription; `--provider`
    always wins over it.
    """
    import rewriter

    settings = config.Settings.load()
    name = rewriter.effective_provider_name(
        settings, force=getattr(args, "provider", None), allow_auto=True)
    return name, rewriter.build_provider(
        settings, force=getattr(args, "provider", None), allow_auto=True)


def cmd_ai_status(args) -> int:
    """What would a rewrite cost, and to whom — asked without spending it.

    Every provider answers this without billing anything: a key check for
    Anthropic, `claude auth status` for Claude Code, `/api/me` for xFormat.
    """
    from llm.base import LLMProviderFactory, LLMUnavailable

    settings = config.Settings.load()
    name, provider = _provider_for(args)
    auto = (name != (settings.llm_provider or "anthropic")
            and not getattr(args, "provider", None))

    print(f"provider: {name}  ({provider.display_name})")
    if auto:
        print("  auto-selected: this is a Claude Code session, so its own "
              "signed-in account pays rather than a second subscription")
        print("  (disable with prefer_claude_code_in_cli=false in settings.json)")
    print(f"configured in settings.json: {settings.llm_provider}")
    print(f"available: {', '.join(LLMProviderFactory.available())}")

    try:
        status = provider.auth_status()
    except LLMUnavailable as exc:
        print(f"  status: unavailable — {exc}")
        return EXIT_ERROR
    state = "signed in" if status.signed_in else "NOT signed in"
    print(f"  status: {state}  {status.detail}")
    if status.quota_remaining is not None:
        print(f"  budget left this period: {status.quota_remaining}")

    # Being signed in and being *allowed* are different questions on xFormat:
    # the account can be perfectly valid while this application has no consent,
    # and a status that reported only the first would call a broken setup ready.
    if status.signed_in and name == "xformat":
        try:
            app = provider.app_state()
        except LLMUnavailable as exc:
            print(f"  app consent: could not be read — {exc}")
            return EXIT_OK
        if app is None:
            print(f"  app consent: this backend does not know '{provider.client_app}'")
        elif app.get("connected"):
            print(f"  app consent: granted for {app.get('name')}")
        else:
            print(f"  app consent: MISSING for {app.get('name')} — run `ai grant`")
            return EXIT_FINDINGS
    return EXIT_OK if status.signed_in else EXIT_FINDINGS


def cmd_ai_login(args) -> int:
    """Sign in to the account that pays for AI calls.

    Only xFormat has credentials to take here. Claude Code owns its own
    login and Anthropic takes a key, so for those this says where to go
    rather than pretending to a flow it does not have.
    """
    import getpass

    from llm.base import LLMAuthError, LLMUnavailable

    settings = config.Settings.load()
    name = args.provider or "xformat"
    if name == "claude-code":
        print("Claude Code manages its own sign-in. Run: claude auth login")
        return EXIT_OK
    if name == "anthropic":
        print("The Anthropic provider takes an API key, not a login. Set "
              "ANTHROPIC_API_KEY, or enter the key in Settings (it is stored "
              "in the OS keychain, never in settings.json).")
        return EXIT_OK

    from llm.base import LLMProviderFactory

    provider = LLMProviderFactory.create(
        "xformat", base_url=settings.xformat_base_url,
        endpoints=settings.xformat_endpoints,
    )
    email = args.email or input("xFormat email: ").strip()
    # Never accepted as an argument: a password on the command line lands in
    # the shell history and in the process list of every user on the machine.
    password = os.environ.get("XFORMAT_PASSWORD") or getpass.getpass("Password: ")
    try:
        status = provider.sign_in(email, password)
    except (LLMAuthError, LLMUnavailable) as exc:
        print(f"sign-in failed: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(f"signed in: {status.detail}")
    if status.quota_remaining is not None:
        print(f"budget left this period: {status.quota_remaining}")
    return EXIT_OK


def cmd_ai_logout(args) -> int:
    from llm.base import LLMProviderFactory

    settings = config.Settings.load()
    name = args.provider or "xformat"
    if name != "xformat":
        print(f"nothing to sign out of for '{name}'.")
        return EXIT_OK
    provider = LLMProviderFactory.create(
        "xformat", base_url=settings.xformat_base_url,
        endpoints=settings.xformat_endpoints,
    )
    provider.sign_out()
    print("signed out of xFormat (session revoked server-side, tokens removed "
          "from the keychain).")
    return EXIT_OK


def _xformat_provider():
    """The xFormat provider specifically, regardless of what is configured.

    The consent commands only make sense for it: a personal API key and a local
    Claude Code session have no notion of a third-party application asking for
    access to someone's account.
    """
    from llm.base import LLMProviderFactory

    settings = config.Settings.load()
    return LLMProviderFactory.create(
        "xformat", base_url=settings.xformat_base_url,
        endpoints=settings.xformat_endpoints,
    )


def cmd_ai_apps(args) -> int:
    """Which applications this xFormat account has let in."""
    from llm.base import LLMAuthError, LLMUnavailable

    provider = _xformat_provider()
    try:
        apps = provider.list_apps()
    except (LLMAuthError, LLMUnavailable) as exc:
        print(f"could not read connected apps: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if not apps:
        print("the backend reported no applications (an older deployment?)")
        return EXIT_OK
    for app in apps:
        mark = "connected" if app.get("connected") else "not connected"
        needs = "" if app.get("requiresGrant") else "  (no consent needed)"
        here = "  <- this app" if app.get("slug") == provider.client_app else ""
        print(f"  {app.get('slug'):<12} {mark:<14} {app.get('name', '')}{needs}{here}")
    return EXIT_OK


def cmd_ai_grant(args) -> int:
    """Allow this application to use the signed-in xFormat account."""
    from llm.base import LLMAuthError, LLMUnavailable

    provider = _xformat_provider()
    slug = args.app or provider.client_app
    try:
        result = provider.grant_app(slug)
    except (LLMAuthError, LLMUnavailable) as exc:
        print(f"could not grant access: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print(f"granted: {result.get('name') or slug} may now use this account.")
    return EXIT_OK


def cmd_ai_revoke(args) -> int:
    from llm.base import LLMAuthError, LLMUnavailable

    provider = _xformat_provider()
    slug = args.app or provider.client_app
    try:
        result = provider.revoke_app(slug)
    except (LLMAuthError, LLMUnavailable) as exc:
        print(f"could not revoke access: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if result.get("changed"):
        print(f"revoked: {slug} can no longer use this account.")
    else:
        print(f"nothing to revoke: {slug} had no active grant.")
    return EXIT_OK


def cmd_ai_rewrite(args) -> int:
    """Rewrite one passage, or a whole batch from stdin.

    The point is not the rewrite itself — the app does that from the results
    panel. It is that the billing path can be exercised end to end from a
    terminal, with one short passage, before anyone points a bulk run at it.
    """
    from llm.base import LLMAuthError, LLMUnavailable

    text = args.text
    if text is None:
        text = sys.stdin.read()
    passages = [p.strip() for p in text.split("\n\n") if p.strip()] if args.split else [text.strip()]
    if not any(passages):
        print("nothing to rewrite", file=sys.stderr)
        return EXIT_ERROR

    name, provider = _provider_for(args)
    if not args.quiet:
        print(f"# provider: {name}", file=sys.stderr)
    try:
        results = provider.rewrite_batch([(p, args.language) for p in passages])
    except (LLMAuthError, LLMUnavailable) as exc:
        print(f"rewrite failed: {exc}", file=sys.stderr)
        return EXIT_ERROR
    print("\n\n".join(results))
    return EXIT_OK
