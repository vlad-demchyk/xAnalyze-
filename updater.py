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

import base64
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import tarfile
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

import config
from cli_impl import EXIT_ERROR, EXIT_OK
from update_trust import UPDATE_SIGNING_PUBLIC_KEYS

# ------------------------------------------------------------------ config

GITHUB_OWNER = "vlad-demchyk"
GITHUB_REPO = "xAnalyze-"
API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
MANIFEST_ASSET = "xanalyze-update-manifest.json"
SIGNATURE_ASSET = f"{MANIFEST_ASSET}.sig"

# Exact hosts used by the GitHub API and release-asset redirects. A suffix
# check would accept attacker-controlled names such as github.com.example.
_TRUSTED_UPDATE_HOSTS = frozenset({
    "api.github.com",
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
})
_MAX_MANIFEST_BYTES = 1024 * 1024
_MAX_SIGNATURE_BYTES = 4096
_MAX_ASSET_BYTES = 2 * 1024 * 1024 * 1024
_SHA256 = re.compile(r"[0-9a-f]{64}")

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


@dataclass(frozen=True)
class AssetIntegrity:
    name: str
    size: int
    sha256: str


@dataclass(frozen=True)
class UpdateManifest:
    release: str
    assets: dict[str, AssetIntegrity]
    signature_verified: bool


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
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2026-03-10",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _require_trusted_url(url: str) -> str:
    """Accept only the exact HTTPS origins used for GitHub releases."""
    try:
        parsed = urlparse(url)
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise RuntimeError("invalid update URL") from exc
    if (parsed.scheme.lower() != "https"
            or parsed.username is not None or parsed.password is not None
            or (parsed.hostname or "").lower() not in _TRUSTED_UPDATE_HOSTS
            or port not in {None, 443}):
        raise RuntimeError("untrusted update URL")
    return url


def _host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


