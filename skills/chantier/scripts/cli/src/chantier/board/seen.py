"""What the board saw on the forge: one JSON line per merge the record does not hold, in
`board-seen.jsonl` at the planning folder's root. It is local (ignored by git); the board's PRs
route is its only writer and `chantier status` its only reader. The board records nothing in a
batch: the line is a signal the Chief of Staff reads at its next `status`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from chantier.core import clock
from chantier.core.files import read_text
from chantier.core.repo import Repo
from chantier.lifecycle.stages import changes_lock

FILE = "board-seen.jsonl"


def read(changes: Path) -> tuple[list[dict[str, Any]], list[int]]:
    """The lines that are JSON objects, and the numbers (from 1) of the lines that are not."""
    path = changes / FILE
    if not path.is_file():
        return [], []
    found: list[dict[str, Any]] = []
    bad: list[int] = []
    for n, line in enumerate(read_text(path, "replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            entry = None
        if isinstance(entry, dict):
            found.append(entry)
        else:
            bad.append(n)
    return found, bad


def signal(repo: Repo, batch: str, rows: list[dict[str, Any]]) -> None:
    """Append one line for each merged row the record does not show merged, once per batch and
    CR: a later read that sees the same merge writes nothing."""
    pending = [r for r in rows if r.get("why") == "merged"]
    if not pending:
        return
    with changes_lock(repo):
        seen = {(e.get("batch"), e.get("cr")) for e in read(repo.changes)[0]}
        lines = ""
        for r in pending:
            if (batch, r["cr"]) in seen:
                continue
            into = r["merged_into"] or {}
            entry = {
                "t": clock.now(),
                "kind": "merged",
                "batch": batch,
                "cr": r["cr"],
                "pr": r["pr"],
                "into": into.get("branch"),
                "into_cr": into.get("cr"),
                "merged_at": r["merged_at"],
            }
            lines += json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n"
        if lines:
            with (repo.changes / FILE).open("ab") as f:
                f.write(lines.encode("utf-8", errors="replace"))
