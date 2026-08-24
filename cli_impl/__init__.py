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

#: A run that stopped part-way and left a resumable state behind. Its own
#: code rather than `EXIT_ERROR`, because the two call for different
#: responses: an error means the invocation was wrong, this means the work is
#: on disk and one command continues it. A caller that does not know the code
#: still reads it as non-zero, which is correct.
EXIT_INCOMPLETE = 3
