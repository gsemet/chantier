"""The fingerprint of a project's record and the per-project cache of its state: a `stat` walk,
no read, so an unchanged project answers `304` without opening a file."""

from __future__ import annotations

import fnmatch
import hashlib
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from chantier.core.files import is_lock, rel_in

if TYPE_CHECKING:
    from chantier.store import PlanStore

# The stage folders the state reads whole; the archives and the trash are read for their last
# folders only, so a shallow walk of them is enough (a folder added or removed moves its parent).
DEEP = ("1-inbox", "2-backlog", "3-ready", "4-batch")
SHALLOW = ("5-archives", "6-trash", "5-archives/batches")
# the batch's own files are in `4-batch`
SINGLE = ("seat.json", "next-batch.json", "board-journal.jsonl", "forge-journal.jsonl")
# a `lease hold`'s record at the root: one that starts or ends moves a CR row's `lease.holds`
HOLDS = ".lease-hold.*.run"


def counts_for(rel: str) -> bool:
    """A change at `rel` (under the planning folder, forward slashes) moves what `fingerprint`
    reads: one of the single files, a `lease hold`'s record, anything under a stage folder, or
    an entry of the archives and the trash (or what is in it: its time moves). Locks never."""
    parts = rel.split("/")
    if rel in ("", ".") or any(is_lock(p) for p in parts):
        return False
    if len(parts) == 1 and (parts[0] in SINGLE or fnmatch.fnmatchcase(parts[0], HOLDS)):
        return True
    if parts[0] in DEEP:
        return True
    return any(
        parts[: len(top)] == top and len(parts) <= len(top) + 2
        for top in (s.split("/") for s in SHALLOW)
    )


def _join(base: str, name: str) -> str:
    return name if base == "." else f"{base}/{name}"


def _entry(store: PlanStore, rel: str) -> str:
    info = store.stat(rel)
    return f"{rel}:-" if info is None else f"{rel}:{info[0]}:{info[1]}"


def _deep(store: PlanStore, rel: str) -> list[str]:
    """Every entry under a folder: its size and time, locks left out, the folders walked in
    order. A folder that cannot be read gives its own `-` line."""
    if not store.is_dir(rel):
        return [f"{rel}:-"]
    found: list[str] = []
    for here, dirs, names in store.walk(rel):
        dirs[:] = sorted(d for d in dirs if not is_lock(d))
        found += [_entry(store, _join(here, n)) for n in sorted(dirs + names) if not is_lock(n)]
    return found


def _shallow(store: PlanStore, rel: str) -> list[str]:
    try:
        names = store.listdir(rel)
    except OSError:
        return [f"{rel}:-"]
    return [_entry(store, _join(rel, n)) for n in names if not is_lock(n)]


def fingerprint(store: PlanStore, changes: Path, extra: str = "") -> str:
    """A hash of the size and modification time of what the state reads, and of `extra` (the
    live cost's marks)."""
    base = rel_in(store.root, changes)
    lines = [_entry(store, _join(base, name)) for name in SINGLE]
    lines += [_entry(store, _join(base, n)) for n in store.glob(base, HOLDS)]
    for name in DEEP:
        lines += _deep(store, _join(base, name))
    for name in SHALLOW:
        lines += _shallow(store, _join(base, name))
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
