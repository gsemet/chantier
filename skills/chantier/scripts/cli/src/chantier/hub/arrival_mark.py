"""The arrivals told: `arrivals-told.json`, local (never published), holds the highest `seq` of an
`arrived@1` line already told, by a watcher, by `watch --once` or by the listing of `seat` and
`status`; the mark only moves forward."""

from __future__ import annotations

import json
from typing import Any

from chantier.core.repo import Repo
from chantier.hub import journal
from chantier.lifecycle.stages import changes_lock

TOLD_FILE = "arrivals-told.json"
ARRIVALS_SHOWN = 10


def told_mark(repo: Repo) -> int:
    """The highest `seq` of an `arrived@1` line already told, 0 for none (or an unreadable file)."""
    store = repo.store
    try:
        data = json.loads(store.read_text(TOLD_FILE)) if store.is_file(TOLD_FILE) else None
    except (OSError, ValueError):
        return 0
    seq = data.get("seq") if isinstance(data, dict) else None
    return seq if type(seq) is int else 0


def move_told_mark(repo: Repo, seq: int) -> None:
    """Move the mark to `seq`, under the lifecycle lock: never back."""
    with changes_lock(repo):
        if seq > told_mark(repo):
            repo.store.write_json(TOLD_FILE, {"seq": seq})


def tell_arrivals(repo: Repo, lines: list[dict[str, Any]]) -> None:
    """The mark moves to the highest `seq` of an `arrived@1` line among these lines, if any."""
    seqs = [
        e["seq"]
        for e in lines
        if e.get("type") == "arrived@1" and type(e.get("seq")) is int and journal.listed(e)
    ]
    if seqs:
        move_told_mark(repo, max(seqs))


def arrival_lines(
    entries: list[dict[str, Any]], told: int, cli: str = "chantier"
) -> tuple[list[str], int]:
    """The lines of the `arrived@1` entries past the mark, in `seq` order, at most
    `ARRIVALS_SHOWN`, then `and <k> more arrivals: <cli> watch --once --after <seq of the last
    shown>`; and the `seq` to move the mark to (the last one shown, 0 for none). A line of a refused
    payload or of no published type is skipped, as in `lines`."""
    found = sorted(
        (
            e
            for e in entries
            if journal.listed(e)
            and e.get("type") == "arrived@1"
            and type(e.get("seq")) is int
            and e["seq"] > told
        ),
        key=lambda e: e["seq"],
    )
    shown = found[:ARRIVALS_SHOWN]
    out = [journal.event_text(e) for e in shown]
    if len(found) > len(shown):
        more = len(found) - len(shown)
        out.append(f"and {more} more arrivals: {cli} watch --once --after {shown[-1]['seq']}")
    return out, int(shown[-1]["seq"]) if shown else 0
