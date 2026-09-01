"""Where a signed-in browser session for a site is kept, and who may read it.

Half of what is worth auditing is behind a login, and the only way in that
does not involve this tool handling anybody's credentials is the obvious one:
a person signs in themselves, in a real browser window, and the run reuses
what that browser was given. QtWebEngine stores that for us - a named,
persistent profile with `ForcePersistentCookies` is the same mechanism a
browser profile is - so this module is only about *where* it lives, *whose*
it is, and how to get rid of it.

Three rules, and none of them is optional:

* **Nothing here ever reaches a report, a log or a run folder.** What a
  document may say is "this run was signed in as a session for host X". The
  values are the session; printing them is handing the session over.
* **One profile per host.** A session for `staging.example.com` has no
  business travelling to `example.com`, and a single shared profile would
  mean the last site signed into decides who the next scan is.
* **It can be forgotten, and the person can see that it exists.** A tool
  that quietly keeps a way into somebody's account is not a tool anybody
  should install. `forget()` is the whole answer, and `known_hosts()` is how
  a surface shows what there is to forget.

**No credentials are stored, ever.** This tool never sees a password: the
sign-in happens in the browser window, against the site's own form, and what
survives is what the site chose to give that browser.
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

import config

#: Where the profiles live. Under the app's own config directory rather than
#: anywhere near a repository: a checkout gets committed, and this must not
#: be a thing that can be committed by accident.
_DIRNAME = "sessions"

#: What a host may look like as a directory name. A hostname is already
#: restricted, but it arrives from a URL a person typed and this builds a
#: filesystem path out of it - so it is rewritten rather than trusted.
_SAFE = re.compile(r"[^a-z0-9._-]+")


def host_of(url: str) -> str:
    """The host a session belongs to, or "" if there is not one.

    The port is part of it: `localhost:3000` and `localhost:8080` are two
    different applications on nearly every developer's machine.
    """
    text = (url or "").strip()
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    parsed = urlparse(text)
    host = (parsed.netloc or "").lower()
    return host


def _slug(host: str) -> str:
    return _SAFE.sub("-", (host or "").lower()).strip("-")


def sessions_root() -> Path:
    """The directory holding every profile, created 0700 on first use."""
    root = Path(config.config_file()).parent / _DIRNAME
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        # A filesystem that does not do POSIX modes (a mounted share) is not
        # a reason to refuse to work; it is a reason not to pretend the
        # permission was set.
        pass
    return root


def profile_dir(host: str, create: bool = False) -> Path:
    """Where this host's browser profile lives."""
    path = sessions_root() / _slug(host)
    if create:
        path.mkdir(parents=True, exist_ok=True)
        try:
            path.chmod(0o700)
        except OSError:
            pass
    return path


def has_session(host: str) -> bool:
    """Is there a stored profile for this host?

    A directory that exists but holds nothing is not a session: the profile
    is created when the sign-in window opens, and a person who closed that
    window without signing in must not be told they are signed in.
    """
    path = profile_dir(host)
    if not path.is_dir():
        return False
    return any(path.iterdir())


def known_hosts() -> list:
    """Every host with a stored session, so a surface can list them."""
    root = sessions_root()
    if not root.is_dir():
        return []
    return sorted(entry.name for entry in root.iterdir()
                  if entry.is_dir() and any(entry.iterdir()))


def forget(host: str) -> bool:
    """Delete this host's profile. `True` if there was one to delete."""
    path = profile_dir(host)
    if not path.is_dir():
        return False
    shutil.rmtree(path, ignore_errors=True)
    return not path.exists()


def forget_all() -> int:
    """Delete every stored session, and say how many there were."""
    hosts = known_hosts()
    for host in hosts:
        forget(host)
    return len(hosts)


#: The cookies a fetch needs, written beside the browser profile.
#:
#: Two clients read one site: QtWebEngine renders the pages, and `requests`
#: fetches them for the crawl. They share no storage, so a sign-in performed
#: in the browser leaves the fetcher looking at the login form - the two
#: halves of one run disagreeing about who is asking. This file is the
#: bridge, and it is the one genuinely sensitive thing this tool writes:
#: 0600, beside the profile, never logged, never in a report, and deleted by
#: `forget()` along with everything else for that host.
_COOKIES = "cookies.json"


def cookies_path(host: str) -> Path:
    return profile_dir(host) / _COOKIES


def save_cookies(host: str, cookies: dict) -> None:
    """Write the fetcher's copy of the session, readable only by its owner."""
    import json

    path = profile_dir(host, create=True) / _COOKIES
    # Created with the mode set, not chmod'ed after: between the write and
    # the chmod the file is world-readable, and the window in between is
    # exactly when another process on a shared machine would read it.
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(dict(cookies or {}), handle)


def load_cookies(host: str) -> dict:
    """The fetcher's copy, or `{}`. Never raises: a session that cannot be
    read is a run without one, not a failed run."""
    import json

    path = cookies_path(host)
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:  # noqa: BLE001 - see the docstring
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def apply_to(config, target: str) -> tuple:
    """Sign a crawl config in for `target`, and say what happened.

    Returns `(host, count)`: the host to render as and how many values were
    given to the fetcher, or `("", 0)` when there is no session. Both halves
    or neither - `requests` and QtWebEngine share no storage, and handing the
    session to one of them produces a run where the browser sees the account
    and the fetch sees the login form.

    Quiet on purpose: every surface says this differently - the CLI prints a
    line, the window shows a status - and a shared helper that printed would
    make one of them say it twice.
    """
    host = host_of(target)
    if not host or not has_session(host):
        return "", 0
    cookies = load_cookies(host)
    if cookies:
        config.cookies = dict(cookies)
    return host, len(cookies)


def describe(host: str) -> str:
    """One line about a session, with nothing secret in it.

    This is what a report or a run header may carry: the fact, the host, and
    nothing else. Deliberately not "a session cookie for X" - what is stored
    is a browser profile, and naming cookies invites somebody to print one.
    """
    return f"signed-in session for {host}" if has_session(host) else ""


#: The environment variable a test uses to keep every profile out of the
#: developer's own config directory. `config.config_file()` already resolves
#: at call time (see its docstring), so setting `XDG_CONFIG_HOME` is enough -
#: this name exists so the reason is written down somewhere.
ISOLATION_ENV = "XDG_CONFIG_HOME"


def env_isolated(path) -> None:
    """Point this module at `path` for the rest of the process."""
    os.environ[ISOLATION_ENV] = str(path)
