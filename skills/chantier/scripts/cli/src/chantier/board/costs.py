"""The costs: the recorded figures, the live computation in memory, and the 5-minute rule.

The board never records a cost: recording writes `batch.json`, which is the batch's."""

from __future__ import annotations

import threading
import time
from typing import Any

from chantier.commands.cost.breakdown import cost_groups
from chantier.commands.cost.pricing import sum_unpriced
from chantier.commands.cost.sessions import cost_rows, foreman_uuid
from chantier.core import clock
from chantier.core.errors import ChantierError
from chantier.core.records import read_batch_json
from chantier.core.repo import Repo

RULE_S = 300  # a live figure older than this is computed again, when a page looks at it


def compute(repo: Repo) -> dict[str, Any]:
    """The live figure, the way `chantier cost --by cr` computes it. Reads transcripts; writes
    nothing."""
    folders = repo.batch_folders()
    if not folders:
        raise ChantierError("no batch to price")
    d = read_batch_json(folders[0] / "batch.json")
    rows = cost_rows(repo, d, d.host, foreman_uuid(d))
    groups = cost_groups(repo, d.id, rows, "cr")
    return {
        "spent_usd": sum(r["usd"] for r in rows),
        "unpriced": sum_unpriced(rows),
        "per_cr": {k: {"calls": v[0], "usd": v[1], "unpriced": v[2]} for k, v in groups.items()},
        "at": clock.now(),
        "error": None,
    }


def _failed(e: Exception) -> dict[str, Any]:
    line = " ".join(str(e).split()) or type(e).__name__
    return {
        "spent_usd": None,
        "unpriced": {},
        "per_cr": {},
        "at": clock.now(),
        "error": line if isinstance(e, ChantierError) else f"{type(e).__name__}: {line}",
    }


class Live:
    """One project's live figure: computed in a thread, one at a time."""

    def __init__(self, repo: Repo) -> None:
        self.repo = repo
        self._lock = threading.Lock()
        self._result: dict[str, Any] | None = None
        self._computing = False
        self._done: float | None = None  # monotonic time of the last end

    def snapshot(self) -> dict[str, Any] | None:
        """`None` before any computation, else the figure, with `computing`."""
        with self._lock:
            if self._result is None and not self._computing:
                return None
            kept = self._result or {"spent_usd": None, "unpriced": {}, "per_cr": {}}
            return {"at": None, "error": None, **kept, "computing": self._computing}

    def mark(self) -> str:
        """What a fingerprint holds of the live figure: its time and whether it computes."""
        found = self.snapshot()
        return "-" if found is None else f"{found['at']}|{found['computing']}|{found['error']}"

    def ask(self, running: bool) -> None:
        """The 5-minute rule: a page looks at a running batch whose live figure is missing or
        older than five minutes. Nothing is computed while no page looks."""
        with self._lock:
            old = self._done is None or time.monotonic() - self._done > RULE_S
        if running and old:
            self.start()

    def start(self) -> None:
        """Compute now; a second call while one runs changes nothing."""
        with self._lock:
            if self._computing:
                return
            self._computing = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self) -> None:
        try:
            result = compute(self.repo)
        except Exception as e:  # reported as `live.error`, never raised in the thread
            result = _failed(e)
        with self._lock:
            self._result, self._computing, self._done = result, False, time.monotonic()


def recorded(state: dict[str, Any]) -> dict[str, Any]:
    """The figures the record keeps: what `status --refresh` and `pause` wrote."""
    batch = state["batch"]
    if batch is None:
        return {"spent_usd": None, "budget_usd": None, "unpriced": {}, "per_cr": {}, "at": None}
    return {
        "spent_usd": batch["spent_usd"],
        "budget_usd": batch["budget_usd"],
        "unpriced": batch["unpriced"],
        "per_cr": {c["cr"]: c["cost_usd"] for c in batch["crs"]},
        "at": batch["cost_at"],
    }
