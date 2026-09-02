"""Self-update from GitHub Releases.

Checks the configured GitHub repository for a newer release, downloads
the asset that matches the current platform, and replaces the running
binary in place.  Updates both CLI and GUI when applicable.

Designed to be called two ways:

* ``xanalyze update`` — explicit, blocks until done, prints progress.
* Any other command — a quick, non-blocking version check that prints a
  one-line hint if a newer release exists.  Cached so it fires at most
  once a day (see ``_CHECK_INTERVAL``).

When running from source (``python cli.py``) there is nothing to replace,
so the check still runs but the update command says so and exits.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import tarfile
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import config
from cli_impl import EXIT_ERROR, EXIT_OK

# ------------------------------------------------------------------ config

GITHUB_OWNER = "vlad-demchyk"
GITHUB_REPO = "xAnalyze-"
API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

#: How often the background check fires.  The timestamp lives in the
#: config directory so it survives restarts but not manual deletion.
_CHECK_INTERVAL = 86400  # 24 hours

#: Asset name patterns to look for, in preference order.  ``{arch}`` is
#: replaced at runtime with ``arm64`` or ``x64``.
_CLI_ASSET_PATTERNS = [
    "xanalyze-cli-macos-{arch}.tar.gz",
    "xanalyze-cli-{arch}.tar.gz",
    "xanalyze-cli.tar.gz",
]

_GUI_ASSET_PATTERNS = [
    "XAnalyze.app.zip",
    "XAnalyze-macos-{arch}.app.zip",
]


# ------------------------------------------------------------------ types

@dataclass
class ReleaseInfo:
    tag: str
    version: str
    body: str
    assets: list[dict]
    html_url: str


# -------------------------------------------------------------- versioning

def parse_version(v: str) -> tuple[int, ...]:
    """``'0.5.0'`` → ``(0, 5, 0)``.  Strips a leading ``v``."""
    v = v.lstrip("v")
    parts = []
    for p in v.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break
    return tuple(parts) or (0,)


def newer(remote: str, local: str) -> bool:
    """Is *remote* strictly newer than *local*?"""
    return parse_version(remote) > parse_version(local)


# ----------------------------------------------------------- GitHub fetch

def _gh_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_latest() -> ReleaseInfo:
    """GET the latest release from GitHub.  Raises on network / HTTP errors."""
    req = Request(API_URL, headers=_gh_headers())
    with urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    return ReleaseInfo(
        tag=data["tag_name"],
        version=data["tag_name"].lstrip("v"),
        body=data.get("body", ""),
        assets=data.get("assets", []),
        html_url=data.get("html_url", ""),
    )


# -------------------------------------------------------- asset selection

def _current_arch() -> str:
    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        return "arm64"
    return "x64"


def find_cli_asset(release: ReleaseInfo) -> dict | None:
    """Return the asset dict for the CLI binary that matches this machine."""
    arch = _current_arch()
    for pattern in _CLI_ASSET_PATTERNS:
        name = pattern.format(arch=arch)
        for asset in release.assets:
            if asset["name"] == name:
                return asset
    # Fallback: any asset whose name contains "cli"
    for asset in release.assets:
        if "cli" in asset["name"].lower():
            return asset
    return None


def find_gui_asset(release: ReleaseInfo) -> dict | None:
    """Return the asset dict for the GUI app that matches this machine."""
    arch = _current_arch()
    for pattern in _GUI_ASSET_PATTERNS:
        name = pattern.format(arch=arch)
        for asset in release.assets:
            if asset["name"] == name:
                return asset
    # Fallback: any asset whose name contains "app" and ends with .zip
    for asset in release.assets:
        if "app" in asset["name"].lower() and asset["name"].endswith(".zip"):
            return asset
    return None


# ------------------------------------------------------------- check cache

def _cache_path() -> Path:
    return config._config_dir() / "update_check.json"


def _last_check() -> float:
    try:
        data = json.loads(_cache_path().read_text())
        return float(data.get("at", 0))
    except (OSError, ValueError, TypeError):
        return 0.0


def _save_check(latest_version: str) -> None:
    try:
        _cache_path().write_text(json.dumps({
            "at": time.time(),
            "version": latest_version,
        }))
    except OSError:
        pass


def check_for_update(*, quiet: bool = False) -> str | None:
    """Quick check: return the new version string if one is available.

    Respects the daily cache unless *quiet* is False (explicit command).
    Returns ``None`` when no update is available or the check fails.
    """
    now = time.time()
    if quiet and (now - _last_check()) < _CHECK_INTERVAL:
        return None

    try:
        release = fetch_latest()
    except Exception:  # noqa: BLE001
        return None

    _save_check(release.version)

    if newer(release.version, config.APP_VERSION):
        return release.version
    return None


def print_update_hint(new_version: str) -> None:
    """One-line hint printed to stderr before the real command runs."""
    print(
        f"# XAnalyze {new_version} is available (you have {config.APP_VERSION}). "
        f"Run `xanalyze update` to upgrade.",
        file=sys.stderr,
    )


# ----------------------------------------------------------- binary locate

def _running_binary() -> Path | None:
    """The path to the frozen binary, or ``None`` when running from source."""
    if not getattr(sys, "frozen", False):
        return None
    return Path(sys.executable).resolve()


def _cli_binary_path() -> Path | None:
    """The ``xanalyze`` symlink target, if installed via ``cli_install``.

    When running frozen this is the same as ``_running_binary``.  When
    running from source we still check the symlink in case a frozen
    version is installed alongside the checkout.
    """
    frozen = _running_binary()
    if frozen:
        return frozen
    # Check if there is an installed CLI symlink
    from cli_install import installed_target
    target = installed_target()
    if target and target.exists():
        return target
    return None


def _gui_app_path() -> Path | None:
    """Path to the installed GUI app, or ``None``."""
    app = Path("/Applications/XAnalyze.app")
    if app.exists():
        return app
    return None


# --------------------------------------------------------- download+replace

def _download(url: str, dest: Path) -> None:
    """Stream *url* to *dest*, printing progress to stderr."""
    req = Request(url, headers=_gh_headers())
    with urlopen(req, timeout=30) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 1024 * 256  # 256 KB
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    mb = downloaded // (1024 * 1024)
                    total_mb = total // (1024 * 1024)
                    print(f"\r# downloading: {mb}/{total_mb} MB ({pct}%)",
                          end="", file=sys.stderr, flush=True)
        if total:
            print(file=sys.stderr)


def _extract_cli_binary(archive: Path) -> Path:
    """Extract the ``xanalyze`` binary from a tarball into a temp dir."""
    tmp = Path(tempfile.mkdtemp(prefix="xanalyze-update-"))
    with tarfile.open(archive) as tf:
        # Find the executable inside the archive
        members = tf.getmembers()
        # Look for a file named "xanalyze" (not a directory)
        target = None
        for m in members:
            if m.isfile() and Path(m.name).name == "xanalyze":
                target = m
                break
        if target is None:
            # Fallback: first regular file
            for m in members:
                if m.isfile():
                    target = m
                    break
        if target is None:
            raise RuntimeError("no executable found in the archive")
        tf.extract(target, tmp)
        extracted = tmp / target.name
        if not extracted.exists():
            # Handle nested paths
            extracted = tmp / Path(target.name).name
        if not extracted.exists():
            # Walk to find it
            for p in tmp.rglob("*"):
                if p.is_file() and p.name == "xanalyze":
                    extracted = p
                    break
        return extracted


def _extract_gui_app(archive: Path) -> Path:
    """Extract ``XAnalyze.app`` from a zip into a temp dir."""
    import zipfile

    tmp = Path(tempfile.mkdtemp(prefix="xanalyze-update-gui-"))
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(tmp)
    app = tmp / "XAnalyze.app"
    if not app.exists():
        # Walk to find it
        for p in tmp.rglob("XAnalyze.app"):
            if p.is_dir():
                return p
        raise RuntimeError("XAnalyze.app not found in the archive")
    return app


def _replace_binary(old: Path, new: Path) -> None:
    """Replace *old* with *new*, preserving permissions.

    On macOS the binary may be inside a signed .app bundle — we only
    replace the CLI binary (the symlink target), not the GUI executable.
    """
    # Copy permissions from old to new
    old_stat = old.stat()
    # Write the new binary
    backup = old.with_suffix(".bak")
    if backup.exists():
        backup.unlink()
    shutil.copy2(str(old), str(backup))
    try:
        shutil.copy2(str(new), str(old))
        # Restore original permissions (important for executables)
        old.chmod(old_stat.st_mode)
    except Exception:
        # Restore from backup on failure
        if backup.exists():
            shutil.copy2(str(backup), str(old))
        raise
    finally:
        # Clean up backup on success (leave it on failure)
        if old.exists() and backup.exists():
            try:
                backup.unlink()
            except OSError:
                pass


def do_update() -> int:
    """Full update flow: check → download → replace.

    Updates CLI if a frozen binary or symlink is found.
    Updates GUI if ``/Applications/XAnalyze.app`` exists.

    Returns `EXIT_OK` on success and `EXIT_ERROR` when the release could not
    be reached or read. Not 1: everywhere else in this CLI 1 means "something
    was found", and an update that could not reach GitHub has found nothing.
    See `cli_impl` for the whole list.
    """
    print(f"# XAnalyze updater — current version: {config.APP_VERSION}",
          file=sys.stderr)

    # 1. Check for update
    try:
        release = fetch_latest()
    except HTTPError as exc:
        print(f"error: GitHub API returned {exc.code}", file=sys.stderr)
        return EXIT_ERROR
    except URLError as exc:
        print(f"error: could not reach GitHub: {exc.reason}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    print(f"# latest release: {release.tag}", file=sys.stderr)

    if not newer(release.version, config.APP_VERSION):
        print("Already up to date.")
        return EXIT_OK

    updated = 0

    # 2. Update CLI
    cli_binary = _cli_binary_path()
    cli_asset = find_cli_asset(release)
    if cli_asset and cli_binary:
        print(f"# CLI asset: {cli_asset['name']} "
              f"({cli_asset['size'] // (1024*1024)} MB)", file=sys.stderr)
        print(f"# CLI target: {cli_binary}", file=sys.stderr)

        tmp_dir = Path(tempfile.mkdtemp(prefix="xanalyze-update-"))
        archive_path = tmp_dir / cli_asset["name"]
        try:
            _download(cli_asset["browser_download_url"], archive_path)
            extracted = _extract_cli_binary(archive_path)
            _replace_binary(cli_binary, extracted)
            updated += 1
            print(f"# CLI updated: {cli_binary}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"# CLI update failed: {exc}", file=sys.stderr)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    elif cli_asset is None:
        print("# no CLI asset found in release", file=sys.stderr)

    # 3. Update GUI
    gui_app = _gui_app_path()
    gui_asset = find_gui_asset(release)
    if gui_asset and gui_app:
        print(f"# GUI asset: {gui_asset['name']} "
              f"({gui_asset['size'] // (1024*1024)} MB)", file=sys.stderr)
        print(f"# GUI target: {gui_app}", file=sys.stderr)

        tmp_dir = Path(tempfile.mkdtemp(prefix="xanalyze-update-gui-"))
        archive_path = tmp_dir / gui_asset["name"]
        try:
            _download(gui_asset["browser_download_url"], archive_path)
            extracted = _extract_gui_app(archive_path)
            # Replace: remove old .app, move new one in
            if gui_app.exists():
                shutil.rmtree(gui_app)
            shutil.move(str(extracted), str(gui_app))
            updated += 1
            print(f"# GUI updated: {gui_app}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"# GUI update failed: {exc}", file=sys.stderr)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    elif gui_asset is None:
        print("# no GUI asset found in release", file=sys.stderr)

    if updated == 0:
        print("Nothing to update. Download manually from:\n"
              f"  {release.html_url}", file=sys.stderr)
        return EXIT_ERROR

    print(f"\nUpdated XAnalyze {config.APP_VERSION} → {release.version}")
    if release.body:
        print(f"\nRelease notes:\n{release.body[:500]}")
    return EXIT_OK
