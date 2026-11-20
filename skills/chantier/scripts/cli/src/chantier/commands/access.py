"""`chantier access`: what the rules say now for this session, read-only. It writes nothing, renews
no lease and removes no dead hold record; the refusals it quotes stay their commands'."""

from __future__ import annotations

import argparse

from chantier.board import running
from chantier.board.projects import project_name
from chantier.commands.take_checks import check_take_all
from chantier.core import leases
from chantier.core.batch import find_cr_batch, read_batch
from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.ids import normalize_cr
from chantier.core.records import BatchRecord, CrEntry, Lease
from chantier.core.repo import Repo
from chantier.core.seat import read_seat
from chantier.hub import state
from chantier.hub.autostart import holds_seat, session_key
from chantier.rails import held, usd_text
from chantier.writer import lines as writer

ACTIONS = ("write", "claim", "push")
REWRITE = "a rewrite uses --force-with-lease (driver.md)"


def access(args: argparse.Namespace) -> list[str]:
    action, cr = _action_and_cr(args)
    repo = Repo.find(readonly=True)
    out = [_session_line(repo)]
    if action in (None, "write"):
        out.append(_write_line(repo))
    if cr is not None:
        found = _find(repo, cr, args.batch)
        if action in (None, "claim"):
            out += _claim_lines(repo, found, args)
        if action in (None, "push"):
            out += _push_lines(repo, found, args)
            if repo.external:
                out.append("push surface: only the writer pushes the surface; never by hand")
    writer.forget()  # a check that passed is no write: nothing to say of the writer's push
    return out


def _action_and_cr(args: argparse.Namespace) -> tuple[str | None, str | None]:
    first, second = args.action_or_cr, args.cr
    action = first if first in ACTIONS else None
    cr = second if action else first
    if action is None and second is not None:
        raise ChantierError(
            f"access: {second!r} follows no action (write, claim or push)", EXIT_USAGE
        )
    if action in ("claim", "push") and not cr:
        raise ChantierError(f"access {action} <cr>: name the CR", EXIT_USAGE)
    return action, normalize_cr(cr) if cr else None


def _session_line(repo: Repo) -> str:
    held_seat = read_seat(repo)
    head = f"session {session_key()}: "
    if held_seat is None:
        return head + "no seat recorded"
    if holds_seat(held_seat.transcript):
        return head + f"holds the seat of {project_name(repo)}"
    return head + f"the seat is {held_seat.session} ({held_seat.link or 'unknown'})"


def _write_line(repo: Repo) -> str:
    if not repo.external:
        return (
            "write: allowed: in-project planning folder, under the lifecycle lock; chantier "
            "commits nothing"
        )
    entry = state.live_entry(repo.git_dir, state.WRITER)
    if entry is not None and entry.get("state") == "stopped":
        return f"write: refused: {writer.stopped_text(entry)}"
    if entry is None:
        server = writer.older_board(repo.git_dir)
        if server is None:
            return f"write: refused: the surface's writer is not running; {writer.START}"
        stop = running.stop_command(int(server["pid"]))
        return (
            "write: refused: the surface's writer is not running: "
            f"{writer.older_text(server)}; stop it ({stop}), then {writer.START}"
        )
    why = writer.pending_why(entry)
    tail = f"; not pushed yet: {why}" if why is not None else ""
    return (
        f"write: allowed: the surface's writer runs (pid {entry.get('pid')}, "
        f"{entry.get('state')}); it commits and pushes within 5 min{tail}"
    )


def _find(repo: Repo, cr: str, batch: str | None) -> tuple[BatchRecord, CrEntry] | str:
    """The batch record and the CR, else the refusal text."""
    try:
        name = find_cr_batch(repo, cr, batch)
        d = read_batch(repo, name)
    except ChantierError as e:
        return str(e)
    c = next((x for x in d.crs if x.id == cr), None)
    return (d, c) if c is not None else f"unknown CR {cr} in batch {name}"


def _budget_left(d: BatchRecord) -> str:
    if not d.budget_usd:
        return "none set"
    if d.spent_usd is None:
        return f"budget ${d.budget_usd:.2f}, spend unknown"
    return usd_text(d.budget_usd - d.spent_usd, d.unpriced)


def _claim_lines(
    repo: Repo, found: tuple[BatchRecord, CrEntry] | str, args: argparse.Namespace
) -> list[str]:
    if isinstance(found, str):
        return [f"claim: refused: {found}"]
    d, c = found
    repo.command = "take"  # a refusal of the store names `take`, the command it explains
    try:
        # `note` is only read for its truth: the --note rule is `take`'s, said in the answer
        check_take_all(repo, d, c, note="-", reclaim=False, read_only=True)
    except ChantierError as e:
        out = [f"claim: refused: {str(e).removeprefix('take: ')}"]
    else:
        text = (
            f"claim: allowed: {c.id} is {c.status}; {len(held(d))} of {d.slots} slots held; "
            f"dependencies ready; budget left {_budget_left(d)} (last recorded spend)"
        )
        if c.status in {"working", "ready", "blocked"}:
            text += f"; take needs --note saying why ({c.id} is {c.status})"
        out = [text]
    if args.epoch != d.foreman_epoch:
        out.append(f"claim: needs the steering session's --epoch (Foreman n°{d.foreman_epoch})")
    return out


def _push_lines(
    repo: Repo, found: tuple[BatchRecord, CrEntry] | str, args: argparse.Namespace
) -> list[str]:
    if isinstance(found, str):
        return [f"push: refused: {found}"]
    c = found[1]
    if c.status != "working":
        return [f"push: refused: {c.id} is {c.status}"]
    lease = c.lease
    if lease is None:
        return [
            f"push: allowed: {c.id} is working; no lease in this batch; push {c.branch} "
            f"without force; {REWRITE}"
        ]
    if lost := _lease_lost(lease, args.lease):
        return [f"push: refused: {lost}"]
    push = f"push {c.branch} without force; {REWRITE}"
    if leases.liveness(repo, c.id, lease, drop=False).state == leases.LIVE:
        return [f"push: allowed: lease {lease.n} of {c.id} is live; {push}"]
    return [
        f"push: allowed: lease {lease.n} of {c.id} not confirmed since {leases.hm(lease.expires)}, "
        f"not taken again; renew it first (lease {c.id} renew --lease {lease.n}), then {push}"
    ]


def _lease_lost(lease: Lease, given: int | None) -> str | None:
    """Why a `--lease` is no claim on the CR's current lease, else None."""
    if given is None:
        return f"no --lease given (lease {lease.n} is current)"
    if given != lease.n or lease.ended:
        ended = f", ended at {leases.hm(lease.ended)}" if lease.ended else ""
        return f"claim lost (lease {lease.n} is current){ended}"
    return None
