"""Keeping the file the user had, so any write can be taken back.

There are two ways this tool writes to disk - the character fixes from the
text scan, and the corrections from the audit - and until this module existed
each carried its own copy of the same rule. Two implementations of a safety
net is one more than can be kept correct: the rule below is subtle enough
that having it written twice is how a version of it eventually loses.

**Only the first backup is kept.** A second run must not overwrite the copy
made by the first, or "undo" would return the file to the state between two
runs rather than to the state the user actually had. That is the difference
between a way out and a slightly older mistake.
"""
from __future__ import annotations

import os

SUFFIX = ".bak"


def path_for(file_path: str) -> str:
    return file_path + SUFFIX


def exists(file_path: str) -> bool:
    return os.path.exists(path_for(file_path))


def take(file_path: str, original_text: str) -> str:
    """Copy the file before it is first changed. Returns the backup's path.

    Returns an empty string when a backup was already taken - not an error,
    and deliberately not a fresh copy.
    """
    backup_path = path_for(file_path)
    if os.path.exists(backup_path):
        return ""
    with open(backup_path, "w", encoding="utf-8") as handle:
        handle.write(original_text)
    return backup_path


def restore(paths, remove_backup: bool = True) -> tuple:
    """Put files back the way they were before the first change.

    Returns `(restored, problems)`. Deliberately not a stack of undo steps:
    the promise is "back to how it was", which one copy per file can keep and
    a stack of partial states cannot.
    """
    restored, problems = [], []
    for file_path in paths:
        backup_path = path_for(file_path)
        if not os.path.exists(backup_path):
            problems.append(f"{file_path}: no backup was kept, nothing to go back to")
            continue
        try:
            with open(backup_path, encoding="utf-8") as handle:
                original = handle.read()
            with open(file_path, "w", encoding="utf-8") as handle:
                handle.write(original)
            restored.append(file_path)
            if remove_backup:
                os.unlink(backup_path)
        except OSError as exc:
            problems.append(f"{file_path}: {exc}")
    return restored, problems


def existing_for(paths) -> list:
    """Which of these files have a backup waiting to be restored."""
    seen, out = set(), []
    for file_path in paths:
        if file_path in seen:
            continue
        seen.add(file_path)
        if exists(file_path):
            out.append(file_path)
    return out
