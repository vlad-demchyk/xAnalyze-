"""The log the app keeps about itself.

A user reporting "the scan found nothing" hands over a screenshot of a
finished window. What actually happened - which pages were fetched, which
engine refused to start, which rule raised, how long the browser pass took -
lived in stderr, and stderr is gone by the time anyone asks. This is the
file that survives the run.

**Written as JSON Lines, one file per day.** Both halves of that matter. A
record is a dict, so a viewer can filter by level or by run without parsing
prose, and a day per file makes retention a matter of deleting files rather
than rewriting one. `xanalyze-2026-08-27.log`.

**It never raises.** Every public function swallows its own errors: a log
that can break a scan is worse than no log at all, and the one thing this
must not do is become the reason a run fails.

**It cleans up after itself**, because a debug log that fills a disk gets
switched off and then it helps nobody. Two limits, both enforced together
and both deliberately conservative:

* files older than `RETENTION_DAYS` are removed, and
* whatever is left is trimmed to `MAX_TOTAL_BYTES`, oldest first.

Cleanup runs once per process, on the first write, rather than on every
call: the cost is a directory listing, and paying it per log line would make
logging expensive enough to think twice about - which is how logging stops
being added.

Read it with `xanalyze logs` (CLI), the Logs screen in the TUI, or the log
panel in the window. All three call `read_records` here, so what they show
is the same list in a different frame.
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP_NAME = "xanalyze"

#: Anything older than this is deleted. Two weeks is long enough that a bug
#: reported "last week" is still in the file and short enough that the
#: directory does not become an archive nobody reads.
RETENTION_DAYS = 14
#: The whole directory, all files together. Twenty megabytes of JSON Lines is
#: tens of thousands of records - far more than any one investigation needs -
#: and small enough that nobody has to think about it.
MAX_TOTAL_BYTES = 20 * 1024 * 1024
#: One record. A truncated line is still a usable record; an unbounded one
#: can be a whole HTML page, and a handful of those are the file.
MAX_RECORD_BYTES = 8 * 1024

LEVELS = ("debug", "info", "warning", "error")
#: Records below this are dropped at the door. `debug` is off by default
#: because it is written from inside loops - a crawl of thirty pages should
#: not cost thirty records unless someone asked for them.
DEFAULT_LEVEL = "info"

_lock = threading.Lock()
_cleaned = False
_run_id = ""


def log_dir() -> Path:
    """Where the files live, resolved now rather than at import.

    Same reasoning as `config.config_file`: a module constant is computed
    once from whatever the environment was during import, which makes the
    real directory unavoidable for a test. `XANALYZE_LOG_DIR` isolates a
    whole process.
    """
    override = os.environ.get("XANALYZE_LOG_DIR")
    if override:
        path = Path(override)
    else:
        base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
        path = Path(base) / APP_NAME / "logs"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return path


def _level_floor() -> str:
    wanted = (os.environ.get("XANALYZE_LOG_LEVEL") or DEFAULT_LEVEL).lower()
    return wanted if wanted in LEVELS else DEFAULT_LEVEL


def enabled_for(level: str) -> bool:
    try:
        return LEVELS.index(level) >= LEVELS.index(_level_floor())
    except ValueError:
        return True


def file_for(day: datetime | None = None) -> Path:
    day = day or datetime.now(timezone.utc)
    return log_dir() / f"{APP_NAME}-{day.strftime('%Y-%m-%d')}.log"


def set_run(run_id: str) -> None:
    """Tag every following record with the run it belongs to.

    A machine that scans nightly has several runs in one file, and "which
    run was this" is the first question anyone asks of a line.
    """
    global _run_id
    _run_id = str(run_id or "")


def current_run() -> str:
    return _run_id


def log(event: str, level: str = "info", **fields) -> None:
    """One record. Never raises, never blocks on anything but the file lock."""
    try:
        if not enabled_for(level):
            return
        record = {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "level": level if level in LEVELS else "info",
            "event": str(event),
        }
        if _run_id:
            record["run"] = _run_id
        for key, value in fields.items():
            record[key] = _plain(value)
        line = json.dumps(record, ensure_ascii=False, default=str)
        if len(line) > MAX_RECORD_BYTES:
            record = {**{k: record[k] for k in ("at", "level", "event")},
                      "truncated": True,
                      "detail": line[:MAX_RECORD_BYTES]}
            line = json.dumps(record, ensure_ascii=False, default=str)
        with _lock:
            _clean_once()
            with open(file_for(), "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
    except Exception:  # noqa: BLE001 - see the module docstring
        pass


def debug(event: str, **fields) -> None:
    log(event, "debug", **fields)


def info(event: str, **fields) -> None:
    log(event, "info", **fields)


def warning(event: str, **fields) -> None:
    log(event, "warning", **fields)


def error(event: str, **fields) -> None:
    log(event, "error", **fields)


def _plain(value):
    """Whatever was passed, in a shape `json.dumps` will not choke on."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value][:50]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in list(value.items())[:50]}
    return str(value)


