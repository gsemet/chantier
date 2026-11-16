"""The PRs page's server side: the batch's PRs read on the forge, judged against the record.

The page reads only: it writes nothing in the record, the planning folder, git or the forge. A
read of the forge is kept for `TTL_S` seconds per project, whatever the number of pages open, and
a failed read keeps the last good one with its time. The `Context` imports this module, so it
never imports the `Context`."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from chantier.board import forge_read
from chantier.commands.forge_stack_gh import pr_parts
from chantier.core import clock
from chantier.core.errors import ChantierError

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
    """The last forge read of each project. A call within `TTL_S` of the last one, for the same
    PRs, gets that read again; a second caller waits for the call in flight and gets its read."""

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
    ) -> tuple[dict[int, dict[str, Any]], str | None, str | None]:
        """The forge's state of each PR by number, when it was read, and the error of the last
        call (the state and time then are the last good read's, empty before any)."""
        with self._lock(key):
            kept = self._entries.get(key)
            at = self._now()
            if not (kept and kept.links == tuple(links) and at - kept.tried < self.ttl):
                kept = self._entries[key] = self._call(kept, links, load, at)
            return kept.forge, kept.read_at, kept.error

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
        return "merged" if c["state"] != "merged" else None
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
    }


def _in_order(batch: dict[str, Any]) -> list[dict[str, Any]]:
    """The CRs with a PR: the merge order first, then the others as the batch lists them."""
    by_id = {c["cr"]: c for c in batch["crs"]}
    first = [by_id[i] for i in batch["merge_order"] if i in by_id]
    rest = [c for c in batch["crs"] if c["cr"] not in batch["merge_order"]]
    return [c for c in [*first, *rest] if c["pr"]]


def answer(reads: ForgeReads, key: str, state: dict[str, Any]) -> dict[str, Any]:
    """The page's answer for a project whose record is `state`. With no batch, or no PR yet, the
    forge is not asked."""
    batch = state["batch"]
    out: dict[str, Any] = {
        "batch": batch["id"] if batch else None,
        "paused": bool(batch and batch["state"] == "paused"),
        "last_batch": None if batch else (state["history"] or [{}])[0].get("id"),
        "rows": [],
        "read_at": None,
        "error": None,
        "all_done": False,
        "now": clock.now(),
    }
    withpr = _in_order(batch) if batch else []
    if not withpr:
        return out
    forge, out["read_at"], out["error"] = reads.get(key, [c["pr"] for c in withpr], forge_read.read)
    branches = {c["branch"]: c["cr"] for c in batch["crs"] if c["branch"]}
    found = [(c, _number(c["pr"])) for c in withpr]
    rows = [row_of(c, forge[n], n, branches) for c, n in found if n in forge]
    out["rows"] = rows
    out["all_done"] = len(rows) == len(withpr) and all(r["state"] in DONE for r in rows)
    return out
