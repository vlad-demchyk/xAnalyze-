"""Local app configuration: API keys and persisted user settings.

Settings are stored in a small JSON file in the user's config directory so
they survive restarts. Secrets (API keys) are read from environment
variables first and only fall back to the file, so you can keep them out
of the file entirely if you prefer (e.g. export ANTHROPIC_API_KEY=...).
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_NAME = "ai-content-scanner"


def _config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


CONFIG_FILE = _config_dir() / "settings.json"


@dataclass
class Settings:
    ui_language: str = "uk"                 # 'uk' | 'it' | 'en'
    default_detector: str = "offline"        # matches DetectorFactory registry names
    crawl_depth: int = 1
    max_pages: int = 30
    # Anthropic's current default model. Older ids stay valid — this is only
    # what a fresh install starts on; see `_MIGRATIONS` for how a stored
    # value from a previous version is handled.
    claude_model: str = "claude-opus-5"
    # 'auto' follows the OS appearance; 'light' / 'dark' pin it. The palette
    # itself comes from xFormat's design tokens either way (ui/tokens.py).
    theme: str = "auto"
    # Repository mode: what counts as text worth reading. 'content' is the
    # copy that ships to a user; 'technical' is comments and docstrings;
    # 'both' is either. See repo_scanner's SCOPE_* constants.
    repo_scope: str = "content"

    # The non-keyboard-character pass runs alongside whichever detector is
    # selected: it's offline, exact, and its fix costs nothing, so there's
    # no reason to make the user choose between it and a content detector.
    unicode_check_enabled: bool = True
    # Which unicode_rules categories to report. Defaults to all of them;
    # drop "typography" to keep proper em dashes and curly quotes.
    unicode_categories: list = field(
        default_factory=lambda: ["invisible", "space", "homoglyph", "styled", "typography"]
    )

    # Which backend pays for rewrite calls: "anthropic" (your own API key),
    # "xformat" (app.xformat.net subscription) or "claude-code" (the `claude`
    # CLI already signed in on this machine). See llm/.
    llm_provider: str = "anthropic"
    # When this tool runs *inside* Claude Code — a hook, a CI step, an agent
    # calling cli.py — that session is already authenticated and already
    # being paid for. Routing those calls to a subscription instead would
    # bill a second account for the same work, and would fail outright on a
    # machine that has Claude Code but no xFormat login. So inside Claude
    # Code the CLI uses Claude Code, unless `--provider` says otherwise.
    # This only affects the CLI: the desktop app is not launched by an agent,
    # and there the user's explicit choice in Settings is the answer.
    prefer_claude_code_in_cli: bool = True
    # Model for that automatic route. Empty means "whatever the CLI is
    # configured to use", which is what someone driving this from a Claude
    # Code session normally expects; set e.g. "sonnet" to pin it cheaper.
    claude_code_model: str = ""
    # The API host, not the app host: app.xformat.net serves the web client.
    # Mirrors BUILTIN_API_URL in the frontend's saasAuth/backendUrl.ts.
    xformat_base_url: str = "https://api.xformat.net"
    # Overrides for XFormatEndpoints — only the keys you want to change.
    # Lets the API contract be corrected from Settings without a code edit.
    xformat_endpoints: dict = field(default_factory=dict)

    # Findings the user has already decided about — phrases that are house
    # style, checks they don't want, paths and page regions to skip, and
    # individual dismissed findings. See suppression.py; a scanned project
    # can add its own list in a committed `.xanalyze-ignore` file.
    ignore: dict = field(default_factory=dict)

    # Legacy seam for a fuller backend integration (see backend_connector.py).
    backend_url: str = ""
    backend_enabled: bool = False

    @classmethod
    def load(cls) -> "Settings":
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                merged = {**asdict(cls()), **data}
                # Drop keys from older/newer versions so an out-of-date config
                # file can't stop the app from starting.
                known = set(cls.__dataclass_fields__)
                return _migrate(cls(**{k: v for k, v in merged.items() if k in known}))
            except (json.JSONDecodeError, TypeError):
                pass
        return cls()

    def save(self) -> None:
        CONFIG_FILE.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")


# Values that were *this application's* defaults in an earlier version, and
# what they become. Applied on load so an existing settings.json doesn't
# leave someone pinned to a retired model or a detector that no longer
# exists as a separate entry.
#
# Only these exact strings are rewritten. A value the user chose themselves
# is left alone even when it is old — picking a specific model or a specific
# base URL is a decision, and silently overruling it would be worse than
# leaving it slightly stale.
_MIGRATIONS = {
    "default_detector": {
        # The two offline passes stopped being separate detectors; see
        # detectors/offline.py. The factory also aliases both names, so this
        # is belt and braces — it keeps the stored value truthful rather
        # than relying on the alias forever.
        "heuristic": "offline",
        "unicode-anomalies": "offline",
    },
    "claude_model": {
        "claude-sonnet-4-5": "claude-opus-5",
    },
    "xformat_base_url": {
        # Was a guess at the API host before the backend was wired up; the
        # app domain serves the web client and answers 404 for /api/auth/*.
        "https://app.xformat.net": "https://api.xformat.net",
    },
}


def _migrate(settings: "Settings") -> "Settings":
    for field_name, replacements in _MIGRATIONS.items():
        current = getattr(settings, field_name, None)
        if current in replacements:
            setattr(settings, field_name, replacements[current])
    return settings


def get_anthropic_api_key() -> str | None:
    """Env var first, then the OS keychain (see llm/credentials.py).

    The key is never written to the plain settings.json — if the user types
    one into Settings it goes to the keychain like any other secret.
    """
    env = os.environ.get("ANTHROPIC_API_KEY")
    if env:
        return env
    try:
        from llm import credentials
        return credentials.load_secret("anthropic_api_key")
    except Exception:  # noqa: BLE001 - never let credential storage break startup
        return None


def set_anthropic_api_key(value: str) -> None:
    from llm import credentials
    if value:
        credentials.save_secret("anthropic_api_key", value)
    else:
        credentials.delete_secret("anthropic_api_key")
