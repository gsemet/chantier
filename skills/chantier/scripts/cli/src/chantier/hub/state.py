"""The surface server's state file: `<git common dir>/chantier/server.json`, never in a working
tree, never pushed, mode 0600 because it holds the board's key.

It holds the `key` and `created` (kept across starts), the `server` entry (the process that runs
`chantier board`: `pid`, `host`, `port`, `version`, `served`, `started`) and the `hub` entry (the
process that holds `hub.lock`, the server or, with no server, a watcher: `pid`, `version`,
`started` and, per project, `read_at`, `error`, `error_at`). An entry whose process has not been
alive since `started` is no entry.

Every write reads the file, changes one entry and replaces the file atomically, under a short OS
lock on `server.json.lock` (taken without waiting, retried for up to a second). Readers take no
lock: the replace is atomic. A failed write raises `StateError`, an `OSError`.

`board.json` (the key and the board's `running` record) and `hub.json` (the hub's record) of
earlier versions are migrated or deleted here, once."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from chantier import procs
from chantier.core import clock
from chantier.core.files import read_text, try_lock, unlock, write_json

FILE = "server.json"
LOCK = "server.json.lock"
OLD_BOARD = "board.json"
OLD_HUB = "hub.json"
WAIT_S = 1.0  # how long a write waits for the write lock
STEP_S = 0.02
SERVER, HUB = "server", "hub"


class StateError(OSError):
    """A write of `server.json` that failed: its message is `<path>: <reason>`."""


def folder(git_dir: Path) -> Path:
    return git_dir / "chantier"


def path(git_dir: Path) -> Path:
    return folder(git_dir) / FILE


def read(git_dir: Path) -> dict[str, Any]:
    """The file's content; empty when it is missing or unreadable."""
    return _read(path(git_dir))


def _read(file: Path) -> dict[str, Any]:
    try:
        data = json.loads(read_text(file))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _epoch(started: object) -> float | None:
    try:
        return datetime.strptime(str(started), clock.FORMAT).replace(tzinfo=UTC).timestamp()
    except ValueError:
        return None


def live_entry(git_dir: Path, name: str) -> dict[str, Any] | None:
    """The `server` or `hub` entry when its process is alive and is the recorded one, else None."""
    entry = read(git_dir).get(name)
    if not isinstance(entry, dict):
        return None
    pid, when = entry.get("pid"), _epoch(entry.get("started"))
    if not isinstance(pid, int) or isinstance(pid, bool) or when is None:
        return None
    if name == SERVER and (
        not isinstance(entry.get("port"), int) or not isinstance(entry.get("host"), str)
    ):
        return None
    return entry if procs.alive_since(pid, when, unreadable=True) else None


def modify(git_dir: Path, change: Callable[[dict[str, Any]], None]) -> None:
    """Read the file, apply `change` to its content, replace it atomically, under the write lock.
    Raises `StateError` on an `OSError` or when the lock is not taken within `WAIT_S`."""
    target = path(git_dir)
    try:
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        handle = (target.parent / LOCK).open("a+")
    except OSError as e:
        raise StateError(f"{target}: {e}") from e
    try:
        deadline = time.monotonic() + WAIT_S
        while not try_lock(handle):
            if time.monotonic() >= deadline:
                raise StateError(f"{target}: the write lock ({LOCK}) is held by another process")
            time.sleep(STEP_S)
        try:
            data = _read(target)
            change(data)
            write_json(target, data)
            os.chmod(target, 0o600)
        except OSError as e:
            raise StateError(f"{target}: {e}") from e
        finally:
            unlock(handle)
    finally:
        handle.close()


def check_writable(git_dir: Path) -> None:
    """Write the file as it is: raises `StateError` when a write would fail."""
    modify(git_dir, lambda _data: None)


def set_key(git_dir: Path, key: str) -> None:
    """Record a new key and when it was made; the entries stay."""

    def put(data: dict[str, Any]) -> None:
        data["key"], data["created"] = key, clock.now()

    modify(git_dir, put)


def migrate(git_dir: Path) -> None:
    """Once: with no `key` in `server.json` and a `board.json` present, move its key, its
    `created` and its `running` record (as the `server` entry) into `server.json` in one write,
    then delete `board.json`. Raises `StateError` when the write fails."""
    old = folder(git_dir) / OLD_BOARD
    if not old.is_file() or read(git_dir).get("key"):
        return
    kept = _read(old)
    moved = {k: kept[k] for k in ("key", "created") if k in kept}
    running = kept.get("running")

    def put(data: dict[str, Any]) -> None:
        data.update(moved)
        if isinstance(running, dict):
            data[SERVER] = running

    modify(git_dir, put)
    old.unlink(missing_ok=True)


def write_server(git_dir: Path, host: str, port: int, version: str, served: str) -> None:
    """Record this process as the server that serves the folder."""
    entry = {
        "pid": os.getpid(),
        "host": host,
        "port": port,
        "version": version,
        "served": served,
        "started": clock.now(),
    }
    modify(git_dir, lambda data: data.__setitem__(SERVER, entry))


def hub_record(version: str) -> dict[str, Any]:
    return {"pid": os.getpid(), "version": version, "started": clock.now(), "projects": {}}


def write_hub(git_dir: Path, record: dict[str, Any]) -> None:
    """Record this process as the forge hub (and drop `hub.json` of an earlier version)."""
    modify(git_dir, lambda data: data.__setitem__(HUB, json.loads(json.dumps(record))))
    (folder(git_dir) / OLD_HUB).unlink(missing_ok=True)


def remove_entry(git_dir: Path, name: str, pid: int) -> None:
    """Remove the entry when it still names this PID (a later process's entry stays)."""

    def drop(data: dict[str, Any]) -> None:
        entry = data.get(name)
        if isinstance(entry, dict) and entry.get("pid") == pid:
            del data[name]

    modify(git_dir, drop)


def other_version(record: dict[str, Any] | None, version: str) -> str | None:
    """The entry's version when it differs from `version`, else None."""
    found = (record or {}).get("version")
    return found if isinstance(found, str) and found != version else None
