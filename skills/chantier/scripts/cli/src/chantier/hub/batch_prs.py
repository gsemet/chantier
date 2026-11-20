"""The provider `batch`: the PRs of the running batch in `4-batch/`, as interests of kind `pr`.

It judges them as the board's PRs page judges them (`prs.rows_of`): a `merged` event for each row
the forge shows merged and the record does not, a `checks-red` for each CR ready to merge in the
record whose open PR has failing checks."""

from __future__ import annotations

from typing import Any

from chantier.board import prs
from chantier.board.crs import link_of
from chantier.connectors import connector_for
from chantier.connectors.base import Facts
from chantier.core.batch import apply_batch_settings
from chantier.core.errors import ChantierError
from chantier.core.records import BatchRecord, read_batch_json
from chantier.core.repo import Repo
from chantier.hub import journal
from chantier.hub.interest import Interest
from chantier.stack_words import READY_TO_MERGE, ready_word

ALWAYS = frozenset({"state", "checks"})


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


class BatchPrs:
    name = "batch"
    kinds = frozenset({"pr"})

    def collect(self, repo: Repo) -> list[Interest]:
        d = running_batch(repo)
        if d is None or not to_read(d):
            return []
        return [
            Interest("pr", c["pr"], ALWAYS, f"{d.id} {c['cr']}", self.name)
            for c in state_of(repo, d)
        ]

    def judge(
        self, repo: Repo, interests: list[Interest], facts: dict[str, Facts]
    ) -> list[dict[str, Any]]:
        d = running_batch(repo)
        if d is None:
            return []
        forge: dict[int, Facts] = {}
        for link, found in facts.items():
            connector = connector_for(link)
            if connector is not None:
                forge[connector.number(link)] = found
        return events_of(d, state_of(repo, d), forge)


PROVIDER = BatchPrs()
