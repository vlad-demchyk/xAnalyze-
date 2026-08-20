"""Credential storage for account-based providers.

Order of preference:
1. `keyring` — the OS keychain (macOS Keychain, Windows Credential Manager,
   GNOME Keyring / KWallet). Encrypted at rest, managed by the OS.
2. A file under the app's config dir with 0600 permissions, used only if
   keyring isn't installed or has no usable backend (common on bare Linux
   servers). This is clearly less safe and the settings dialog says so.

What gets stored is the session/refresh token, never the password —
the password is used once to sign in and then dropped.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import config

SERVICE_NAME = "xanalyze"
# Pre-rename service/dir name. `load_secret` falls back to this so a token
# saved before the rename doesn't become invisible; see its docstring.
OLD_SERVICE_NAME = "ai-content-scanner"


def _fallback_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    d = Path(base) / SERVICE_NAME
    d.mkdir(parents=True, exist_ok=True)
    config.migrate_legacy_file(Path(base) / OLD_SERVICE_NAME, d, "credentials.json")
    return d / "credentials.json"


def _keyring():
    """Return the keyring module only if it has a backend that actually
    works.

    `keyring` installs cleanly on headless Linux but resolves to a
    `fail.Keyring` stub that raises NoKeyringError on first use, so the
    presence of the package proves nothing. The stub lives in
    `keyring.backends.fail` but its class is plain `Keyring`, so it has to
    be identified by module, not class name.
    """
    try:
        import keyring
    except ImportError:
        return None
    try:
        kr = keyring.get_keyring()
    except Exception:  # noqa: BLE001
        return None
    if kr is None:
        return None
    module = type(kr).__module__ or ""
    if module.endswith("backends.fail") or type(kr).__name__ == "FailKeyring":
        return None
    return keyring


def using_keyring() -> bool:
    return _keyring() is not None


def _file_save(account: str, value: str) -> None:
    path = _fallback_path()
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    data[account] = value
    path.write_text(json.dumps(data), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _file_load(account: str) -> str | None:
    path = _fallback_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8")).get(account)
    except (json.JSONDecodeError, OSError):
        return None


def save_secret(account: str, value: str) -> None:
    kr = _keyring()
    if kr is not None:
        try:
            kr.set_password(SERVICE_NAME, account, value)
            return
        except Exception:  # noqa: BLE001 - locked/broken keychain at runtime
            pass  # fall through to the file so sign-in still works
    _file_save(account, value)


def load_secret(account: str) -> str | None:
    kr = _keyring()
    if kr is not None:
        try:
            value = kr.get_password(SERVICE_NAME, account)
            if value is not None:
                return value
        except Exception:  # noqa: BLE001 - a locked keychain shouldn't crash the app
            pass
        # Nothing under the new service name. Before concluding there's no
        # secret at all, check whether it's sitting under the pre-rename
        # service name — otherwise renaming SERVICE_NAME would silently
        # strand every previously-saved token (xFormat access/refresh,
        # an Anthropic key) in the keychain: still there, but unreachable
        # since nothing looks it up under the old name any more.
        #
        # Migrated eagerly rather than left in place: once copied under the
        # new name it's a duplicate the user never asked to keep, and an
        # orphaned "ai-content-scanner" keychain entry is just confusing
        # clutter with no code left pointing at it. Only removed after the
        # copy under the new name actually succeeds, so a failure here never
        # loses the only copy of the secret.
        try:
            old_value = kr.get_password(OLD_SERVICE_NAME, account)
        except Exception:  # noqa: BLE001
            old_value = None
        if old_value is not None:
            try:
                kr.set_password(SERVICE_NAME, account, old_value)
            except Exception:  # noqa: BLE001
                pass
            else:
                try:
                    kr.delete_password(OLD_SERVICE_NAME, account)
                except Exception:  # noqa: BLE001 - stale copy left behind is harmless
                    pass
            return old_value
    # Also checked when a keyring exists: a secret may have been written to
    # the file earlier, before a backend became available.
    return _file_load(account)


def delete_secret(account: str) -> None:
    kr = _keyring()
    if kr is not None:
        try:
            kr.delete_password(SERVICE_NAME, account)
        except Exception:  # noqa: BLE001 - already absent is fine
            pass
    # Always clear the file copy too, so signing out really removes it.
    path = _fallback_path()
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop(account, None)
        path.write_text(json.dumps(data), encoding="utf-8")
    except (json.JSONDecodeError, OSError):
        pass
