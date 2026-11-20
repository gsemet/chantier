"""The provider `waits`: the approval, pipeline and merge waits of the running batch's CRs, as
interests of kind `pr`.

A wait is met when the forge shows it so: `merge` when the PR or MR is merged, `pipeline` when the
checks of the wait's head are green, `approval` when the review is approved. A met wait is one
`wait-cleared@1` event (the journal keeps it to one line whatever the number of cycles); the hub
only signals, the steering session clears. A wait the forge can no longer see met (`unseen`) is
told by the cycle in the hub's entry, with no journal line. No wait is read in a second query: the
links join the project's one read. A wait on a link of another repository than the batch's PRs is
left out (`outside`), and so is a GitLab `approval` wait while its read is unproved."""

from __future__ import annotations

from typing import Any

from chantier import connectors
from chantier.board.crs import link_of
from chantier.connectors import gitlab as gitlab_connector
from chantier.connectors.base import Facts, Place
from chantier.core import clock, waits
from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo
from chantier.hub import batch_prs
from chantier.hub.interest import PR, Interest


def counting(d: BatchRecord) -> list[tuple[CrEntry, dict[str, Any]]]:
    """The open approval, pipeline and merge waits of the CRs whose waits count, in the batch's
    CR order."""
    return [
        (c, w)
        for c in sorted(d.crs, key=lambda x: x.order)
        if waits.counted(c.status)
        for w in waits.open_of(c.waits)
        if w["type"] in waits.FORGE_TYPES
    ]


def gitlab_unproved(w: dict[str, Any]) -> bool:
    """A GitLab `approval` wait while the read of GitLab's approvals is not proved."""
    link = w.get("link")
    connector = connectors.connector_for(link) if link else None
    return bool(
        w["type"] == "approval"
        and connector is not None
        and connector.name == "gitlab"
        and not gitlab_connector.APPROVAL_PROVED
    )


def batch_place(d: BatchRecord, repo: Repo) -> Place | None:
    """The repository of the batch's open recorded PRs (the first one's), None with none."""
    if not batch_prs.to_read(d):
        return None
    for row in batch_prs.state_of(repo, d):
        connector = connectors.connector_for(row["pr"])
        if connector is not None:
            return connector.place(row["pr"])
    return None


def split(repo: Repo, d: BatchRecord) -> tuple[list[tuple[CrEntry, dict[str, Any]]], set[str]]:
    """The waits the hub reads, and the keys (`<cr> <wait id>`) of the waits of another
    repository than the batch's. With no open recorded PR the first wait link's repository stands
    for the batch's. A link no connector claims, and a GitLab approval while it is unproved, are
    in neither."""
    reference = batch_place(d, repo)
    read: list[tuple[CrEntry, dict[str, Any]]] = []
    outside: set[str] = set()
    for c, w in counting(d):
        link = w.get("link")
        connector = connectors.connector_for(link) if link else None
        if link is None or connector is None or gitlab_unproved(w):
            continue
        place = connector.place(link)
        reference = reference or place
        if place == reference:
            read.append((c, w))
        else:
            outside.add(f"{c.id} {w['id']}")
    return read, outside


def outside(repo: Repo, d: BatchRecord) -> set[str]:
    """The keys (`<cr> <wait id>`) of the open waits on a link of another repository."""
    return split(repo, d)[1]


def met(w: dict[str, Any], found: Facts) -> bool:
    """Whether the facts of the wait's link show it met."""
    kind = w["type"]
    if kind == "merge":
        return bool(found.get("state") == "merged")
    if kind == "pipeline":
        return bool(found.get("head") == w["ref"] and found.get("checks") == "green")
    return bool(found.get("review") == "approved")


def is_unseen(kind: str, ref: str, found: Facts) -> bool:
    """Whether the forge can no longer show the wait met: an approval whose review it cannot
    tell, a pipeline wait whose head moved past its sha, a merge wait whose request closed."""
    if kind == "approval":
        return found.get("review") == "unknown"
    if kind == "pipeline":
        return bool(found.get("head")) and found.get("head") != ref
    return bool(found.get("state") == "closed")


def unseen(interests: list[Interest], facts: dict[str, Facts]) -> list[str]:
    """The keys (`<cr> <wait id>`) of the interests whose link was read and shows the wait as
    one the forge cannot tell about."""
    out = []
    for i in interests:
        kind, ref = i.meta
        if i.ref in facts and is_unseen(kind, ref, facts[i.ref]):
            _, cr, wait = i.by.split()
            out.append(f"{cr} {wait}")
    return out


class Waits:
    name = "waits"
    kinds = frozenset({PR})

    def collect(self, repo: Repo) -> list[Interest]:
        d = batch_prs.running_batch(repo)
        if d is None:
            return []
        return [
            Interest(
                PR,
                w["link"],
                batch_prs.ALWAYS | ({"review"} if w["type"] == "approval" else set()),
                f"{d.id} {c.id} {w['id']}",
                self.name,
                (w["type"], w["ref"]),
            )
            for c, w in split(repo, d)[0]
            if link_of(w["link"])
        ]

    def judge(
        self, repo: Repo, interests: list[Interest], facts: dict[str, Facts]
    ) -> list[dict[str, Any]]:
        out = []
        for i in interests:
            kind, ref = i.meta
            batch, cr, wait = i.by.split()
            found = facts.get(i.ref)
            if found is not None and met({"type": kind, "ref": ref}, found):
                out.append(
                    {
                        "type": "wait-cleared@1",
                        "batch": batch,
                        "cr": cr,
                        "wait": wait,
                        "wait_type": kind,
                        "ref": ref,
                        "seen_at": clock.now(),
                    }
                )
        return out


PROVIDER = Waits()
