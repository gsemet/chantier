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

from chantier.core.batch_records import last_closed_note, record_path, reserve_record
from chantier.core.clock import now
from chantier.core.errors import (
    EXIT_CONFLICT,
    EXIT_PRECONDITION,
    EXIT_USAGE,
    ChantierError,
)
from chantier.core.files import (
    LOCK_TIMEOUT_S,
    rel_in,
    try_lock,
    unlock,
    write_file,
    write_json,
)
from chantier.core.ids import normalize_batch, normalize_cr
from chantier.core.records import (
    BatchRecord,
    CrEntry,
    EventRecord,
    read_batch_json,
    read_restored_number,
)
from chantier.core.repo import SETTINGS, Repo


def move_directory(repo: Repo, source: Path, destination: Path) -> None:
    """A CR folder to another stage, through the store: its refusals and their exit codes."""
    if not repo.store.is_dir(rel_in(repo.store.root, source)):
        raise ChantierError(f"CR folder not found: {source}", EXIT_USAGE)
    repo.check_publish([source, destination])
    repo.store.move(repo.rel(source), repo.rel(destination))


def apply_batch_settings(repo: Repo, record: BatchRecord) -> None:
    """A batch runs on the settings it was opened with, whatever changed since."""
    settings = record.settings
    if settings is None:
        return
    for key in SETTINGS:
        if key in settings.model_fields_set:
            repo.config[key] = getattr(settings, key)


class Batch:
    """A locked, read-modify-write view of one batch. Use as a context manager."""

    def __init__(
        self,
        repo: Repo,
        batch_id: str | None,
        actor: str = "cli",
        create: BatchRecord | None = None,
    ):
        """`create` opens a new batch: its number is the next, its id `batch-<n>` on two digits."""
        self._create = create
        self._number: int | None = None
        self._record: Path | None = None  # the record `open` wrote, removed if the open fails
        if create is not None:
            self._number = repo.next_batch_number()
            batch_id = f"batch-{self._number:02d}"
            create.id = batch_id
        else:
            batch_id = normalize_batch(batch_id or "")
        self.repo, self.id, self.actor = repo, batch_id, actor
        self.dir = repo.batches
        self._lock: TextIO
        self.record = BatchRecord()
        self._events: list[EventRecord] = []
        self._moves: list[tuple[Path, Path]] = []
        self._consumed: list[Path] = []

    def __enter__(self) -> Self:
        if self._create is None and self.id not in self.repo.batch_ids():
            raise ChantierError(f"unknown batch {self.id}")
        if self._number:  # `open`: its record is published
            self.repo.check_publish([record_path(self.repo, self._number)])
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
        if self.repo.store.exists(rel_in(self.repo.store.root, path)):
            if self._create is not None:
                raise ChantierError(f"batch {self.id} already exists")
            self.record = read_batch_json(self.repo.store, path)
        else:
            self.record = self._create or BatchRecord()
        apply_batch_settings(self.repo, self.record)

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
                    self._record = reserve_record(self.repo, self.record)
                self._drop_consumed()  # what the record now holds, before it is written
                write_json(self.dir / "batch.json", self.record.to_data())
                saved = True
                self._append_events()
                try:
                    self.after_save()
                except Exception as e:  # the state is saved: only a view is stale until next change
                    print(f"warning: STATUS not rewritten: {e}", file=sys.stderr)
        finally:
            self._finish(saved)

    def _drop_consumed(self) -> None:
        for gone in self._consumed:
            if self.repo.store.exists(rel_in(self.repo.store.root, gone)):
                self.repo.store.remove(self.repo.rel(gone))

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
        for path in (self.dir / ".lock", self.dir / "brief.md"):
            with contextlib.suppress(OSError):
                path.unlink()
        if self._record:
            with contextlib.suppress(OSError):
                self.repo.store.remove(self.repo.rel(self._record))

    def log(self, kind: str, cr: str | None = None, **fields: Any) -> None:
        self._events.append(EventRecord(t=now(), actor=self.actor, kind=kind, cr=cr, **fields))

    def cr(self, cr_id: str) -> CrEntry:
        cr_id = normalize_cr(cr_id)
        for c in self.record.crs:
            if c.id == cr_id:
                return c
        raise ChantierError(f"unknown CR {cr_id} in batch {self.id}", EXIT_USAGE)

    def touch(self, c: CrEntry, **fields: Any) -> None:
        for key, value in fields.items():
            setattr(c, key, value)
        c.updated = now()

    def move(self, source: Path, destination: Path) -> None:
        move_directory(self.repo, source, destination)
        self._moves.append((source, destination))

    def consume(self, path: Path) -> None:
        """A file the record now holds the content of: deleted when the record is saved, and kept
        when the command is refused."""
        self.repo.check_publish([path])
        self._consumed.append(path)

    def _rollback_moves(self) -> None:
        for source, destination in reversed(self._moves):
            store = self.repo.store
            if not store.exists(rel_in(store.root, destination)) or store.exists(
                rel_in(store.root, source)
            ):
                raise ChantierError(
                    f"cannot roll back CR move {destination} to {source}; "
                    "preserve both paths and resolve manually"
                )
            self.repo.store.move(self.repo.rel(destination), self.repo.rel(source))
        self._moves.clear()


