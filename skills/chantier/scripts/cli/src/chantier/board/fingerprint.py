"""The fingerprint of a project's record and the per-project cache of its state: a `stat` walk,
no read, so an unchanged project answers `304` without opening a file."""

from __future__ import annotations

import hashlib
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from chantier.board.files import is_lock

# The stage folders the state reads whole; the archives and the trash are read for their last
# folders only, so a shallow walk of them is enough (a folder added or removed moves its parent).
DEEP = ("1-inbox", "2-backlog", "3-ready", "4-batch")
SHALLOW = ("5-archives", "6-trash", "5-archives/batches")
SINGLE = ("seat.json",)  # the batch's own files are in `4-batch`


def _entry(path: Path, base: Path) -> str:
    try:
        info = path.stat()
    except OSError:
        return f"{path.relative_to(base).as_posix()}:-"
    return f"{path.relative_to(base).as_posix()}:{info.st_size}:{info.st_mtime_ns}"


def _walk(folder: Path, base: Path, deep: bool) -> list[str]:
    found: list[str] = []
    try:
        entries = sorted(os.scandir(folder), key=lambda e: e.name)
    except OSError:
        return [f"{folder.relative_to(base).as_posix()}:-"]
    for e in entries:
        if is_lock(e.name):
            continue
        path = Path(e.path)
        found.append(_entry(path, base))
        if deep and e.is_dir(follow_symlinks=False):
            found += _walk(path, base, True)
    return found


def fingerprint(changes: Path, extra: str = "") -> str:
    """A hash of the size and modification time of what the state reads, and of `extra` (the
    live cost's marks)."""
    base = changes.resolve()
    lines = [_entry(base / name, base) for name in SINGLE]
    for name in DEEP:
        lines += _walk(base / name, base, True)
    for name in SHALLOW:
        lines += _walk(base / name, base, False)
    lines.append(extra)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


class StateCache:
    """The last state of each project with its fingerprint."""

    def __init__(self) -> None:
        self._last: dict[str, tuple[str, dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def peek(self, project_id: str) -> dict[str, Any] | None:
        found = self._last.get(project_id)
        return found[1] if found else None

    def get(
        self, project_id: str, print_: str, build: Callable[[], dict[str, Any]]
    ) -> dict[str, Any]:
        """The state of this fingerprint: the kept one, or the one `build` reads now."""
        with self._lock:
            found = self._last.get(project_id)
            if found and found[0] == print_:
                return found[1]
            state = build()
            self._last[project_id] = (print_, state)
            return state
