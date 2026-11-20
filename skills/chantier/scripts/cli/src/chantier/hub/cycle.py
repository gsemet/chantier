"""The hub's cycle: for every project of the surface whose batch in `4-batch/` is running, one
forge read of the batch's PRs, judged as the board's PRs page judges them (`prs.rows_of`), and the
events appended to the project's journal. It runs no git command, records nothing in a batch,
messages no agent and writes nothing but the journals and the `hub` entry of `server.json`.

`forge_read.read` is the one seam: tests replace it."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from chantier import __version__
from chantier.board import forge_read, prs
from chantier.board.crs import link_of
from chantier.board.projects import project_name
from chantier.core import clock
from chantier.core.batch import apply_batch_settings
from chantier.core.errors import ChantierError
from chantier.core.records import BatchRecord, read_batch_json
from chantier.core.repo import Repo, surface_projects
from chantier.hub import journal, state
from chantier.hub import times as hub_times
from chantier.stacks import READY_TO_MERGE, ready_word


def running_batch(repo: Repo) -> BatchRecord | None:
    """The batch in `4-batch/` when it is running (a paused or closed one is not followed)."""
    path = repo.batches / "batch.json"
    if not path.is_file():
        return None
    try:
        d = read_batch_json(path)
    except (OSError, ValueError, ChantierError):
        return None
    return d if d.status == "running" else None


def state_of(repo: Repo, d: BatchRecord) -> list[dict[str, Any]]:
    """The batch's CRs with a PR, in the shape `prs.row_of` reads. The batch runs on the settings
    it was opened with (`apply_batch_settings`), as the board reads it."""
    apply_batch_settings(repo, d)
    return [
        {
            "cr": c.id,
            "title": c.title,
            "kind": c.kind if c.kind in {"fix", "release"} else None,
            "pr": link_of(c.pr),
            "branch": c.branch,
            "to_review": ready_word(d, c, repo) == READY_TO_MERGE,
            "state": c.status,
        }
        for c in sorted(d.crs, key=lambda x: x.order)
        if link_of(c.pr)
    ]


def to_read(d: BatchRecord) -> bool:
    """Whether a CR has a PR the record holds neither merged nor cancelled."""
    return any(link_of(c.pr) and c.status not in ("merged", "cancelled") for c in d.crs)


def events_of(
    d: BatchRecord, withpr: list[dict[str, Any]], forge: dict[int, dict[str, Any]]
) -> list[dict[str, Any]]:
    """The journal events the forge's read shows: a `merged` event for each row the forge shows
    merged and the record does not, a `checks-red` for each CR ready to merge in the record, open
    on the forge, whose checks are failing."""
    branches = {c["branch"]: c["cr"] for c in withpr if c["branch"]}
    rows = prs.rows_of(withpr, forge, branches)
    events = journal.merged_events(d.id, rows)
    ready = {c["cr"] for c in withpr if c["to_review"]}
    for r in rows:
        head = forge[r["number"]].get("head")
        if r["cr"] in ready and r["state"] == "open" and r["checks"] == "failing" and head:
            events.append(journal.red_event(d.id, r["cr"], r["pr"], str(head)))
    return events


class Hub:
    """What the process that holds the hub lock (the surface server, or a watcher when none
    runs) does: its cycle and its `hub` entry. An entry that cannot be written is written again
    at the next cycle; the lock is kept."""

    def __init__(self, repo: Repo, version: str = __version__) -> None:
        self.repo = repo
        self.git_dir: Path = repo.git_dir
        self.record = state.hub_record(version)
        self.last: float | None = None  # the monotonic time of the last cycle
        self._repos: dict[str, Repo] = {}
        self.publish()

    def publish(self) -> None:
        """Write the `hub` entry; a failed write is left to the next cycle."""
        with contextlib.suppress(OSError):
            state.write_hub(self.git_dir, self.record)

    def due(self, now: float) -> bool:
        return self.last is None or now - self.last >= hub_times.cycle_s()

    def projects(self) -> list[Repo]:
        """Every project of the surface, read again at each cycle (a project is built once: it
        costs two git calls); the one project of a repository."""
        if not self.repo.external:
            return [self.repo]
        root = self.repo.surface_root
        found = {}
        for name in surface_projects(root):
            if name not in self._repos:
                self._repos[name] = Repo._external(root, str(root / "projects" / name))
            found[name] = self._repos[name]
        return list(found.values())

    def cycle(self, now: float) -> None:
        """One cycle: each project in turn; a forge error goes in the `hub` entry and the cycle goes
        on. An event its type's model refuses (from what the forge returned) is set aside, the
        others are written, and the entry's `error` is `skipped: <message>` beside its `read_at`."""
        self.last = now
        for repo in self.projects():
            d = running_batch(repo)
            if d is None or not to_read(d):
                continue
            entry = self.record["projects"].setdefault(
                project_name(repo), {"read_at": None, "error": None, "error_at": None}
            )
            withpr = state_of(repo, d)
            try:
                forge = forge_read.read([c["pr"] for c in withpr])
            except (ChantierError, OSError) as e:
                entry["error"] = " ".join(str(e).split()) or type(e).__name__
                entry["error_at"] = clock.now()
                continue
            entry["read_at"], entry["error"], entry["error_at"] = clock.now(), None, None
            accepted, refused = journal.set_aside(events_of(d, withpr, forge))
            journal.append(repo, accepted, "hub")
            if refused:
                entry["error"], entry["error_at"] = journal.skipped(refused), clock.now()
        self.publish()

    def note_error(self, e: Exception) -> None:
        """A cycle that raised outside a forge read: every project's entry carries the error."""
        for entry in self.record["projects"].values():
            entry["error"] = " ".join(str(e).split()) or type(e).__name__
            entry["error_at"] = clock.now()
        self.publish()

    def close(self) -> None:
        with contextlib.suppress(OSError):  # an entry left behind names a dead process
            state.remove_entry(self.git_dir, state.HUB, self.record["pid"])
