"""`park`: the Foreman parks a CR stuck on an outside wait, and `take` brings it back on top.

A parked CR is `blocked` with `parked` set: it holds no slot, it leaves the stack and the series
order, and the CRs that wait with it (its dependents) stay out of them too."""

from __future__ import annotations

import argparse

from chantier.commands.driver_checks import wait_specs
from chantier.commands.orders_reorder import chains_kept
from chantier.commands.waits import add_to_cr
from chantier.core import leases
from chantier.core.batch import Batch, check_epoch, find_cr_batch, require_epoch
from chantier.core.clock import now
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.records import CrEntry
from chantier.core.repo import Repo
from chantier.core.waits import hhmm, open_counted, what
from chantier.lifecycle.session import RenderedBatch
from chantier.lifecycle.stages import changes_lock
from chantier.rails import is_held, is_parked
from chantier.stack_apart import dependents, leave_stack_starts


def _refuse(c: CrEntry, has_wait: bool) -> None:
    """The five refusals, in the spec's order, the first raised: held, status, release or fix,
    already parked, no outside wait."""
    cr = c.id
    if is_held(c):
        raise ChantierError(
            f"park: {cr} is held (order {c.held}): the user's hold, not a park", EXIT_PRECONDITION
        )
    if c.status not in {"working", "blocked"}:
        raise ChantierError(
            f"park: {cr} is {c.status}: only a working or blocked CR is parked", EXIT_PRECONDITION
        )
    if c.kind in {"release", "fix"}:
        what_ = "the release CR" if c.kind == "release" else "a fix CR"
        raise ChantierError(f"park: {cr} is {what_}: it is not parked", EXIT_PRECONDITION)
    if is_parked(c):
        raise ChantierError(
            f"park: {cr} is already parked (since {hhmm(c.parked or '')})", EXIT_PRECONDITION
        )
    if not has_wait:
        raise ChantierError(
            f"park: {cr} has no outside wait recorded: "
            "--wait answer=<question>|approval|pipeline|merge",
            EXIT_PRECONDITION,
        )


def park(args: argparse.Namespace) -> list[str]:
    """`park <cr> --epoch <n> [--wait <type>[=<ref>]]... [--note ...]`: one write of the batch."""
    require_epoch(args.epoch, f"park {args.cr} --epoch <n>")
    specs = wait_specs(args)
    repo = Repo.find()
    batch = find_cr_batch(repo, args.cr, args.batch)
    with changes_lock(repo), RenderedBatch(repo, batch, actor="foreman") as b:
        check_epoch(b, args.epoch)
        d, c = b.record, b.cr(args.cr)
        _refuse(c, bool(specs or open_counted(c)))
        note = " ".join((args.note or "").split())
        _, outside = add_to_cr(repo, d, c, specs, note or "parked") if specs else ([], [])
        mine = open_counted(c)
        was = c.blocked_reason
        reason = (
            note
            or (was if c.status == "blocked" and was else "")
            or "; ".join(what(w) for w in mine)
        )
        leases.end(c.lease)  # its old Driver's next command is `claim lost`
        b.touch(
            c, status="blocked", blocked_reason=f"parked: {reason}", parked=now(), stacked=False
        )
        c.clear_phase()
        leave_stack_starts(b, c)  # after `parked` is set: a started series successor keeps its base
        deps = dependents(d.crs, c, d.mode)
        ids = [w["id"] for w in mine]
        b.log("park", c.id, waits=ids, **({"was": was} if was else {}))
        waits = "; ".join(what(w) for w in mine)
        with_it = f"; waiting with it: {', '.join(x.id for x in deps)}" if deps else ""
        lines = [
            f"parked {c.id}: waits for {waits}; its slot is free and the batch goes on without "
            f"it{with_it}; it comes back on top once the wait is cleared",
            *outside,
        ]
        if c.agent:
            lines.append(
                f"stop its Driver if it still runs, then `agents set {c.id} - --epoch <n>`"
            )
        if d.mode == "stack":
            lines.append(f'stack: `take stack --note "park: {c.id}"`')
    return lines


def unpark(b: Batch, c: CrEntry) -> str:
    """`take` of a parked CR whose waits are cleared: `parked` is unset and the CR takes the place
    on top of the order (`place_on_top`). The line's tail."""
    deps = dependents(b.record.crs, c, b.record.mode)  # worked out with the CR still parked
    c.unset("parked")
    return place_on_top(b, c, deps)


def place_on_top(b: Batch, c: CrEntry, deps: list[CrEntry]) -> str:
    """A CR back from apart (unparked, unheld) takes the place on top of the order, its dependents
    `deps` right above it, their chains kept. A stack or parallel batch: above every CR but the
    release; a series: above every CR that left `queued`, below the queued ones, which move up.
    The line's tail."""
    d = b.record
    rest = [x for x in d.crs if x.id != c.id and x not in deps]
    if d.mode == "series":
        left = [x.order for x in rest if x.kind != "release" and x.status != "queued"]
        floor = min((x.order for x in rest), default=1)
        place = max(left) + 1 if left else floor
    else:
        place = max((x.order for x in rest + deps if x.kind != "release"), default=0) + 1
    seq = chains_kept([c, *deps])
    for x in rest:
        if x.order >= place:
            b.touch(x, order=x.order + len(seq))
    for i, x in enumerate(seq):
        b.touch(x, order=place + i)
    tail = {
        "stack": "; back on top of the stack",
        "series": "; back in the series after its started CRs",
    }.get(d.mode or "", "")
    above = f"; its dependents above it: {', '.join(x.id for x in seq[1:])}" if deps else ""
    return tail + above
