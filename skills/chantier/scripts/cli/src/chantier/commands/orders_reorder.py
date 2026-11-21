"""The order of the open CRs when a batch changes mode: the ones handed back ready first."""

from __future__ import annotations

from chantier.core.batch import Batch
from chantier.core.records import CrEntry, read_events
from chantier.rails import ENDED, is_held


def ready_times(b: Batch) -> dict[str, int]:
    """When each CR was last handed back ready: the place of its last `handback ... ready` event
    in the batch's `events.jsonl`, which is in time order (a stamp has one-second resolution)."""
    when: dict[str, int] = {}
    for i, e in enumerate(read_events(b.repo.store, b.dir)):
        if e.kind == "handback" and e.result == "ready" and e.cr:
            when[e.cr] = i
    return when


def chains_kept(seq: list[CrEntry]) -> list[CrEntry]:
    """A CR below one of its open `after` CRs moves just above the highest of them."""
    seq = list(seq)
    for _ in range(len(seq) * len(seq) + 1):
        ids = [x.id for x in seq]
        for c in seq:
            places = [ids.index(a) for a in c.after if a in ids]
            if places and max(places) > ids.index(c.id):
                seq.remove(c)
                seq.insert(max(places), c)  # the highest moved down one place by the removal
                break
        else:
            return seq
    return seq


def release_holds(b: Batch) -> list[str]:
    """The batch leaves a stack: no stack order to be out of any more, so every ready held CR is
    let go, before `reorder` computes the places; a CR held while it was live (not `ready`) keeps
    its hold. `stack` renumbers only the CRs of the chain, so a held CR's order can equal another's:
    it first takes a unique one, above all."""
    top = max((x.order for x in b.record.crs), default=0)
    out = []
    for c in b.record.crs:
        if not c.held:
            continue
        if is_held(c):
            top += 1
            c.order = top
            if c.status != "ready":
                out.append(
                    f"{c.id}: still held (order {c.held}): it was live; only "
                    f"`order unhold {c.id}` releases it"
                )
                continue
            out.append(f"{c.id}: no longer held (the batch leaves the stack)")
        c.unset("held")
    return out


def reorder(b: Batch) -> list[str]:
    """MS-Q3: the open CRs (a fix and the release keep their place, merged and cancelled ones are
    never touched) take the places they hold, the ones handed back ready first, in the order they
    became ready, then the others in their order; the chains (`after`) kept."""
    open_ = sorted(
        (x for x in b.record.crs if x.status not in ENDED and x.kind not in {"fix", "release"}),
        key=lambda x: x.order,
    )
    when = ready_times(b)
    ready = sorted((x for x in open_ if x.status == "ready"), key=lambda x: when.get(x.id, -1))
    seq = chains_kept(ready + [x for x in open_ if x.status != "ready"])
    for place, c in zip([x.order for x in open_], seq, strict=True):
        if c.order != place:
            b.touch(c, order=place)
    return [x.id for x in seq]
