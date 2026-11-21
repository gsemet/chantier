"""The CRs that keep a batch open at its end: a parked, held or blocked CR, and the queued CRs
that wait only for such CRs. `close` and the batch's end say each one's way back, written here
once (`endpause` re-exports `way_back`)."""

from __future__ import annotations

from chantier.core.records import BatchRecord, CrEntry
from chantier.core.waits import open_counted, what
from chantier.rails import ENDED, is_held, is_parked, unmet

DESTINATIONS = "trash|P1..P4|3-ready"


def _kind(c: CrEntry) -> str:
    return "parked" if is_parked(c) else "held" if is_held(c) else "blocked"


def _out(c: CrEntry) -> bool:
    """A CR that is out of the work until someone brings it back."""
    return c.status == "blocked" or is_held(c)


def _waited_ids(d: BatchRecord, c: CrEntry) -> list[str]:
    return [u.split()[0] for u in unmet(d, c)]


def _ends(ids: list[str], roots: dict[str, list[str]]) -> list[str]:
    """The CRs out of the work that `ids` come to, through the settled queued ones."""
    return list(dict.fromkeys(r for i in ids for r in roots.get(i, [i])))


def carried(d: BatchRecord) -> dict[str, list[str]]:
    """The queued CRs (the release included) with unmet waits that are only blocked or held CRs,
    directly or through such queued CRs, each with the CRs it waits for in the end."""
    found = {x.id: x for x in d.crs}
    roots: dict[str, list[str]] = {}
    for _ in d.crs:  # each pass settles at least one more queued CR, or none is left to settle
        for c in d.crs:
            ids = _waited_ids(d, c)
            if c.status != "queued" or c.id in roots or not ids:
                continue
            if all(i in found and (_out(found[i]) or i in roots) for i in ids):
                roots[c.id] = _ends(ids, roots)
    return roots


def left(d: BatchRecord) -> list[CrEntry]:
    """The CRs that keep the batch open, by order, when every CR is ended or one of them and at
    least one is not ended; none otherwise."""
    queued = carried(d)
    rest = [c for c in d.crs if c.status not in ENDED]
    if not rest or not all(_out(c) or c.id in queued for c in rest):
        return []
    return sorted(rest, key=lambda c: c.order)


def way_back(d: BatchRecord, c: CrEntry) -> str:
    """One CR's way back: the text `close` and `left_open` give."""
    take = f'`take {c.id} --note "wait cleared: <what>" --epoch <n>`'
    if is_parked(c):
        mine = open_counted(c)
        if not mine:
            return f"{c.id} is parked, its wait cleared: {take}"
        shown = "; ".join(what(w) for w in mine)
        clear = f"`wait {c.id} clear {mine[0]['id']} --epoch <n>`"
        return f"{c.id} is parked ({shown}): its wait cleared ({clear}), then {take}"
    if is_held(c):
        return f"{c.id} is held (order {c.held}): the user's `order unhold {c.id}`"
    if c.status == "blocked":
        why = c.blocked_reason or "no reason recorded"
        return f'{c.id} is blocked ({why}): take it back (`take {c.id} --note "<why>" --epoch <n>`)'
    found = {x.id: x for x in d.crs}
    named = ", ".join(f"{i} {_kind(found[i])}" for i in carried(d).get(c.id, []))
    return f"{c.id} is queued, waiting for {named}: it starts once each is back"
