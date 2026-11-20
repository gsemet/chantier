"""What `status`, `handoff`, `take` and `wait` print of a CR's open waits: the facts line, the
status segment, and the notes for a wait the forge hub cannot read."""

from __future__ import annotations

from typing import Any

from chantier.core import waits
from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo

GITLAB_NOTE = " (GitLab approval: cleared by hand until proved)"
OUTSIDE_NOTE = " (not in the batch's repository: cleared by hand)"
UNSEEN_NOTE = " (the forge cannot tell: cleared by hand)"


def unseen_keys(repo: Repo) -> set[str]:
    """The `<cr> <wait id>` keys the live forge hub's entry for this project names as waits the
    forge cannot tell about; none with no hub running."""
    from chantier.hub import state  # noqa: PLC0415 - slow import

    record = state.live_entry(repo.git_dir, state.HUB) or {}
    mine = (record.get("projects") or {}).get((repo.project_dir or repo.root).name) or {}
    found = mine.get("waits_unseen")
    return {str(x) for x in found} if isinstance(found, list) else set()


def open_counted(c: CrEntry) -> list[dict[str, Any]]:
    """The CR's open waits, none for a CR the record holds merged, dropped or cancelled."""
    return waits.open_of(c.waits) if waits.counted(c.status) else []


def _suffix(w: dict[str, Any], key: str, notes: tuple[set[str], set[str]]) -> str:
    from chantier.hub import waits as hub_waits  # noqa: PLC0415 - slow import

    unseen, outside = notes
    if hub_waits.gitlab_unproved(w):
        return GITLAB_NOTE
    if key in outside:
        return OUTSIDE_NOTE
    return UNSEEN_NOTE if key in unseen else ""


def what(w: dict[str, Any]) -> str:
    since = f" since {waits.hhmm(w['since'])}"
    if w["type"] == "answer":
        return f'{w["id"]} answer{since}: "{w["ref"]}"'
    shown = waits.short(w["ref"]) if w["type"] == "pipeline" else w["ref"]
    return f"{w['id']} {w['type']} on {shown}{since}"


def wait_line(repo: Repo, d: BatchRecord, c: CrEntry) -> str | None:
    """`<cr> waits for: w1 answer since HH:MM: "<ref>"; ...` for a CR with open waits, else None."""
    mine = open_counted(c)
    if not mine:
        return None
    notes = _notes(repo, d, mine)
    parts = [what(w) + _suffix(w, f"{c.id} {w['id']}", notes) for w in mine]
    return f"{c.id} waits for: " + "; ".join(parts)


def _notes(repo: Repo, d: BatchRecord, mine: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    """(the waits the forge cannot tell about, the waits of another repository)."""
    if not any(w["type"] in waits.FORGE_TYPES for w in mine):
        return set(), set()
    from chantier.hub import waits as hub_waits  # noqa: PLC0415 - slow import

    return unseen_keys(repo), hub_waits.outside(repo, d)


def status_segment(repo: Repo, c: CrEntry) -> str:
    """` | waits: <type>[, <type>...]` for a status row, with `(the forge cannot tell...)` after
    a type the hub's entry names; empty for a CR with no open wait."""
    mine = open_counted(c)
    if not mine:
        return ""
    unseen = unseen_keys(repo) if any(w["type"] in waits.FORGE_TYPES for w in mine) else set()
    types = [w["type"] + (UNSEEN_NOTE if f"{c.id} {w['id']}" in unseen else "") for w in mine]
    return " | waits: " + ", ".join(types)


def open_keys(d: BatchRecord) -> frozenset[tuple[str, str]]:
    """`(cr, wait id)` of every open wait that counts, for `status`'s `wait-cleared@1` lines."""
    return frozenset((c.id, w["id"]) for c in d.crs for w in open_counted(c))
