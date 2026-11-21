"""`chantier order`: the user's word, recorded at once."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from chantier.commands.endpause import end_of_batch
from chantier.commands.orders_apply import (
    CR_ORDERS,
    HANDLERS,
    apply_order,
)
from chantier.commands.orders_merged import stop_before_merge
from chantier.commands.orders_waive import USAGE as WAIVE_USAGE
from chantier.commands.orders_word import Word
from chantier.core import git, leases
from chantier.core.batch import Batch, check_epoch, require_epoch, resolve_batch
from chantier.core.clock import now, stamp
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.ids import normalize_cr
from chantier.core.records import LIVE, TRASH, OrderRecord
from chantier.core.repo import Repo
from chantier.driver_prompt import DriverBlock, DriverRow, driver_prompt_lines, driver_row
from chantier.hub.autostart import not_running_line
from chantier.lifecycle.filing import new_request, shown
from chantier.lifecycle.session import RenderedBatch
from chantier.lifecycle.stages import changes_lock
from chantier.plugin_files import cli_command
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
    if args.follow_up and kind != "waive":
        raise ChantierError("--follow-up goes with `order waive <cr>` alone", EXIT_USAGE)
    if kind == "waive" and (not args.cr or args.cr == "-"):
        raise ChantierError(WAIVE_USAGE, EXIT_USAGE)
    if kind in CR_ORDERS and (not args.cr or args.cr == "-"):
        raise ChantierError(
            "order rounds <cr> --note <n>" if kind == "rounds" else f"order {kind} <cr>",
            EXIT_USAGE,
        )


def _check_own(args: argparse.Namespace, own: bool) -> None:
    if own and args.kind != "merged" and not (args.kind == "add" and args.fix_for):
        raise ChantierError(
            "only `order merged` and `order add --fix-for` take --epoch: the "
            "Foreman's own merge or fix",
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
        return [f"{b.id} was paused: running again; `pause --epoch <n>` runs again at the end"]
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


def _qa_row(repo: Repo, b: Batch) -> tuple[DriverRow, str]:
    """The QA driver's table row and the project's default branch, both checked before any state
    changes: the configured one, else the remote's; never a guess."""
    if b.record.steering == "direct" and b.record.status != "paused":
        raise ChantierError(
            "a running direct batch takes no QA: order it once the batch is paused "
            "(`pause --epoch <n>`)",
            EXIT_PRECONDITION,
        )
    row = driver_row(b.record.host, "order qa")
    branch = repo.config["default_branch"] or git.default_branch(repo.root, repo.config["remote"])
    if not branch:
        raise ChantierError(
            "order qa: the project's default branch is unknown (set `default_branch` in the "
            "project's configuration, or give the remote a HEAD)",
            EXIT_PRECONDITION,
        )
    return row, branch


def _qa_skeleton(repo: Repo, b: Batch, qa_row: tuple[DriverRow, str], req: _Req) -> list[str]:
    """The QA driver's prompt block, after the order's `QA folder:` line."""
    row, branch = qa_row
    held = leases.lease_of(b.record, req.oid)
    n = held.n if held else 1
    fill = {"<folder>": req.cr, "<batch>": b.id, "<root>": repo.root.as_posix()}
    block = DriverBlock(
        fill,
        f"{cli_command(repo)} <command> --batch {b.id}",
        [f"QA folder: {req.cr}; order {req.oid}", f"default branch: {branch}"],
        note=req.note,
        lease=(
            f"lease: {n} of {req.oid} (renew at each wake: lease {req.oid} renew --lease {n}; "
            f"run a long test under lease {req.oid} hold --lease {n} -- <command>)"
        ),
    )
    return driver_prompt_lines(row, b.record, block)


@dataclass
class _Req:
    """What an order asks: its CR, its note, whether the Foreman's own, whether a new release."""

    cr: str
    note: str
    own: bool
    new_release: bool
    oid: str = ""
    stopped: list[str] | None = None


def _word(b: Batch, args: argparse.Namespace, req: _Req) -> Word:
    cr = req.cr
    if args.kind == "after" and not any(x.id == cr for x in b.record.crs):
        raise ChantierError(f"order after: unknown CR {cr} in batch {b.id}")
    has_cr = (
        args.kind in CR_ORDERS
        or (args.kind == "note" and cr != "-")
        or (args.kind == "waive" and cr != "stack")
    )
    c = b.cr(cr) if has_cr else None
    return Word(
        b,
        args.kind,
        cr,
        c,
        req.note,
        args.fix_for,
        req.own,
        req.new_release,
        follow_up=args.follow_up,
        order_id=req.oid,
        stopped=req.stopped,
    )


def _record_order(b: Batch, args: argparse.Namespace, req: _Req) -> str:
    cr, note, own, new_release = req.cr, req.note, req.own, req.new_release
    oid = req.oid
    # The CLI did its whole part, the Foreman only has to end the order: not a note (the
    # Foreman relays it), not a QA (it starts a driver), not the drop of a live CR, nor the hold of
    # a working CR (it leaves the CR `blocked`; a hold from ready leaves it `ready`).
    applied = args.kind not in {"note", "qa"} and not (
        (args.kind == "drop" and b.cr(cr).status in LIVE)
        or (args.kind == "hold" and b.cr(cr).status == "blocked")
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
            **({"follow_up": args.follow_up} if args.follow_up else {}),
            **({"release": True} if new_release else {}),
        ),
    )
    if args.kind == "qa":
        leases.start(b.record, oid)  # lease 1 of the order's QA driver
    b.log(
        "order",
        None if cr in (None, "-") else cr,
        order=oid,
        order_kind=args.kind,
        note=note,
        **({"to": note} if args.kind == "drop" else {}),
    )
    return oid


