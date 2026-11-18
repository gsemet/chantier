"""The hub's election and its record, in the git folder next to the board's `board.json`.

`hub.lock` is taken with `core.files.try_lock` and never waited on: the OS releases it when the
holder exits or dies, so no stale lock exists. `hub.json` is kept while the lock is held: the
holder's `pid`, `version`, `started` and, per project, `read_at` (the last good read), `error` (the
last failed read's one line, or null) and `error_at`. A record whose process is not alive since
`started` is no record."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any

from chantier import procs
from chantier.core import clock
from chantier.core.files import read_text, try_lock, unlock, write_json

LOCK = "hub.lock"
RECORD = "hub.json"


def folder(git_dir: Path) -> Path:
    return git_dir / "chantier"


class HubLock:
    """One handle on the hub lock: `acquire` wins it or not, at once; `release` lets it go."""

    def __init__(self, git_dir: Path) -> None:
        self.path = folder(git_dir) / LOCK
        self._file: IO[str] | None = None

    @property
    def held(self) -> bool:
        return self._file is not None

    def acquire(self) -> bool:
        if self._file is not None:
            return True
        self.path.parent.mkdir(parents=True, exist_ok=True)
        f = self.path.open("a+")
        if try_lock(f):
            self._file = f
            return True
        f.close()
        return False

    def release(self) -> None:
        f, self._file = self._file, None
        if f is not None:
            try:
                unlock(f)
            finally:
                f.close()


def _read(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(read_text(path))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _epoch(started: object) -> float | None:
    try:
        return datetime.strptime(str(started), clock.FORMAT).replace(tzinfo=UTC).timestamp()
    except ValueError:
        return None


def live(git_dir: Path) -> dict[str, Any] | None:
    """The record of a hub whose process is alive and is the recorded one, else None."""
    data = _read(folder(git_dir) / RECORD)
    pid, when = data.get("pid"), _epoch(data.get("started"))
    if not isinstance(pid, int) or when is None:
        return None
    return data if procs.alive_since(pid, when, unreadable=True) else None


def start_record(version: str) -> dict[str, Any]:
    return {"pid": os.getpid(), "version": version, "started": clock.now(), "projects": {}}


def write(git_dir: Path, data: dict[str, Any]) -> None:
    write_json(folder(git_dir) / RECORD, data)


def remove(git_dir: Path, pid: int) -> None:
    """Remove the record when it still names this PID."""
    path = folder(git_dir) / RECORD
    if _read(path).get("pid") == pid:
        path.unlink(missing_ok=True)


def other_version(record: dict[str, Any] | None, version: str) -> str | None:
    """The hub's version when it differs from `version`, else None."""
    found = (record or {}).get("version")
    return found if isinstance(found, str) and found != version else None
