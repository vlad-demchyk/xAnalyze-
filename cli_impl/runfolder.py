"""Where a run's documents go, and how long each stage took.

One folder per target, one sub-folder per run inside it:

    ~/Desktop/XAnalyze/example.com/
        2026-08-24-0930/
            report.md
            report.pdf
            timings.md
            changes.md          (from the second run on)
        2026-08-24-1145/
            ...

Per target rather than one flat pile, because the question a second run
answers is "what changed since last time", and that only reads as an answer
when both runs sit next to each other. Per run inside it rather than
timestamped file names, because a run produces several documents that belong
together and a folder is what says so.

`changes.md` is absent on a first run: an empty comparison file is worse than
no file, since it looks like the comparison failed.
"""
from __future__ import annotations

import re
import sys
import time
from datetime import datetime
from pathlib import Path

#: The folder every project folder lives under. Named, not the bare Desktop:
#: a tool that drops folders directly on someone's Desktop is a tool they
#: uninstall.
DESKTOP_FOLDER = "XAnalyze"

#: Anything that is not a letter, digit, dot or dash becomes one dash, so a
#: URL or a path turns into one readable folder name. Dots are kept because
#: `example.com` is the name a person recognises.
_UNSAFE = re.compile(r"[^A-Za-z0-9.\-]+")

#: A folder name longer than this is truncated. Long enough to stay
#: recognisable, short enough that the path does not become unusable.
_MAX_SLUG = 60


def slug_for(target: str) -> str:
    """A folder name a person recognises, from a URL or a path.

    `https://example.com/pricing/` -> `example.com-pricing`,
    `/Users/me/code/shop` -> `shop`.

    A URL keeps its host, because the host is what identifies the project. A
    path keeps only its last component: the full path would make a folder
    name nobody can read, and two projects with the same last component are
    rare enough to be worth the collision (both then append runs to the same
    folder, which is wrong but visible, rather than silently hiding one).
    """
    text = (target or "").strip()
    if text.startswith(("http://", "https://")):
        text = text.split("://", 1)[1]
    else:
        stripped = text.rstrip("/\\")
        # `Path("/a/b/").name` is "b"; an empty name means the root itself.
        text = Path(stripped).name or stripped or "scan"
    text = _UNSAFE.sub("-", text).strip("-.") or "scan"
    return text[:_MAX_SLUG]


def _desktop() -> Path:
    """The Desktop, or the home folder when there is no Desktop.

    A machine without `~/Desktop` (a container, a server, a localised
    account whose Desktop lives elsewhere) must still get its documents
    somewhere findable rather than an error.
    """
    desktop = Path.home() / "Desktop"
    return desktop if desktop.is_dir() else Path.home()


class RunFolder:
    """One run's folder, and the paths of the documents that go in it."""

    def __init__(self, project: Path, run: Path) -> None:
        #: The per-target folder: every run of this target is in here.
        self.project = project
        #: This run's folder.
        self.run = run

    @property
    def report(self) -> Path:
        return self.run / "report.md"

    @property
    def styled_report(self) -> Path:
        return self.run / "report.pdf"

    @property
    def timings(self) -> Path:
        return self.run / "timings.md"

    @property
    def changes(self) -> Path:
        return self.run / "changes.md"

    def previous_runs(self) -> list:
        """Every earlier run folder of this target, oldest first."""
        others = [p for p in self.project.iterdir()
                  if p.is_dir() and p != self.run]
        return sorted(others, key=lambda p: p.name)


class RunDocuments:
    """What one run's folder ended up containing, and what it did not.

    `absent` carries a reason per missing document rather than leaving it
    off the list. The four documents are a fixed set - a reader who knows
    there should be a `changes.md` and sees no mention of one cannot tell
    whether the comparison failed or whether this is simply the first run of
    this target, and those are opposite pieces of news.
    """

    def __init__(self, folder: "RunFolder", target: str,
                 written: dict, absent: dict) -> None:
        self.folder = folder
        self.target = target
        #: name -> Path, for documents actually on disk.
        self.written = written
        #: name -> reason, one of "no_audit", "first_run", "not_comparable".
        self.absent = absent

    #: The order they are listed in, which is the order they were written and
    #: the order of decreasing usefulness to a person opening the folder.
    ORDER = ("report.pdf", "report.md", "changes.md", "timings.md")

    def documents(self) -> list:
        """`(name, path_or_None, reason_or_None)` for all four, in order."""
        return [(name, self.written.get(name), self.absent.get(name))
                for name in self.ORDER]


