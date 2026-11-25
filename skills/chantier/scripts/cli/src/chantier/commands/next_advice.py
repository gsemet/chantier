"""`chantier next`: read-only advice. With `--epoch`, the steering session's due list; with `<cr>`,
that CR's next step; with neither, the Chief of Staff's view. It takes no lock, records nothing,
renews no lease and reads no forge: the rails keep their refusals."""

from __future__ import annotations

import argparse

from chantier.commands.activity import stopped_agents
from chantier.commands.crs import cr_events
from chantier.core import leases
from chantier.core.batch import find_cr_batch, read_batch, resolve_batch, stale_epoch
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.ids import normalize_cr
from chantier.core.records import read_events
from chantier.core.repo import Repo
from chantier.hub.autostart import not_running_line
from chantier.status.advice import cr_step
from chantier.status.due import due
from chantier.status.ready_line import ready_lines


def next_(args: argparse.Namespace) -> list[str]:
    if args.lease is not None and args.epoch is not None:
        raise ChantierError(
            "next: --lease is a Driver's, --epoch the steering session's; give one",
            EXIT_PRECONDITION,
        )
    if args.lease is not None and not args.cr:
        raise ChantierError(
            f"next --lease {args.lease} needs the CR: next <cr> --lease {args.lease}",
            EXIT_PRECONDITION,
        )
    repo = Repo.find(readonly=True)
    if args.cr:
        return [f"next: {_cr_next(repo, args)}"]
    if args.epoch is not None:
        return _due_lines(repo, resolve_batch(repo, args.batch, paused=True), args.epoch)
    return chief_view(repo, args.batch)


def _due_lines(repo: Repo, batch: str, epoch: int) -> list[str]:
    d = read_batch(repo, batch)
    stale_epoch(d.id, d.foreman_epoch, epoch)
    items = due(repo, d, read_events(repo.store, repo.batch_dir(batch)))
    return [f"due: {x.text}" for x in items] or ["nothing due: wait"]


def _cr_next(repo: Repo, args: argparse.Namespace) -> str:
    cr = normalize_cr(args.cr)
    batch = find_cr_batch(repo, cr, args.batch)
    d = read_batch(repo, batch)
    c = next((x for x in d.crs if x.id == cr), None)
    if c is None:
        raise ChantierError(f"unknown CR {cr} in batch {batch}", EXIT_USAGE)
    stale_epoch(d.id, d.foreman_epoch, args.epoch)
    lease = leases.lease_of(d, cr)
    if args.lease is not None and lease is not None and (lease.n != args.lease or lease.ended):
        raise leases.lost(cr, args.lease, lease)  # as `round` would; no claim is made
    return cr_step(repo, d, c, cr_events(repo, batch, cr))


def chief_view(repo: Repo, batch: str | None) -> list[str]:
    """The unread asks, the CRs handed back ready, who steers, the watcher's line."""
    try:
        d = read_batch(repo, resolve_batch(repo, batch))
    except ChantierError:
        return ["no running batch", *not_running_line(repo)]
    events = read_events(repo.store, repo.batch_dir(d.id))
    unread = sum(1 for a in d.asks if a.read is None)
    out = [f"asks to carry: {unread} unread (`asks`)" if unread else "asks to carry: none"]
    out += ready_lines(repo, d, events, stopped_agents(repo, d, events)) or ["ready: none"]
    if d.steering == "direct":
        out.append(f"direct mode: you steer: `next --epoch {d.foreman_epoch}` for what is due")
    return [*out, *not_running_line(repo)]
