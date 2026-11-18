"""The PRs page's server side: the batch's PRs read on the forge, judged against the record.

The page reads only: it writes nothing in the record, git or the forge, and nothing in the
planning folder but one line in `forge-journal.jsonl` for a merge the record does not hold. A
read of the forge is kept for `TTL_S` seconds per project and batch shown, whatever the number of
pages open, and a failed read keeps the last good one with its time. The `Context` imports this
module, so it never imports the `Context`."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from chantier.board import forge_read
from chantier.commands.forge_stack_gh import pr_parts
from chantier.core import clock
from chantier.core.errors import ChantierError
from chantier.core.repo import Repo
from chantier.hub import journal

TTL_S = 10.0
MERGED_NOT_RECORDED = "merged on the forge, not recorded yet: tell the Chief of Staff"
DONE = ("merged", "closed")
WORDS = {
    "draft": "draft",
    "closed": "closed",
    "conflicting": "conflicting",
    "failing": "checks failing",
}
Loader = Callable[[list[str]], dict[int, dict[str, Any]]]


@dataclass
class _Entry:
    links: tuple[str, ...]
    tried: float  # monotonic time of the last call to the forge
    forge: dict[int, dict[str, Any]]  # the last good read
    read_at: str | None  # when that good read was made
    error: str | None


class ForgeReads:
    """The last forge read of each project and batch shown (the key). A call within `TTL_S` of the
    last one, for the same PRs, gets that read again; a second caller waits for the call in
    flight and gets its read."""

    def __init__(self, ttl: float = TTL_S, now: Callable[[], float] = time.monotonic) -> None:
        self.ttl = ttl
        self._now = now
        self._entries: dict[str, _Entry] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def _lock(self, key: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(key, threading.Lock())

    def get(
        self, key: str, links: list[str], load: Loader
    ) -> tuple[dict[int, dict[str, Any]], str | None, str | None, bool]:
        """The forge's state of each PR by number, when it was read, the error of the last call
        (the state and time then are the last good read's, empty before any), and whether this
        call asked the forge (False: a kept read, which signals nothing)."""
        with self._lock(key):
            kept = self._entries.get(key)
            at = self._now()
            if kept and kept.links == tuple(links) and at - kept.tried < self.ttl:
                return kept.forge, kept.read_at, kept.error, False
            kept = self._entries[key] = self._call(kept, links, load, at)
            return kept.forge, kept.read_at, kept.error, True

    @staticmethod
    def _call(kept: _Entry | None, links: list[str], load: Loader, at: float) -> _Entry:
        try:
            return _Entry(tuple(links), at, load(links), clock.now(), None)
        except (ChantierError, OSError) as e:
            line = " ".join(str(e).split()) or type(e).__name__
            good = (kept.forge, kept.read_at) if kept else ({}, None)
            return _Entry(tuple(links), at, good[0], good[1], line)


def ready_now(c: dict[str, Any], f: dict[str, Any]) -> bool:
    """Ready to merge now (Q6): the record says so, and the forge says the PR is open, not a
    draft, not conflicting, not being checked, with its checks green or none to run. The forge
    alone never makes a PR ready."""
    return bool(
        c["to_review"]
        and f["state"] == "open"
        and not f["conflicting"]
        and not f["checking"]
        and f["checks"] in ("green", "none")
    )


def why_not(c: dict[str, Any], f: dict[str, Any]) -> str | None:
    """The code of a disagreement between the record and the forge, else None: `merged` (merged
    on the forge, not in the record), or `draft`, `closed`, `conflicting`, `failing` (ready in the
    record, not on the forge)."""
    if f["state"] == "merged":
        # a release PR already merged is in the record as `pr_merged`, whatever the CR's state
        return "merged" if c["state"] != "merged" and not c.get("pr_merged") else None
    if not c["to_review"]:
        return None
    if f["state"] in ("draft", "closed"):
        return str(f["state"])
    if f["conflicting"]:
        return "conflicting"
    return "failing" if f["checks"] == "failing" else None


def disagrees(c: dict[str, Any], f: dict[str, Any]) -> str | None:
    """A few words when the record and the forge disagree, else None."""
    code = why_not(c, f)
    if code is None:
        return None
    if code == "merged":
        return MERGED_NOT_RECORDED
    return f"ready in the record, {WORDS[code]} on the forge"


def _number(link: str) -> int | None:
    """The PR number of a link, None for a link that is neither a PR nor an MR."""
    try:
        return int(pr_parts(link)[3])
    except ChantierError:
        return None


def row_of(
    c: dict[str, Any], f: dict[str, Any], number: int, branches: dict[str, str]
) -> dict[str, Any]:
    """One CR's row: the record's CR `c` against its PR on the forge `f`. `branches` maps a
    branch to the CR whose branch it is."""
    merged = f["state"] == "merged"
    return {
        "cr": c["cr"],
        "title": c["title"],
        "kind": c["kind"],
        "pr": c["pr"],
        "number": number,
        "state": f["state"],
        "conflicting": f["conflicting"],
        "checking": f["checking"],
        "checks": f["checks"],
        "merged_into": {"branch": f["base"], "cr": branches.get(f["base"])} if merged else None,
        "ready_now": ready_now(c, f),
        "disagrees": disagrees(c, f),
        "why": why_not(c, f),
        "merged_at": f["merged_at"],
        "closed_at": f["closed_at"],
        "opened_at": f.get("opened_at"),
        "updated_at": f.get("updated_at"),
        "landed_with": None,  # `answer` fills it once all rows of the read are built
    }


def _instant(text: Any) -> datetime | None:
    """An ISO 8601 time the forge gave as an instant (UTC when it names no zone), else None."""
    if not isinstance(text, str):
        return None
    try:
        t = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=UTC)


def landed_with(row: dict[str, Any], by_cr: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """For a row merged into the branch of another CR of the batch: `{"cr", "at"}` of the CR whose
    PR reached a branch that is no CR's, when each PR of the chain is merged on the forge at the
    same time as the one it carries or later. None for a merge into no CR's branch, a base not
    merged, merged before this PR, a missing time, a missing row or a cycle."""
    into = row.get("merged_into") or {}
    cur, since, walked = into.get("cr"), _instant(row.get("merged_at")), {row["cr"]}
    while cur is not None and since is not None and cur not in walked:
        walked.add(cur)
        base = by_cr.get(cur)
        at = _instant(base.get("merged_at")) if base else None
        if not base or base.get("state") != "merged" or at is None or at < since:
            return None
        cur_into = (base.get("merged_into") or {}).get("cr")
        if cur_into is None:
            return {"cr": cur, "at": base["merged_at"]}
        cur, since = cur_into, at
    return None


def _in_order(batch: dict[str, Any]) -> list[dict[str, Any]]:
    """The CRs with a PR: the merge order first, then the others as the batch lists them."""
    by_id = {c["cr"]: c for c in batch["crs"]}
    first = [by_id[i] for i in batch["merge_order"] if i in by_id]
    rest = [c for c in batch["crs"] if c["cr"] not in batch["merge_order"]]
    return [c for c in [*first, *rest] if c["pr"]]


def _closed_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    """A closed record's CRs that have a PR, as the CR shape `row_of` reads: by `order` when the
    record has it, else as listed. The record keeps no kind, branch, review flag nor state."""
    listed = [
        (c.get("order", i), i, c) for i, c in enumerate(record.get("crs") or []) if c.get("pr")
    ]
    return [
        {
            "cr": c["cr"],
            "title": c.get("title", ""),
            "kind": None,
            "branch": None,
            "to_review": False,
            "state": "merged" if c.get("result") == "merged" else c.get("result"),
            "pr": c["pr"],
        }
        for _, _, c in sorted(listed, key=lambda x: (x[0], x[1]))
    ]


def _shown(
    state: dict[str, Any], want: str | None
) -> tuple[str | None, list[dict[str, Any]], bool, str | None]:
    """The batch the page shows: its id, the CRs with a PR, whether it is closed, and an error.
    The batch in `4-batch/` for no id or its own; else the closed record of that id, or the
    newest closed one for no id with no batch in `4-batch/`."""
    batch = state["batch"]
    if batch and want in (None, "", batch["id"]):
        return batch["id"], _in_order(batch), False, None
    closed = [r for r in state["history"] if isinstance(r, dict) and r.get("state") == "closed"]
    pick = next((r for r in closed if r.get("batch") == want), None) if want else None
    pick = pick or (closed[0] if closed and not want else None)
    if pick:
        return pick["batch"], _closed_rows(pick), True, None
    return None, [], False, f"unknown batch {want}" if want else None


def _closed_row(row: dict[str, Any]) -> dict[str, Any]:
    """A closed batch's row: the record says nothing of readiness, nor of where a PR landed."""
    row["why"] = row["disagrees"] = None
    row["ready_now"] = False
    if row["merged_into"]:
        row["merged_into"]["cr"] = None
    return row


def rows_of(
    withpr: list[dict[str, Any]],
    forge: dict[int, dict[str, Any]],
    branches: dict[str, str],
    closed: bool = False,
) -> list[dict[str, Any]]:
    """The rows of the CRs `withpr` against the forge's read, with where each merged PR landed:
    the one function the page and the forge hub both judge with, so they never disagree."""
    found = [(c, _number(c["pr"])) for c in withpr]
    rows = [row_of(c, forge[n], n, branches) for c, n in found if n in forge]
    if closed:
        rows = [_closed_row(r) for r in rows]
    by_cr = {r["cr"]: r for r in rows}
    for r in rows:
        r["landed_with"] = landed_with(r, by_cr)
    return rows


def answer(
    reads: ForgeReads,
    key: str,
    state: dict[str, Any],
    repo: Repo | None = None,
    batch: str | None = None,
) -> dict[str, Any]:
    """The page's answer for a project whose record is `state`, for the batch `batch` (none: the
    batch in `4-batch/`, else the newest closed one). With no batch, an unknown one or no PR yet,
    the forge is not asked. A closed batch is read on the forge, judged against nothing, and never
    signalled. With a `repo`, a merge the forge shows and the record does not, in the batch in
    `4-batch/`, is left as one line in `forge-journal.jsonl` (the only write)."""
    live = state["batch"]
    shown, withpr, closed, error = _shown(state, batch)
    out: dict[str, Any] = {
        "batch": shown,
        "paused": bool(live and shown == live["id"] and live["state"] == "paused"),
        "closed": closed,
        "rows": [],
        "read_at": None,
        "error": error,
        "all_done": False,
        "now": clock.now(),
    }
    if not withpr:
        return out
    forge, out["read_at"], out["error"], fresh = reads.get(
        f"{key}:{shown}", [c["pr"] for c in withpr], forge_read.read
    )
    branches = {c["branch"]: c["cr"] for c in live["crs"] if c["branch"]} if live else {}
    rows = rows_of(withpr, forge, {} if closed else branches, closed)
    out["rows"] = rows
    if repo is not None and live and fresh and not out["error"] and not closed:
        journal.append(repo, journal.merged_events(live["id"], rows), "board")
    out["all_done"] = len(rows) == len(withpr) and all(r["state"] in DONE for r in rows)
    return out