#: Overrides where project folders are created. For a machine with no
#: Desktop worth writing to - a CI runner, a container - and for tests,
#: which must not write into the person's actual Desktop.
ROOT_ENV = "XANALYZE_REPORT_ROOT"


def default_root() -> Path:
    import os
    override = os.environ.get(ROOT_ENV)
    if override:
        return Path(override).expanduser()
    return _desktop() / DESKTOP_FOLDER


def prepare(target: str, *, root: Path | None = None) -> RunFolder:
    """Create this run's folder under this target's folder, and return it.

    `root` overrides the Desktop, for tests and for anyone who would rather
    the documents landed elsewhere; so does `XANALYZE_REPORT_ROOT`.
    """
    base = Path(root) if root is not None else default_root()
    project = base / slug_for(target)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    run = project / stamp
    # A second run inside the same minute would otherwise overwrite the
    # first one's documents.
    if run.exists():
        for suffix in range(2, 100):
            candidate = project / f"{stamp}-{suffix}"
            if not candidate.exists():
                run = candidate
                break
    run.mkdir(parents=True, exist_ok=True)
    return RunFolder(project, run)


class Timings:
    """How long each stage took, recorded as the run goes.

    Kept as plain wall-clock seconds. The point is not profiling precision -
    it is being able to say "the browser pass is what took forty minutes"
    when someone asks why a scan was slow, and to see that number change
    between runs.
    """

    def __init__(self, started: float | None = None) -> None:
        #: `started` lets a caller that timed the stages elsewhere say when
        #: the run actually began. Without it the total would be measured
        #: from this object's construction, and a `Timings` built after the
        #: run to record what already happened would report a total of
        #: nothing - which turns every stage's share of it into a number in
        #: the thousands.
        self._started = time.monotonic() if started is None else started
        self._stages: list = []
        self._open: tuple | None = None

    def start(self, name: str) -> None:
        """Begin a stage, closing the previous one."""
        self.finish()
        self._open = (name, time.monotonic())

    def finish(self) -> None:
        """Close the stage currently open, if any."""
        if self._open is None:
            return
        name, began = self._open
        self._stages.append((name, time.monotonic() - began))
        self._open = None

    def note(self, name: str, seconds: float) -> None:
        """Record a stage that was timed elsewhere."""
        self._stages.append((name, seconds))

    @property
    def total(self) -> float:
        return time.monotonic() - self._started

    def stages(self) -> list:
        """Closed stages, plus the open one at its duration so far."""
        stages = list(self._stages)
        if self._open is not None:
            name, began = self._open
            stages.append((name, time.monotonic() - began))
        return stages

    def as_markdown(self, target: str, extra: dict | None = None) -> str:
        self.finish()
        lines = [
            f"# Timings for {target}",
            "",
            f"Total {_duration(self.total)}.",
            "",
            "| stage | duration | share |",
            "|---|---|---|",
        ]
        total = self.total or 1.0
        for name, seconds in self._stages:
            lines.append(f"| {name} | {_duration(seconds)} | "
                         f"{seconds / total * 100:.0f}% |")
        lines.append("")
        for label, value in (extra or {}).items():
            lines.append(f"- {label}: {value}")
        if extra:
            lines.append("")
        lines += [
            "Wall-clock seconds, not profiling: the question this answers is "
            "which stage a slow run spent its time in, and whether that "
            "changed since the last run.",
            "",
        ]
        return "\n".join(lines)

    def write(self, path, target: str, extra: dict | None = None) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.as_markdown(target, extra), encoding="utf-8")
        print(f"# timings: {path}", file=sys.stderr)


def _duration(seconds: float) -> str:
    """`93.4` -> `1m 33s`; under a minute keeps one decimal."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, rest = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {rest:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m {rest:02d}s"
