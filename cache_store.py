"""Atomic JSON cache updates that merge only locally changed entries."""
from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path

_mutex = threading.RLock()


def merge_cache(path: Path, entries: dict, baseline: dict, *, clear=False,
                cutoff=None, limit=None, remove_empty=False) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _mutex, open(path.with_suffix(path.suffix + ".lock"), "a+b") as lock:
        if os.name == "nt":
            import msvcrt
            if os.fstat(lock.fileno()).st_size == 0:
                lock.write(b"\0")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            try:
                merged = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                merged = {}
            if clear or not isinstance(merged, dict):
                merged = {}
            for key in baseline.keys() - entries.keys():
                # Do not delete a concurrently refreshed entry.
                if merged.get(key) == baseline[key]:
                    merged.pop(key, None)
            merged.update({k: v for k, v in entries.items()
                           if k not in baseline or v != baseline[k]})
            if cutoff is not None:
                merged = {k: v for k, v in merged.items()
                          if isinstance(v, dict) and isinstance(v.get("at"), (int, float))
                          and v["at"] >= cutoff}
            if limit is not None:
                merged = dict(sorted(merged.items(), key=lambda item: item[1]["at"],
                                     reverse=True)[:limit])
            if remove_empty and not merged:
                path.unlink(missing_ok=True)
                return merged
            fd, name = tempfile.mkstemp(prefix=".cache-", dir=path.parent)
            temporary = Path(name)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump(merged, stream, ensure_ascii=False)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            return merged
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