def _clean_once() -> None:
    global _cleaned
    if _cleaned:
        return
    _cleaned = True
    clean()


def clean(retention_days: int = RETENTION_DAYS,
          max_total_bytes: int = MAX_TOTAL_BYTES) -> dict:
    """Delete what is too old, then what does not fit. Returns what it did.

    Both limits, not either: a machine that scans all day can pass the age
    test and still hold gigabytes, and a machine that scanned once a year ago
    passes the size test while keeping a file nobody will ever read.
    """
    removed_old, removed_size, kept = 0, 0, 0
    try:
        files = sorted(log_dir().glob(f"{APP_NAME}-*.log"))
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        surviving = []
        for path in files:
            try:
                stamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
            except OSError:
                continue
            if stamp < cutoff:
                try:
                    path.unlink()
                    removed_old += 1
                except OSError:
                    pass
                continue
            surviving.append(path)

        total = 0
        for path in surviving:
            try:
                total += path.stat().st_size
            except OSError:
                pass
        # Oldest first: the newest file is the one an investigation is
        # actually about, and it is the last thing to go.
        for path in surviving:
            if total <= max_total_bytes:
                break
            try:
                size = path.stat().st_size
                path.unlink()
                total -= size
                removed_size += 1
            except OSError:
                pass
        kept = max(0, len(surviving) - removed_size)
    except Exception:  # noqa: BLE001
        pass
    return {"removed_expired": removed_old, "removed_oversize": removed_size,
            "kept": kept}


def read_records(limit: int = 200, level: str = "", contains: str = "",
                 run: str = "", days: int = RETENTION_DAYS) -> list:
    """The most recent records first, filtered.

    Reads whole files rather than seeking backwards from the end: a day's
    log is bounded by `MAX_TOTAL_BYTES` across the whole directory, so the
    simple thing is also the fast enough thing, and a seek that lands in the
    middle of a line is a bug waiting for a large file to expose it.
    """
    wanted_rank = LEVELS.index(level) if level in LEVELS else -1
    needle = (contains or "").lower()
    records: list = []
    try:
        files = sorted(log_dir().glob(f"{APP_NAME}-*.log"), reverse=True)[:max(1, days)]
        for path in files:
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line in reversed(lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    # A line torn by a crash mid-write is shown, not dropped:
                    # the run that produced it is the interesting one.
                    record = {"at": "", "level": "error", "event": "unparsed",
                              "detail": line[:400]}
                if wanted_rank >= 0:
                    rank = LEVELS.index(record.get("level", "info")) \
                        if record.get("level") in LEVELS else 1
                    if rank < wanted_rank:
                        continue
                if run and record.get("run") != run:
                    continue
                if needle and needle not in json.dumps(record, ensure_ascii=False).lower():
                    continue
                records.append(record)
                if len(records) >= limit:
                    return records
    except Exception:  # noqa: BLE001
        pass
    return records


def summary() -> dict:
    """What the directory holds, for a viewer's header line."""
    files, total = [], 0
    try:
        for path in sorted(log_dir().glob(f"{APP_NAME}-*.log")):
            try:
                size = path.stat().st_size
            except OSError:
                continue
            files.append({"name": path.name, "bytes": size})
            total += size
    except Exception:  # noqa: BLE001
        pass
    return {"directory": str(log_dir()), "files": files, "bytes": total,
            "retention_days": RETENTION_DAYS, "max_bytes": MAX_TOTAL_BYTES,
            "level": _level_floor()}


def format_line(record: dict) -> str:
    """One record as a line a person reads in a terminal."""
    at = (record.get("at") or "")[11:19] or "--:--:--"
    level = (record.get("level") or "info")[:5].ljust(5)
    event = record.get("event", "")
    rest = {k: v for k, v in record.items()
            if k not in ("at", "level", "event", "run")}
    tail = " ".join(f"{k}={v}" for k, v in rest.items())
    return f"{at} {level} {event}" + (f"  {tail}" if tail else "")


def _reset_for_tests() -> None:
    global _cleaned, _run_id
    _cleaned = False
    _run_id = ""
