"""The `writer` entry of `server.json` (the spec's C.4): built here, written by the writer only."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path
from typing import Any

from chantier.core import clock
from chantier.hub import state

SYNCING, SYNCED, PENDING, OFFLINE, CONFLICT, BLOCKED, STOPPED = (
    "syncing",
    "synced",
    "pending",
    "offline",
    "conflict",
    "blocked",
    "stopped",  # the writer's thread died: the server serves, writes are refused; `text` says why
)
OFF = "off"  # what readers derive when there is no live entry
STATES = (SYNCING, SYNCED, PENDING, OFFLINE, CONFLICT, BLOCKED, STOPPED)
TEXT_MAX = 200


def cut(text: str, limit: int = TEXT_MAX) -> str:
    """One line, at most `limit` characters."""
    line = " ".join(text.split())
    return line if len(line) <= limit else line[: limit - 3] + "..."


def new(version: str) -> dict[str, Any]:
    return {
        "pid": os.getpid(),
        "version": version,
        "started": clock.real_now(),
        "state": SYNCING,
        "reason": "",
        "text": "",
        "since": clock.now(),
        "last_cycle": None,
        "pending": 0,
        "pending_since": None,
        "ahead": 0,
        "unpushed_since": None,
        "last_commit": None,
        "last_push": None,
        "last_fetch": None,
        "conflict": None,
        "failure": None,
    }


def publish(git_dir: Path, record: dict[str, Any]) -> None:
    """Write the entry; a failed write is left to the next cycle."""
    with contextlib.suppress(OSError):
        state.write_writer(git_dir, record)


def read(git_dir: Path) -> dict[str, Any]:
    """The live `writer` entry as written, or `{"state": "off"}` when no live process holds it."""
    return state.live_entry(git_dir, state.WRITER) or {"state": OFF}