class _TrustedRedirectHandler(HTTPRedirectHandler):
    """Reject a redirect before urllib connects to its target.

    And drop the credential when the host changes. `urllib` copies every
    header except `content-length` and `content-type` onto the redirected
    request, so `Authorization: Bearer $GITHUB_TOKEN` followed the release
    asset from `api.github.com` to the download host. The asset URL is
    already signed and needs no token; sending one hands a personal access
    token to a host that never asked for it.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _require_trusted_url(newurl)
        request = super().redirect_request(req, fp, code, msg, headers, newurl)
        if request is not None and _host_of(newurl) != _host_of(req.full_url):
            request.headers = {name: value
                               for name, value in request.headers.items()
                               if name.lower() != "authorization"}
        return request


def _open_trusted(url: str, *, timeout: int):
    _require_trusted_url(url)
    request = Request(url, headers=_gh_headers())
    response = build_opener(_TrustedRedirectHandler()).open(
        request, timeout=timeout)
    try:
        _require_trusted_url(response.geturl())
    except Exception:
        response.close()
        raise
    return response


def fetch_latest() -> ReleaseInfo:
    """GET the latest release from GitHub.  Raises on network / HTTP errors."""
    with _open_trusted(API_URL, timeout=15) as resp:
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


def _asset_named(release: ReleaseInfo, name: str) -> dict | None:
    for asset in release.assets:
        if asset.get("name") == name:
            return asset
    return None


def _read_remote_asset(asset: dict, *, limit: int) -> bytes:
    """Read a small release asset under a hard size and origin limit."""
    url = asset.get("browser_download_url", "")
    with _open_trusted(url, timeout=30) as response:
        raw_length = response.headers.get("Content-Length")
        try:
            declared = int(raw_length) if raw_length is not None else None
        except (TypeError, ValueError) as exc:
            raise RuntimeError("invalid update Content-Length") from exc
        if declared is not None and (declared < 0 or declared > limit):
            raise RuntimeError("update metadata is too large")
        payload = response.read(limit + 1)
    if len(payload) > limit:
        raise RuntimeError("update metadata is too large")
    if declared is not None and len(payload) != declared:
        raise RuntimeError("incomplete update metadata")
    return payload


def _verify_manifest_signature(payload: bytes, encoded_signature: bytes) -> bool:
    """Verify Ed25519 when configured, otherwise select the visible fallback."""
    public_keys = tuple(key.strip() for key in UPDATE_SIGNING_PUBLIC_KEYS
                        if key.strip())
    if not public_keys:
        return False
    if not encoded_signature.strip():
        raise RuntimeError("update manifest signature is missing")

    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        signature = base64.b64decode(encoded_signature.strip(), validate=True)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("update manifest signature is invalid") from exc
    last_error = None
    for public_text in public_keys:
        try:
            public_bytes = base64.b64decode(public_text, validate=True)
            public_key = Ed25519PublicKey.from_public_bytes(public_bytes)
            public_key.verify(signature, payload)
            return True
        except (InvalidSignature, TypeError, ValueError) as exc:
            last_error = exc
    raise RuntimeError("update manifest signature is invalid") from last_error


def _parse_update_manifest(payload: bytes, release: ReleaseInfo,
                           *, signature_verified: bool) -> UpdateManifest:
    try:
        data = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("update manifest is not valid JSON") from exc
    if (not isinstance(data, dict) or data.get("version") != 1
            or data.get("release") != release.tag
            or not isinstance(data.get("assets"), dict)):
        raise RuntimeError("update manifest does not match this release")

    assets: dict[str, AssetIntegrity] = {}
    for name, record in data["assets"].items():
        if (not isinstance(name, str) or Path(name).name != name
                or not isinstance(record, dict)):
            raise RuntimeError("update manifest contains an invalid asset")
        size = record.get("size")
        digest = record.get("sha256")
        if (not isinstance(size, int) or isinstance(size, bool)
                or size <= 0 or size > _MAX_ASSET_BYTES
                or not isinstance(digest, str)
                or _SHA256.fullmatch(digest.lower()) is None):
            raise RuntimeError("update manifest contains invalid integrity data")
        assets[name] = AssetIntegrity(name, size, digest.lower())
    if not assets:
        raise RuntimeError("update manifest contains no assets")
    return UpdateManifest(release.tag, assets, signature_verified)


def fetch_update_manifest(release: ReleaseInfo) -> UpdateManifest:
    """Fetch, authenticate and parse the integrity manifest for a release."""
    manifest_asset = _asset_named(release, MANIFEST_ASSET)
    if manifest_asset is None:
        raise RuntimeError("release has no update manifest")
    payload = _read_remote_asset(manifest_asset, limit=_MAX_MANIFEST_BYTES)

    signature_asset = _asset_named(release, SIGNATURE_ASSET)
    signature = (b"" if signature_asset is None else
                 _read_remote_asset(signature_asset,
                                    limit=_MAX_SIGNATURE_BYTES))
    verified = _verify_manifest_signature(payload, signature)
    return _parse_update_manifest(
        payload, release, signature_verified=verified)


def _asset_integrity(asset: dict, manifest: UpdateManifest) -> AssetIntegrity:
    name = asset.get("name")
    integrity = manifest.assets.get(name)
    if integrity is None:
        raise RuntimeError(f"asset is absent from update manifest: {name}")
    size = asset.get("size")
    if not isinstance(size, int) or isinstance(size, bool) or size != integrity.size:
        raise RuntimeError(f"asset size disagrees with update manifest: {name}")
    api_digest = asset.get("digest")
    if (api_digest is not None
            and api_digest != f"sha256:{integrity.sha256}"):
        raise RuntimeError(f"asset digest disagrees with update manifest: {name}")
    _require_trusted_url(asset.get("browser_download_url", ""))
    return integrity


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

def _download(url: str, dest: Path, integrity: AssetIntegrity) -> None:
    """Stream one trusted asset and prove its size and SHA-256."""
    with _open_trusted(url, timeout=30) as resp:
        raw_total = resp.headers.get("Content-Length")
        try:
            total = int(raw_total) if raw_total is not None else 0
        except (TypeError, ValueError) as exc:
            raise RuntimeError("invalid asset Content-Length") from exc
        if total and total != integrity.size:
            raise RuntimeError("asset Content-Length disagrees with manifest")
        downloaded = 0
        digest = hashlib.sha256()
        chunk_size = 1024 * 256  # 256 KB
        with open(dest, "wb") as f:
            while True:
                remaining = integrity.size - downloaded
                chunk = resp.read(min(chunk_size, remaining + 1))
                if not chunk:
                    break
                downloaded += len(chunk)
                if downloaded > integrity.size:
                    raise RuntimeError("downloaded asset exceeds manifest size")
                digest.update(chunk)
                f.write(chunk)
                if total:
                    pct = downloaded * 100 // total
                    mb = downloaded // (1024 * 1024)
                    total_mb = total // (1024 * 1024)
                    print(f"\r# downloading: {mb}/{total_mb} MB ({pct}%)",
                          end="", file=sys.stderr, flush=True)
        if total:
            print(file=sys.stderr)
    if downloaded != integrity.size:
        raise RuntimeError("downloaded asset size does not match manifest")
    if digest.hexdigest() != integrity.sha256:
        raise RuntimeError("downloaded asset checksum does not match manifest")


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

    try:
        manifest = fetch_update_manifest(release)
    except Exception as exc:  # noqa: BLE001
        print(f"error: release integrity check failed: {exc}", file=sys.stderr)
        return EXIT_ERROR
    if not manifest.signature_verified:
        print("# warning: update signing key is not configured; "
              "using HTTPS, size and SHA-256 fallback", file=sys.stderr)

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
            integrity = _asset_integrity(cli_asset, manifest)
            _download(cli_asset["browser_download_url"], archive_path,
                      integrity)
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
            integrity = _asset_integrity(gui_asset, manifest)
            _download(gui_asset["browser_download_url"], archive_path,
                      integrity)
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