DROP_USAGE = (
    "order drop <cr> --note trash|inbox|P1..P4: where the CR goes; ask the user when they "
    "have not said it"
)
_DROP_FOLDERS = {"trash": TRASH, "inbox": "1-inbox", **{f"p{n}": f"2-backlog/P{n}" for n in "1234"}}


def _drop_folder(note: str) -> str:
    """`order drop`'s word as the folder it names; no default, the user says where."""
    folder = _DROP_FOLDERS.get(note.strip().lower())
    if folder is None:
        raise ChantierError(DROP_USAGE, EXIT_USAGE)
    return folder


def _normalise_args(args: argparse.Namespace, note: str) -> str:
    """The CR ids of the arguments in their canonical form; returns the note (`drop`'s, as the
    folder it names)."""
    if args.kind == "drop":
        note = _drop_folder(note)
    if (
        args.kind in CR_ORDERS
        or args.kind == "note"
        or (args.kind == "waive" and args.cr != "stack")
    ):
        args.cr = _cr_arg(args.cr)
    args.fix_for = _cr_arg(args.fix_for)
    if args.kind == "after" and note.strip() != "-":
        note = ", ".join(_cr_arg(s.strip()) for s in note.split(","))
    return note


def order(args: argparse.Namespace) -> list[str]:
    """The Chief of Staff's word, in the state at once; the Foreman sees it in `status` and
    marks it `order done` once its own part is done. `order merged --epoch <n>` is the Foreman
    recording a merge it made itself, `order add --fix-for --epoch <n>` a fix it starts under
    the grant: done at once."""
    note = args.note or ""
    new_release = bool(getattr(args, "release", False))
    _check_args(args, note, new_release)
    repo = Repo.find()
    if args.kind == "done":
        return _order_done(repo, args)
    note = _normalise_args(args, note)
    return _ordered(repo, args, note, new_release)


def _ordered(repo: Repo, args: argparse.Namespace, note: str, new_release: bool) -> list[str]:
    """Apply and record one order, in the batch's own locks: the lines the Chief of Staff relays."""
    own = args.epoch is not None
    _check_own(args, own)
    actor = "foreman" if own else "chief-of-staff"
    stopped = stop_before_merge(repo, args, actor) if args.kind == "merged" else None
    fresh: list[str] = []
    if args.kind == "qa" or (own and args.kind == "add" and args.fix_for):
        from chantier.commands.batch_status import refresh_for_check  # noqa: PLC0415 - slow

        fresh = refresh_for_check(repo, resolve_batch(repo, args.batch), actor)  # budget checked
    with (
        changes_lock(repo),
        RenderedBatch(repo, resolve_batch(repo, args.batch), actor=actor) as b,
    ):
        check_epoch(b, args.epoch)
        qa_row = _qa_row(repo, b) if args.kind == "qa" else None  # before any state changes
        reopened = _reopen(b, args.kind)
        cr = _qa_folder(repo, b, note) if qa_row else args.cr
        req = _Req(cr, note, own, new_release, f"O-{len(b.record.orders) + 1}", stopped)
        w = _word(b, args, req)
        effect = reopened + apply_order(w)
        oid = _record_order(b, args, req)
        skeleton = _qa_skeleton(repo, b, qa_row, req) if qa_row else []
        batch_id = b.id
        watch = not_running_line(repo) if args.kind == "qa" and reopened else []
    if w.ended:  # a CR ended: the locks are released, and the batch ends or says why it stays open
        effect += end_of_batch(repo, batch_id, f"order {oid}")
    if own:
        return [*effect, *fresh, *watch]
    target = f" {cr}" if cr and cr != "-" else ""
    text = f" {note}" if note else ""
    return [
        f"[chief-of-staff→foreman] order {oid}: {args.kind}{target}{text}{w.clause}",
        *effect,
        *skeleton,
        *fresh,
        *watch,
    ]


def _order_done(repo: Repo, args: argparse.Namespace) -> list[str]:
    if not args.cr or not args.cr.startswith("O-"):
        raise ChantierError("order done <O-k>", EXIT_USAGE)
    require_epoch(args.epoch, f"order done {args.cr} --epoch <n>")
    with RenderedBatch(repo, resolve_batch(repo, args.batch), actor="foreman") as b:
        check_epoch(b, args.epoch)
        o = next((x for x in b.record.orders if x.id == args.cr), None)
        if o is None:
            raise ChantierError(f"unknown order {args.cr}", EXIT_USAGE)
        if o.done:
            return [f"{args.cr} already done"]
        o.done = now()
        leases.end(o.lease)
        b.log("order-done", None, order=args.cr)
    return [f"{args.cr} done"]