def resolve_batch(repo: Repo, batch: str | None, paused: bool = False) -> str:
    """`--batch`, else `CHANTIER_BATCH`, else the only running batch; never a guess among
    several. A reading command passes `paused=True`: with no batch running it takes the only
    paused one. A refusal names the paused batches and `--batch`."""
    if batch or os.environ.get("CHANTIER_BATCH"):
        return normalize_batch(batch or os.environ["CHANTIER_BATCH"])
    names = repo.open_batches()
    if len(names) == 1:
        return names[0]
    if not names:
        held = repo.paused_batches()
        if paused and len(held) == 1:
            return held[0]
        if held:
            flag = f"--batch {held[0]}" if len(held) == 1 else "--batch <name>"
            raise ChantierError(
                f"no running batch; paused: {', '.join(held)}: pass `{flag}`"
                + last_closed_note(repo).replace("; no batch closed yet", "")
            )
        raise ChantierError("no running batch: run `chantier open` first" + last_closed_note(repo))
    raise ChantierError(f"several running batches ({', '.join(names)}): pass --batch", EXIT_USAGE)


def require_epoch(epoch: int | None, usage: str, tail: str = "") -> None:
    """A steering command carries `--epoch`: the Foreman's number in its batch. Called before
    anything is written; `usage` is the command's own form, e.g. `take <cr> --epoch <n>`."""
    if epoch is None:
        raise ChantierError(
            f"{usage}: the steering session's command; <n> is your number as Foreman of the "
            f"batch (Foreman n°<n>){tail}",
            EXIT_PRECONDITION,
        )


def check_epoch(b: Batch, epoch: int | None) -> None:
    """A Foreman command carries the number it was started with; a stale Foreman is refused."""
    stale_epoch(b.id, b.record.foreman_epoch, epoch)


def stale_epoch(batch_id: str, current: int, epoch: int | None) -> None:
    """The comparison `check_epoch` makes, also on a record read with no lock (`next`): exit 3."""
    if epoch is not None and epoch != current:
        raise ChantierError(
            f"stale Foreman: Foreman n°{epoch} of {batch_id}, which is now at Foreman "
            f"n°{current}; stop now",
            EXIT_CONFLICT,
        )


def read_batch(repo: Repo, batch_id: str) -> BatchRecord:
    record = read_batch_json(repo.store, repo.batch_dir(batch_id) / "batch.json")
    apply_batch_settings(repo, record)
    return record


def find_cr_batch(repo: Repo, cr_id: str, batch: str | None) -> str:
    """The batch holding a CR: the one given, else the batch that has it (a paused batch
    can hold queued CRs)."""
    cr_id = normalize_cr(cr_id)
    if batch:
        return normalize_batch(batch)
    for d in reversed(repo.batch_folders()):
        b = read_batch_json(repo.store, d / "batch.json")
        if any(c.id == cr_id for c in b.crs):
            return b.id
    raise ChantierError(f"no batch holds {cr_id}", EXIT_USAGE)


RESTORED_NUMBER_FILE = "restored.json"


def next_cr_number(repo: Repo, roots: tuple[Path, ...] = ()) -> int:
    """Choose a number under the lifecycle lock, without reserving it on a failed move."""
    previous: int = repo.config["first_cr_number"] - 1
    # a number `restore` took off a folder: once given, a number is never given again
    previous = max(previous, read_restored_number(repo.store, repo.changes / RESTORED_NUMBER_FILE))
    store = repo.store
    children: list[str] = []
    for root in roots:
        rel = rel_in(store.root, root)
        if store.is_dir(rel):
            children += [n for n in store.listdir(rel) if store.is_dir(f"{rel}/{n}")]
    for child in children:
        name = re.sub(r"^(?:\d{6}-\d{4}-)+", "", child)  # the date is no number
        match = re.match(r"^(?:CR-)?(\d+)(?:-|$)", name, re.I)
        if match:
            previous = max(previous, int(match.group(1)))
    recorded = [
        cr.id
        for batch in repo.batch_folders()
        for cr in read_batch_json(repo.store, batch / "batch.json").crs
    ]
    for cr_id in recorded:
        match = re.fullmatch(r"CR-(\d+)", cr_id)
        if match:
            previous = max(previous, int(match.group(1)))
    return previous + 1
