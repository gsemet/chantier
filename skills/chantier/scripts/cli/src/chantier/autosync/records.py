"""The files the surface's autosync tool keeps in its state folder, read as the tool reads them.
Nothing here writes or deletes: a participant file whose process is dead is only skipped."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

from pydantic import ValidationError

from chantier.core.files import read_text
from chantier.core.records import Record


class Control(Record):
    """`control.json`. `enabled` is true unless it is `false`, as the tool reads it."""

    enabled: object = True
    local_only: bool = False
    reason: str = ""
    updated_at: float | None = None
    updated_by_pid: int | None = None

    @property
    def on(self) -> bool:
        return self.enabled is not False


class SyncStatus(Record):
    """`status.json`: `state` is synced, pending, waiting, offline, action_required or
    approval_required; an approval also names its `incident`."""

    state: str = ""
    message: str = ""
    updated_at: float | None = None
    incident: str | None = None


class Watcher(Record):
    """`watcher.json`: the leader's process, while one runs."""

    pid: int | None = None
    local_only: bool = False


class Participant(Record):
    """`participants/<pid>.json`: a process that is a member of the group."""

    pid: int
    harness: str = ""
    owner_pid: int | None = None
    session_id: str | None = None
    role: str = ""
    since: float | None = None


_M = TypeVar("_M", bound=Record)


@dataclass
class GroupFiles:
    """What the state folder holds. `exists` is false while the tool never ran there."""

    exists: bool = False
    control: Control | None = None
    status: SyncStatus | None = None
    watcher: Watcher | None = None
    participants: list[Participant] = field(default_factory=list[Participant])
    unreadable: list[str] = field(default_factory=list[str])


def _load(path: Path, model: type[_M], bad: list[str]) -> _M | None:
    """The file as `model`; None when it is absent, and named in `bad` when it cannot be read."""
    if not path.is_file():
        return None
    try:
        return model.model_validate_json(read_text(path))
    except (OSError, ValueError, ValidationError):
        bad.append(path.name)
        return None


def _participants(folder: Path, bad: list[str]) -> list[Participant]:
    if not folder.is_dir():
        return []
    found = (_load(path, Participant, bad) for path in sorted(folder.glob("*.json")))
    return [p for p in found if p is not None]


def read_group(state_dir: Path) -> GroupFiles:
    """Read the group's files; never writes or deletes. An unreadable file is named in
    `unreadable` and left out, never guessed."""
    if not state_dir.is_dir():
        return GroupFiles()
    bad: list[str] = []
    return GroupFiles(
        exists=True,
        control=_load(state_dir / "control.json", Control, bad),
        status=_load(state_dir / "status.json", SyncStatus, bad),
        watcher=_load(state_dir / "watcher.json", Watcher, bad),
        participants=_participants(state_dir / "participants", bad),
        unreadable=bad,
    )
