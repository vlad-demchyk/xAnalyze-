"""What this run is about to do, and what it is about to leave undone.

A scan takes what it was given and reports what it found. Two of the most
useful things this tool can do are not defaults and were never mentioned:

* a **site** audited without `--repo` reports the page a problem is on, and
  cannot say which file to open - the repository behind it was never asked
  for;
* a **repository** scanned without `--devserver` is read as source, so every
  rule that needs a rendered page (contrast, focus order, layout at a
  breakpoint, the measurements) simply does not run - and the project may
  be one command away from serving itself.

Neither is a defect in the run. Both are the difference between a shallow
answer and a deep one, and the person or the agent that started the run is
the only one who can decide. So they are said before the work starts, in a
line an agent can match on and a person can read, and the run continues
either way: this is a notice, not a prompt, because a scan that blocks on a
question cannot be put in a pipeline.

`--no-hints` silences them. Nothing here changes what is measured.
"""
from __future__ import annotations

from pathlib import Path

#: Prefix every line carries, so an agent driving the CLI can find them
#: without parsing prose. One code per kind of missed depth.
PREFIX = "# [hint]"


def _repo_hint(target: str) -> str:
    return (f"{PREFIX} repo: no --repo given, so findings will name the page "
            f"and not the file behind it. Pass --repo PATH to point at the "
            f"checkout that serves {target} and every text finding that "
            f"matches a passage in it gets a file and a line.")


def _devserver_hint(root: Path, stack_name: str, deps: bool) -> str:
    how = (f"Pass --devserver to start it and audit the rendered site"
           if deps else
           f"Pass --devserver --yes to install its dependencies and start it")
    return (f"{PREFIX} devserver: this looks like a {stack_name} project, so "
            f"it can serve itself. Read as source, the rules that need a "
            f"rendered page do not run: contrast, focus order, layout at a "
            f"breakpoint, and every measurement. {how}, or point the scan at "
            f"a server you already have with --url http://localhost:PORT.")


def _browser_hint() -> str:
    return (f"{PREFIX} browser: --no-browser was given, so this is the static "
            f"reading only. axe, HTML_CodeSniffer, the state rules and the "
            f"measurements are all skipped, and a quiet result here is not "
            f"the same answer a rendered one would give.")


def _breakpoints_hint() -> str:
    return (f"{PREFIX} breakpoints: only the desktop width is audited. Pass "
            f"--breakpoints all for tablet, mobile and the 320 px reflow "
            f"check, which is where responsive failures live.")


#: The codes, which are also the translation-key stems for a surface that
#: does not print English. One per kind of depth a run is not reaching.
REPO = "repo"
DEVSERVER = "devserver"
BROWSER = "browser"
BREAKPOINTS = "breakpoints"


def missed(command: str, target: str, args, *, is_url: bool) -> list:
    """`[(code, fields)]` - the depth this run is not reaching, as data.

    Split out of `hints` when the window needed the same answers: the CLI
    prints an English line with a flag in it, and a window has neither a
    flag to name nor English to print. Two implementations of "what is this
    run leaving undone" is how two surfaces start disagreeing about it.
    """
    if getattr(args, "no_hints", False):
        return []
    found = []
    if is_url:
        if not getattr(args, "repo", None):
            found.append((REPO, {"target": target}))
    else:
        root = Path(target)
        if root.is_dir() and not getattr(args, "devserver", False) \
                and not getattr(args, "url", False):
            stack = _stack_of(root)
            if stack is not None:
                found.append((DEVSERVER, {"stack": stack.name,
                                          "deps": stack.deps_satisfied(root)}))
    if command in ("audit", "fullscan"):
        if getattr(args, "no_browser", False):
            found.append((BROWSER, {}))
        elif is_url and not getattr(args, "breakpoints", None):
            found.append((BREAKPOINTS, {}))
    return found


def hints(command: str, target: str, args, *, is_url: bool) -> list:
    """The lines to print before this run starts. Empty is a normal answer."""
    writers = {
        REPO: lambda fields: _repo_hint(fields["target"]),
        DEVSERVER: lambda fields: _devserver_hint(Path(target), fields["stack"],
                                                  fields["deps"]),
        BROWSER: lambda _fields: _browser_hint(),
        BREAKPOINTS: lambda _fields: _breakpoints_hint(),
    }
    return [writers[code](fields)
            for code, fields in missed(command, target, args, is_url=is_url)]


def _stack_of(root: Path):
    """The dev-server stack this project looks like, or None.

    Imported here rather than at module level: `devserver` pulls in the
    process machinery, and a hint must not make a scan slower to start.
    """
    try:
        import devserver

        return devserver.detect_stack(root)
    except Exception:  # noqa: BLE001 - a hint is never worth a failed run
        return None


def announce(command: str, target: str, args, *, is_url: bool, out) -> list:
    """Print the hints and hand them back, for a caller that also logs them."""
    lines = hints(command, target, args, is_url=is_url)
    for line in lines:
        print(line, file=out, flush=True)
    return lines
