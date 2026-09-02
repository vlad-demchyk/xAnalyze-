"""Running a CLI command from inside the terminal interface.

Two problems this solves, both of which made the TUI look broken.

**The output went nowhere useful.** Every command writes its result to
stdout and its progress to stderr, and the TUI owns the terminal - so the
result either vanished or drew over the interface. Every screen ended with
"See results in terminal", which is not a result, it is an apology. Here
stdout and stderr are captured: the JSON becomes a structured result the TUI
can show, and the `#` progress lines drive a live status line.

**The interface froze.** A scan ran on the UI thread, so nothing repainted
and no key was answered until it finished - minutes, for a site crawl. Here
every run happens on a worker thread.

The worker never touches the interface. It appends to a lock-guarded list
and sets an event; the screen drains both on a timer. The obvious design -
have the capture call `App.call_from_thread` as each line arrives - is a
deadlock waiting to happen, and was one: the capture replaces `sys.stderr`
process-wide, so anything the *main* thread writes there re-enters the
callback, and `call_from_thread` refuses to be called from the main thread.
Polling has no such edge, and a status line does not need sub-frame latency.
"""
from __future__ import annotations

import argparse
import io
import json
import threading


class _Capture(io.TextIOBase):
    """Collects everything written and splits it into whole lines.

    A stand-in for stdout or stderr while a command runs. Deliberately inert:
    it stores and it locks, and it calls nothing.
    """

    def __init__(self, lock: threading.Lock, lines: list | None = None):
        self._lock = lock
        self._chunks: list = []
        self._pending = ""
        #: Shared with the owner when this stream's lines are wanted live.
        self._lines = lines

    def write(self, text: str) -> int:
        with self._lock:
            self._chunks.append(text)
            if self._lines is None:
                return len(text)
            self._pending += text
            while "\n" in self._pending:
                line, self._pending = self._pending.split("\n", 1)
                line = line.strip()
                if line:
                    self._lines.append(line)
        return len(text)

    def flush(self) -> None:  # pragma: no cover - required by the io contract
        pass

    def writable(self) -> bool:
        return True

    def getvalue(self) -> str:
        with self._lock:
            return "".join(self._chunks)


class RunResult:
    """What a finished command left behind."""

    def __init__(self, exit_code: int, stdout: str, stderr: str,
                 error: str = "") -> None:
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        #: Set when the command raised instead of returning.
        self.error = error

    @property
    def ok(self) -> bool:
        return not self.error

    def payload(self) -> dict | None:
        """The command's JSON result, or None when it printed something else.

        Commands print their JSON as the last thing they write, and some also
        print plain lines before it, so the object is located rather than
        assumed to start at character zero.
        """
        text = self.stdout.strip()
        if not text:
            return None
        start = text.find("{")
        if start < 0:
            return None
        try:
            return json.loads(text[start:])
        except ValueError:
            return None

    def report_paths(self) -> list:
        """Files the run says it wrote, in the order it announced them.

        Read from the progress lines rather than from the arguments: the
        command decides where a default report goes (a per-target folder on
        Documents), and the screen should name what was actually written.
        """
        wanted = ("# report:", "# styled report:", "# agent briefing:",
                  "# timings:", "# comparison:", "# run folder:")
        paths = []
        for line in self.stderr.splitlines():
            line = line.strip()
            for prefix in wanted:
                if line.startswith(prefix):
                    path = line[len(prefix):].strip()
                    if path and path not in paths:
                        paths.append(path)
        return paths


class Run:
    """A command running on a worker thread, polled by the screen."""

    def __init__(self, command, args: argparse.Namespace) -> None:
        self._lock = threading.Lock()
        self._lines: list = []
        self._taken = 0
        self._out = _Capture(self._lock)
        self._err = _Capture(self._lock, self._lines)
        self.result: RunResult | None = None
        self._command = command
        self._args = args
        self._thread: threading.Thread | None = None

    def start(self) -> "Run":
        self._thread = threading.Thread(target=self._work, daemon=True)
        self._thread.start()
        return self

    @property
    def running(self) -> bool:
        return self.result is None

    def new_lines(self) -> list:
        """Progress lines that have appeared since the last call."""
        with self._lock:
            fresh = self._lines[self._taken:]
            self._taken = len(self._lines)
        return list(fresh)

    def join(self, timeout: float | None = None) -> None:
        """For tests and for shutdown; the interface polls instead."""
        if self._thread is not None:
            self._thread.join(timeout)

    def _work(self) -> None:
        import sys

        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = self._out, self._err
        error = ""
        code = 1
        try:
            code = self._command(self._args)
            if code is None:
                code = 0
        except SystemExit as exc:  # a command refusing its own arguments
            code = int(exc.code) if isinstance(exc.code, int) else 1
            error = "" if exc.code in (0, None) else str(exc)
        except Exception as exc:  # noqa: BLE001 - shown, never swallowed
            error = f"{type(exc).__name__}: {exc}"
        finally:
            sys.stdout, sys.stderr = old_out, old_err
            # Assigned last: `running` flips on this, so everything the
            # result reads must already be in place.
            self.result = RunResult(code, self._out.getvalue(),
                                    self._err.getvalue(), error)


def start(command, args: argparse.Namespace) -> Run:
    """Begin running `command(args)` on a worker thread."""
    return Run(command, args).start()
