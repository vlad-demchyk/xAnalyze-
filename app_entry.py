"""Frozen entry point: one executable, two roles, chosen by invocation name.

Only used by `packaging/XAnalyze.spec` — a `python main.py` / `python cli.py`
dev run never touches this file.

The alternative considered was PyInstaller's `MERGE()`, building a genuinely
separate `xanalyze-cli` executable alongside the GUI one. `MERGE()` gives
every executable *after* the first "onefile" semantics: it has to extract
its referenced dependencies from the first executable's directory into a
temp dir on every single launch. The CLI depends on the same PySide6/
QtWebEngine binaries as the GUI (`audit.driver`, used by `cli.py audit
--render`, imports `QtWebEngineCore` too), so every `xanalyze scan ...`
invocation would pay that extraction cost - fine for an app opened once,
wrong for a command meant to start quickly and often.

Instead: one binary, exposed under a second name via a symlink
(`cli_install.py`). The shell sets `sys.argv[0]` to the name actually typed,
not the name of the file the symlink resolves to - the same mechanism `git`
uses for `git-<subcommand>` and BusyBox uses for its applets - so the two
roles are told apart with no extra process, no extra copy, no extraction.
"""
from __future__ import annotations

import sys
from pathlib import Path

#: Must match `cli_install.CLI_NAME` - the name the symlink is installed
#: under. Not imported from there to keep this dispatch trivial to read
#: without following another module first.
_CLI_INVOCATION_NAME = "xanalyze"


def run() -> int:
    if Path(sys.argv[0]).name == _CLI_INVOCATION_NAME:
        import cli
        return cli.main(sys.argv[1:])
    import main as gui_main
    return gui_main.main()


if __name__ == "__main__":
    sys.exit(run())
