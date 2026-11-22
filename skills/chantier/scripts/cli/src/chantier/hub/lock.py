"""The surface server's election and the watchers' locks, in the git folder next to its
`server.json` (`state.py`).

`hub.lock` is taken with `core.files.try_lock` and never waited on: the OS releases it when the
holder exits or dies, so no stale lock exists. The holder is the forge hub: the surface server
(`chantier serve`), and no other process; a watcher never takes it. The hub's record is the `hub`
entry of `server.json`, written by the holder only.

The surface's writer holds `writer.lock` the same way, and `writer.wake` is the file that `sync now`
and the board's button touch to start a cycle at once.

Each watcher also holds `watch-<project>/<session>.lock`, the same way: `watchers` lists the
sessions whose watcher of a project runs now."""

from __future__ import annotations

import os
from pathlib import Path
from typing import IO

from chantier.core.files import try_lock, unlock

LOCK = "hub.lock"
WRITER_LOCK = "writer.lock"
WRITER_WAKE = "writer.wake"
WATCHER_SUFFIX = ".lock"


def folder(git_dir: Path) -> Path:
    return git_dir / "chantier"


class _FileLock:
    """One handle on a lock file: `acquire` wins it or not, at once; `release` lets it go."""

    def __init__(self, path: Path) -> None:
        self.path = path
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


class HubLock(_FileLock):
    """The hub's lock: its holder is the surface server's hub loop, one per surface and machine."""

    def __init__(self, git_dir: Path) -> None:
        super().__init__(folder(git_dir) / LOCK)


class WriterLock(_FileLock):
    """The surface's writer's lock: its holder is the surface server's writer thread."""

    def __init__(self, git_dir: Path) -> None:
        super().__init__(folder(git_dir) / WRITER_LOCK)


def wake_path(git_dir: Path) -> Path:
    return folder(git_dir) / WRITER_WAKE


def wake(git_dir: Path) -> None:
    """Ask the writer for a cycle at once: touch `writer.wake`."""
    target = wake_path(git_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.touch()
    os.utime(target)


class WatcherLock(_FileLock):
    """A watcher's lock, one file per project and session; its name is the record, nothing is
    written in it, and it is left in place when the watcher ends."""

    def __init__(self, git_dir: Path, project: str, session: str) -> None:
        super().__init__(watcher_folder(git_dir, project) / f"{session}{WATCHER_SUFFIX}")


def watcher_folder(git_dir: Path, project: str) -> Path:
    return folder(git_dir) / f"watch-{project}"


def watchers(git_dir: Path, project: str) -> list[str]:
    """The sessions that hold a watcher's lock of this project now. The probe opens each existing
    lock file and tries the lock: taken means no watcher holds it, so it lets go at once. It
    creates no file and no folder."""
    here = watcher_folder(git_dir, project)
    if not here.is_dir():
        return []
    found: list[str] = []
    for path in sorted(here.glob(f"*{WATCHER_SUFFIX}")):
        try:
            f = path.open("r+")
        except OSError:
            continue
        try:
            if try_lock(f):
                unlock(f)
            else:
                found.append(path.name[: -len(WATCHER_SUFFIX)])
        finally:
            f.close()
    return found
