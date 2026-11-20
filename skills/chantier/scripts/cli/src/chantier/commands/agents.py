"""`agents set`: the agent id a unit's Driver runs under, and the lease that goes with it."""

from __future__ import annotations

import argparse

from chantier.core import leases
from chantier.core.batch import Batch, check_epoch, find_cr_batch, require_epoch, resolve_batch
from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.records import OrderRecord
from chantier.core.repo import Repo
from chantier.lifecycle.session import RenderedBatch


def agents(args: argparse.Namespace) -> list[str]:
    """The agent id a CR's Driver or the stack driver runs under: the Foreman records it after
    each start, so a restart and the cost know who ran what."""
    require_epoch(args.epoch, f"agents set {args.cr} <id>|- --epoch <n>")
    repo = Repo.find()
    batch = (
        find_cr_batch(repo, args.cr, args.batch)
        if args.cr != "stack" and not args.cr.startswith("O-")
        else resolve_batch(repo, args.batch)
    )
    with RenderedBatch(repo, batch, actor="foreman") as b:
        check_epoch(b, args.epoch)
        if args.agent == "-":  # the agent ended: the next one may start
            args.agent = None
        extra: list[str] = []
        if args.cr == "stack":
            b.record.stack_agent = args.agent
        elif args.cr.startswith("O-"):  # a QA order: its driver is a Driver of the batch for `cost`
            o = next((x for x in b.record.orders if x.id == args.cr), None)
            if o is None or o.kind != "qa":
                raise ChantierError(f"agents set {args.cr}: not a QA order of {b.id}", EXIT_USAGE)
            if args.agent is not None:
                extra = _restart_lease(b, o, bool(args.reclaim))
                o.driven = True
            o.agent = args.agent
        else:
            b.touch(b.cr(args.cr), agent=args.agent)
        if args.agent is None:  # the steering session cleared it after the agent's reported end
            _end_live_lease(b, args.cr)
        b.log("agent", args.cr, agent=args.agent)
    return [f"{args.cr} → {args.agent}", *extra]


def _end_live_lease(b: Batch, unit: str) -> None:
    """A lease that is live ends with the agent it belonged to; a not confirmed one stays, for the
    host check and `--reclaim`."""
    lease = leases.lease_of(b.record, unit)
    if lease is not None and leases.liveness(b.repo, unit, lease).state == leases.LIVE:
        leases.end(lease)


def _restart_lease(b: Batch, o: OrderRecord, reclaim: bool) -> list[str]:
    """A QA driver recorded: the first one (no driver recorded before, `driven`) keeps lease 1,
    or gets the next if a clearance ended it; a restart (a later one) is refused while the lease
    is live or not confirmed, unless `--reclaim`, and starts the next lease otherwise."""
    if o.lease is None:
        return []
    if not o.driven and o.lease.ended is None:
        return []
    old = leases.check_free(b.repo, b.record, o.id, reclaim)
    leases.reclaim(b, o.id, old)
    lease = leases.start(b.record, o.id)
    return [leases.line(b.repo, o.id, lease)]
