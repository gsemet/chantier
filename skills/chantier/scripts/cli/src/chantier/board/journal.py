"""The board's journal: one JSON line per write the board made, in `board-journal.jsonl` at the
planning folder's root. It is local (ignored by git); the server is its only writer. "Rescan" is
a line, not a deletion: the entries that count are the lines after the last one."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from chantier.core import clock
from chantier.core.files import rel_in
from chantier.core.repo import Repo
from chantier.lifecycle.stages import changes_lock

if TYPE_CHECKING:
    from chantier.store import PlanStore

FILE = "board-journal.jsonl"


def _lines(store: PlanStore, changes: Path) -> list[dict[str, Any]]:
    """Every line of the journal that is a JSON object; a damaged line is skipped."""
    path = rel_in(store.root, changes / FILE)
    if not store.is_file(path):
        return []
    found: list[dict[str, Any]] = []
    for line in store.read_text(path, "replace").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict):
            found.append(entry)
    return found


def since_rescan(store: PlanStore, changes: Path) -> list[dict[str, Any]]:
    """The entries after the last `rescan` line."""
    entries = _lines(store, changes)
    last = max((i for i, e in enumerate(entries) if e.get("kind") == "rescan"), default=-1)
    return entries[last + 1 :]


def _append(repo: Repo, entry: dict[str, Any]) -> None:
    """One line, appended whole under the lifecycle lock."""
    # a lone surrogate (a half of an emoji from a page) cannot be UTF-8: it is replaced
    line = json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n"
    data = line.encode("utf-8", errors="replace")
    with changes_lock(repo), (repo.changes / FILE).open("ab") as f:
        f.write(data)


def record(repo: Repo, kind: str, items: list[str], words: str) -> dict[str, Any]:
    """Note one write: its kind, the slugs it touched and the toast's words."""
    entry = {"t": clock.now(), "kind": kind, "items": items, "text": words}
    _append(repo, entry)
    return entry


def rescan(repo: Repo) -> dict[str, Any]:
    """The user told the Chief of Staff to read again: the count starts over."""
    entry = {"t": clock.now(), "kind": "rescan"}
    _append(repo, entry)
    return entry
