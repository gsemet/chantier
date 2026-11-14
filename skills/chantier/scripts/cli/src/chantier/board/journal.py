"""The board's journal: one JSON line per write the board made, in `board-journal.jsonl` at the
planning folder's root. It is local (ignored by git); the server is its only writer. "Rescan" is
a line, not a deletion: the entries that count are the lines after the last one."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from chantier.core import clock
from chantier.core.files import read_text
from chantier.core.repo import Repo
from chantier.lifecycle.stages import changes_lock

FILE = "board-journal.jsonl"
KINDS = ("new", "move", "label", "group", "ungroup", "edit", "next-batch")


def _lines(changes: Path) -> list[dict[str, Any]]:
    """Every line of the journal that is a JSON object; a damaged line is skipped."""
    path = changes / FILE
    if not path.is_file():
        return []
    found: list[dict[str, Any]] = []
    for line in read_text(path, "replace").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict):
            found.append(entry)
    return found


def since_rescan(changes: Path) -> list[dict[str, Any]]:
    """The entries after the last `rescan` line."""
    entries = _lines(changes)
    last = max((i for i, e in enumerate(entries) if e.get("kind") == "rescan"), default=-1)
    return entries[last + 1 :]


def _append(repo: Repo, entry: dict[str, Any]) -> None:
    """One line, appended whole under the lifecycle lock."""
    line = json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n"
    with changes_lock(repo), (repo.changes / FILE).open("ab") as f:
        f.write(line.encode("utf-8"))


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
