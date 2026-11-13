"""The locked, read-modify-write view of the batch's record; every change is one event."""

from __future__ import annotations

import contextlib
import json
import os
import re
import sys
import time
from pathlib import Path
from types import TracebackType
from typing import Any, Self, TextIO

from chantier.core.batch_records import last_closed_note, reserve_record
from chantier.core.clock import now
from chantier.core.errors import EXIT_CONFLICT, EXIT_EXTERNAL, EXIT_USAGE, ChantierError
from chantier.core.files import (
    LOCK_TIMEOUT_S,
    retry,
    try_lock,
    unlock,
    write_file,
    write_json,
)
from chantier.core.records import (
    BatchRecord,
    EventRecord,
    normalize_batch,
    normalize_cr,
    read_batch_json,
    read_restored_number,
)
from chantier.core.repo import SETTINGS, Repo


def move_directory(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise ChantierError(f"CR folder not found: {source}", EXIT_USAGE)
    if destination.exists() or destination.is_symlink():
        raise ChantierError(f"refusing to overwrite CR folder: {destination}", EXIT_CONFLICT)
    if source == destination or source in destination.parents:
        raise ChantierError(f"invalid CR move: {source} to {destination}", EXIT_USAGE)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        retry(source.rename, destination)
    except OSError as e:
        raise ChantierError(
            f"cannot move CR folder {source} to {destination}: {e}", EXIT_EXTERNAL
        ) from e


def apply_batch_settings(repo: Repo, data: dict[str, Any]) -> None:
    """A batch runs on the settings it was opened with, whatever changed since."""
    settings = data.get("settings")
    if settings is None:
        return
    for key in SETTINGS:
        if key in settings:
            repo.config[key] = settings[key]


class Batch:
    """A locked, read-modify-write view of one batch. Use as a context manager."""

    def __init__(
        self,
        repo: Repo,
        batch_id: str | None,
        actor: str = "cli",
        create: dict[str, Any] | None = None,
    ):
        """`create` opens a new batch: its number is the next, its id `batch-<n>` on two digits."""
        self._create = create
        self._number: int | None = None
        self._record: Path | None = None  # the record `open` wrote, removed if the open fails
        if create is not None:
            self._number = repo.next_batch_number()
            batch_id = f"batch-{self._number:02d}"
            create["id"] = batch_id
        else:
            batch_id = normalize_batch(batch_id or "")
        self.repo, self.id, self.actor = repo, batch_id, actor
        self.dir = repo.batches
        self._lock: TextIO
        self.data: dict[str, Any] = {}
        self._events: list[EventRecord] = []
        self._moves: list[tuple[Path, Path]] = []

    def __enter__(self) -> Self:
        if self._create is None and self.id not in self.repo.batch_ids():
            raise ChantierError(f"unknown batch {self.id}")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.repo.ensure_gitignore()
        self._lock = open(self.dir / ".lock", "a+")  # closed in __exit__
        acquired = False
        try:
            self._wait_for_lock()
            acquired = True
            self._load()
        except BaseException:
            if acquired:
                unlock(self._lock)
            self._lock.close()
            raise
        return self

    def _wait_for_lock(self) -> None:
        deadline = time.monotonic() + LOCK_TIMEOUT_S
        while not try_lock(self._lock):
            if time.monotonic() > deadline:
                raise ChantierError(f"batch {self.id} is locked for over {LOCK_TIMEOUT_S} s")
            time.sleep(0.05)

    def _load(self) -> None:
        path = self.dir / "batch.json"
        if path.exists():
            if self._create is not None:
                raise ChantierError(f"batch {self.id} already exists")
            self.data = read_batch_json(path)
        else:
            self.data = self._create or {}
        apply_batch_settings(self.repo, self.data)

    def after_save(self) -> None:
        """What follows a saved change: nothing here; a layer above renders the STATUS files."""

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        saved = False
        try:
            if exc_type is None and self._events:
                if self._number:  # the number is reserved by the record, before the state
                    self._record = reserve_record(self.repo, self.data)
                write_json(self.dir / "batch.json", BatchRecord.model_validate(self.data).to_data())
                saved = True
                self._append_events()
                try:
                    self.after_save()
                except Exception as e:  # the state is saved: only a view is stale until next change
                    print(f"warning: STATUS not rewritten: {e}", file=sys.stderr)
        finally:
            self._finish(saved)

    def _append_events(self) -> None:
        with open(self.dir / "events.jsonl", "a", encoding="utf-8") as f:
            f.writelines(json.dumps(e.to_data()) + "\n" for e in self._events)
        if self._number:
            write_file(self.repo.changes / ".batch-number", f"{self._number}\n")

    def _finish(self, saved: bool) -> None:
        try:
            if not saved:
                self._rollback_moves()
        finally:
            with contextlib.suppress(Exception):
                unlock(self._lock)
            self._lock.close()
            # a failed `open` leaves none of the batch's own files, and touches no CR folder:
            # the state folders stay; the record it wrote goes too
            if self._number and not saved:
                self._remove_own_files()

    def _remove_own_files(self) -> None:
        for path in (
            self.dir / ".lock",
            self.dir / "brief.md",
            *([self._record] if self._record else []),
        ):
            with contextlib.suppress(OSError):
                path.unlink()

    def log(self, kind: str, cr: str | None = None, **fields: Any) -> None:
        self._events.append(EventRecord(t=now(), actor=self.actor, kind=kind, cr=cr, **fields))

    def cr(self, cr_id: str) -> dict[str, Any]:
        cr_id = normalize_cr(cr_id)
        for c in self.data["crs"]:
            if c["id"] == cr_id:
                found: dict[str, Any] = c
                return found
        raise ChantierError(f"unknown CR {cr_id} in batch {self.id}", EXIT_USAGE)

    def touch(self, c: dict[str, Any], **fields: Any) -> None:
        c.update(fields)
        c["updated"] = now()

    def move(self, source: Path, destination: Path) -> None:
        move_directory(source, destination)
        self._moves.append((source, destination))

    def _rollback_moves(self) -> None:
        for source, destination in reversed(self._moves):
            if not destination.exists() or source.exists():
                raise ChantierError(
                    f"cannot roll back CR move {destination} to {source}; "
                    "preserve both paths and resolve manually"
                )
            source.parent.mkdir(parents=True, exist_ok=True)
            retry(destination.rename, source)
        self._moves.clear()


def resolve_batch(repo: Repo, batch: str | None) -> str:
    """`--batch`, else `CHANTIER_BATCH`, else the only running batch; never a guess among
    several."""
    if batch or os.environ.get("CHANTIER_BATCH"):
        return normalize_batch(batch or os.environ["CHANTIER_BATCH"])
    names = repo.open_batches()
    if len(names) == 1:
        return names[0]
    if not names:
        raise ChantierError("no running batch: run `chantier open` first" + last_closed_note(repo))
    raise ChantierError(f"several running batches ({', '.join(names)}): pass --batch", EXIT_USAGE)


def check_epoch(b: Batch, epoch: int | None) -> None:
    """A Foreman command carries the epoch it was started with; a stale Foreman is refused."""
    if epoch is None:
        return
    current = b.data.get("foreman_epoch", 0)
    if epoch != current:
        raise ChantierError(
            f"stale Foreman: epoch {epoch}, batch {b.id} is at epoch {current}; stop now",
            EXIT_CONFLICT,
        )


def read_batch(repo: Repo, batch_id: str) -> dict[str, Any]:
    data = read_batch_json(repo.batch_dir(batch_id) / "batch.json")
    apply_batch_settings(repo, data)
    return data


def find_cr_batch(repo: Repo, cr_id: str, batch: str | None) -> str:
    """The batch holding a CR: the one given, else the batch that has it (a paused batch
    can hold queued CRs)."""
    cr_id = normalize_cr(cr_id)
    if batch:
        return normalize_batch(batch)
    for d in reversed(repo.batch_folders()):
        b = read_batch_json(d / "batch.json")
        if any(c["id"] == cr_id for c in b["crs"]):
            return str(b["id"])
    raise ChantierError(f"no batch holds {cr_id}", EXIT_USAGE)


RESTORED_NUMBER_FILE = "restored.json"


def next_cr_number(repo: Repo, roots: tuple[Path, ...] = ()) -> int:
    """Choose a number under the lifecycle lock, without reserving it on a failed move."""
    previous: int = repo.config["first_cr_number"] - 1
    # a number `restore` took off a folder: once given, a number is never given again
    previous = max(previous, read_restored_number(repo.changes / RESTORED_NUMBER_FILE))
    children = [c for root in roots if root.is_dir() for c in root.iterdir() if c.is_dir()]
    for child in children:
        name = re.sub(r"^(?:\d{6}-\d{4}-)+", "", child.name)  # the date is no number
        match = re.match(r"^(?:CR-)?(\d+)(?:-|$)", name, re.I)
        if match:
            previous = max(previous, int(match.group(1)))
    recorded = [
        cr.get("id", "")
        for batch in repo.batch_folders()
        for cr in read_batch_json(batch / "batch.json").get("crs", [])
    ]
    for cr_id in recorded:
        match = re.fullmatch(r"CR-(\d+)", cr_id)
        if match:
            previous = max(previous, int(match.group(1)))
    return previous + 1
