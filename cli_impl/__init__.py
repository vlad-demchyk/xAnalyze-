"""Implementation modules behind the `cli.py` facade.

`cli.py` stays a single runnable file (`python cli.py ...`) and keeps the
parser and command dispatch; everything it delegates to lives here, grouped
by concern rather than by command.
"""

#: Exit codes shared by every command module. `cli.py` re-exports them so
#: `import cli` keeps working.
EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2
