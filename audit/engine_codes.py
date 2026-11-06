"""Which codes of the bundled engines a person has already weighed (T-1963).

axe-core and HTML_CodeSniffer decide their own rules, and an update brings
new ones with them. A new code arrives with the engine's own severity, which
nobody here has checked against a real site - and every rule written for
this audit so far produced false positives on its first real crawl. So a code
the recorded engine version did not have is reported as a note (minor,
advisory) until somebody looks at it, and the run's log says which codes
those were.

`audit/vendor/engine_codes.json` records, per engine, the version the
weights were checked against and the codes it had. While the vendored file
is still that version, every code it emits is known by definition - the
list only matters after an update. After reviewing one, a person runs
`python -m audit.engine_codes --write` to record the new version.

The HTML_CodeSniffer list is the message codes read from the source, which
misses the few it assembles at run time; such a code is treated as new after
an update, which errs on the side of a note rather than a false alarm.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

VENDOR = Path(__file__).resolve().parent / "vendor"
TABLE = VENDOR / "engine_codes.json"

AXE = "axe"
HTMLCS = "htmlcs"

_FILES = {AXE: "axe.min.js", HTMLCS: "HTMLCS.js"}
_VERSION_RE = {
    AXE: re.compile(r"axe v(\d+\.\d+\.\d+)"),
    HTMLCS: re.compile(r"html_codesniffer - v(\d+\.\d+\.\d+)"),
}

_reported: set = set()


def _source(engine: str) -> str:
    return (VENDOR / _FILES[engine]).read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def vendored_version(engine: str) -> str:
    """The version in the bundled file's banner, or "" when unreadable."""
    try:
        head = _source(engine)[:400]
    except OSError:
        return ""
    found = _VERSION_RE[engine].search(head)
    return found.group(1) if found else ""


def codes_in_source(engine: str) -> list:
    """The codes the bundled engine can emit, read from its source."""
    text = _source(engine)
    if engine == AXE:
        found = re.findall(r'\{id:"([a-z0-9-]+)",(?:impact:"\w+",)?selector:', text)
    else:
        found = re.findall(
            r'addMessage\(HTMLCS\.(?:ERROR|WARNING),[^;]*?,\s*"([A-Za-z0-9_.]+)"\s*[,)]',
            text)
    return sorted(set(found))


@lru_cache(maxsize=1)
def recorded() -> dict:
    try:
        return json.loads(TABLE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def is_known(engine: str, code: str) -> bool:
    """Has a person weighed this code, for the engine version bundled now?"""
    entry = recorded().get(engine) or {}
    if not entry:
        return True  # no table at all: nothing to compare with, change nothing
    if vendored_version(engine) == entry.get("version"):
        return True
    known = entry.get("codes") or []
    if engine == AXE:
        return code in known
    # An HTML_CodeSniffer code is the sniff's path plus the message code:
    # `WCAG2AA.Principle1.Guideline1_1.1_1_1.H30.2` ends in `H30.2`.
    return any(code == item or code.endswith("." + item) for item in known)


def note_unverified(engine: str, code: str) -> None:
    """Log a new code once per run, so an update's arrivals are visible."""
    key = (engine, code)
    if key in _reported:
        return
    _reported.add(key)
    try:
        import applog

        applog.warning("audit.engine_code_unverified", engine=engine, code=code,
                       version=vendored_version(engine),
                       recorded=(recorded().get(engine) or {}).get("version", ""))
    except Exception:  # noqa: BLE001 - logging never breaks an audit
        pass


def table() -> dict:
    return {engine: {"version": vendored_version(engine),
                     "codes": codes_in_source(engine)}
            for engine in (AXE, HTMLCS)}


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="engine_codes",
        description="Compare or record the bundled engines' known codes.")
    parser.add_argument("--write", action="store_true",
                        help="record the bundled versions as reviewed")
    args = parser.parse_args(argv)
    current = table()
    if args.write:
        TABLE.write_text(json.dumps(current, indent=1) + "\n", encoding="utf-8")
        print(f"recorded {TABLE}")
        return 0
    old = recorded()
    for engine, entry in current.items():
        before = old.get(engine) or {}
        added = sorted(set(entry["codes"]) - set(before.get("codes") or []))
        print(f"{engine}: bundled {entry['version'] or '?'}, "
              f"recorded {before.get('version') or 'none'}, "
              f"{len(added)} code(s) not recorded")
        for code in added[:50]:
            print(f"  + {code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
