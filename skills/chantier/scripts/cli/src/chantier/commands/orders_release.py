"""The orders of the release CR and of its fixes."""

from __future__ import annotations

from chantier.commands.opening import add_cr, declare_dependencies, release_waits_for_all
from chantier.core.batch import Batch
from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.records import CrEntry, ReleaseGrant
from chantier.rails import ENDED, alone, is_release


def release_cr(b: Batch, kind: str, cr_id: str) -> ReleaseGrant:
    release = b.record.release or ReleaseGrant()
    if release.cr != cr_id:
        raise ChantierError(
            f"order {kind} names the batch's release CR ({release.cr or 'none'})", EXIT_USAGE
        )
    return release


def refused(usage: str, value: str, wanted: str) -> ChantierError:
    why = f"{value!r} is not {wanted}" if value.strip() else f"no value given: {wanted}"
    return ChantierError(f"{usage}: {why}", EXIT_USAGE)


def _started(c: CrEntry) -> bool:
    """A release has started when it ran an attempt or a Driver holds it or it is handed back; a
    merged release PR puts it back to `queued`, which `attempts` still tells."""
    return bool(c.attempts > 0 or c.status != "queued")


def add_release(b: Batch, note: str) -> list[str]:
    """`order add --release`: the batch's release CR, with the default grant, waiting for every
    other CR; the grant and the approvals are the user's word after (`order grant`, `approve`)."""
    open_ = next((x for x in b.record.crs if is_release(x) and x.status != "cancelled"), None)
    if open_:
        raise ChantierError(
            f"order add --release: {open_.id} is already the release CR of "
            f"{b.id}; a batch has one. Put the second release in the next batch, "
            "once this one is closed"
        )
    c = add_cr(b, note, kind="release")
    b.record.release = ReleaseGrant(autonomous=0, fixes=False, published=0, cr=c.id)
    declare_dependencies(b, [c])
    release_waits_for_all(b)
    waits = f", after {', '.join(c.after)}" if c.after else ""
    word = (
        ""
        if alone(b.record.crs, c)
        else (
            "; it starts once every other CR is handed back ready (stack, series) or merged "
            "(parallel), "
            "and its PR is the user's to merge"
        )
    )
    return [
        f"added {c.id} (release), queued{waits}; each irreversible action waits for the "
        f"merge of the release PR (`order grant` changes it){word}"
    ]


def join_release(b: Batch, added: CrEntry) -> None:
    """A CR joined the batch: the release waits for it, and the user's word to run the procedure
    given before no longer holds, since what ships changed. A release that started takes no new
    CR."""
    rel = next((x for x in b.record.crs if is_release(x) and x.status not in ENDED), None)
    if rel is None:
        return
    release_waits_for_all(b)
    if rel.procedure:
        rel.unset("procedure")
        rel.append("notes", f"procedure word voided: {added.id} was added")
        b.touch(rel)
        b.log("confirm-void", rel.id, added=added.id)


def check_release_open(b: Batch) -> None:
    rel = next((x for x in b.record.crs if is_release(x) and x.status not in ENDED), None)
    if rel and _started(rel):
        raise ChantierError(
            f"order add: {rel.id} has started ({rel.status}, attempts "
            f"{rel.attempts}) and ships the work under it. Add "
            f"a fix with `order add --fix-for {rel.id}`, or put the new work "
            "in the next batch"
        )
