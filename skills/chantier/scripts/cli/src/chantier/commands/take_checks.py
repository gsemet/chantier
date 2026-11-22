"""What `take` asks of a CR before it changes anything, written once: `take` and `access` both
call it, so a check added here is answered by both."""

from __future__ import annotations

from chantier.commands.driver_checks import check_release_branch
from chantier.core import leases
from chantier.core.records import BatchRecord, CrEntry, Lease
from chantier.core.repo import Repo
from chantier.lifecycle.stages import cr_directory, stage_layout
from chantier.rails import check_take
from chantier.stack_apart import refuse_parked_waiting
from chantier.stacks import refuse_held


def check_take_all(
    repo: Repo,
    d: BatchRecord,
    c: CrEntry,
    *,
    note: str | None,
    reclaim: bool,
) -> Lease | None:
    """The checks from a CR held out of the stack to the published paths, in `take`'s order,
    first refusal raised; returns the last lease for `--reclaim` to end. The batch and the
    epoch, checked before it, are `take`'s own (a check added before this one is not answered
    by `access`)."""
    refuse_held(c)
    refuse_parked_waiting(c)
    check_take(d, c, note)
    old = leases.check_free(repo, d, c.id, reclaim)
    if c.status != "working":
        check_release_branch(repo, d, c)
    paths, here = stage_layout(repo), cr_directory(repo, c)
    there = paths["actives"] / here.name if here.parent == paths["pending"] else here
    repo.check_publish([here, there, there / "work"])
    return old
