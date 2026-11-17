"""What the board saw on the forge: one JSON line per merge the record does not hold, in
`board-seen.jsonl` at the planning folder's root. It is local (ignored by git); the board's PRs
route is its only writer and `chantier status` its only reader. The board records nothing in a
batch: the line is a signal the Chief of Staff reads at its next `status`.

A line is written once per batch, CR and landed-or-not: a PR merged into another CR's branch is
first read not landed, and one second line follows, once, when a later read finds it landed with
its base (the line then carries `landed_with` and `landed_at`)."""

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
    """Append one line for each merged row the record does not show merged, once per batch, CR
    and landed-or-not: a later read that sees the same merge in the same state writes nothing."""
    pending = [r for r in rows if r.get("why") == "merged"]
    if not pending:
        return
    with changes_lock(repo):
        seen = {
            (e.get("batch"), e.get("cr"), bool(e.get("landed_with"))) for e in read(repo.changes)[0]
        }
        lines = ""
        for r in pending:
            landed = r.get("landed_with") or {}
            if (batch, r["cr"], bool(landed)) in seen:
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
            if landed:
                entry["landed_with"], entry["landed_at"] = landed["cr"], landed["at"]
            lines += json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n"
        if lines:
            with (repo.changes / FILE).open("ab") as f:
                f.write(lines.encode("utf-8", errors="replace"))


def lines(entries: list[dict[str, Any]], batch: str, open_crs: set[str]) -> list[str]:
    """The `status` lines for the Chief of Staff, one per open CR of `batch`: the entry that
    says the PR landed wins, else the first."""
    chosen: dict[str, dict[str, Any]] = {}
    for e in entries:
        cr = e.get("cr")
        if e.get("kind") != "merged" or e.get("batch") != batch or cr not in open_crs:
            continue
        if cr not in chosen or (e.get("landed_with") and not chosen[cr].get("landed_with")):
            chosen[cr] = e
    out: list[str] = []
    for cr, e in chosen.items():
        head = f"board saw merged: {cr} {e.get('pr')}"
        at = e.get("merged_at")
        if e.get("into_cr") and e.get("landed_with"):
            out.append(
                f"{head} into {e['into_cr']}'s branch at {at}, landed with {e['landed_with']} "
                f"at {e.get('landed_at')}; for the Chief of Staff: order merged {cr}"
            )
        elif e.get("into_cr"):
            out.append(
                f"{head} into {e['into_cr']}'s branch at {at}; for the Chief of Staff: not "
                f"landed, tell the user, record nothing until {e['into_cr']} lands"
            )
        else:
            out.append(
                f"{head} into {e.get('into')} at {at}; for the Chief of Staff: order merged {cr}"
            )
    return out
