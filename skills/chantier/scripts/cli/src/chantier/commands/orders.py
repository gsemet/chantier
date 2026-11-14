"""`chantier order`: the user's word, recorded at once."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from chantier.commands.orders_apply import CR_ORDERS, HANDLERS, Word, apply_order
from chantier.core.batch import Batch, check_epoch, resolve_batch
from chantier.core.clock import now, stamp
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.ids import normalize_cr
from chantier.core.records import LIVE, OrderRecord
from chantier.core.repo import Repo
from chantier.lifecycle.convert import open_repo
from chantier.lifecycle.filing import new_request, shown
from chantier.lifecycle.session import RenderedBatch
from chantier.lifecycle.stages import changes_lock
from chantier.rails import check_budget, check_slot

ORDER_KINDS = {*HANDLERS, "done"}

_cr_arg = normalize_cr  # `order after`'s list is split here; every other argument is read by `main`


def _check_args(args: argparse.Namespace, note: str, new_release: bool) -> None:
    """The refusals that need no record: a missing word or CR, a flag on the wrong kind."""
    kind = args.kind
    if kind not in ORDER_KINDS:
        raise ChantierError(f"order kind: one of {', '.join(sorted(ORDER_KINDS))}", EXIT_USAGE)
    if kind == "add" and not note.strip():
        raise ChantierError(
            "order add --note <prepared-CR-folder-or-specification> "
            "[--fix-for <release-cr> | --release]",
            EXIT_USAGE,
        )
    if new_release and (kind != "add" or args.fix_for):
        raise ChantierError(
            "--release goes with `order add` alone: it adds the batch's release "
            "CR; a fix of it is `order add --fix-for <release-cr>`",
            EXIT_USAGE,
        )
    if kind == "qa" and not note.strip():
        raise ChantierError('order qa --note "<what to test>"', EXIT_USAGE)
    if kind in CR_ORDERS and (not args.cr or args.cr == "-"):
        raise ChantierError(
            "order rounds <cr> --note <n>" if kind == "rounds" else f"order {kind} <cr>",
            EXIT_USAGE,
        )


def _reopen(b: Batch, kind: str) -> list[str]:
    """A paused batch: `add` leaves it paused, `qa` runs it again."""
    if b.record.status != "paused":
        return []
    if kind == "add":
        # the batch stays paused: the first `take` sets it running again
        return [f"{b.id} stays paused: the first `take` sets it running again"]
    if kind == "qa":
        # a QA driver holds a slot from the order on: the batch runs again, its pause and
        # cost to date are void
        b.record.status = "running"
        b.record.unset("paused")
        b.record.unset("summary")
        b.log("reopen", None)
        return [f"{b.id} was paused: running again; `pause` runs again at the end"]
    return []


def _qa_folder(repo: Repo, b: Batch, note: str) -> str:
    """A work folder the QA driver fills, in the inbox: a QA driver is a Driver, so refused
    before anything is created, and the open order holds the slot until `order done`."""
    check_budget(b.record)
    check_slot(b.record, "a QA driver")
    return shown(
        repo,
        new_request(
            repo,
            f"qa-{stamp()}",
            f"# QA\n\n{note}\n".encode(),
            "a QA folder of this minute exists: try again in a minute",
        ),
    )


@dataclass
class _Req:
    """What an order asks: its CR, its note, whether the Foreman's own, whether a new release."""

    cr: str
    note: str
    own: bool
    new_release: bool


def _word(b: Batch, args: argparse.Namespace, req: _Req) -> Word:
    cr = req.cr
    if args.kind == "after" and not any(x.id == cr for x in b.record.crs):
        raise ChantierError(f"order after: unknown CR {cr} in batch {b.id}")
    has_cr = args.kind in CR_ORDERS or (args.kind == "note" and cr != "-")
    c = b.cr(cr) if has_cr else None
    return Word(b, args.kind, cr, c, req.note, args.fix_for, req.own, req.new_release)


def _record_order(b: Batch, args: argparse.Namespace, req: _Req) -> str:
    cr, note, own, new_release = req.cr, req.note, req.own, req.new_release
    oid = f"O-{len(b.record.orders) + 1}"
    # The CLI did its whole part, the Foreman only has to end the order: not a note (the
    # Foreman relays it), not a QA (it starts a driver), not the drop of a live CR.
    applied = args.kind not in {"note", "qa"} and not (
        args.kind == "drop" and b.cr(cr).status in LIVE
    )
    b.record.append(
        "orders",
        OrderRecord(
            id=oid,
            kind=args.kind,
            cr=cr or "-",
            note=note,
            sent=now(),
            done=now() if own else None,
            **({} if own else {"applied": applied}),
            **({"fix_for": args.fix_for} if args.fix_for else {}),
            **({"release": True} if new_release else {}),
        ),
    )
    b.log("order", None if cr in (None, "-") else cr, order=oid, order_kind=args.kind, note=note)
    return oid


def order(args: argparse.Namespace) -> list[str]:
    """The Chief of Staff's word, in the state at once; the Foreman sees it in `status` and
    marks it `order done` once its own part is done. `order merged --epoch <n>` is the Foreman
    recording a merge it made itself, `order add --fix-for --epoch <n>` a fix it starts under
    the grant: done at once."""
    note = args.note or ""
    new_release = bool(getattr(args, "release", False))
    _check_args(args, note, new_release)
    repo = open_repo()
    if args.kind == "done":
        return _order_done(repo, args)
    if args.kind in CR_ORDERS or args.kind == "note":
        args.cr = _cr_arg(args.cr)
    args.fix_for = _cr_arg(args.fix_for)
    if args.kind == "after" and note.strip() != "-":
        note = ", ".join(_cr_arg(s.strip()) for s in note.split(","))
    own = args.epoch is not None
    if own and args.kind != "merged" and not (args.kind == "add" and args.fix_for):
        raise ChantierError(
            "only `order merged` and `order add --fix-for` take --epoch: the "
            "Foreman's own merge or fix",
            EXIT_USAGE,
        )
    actor = "foreman" if own else "chief-of-staff"
    with (
        changes_lock(repo),
        RenderedBatch(repo, resolve_batch(repo, args.batch), actor=actor) as b,
    ):
        check_epoch(b, args.epoch)
        if args.kind == "qa" and b.record.steering == "direct" and b.record.status != "paused":
            raise ChantierError(
                "a running direct batch takes no QA: order it once the batch is paused (`pause`)",
                EXIT_PRECONDITION,
            )
        cr = args.cr
        reopened = _reopen(b, args.kind)
        if args.kind == "qa":
            cr = _qa_folder(repo, b, note)
        req = _Req(cr, note, own, new_release)
        effect = reopened + apply_order(_word(b, args, req))
        oid = _record_order(b, args, req)
    if own:
        return effect
    target = f" {cr}" if cr and cr != "-" else ""
    text = f" {note}" if note else ""
    return [f"[chief-of-staff→foreman] order {oid}: {args.kind}{target}{text}", *effect]


def _order_done(repo: Repo, args: argparse.Namespace) -> list[str]:
    if not args.cr or not args.cr.startswith("O-"):
        raise ChantierError("order done <O-k>", EXIT_USAGE)
    with RenderedBatch(repo, resolve_batch(repo, args.batch), actor="foreman") as b:
        check_epoch(b, args.epoch)
        o = next((x for x in b.record.orders if x.id == args.cr), None)
        if o is None:
            raise ChantierError(f"unknown order {args.cr}", EXIT_USAGE)
        if o.done:
            return [f"{args.cr} already done"]
        o.done = now()
        b.log("order-done", None, order=args.cr)
    return [f"{args.cr} done"]
