"""Reading and writing files: atomic writes, the OS locks, the planning folder's .gitignore."""

from __future__ import annotations

import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import IO, Any, TypeVar

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


_T = TypeVar("_T")
LOCK_TIMEOUT_S = 30


def try_lock(f: IO[str]) -> bool:
    """Take the exclusive lock on an open lock file without waiting; False if another holds it."""
    if sys.platform == "win32":
        f.seek(0)
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    else:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True


def unlock(f: IO[str]) -> None:
    if sys.platform == "win32":
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(f, fcntl.LOCK_UN)


def retry(op: Callable[..., _T], *args: Any) -> _T:
    """Windows refuses to open a file while another process renames over it, and to rename over
    one another process has open: both are brief, so try again for up to a second."""
    for _ in range(100):
        try:
            return op(*args)
        except PermissionError:
            if sys.platform != "win32":
                raise
            time.sleep(0.01)
    return op(*args)


def read_text(path: Path, errors: str = "strict") -> str:
    """A planning folder's file. Windows PowerShell 5.1 (`Set-Content -Encoding utf8`,
    `Out-File`) starts what an agent writes with a byte-order mark: read through it. Writes
    stay plain UTF-8."""
    return retry(path.read_text, "utf-8-sig", errors)


def read_json(path: Path) -> Any:
    return json.loads(read_text(path))


def write_file(path: Path, text: str) -> None:
    """Write by atomic rename, so a reader never sees half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:  # `\n` on Windows too
        f.write(text)
    retry(os.replace, tmp, path)


def write_json(path: Path, data: Any) -> None:
    write_file(path, json.dumps(data, indent=2) + "\n")


# The files that stay on the steering machine, never published by the surface's git: a running
# batch's own files, the locks, the seat, the detailed logs.
IGNORED = (
    "STATUS.md",
    "STATUS.json",
    ".lock",
    ".lifecycle.lock",
    ".long-gate.lock",
    ".long-gate.run",
    ".long-gate.stop",
    ".long-gate.queue/",
    ".batch-number",
    ".closing-*",
    "seat.json",
    "/4-batch/batch.json",
    "/4-batch/events.jsonl",
    "/4-batch/brief.md",
    "work/gates/",
    "*.log",
    "*.tmp",
)


_IGNORE_HEAD = "# chantier: local files of a running batch and detailed logs, never published"


_ignored_done: set[str] = set()


def ensure_gitignore(changes: Path) -> None:
    """Write or complete the planning folder's own `.gitignore`, before any local file exists."""
    key = str(changes)
    if key in _ignored_done or not changes.is_dir():
        return
    path = changes / ".gitignore"
    have = read_text(path).splitlines() if path.is_file() else []
    missing = [e for e in IGNORED if e not in have]
    if missing:
        add = ([] if _IGNORE_HEAD in have else [_IGNORE_HEAD]) + missing
        write_file(path, "\n".join([*have, *add]) + "\n")
    _ignored_done.add(key)
