"""`chantier status`, `asks` and `agents`."""

from __future__ import annotations

import argparse
from typing import Any

from chantier.commands.activity import activity
from chantier.commands.cost.breakdown import cost_groups, cost_summary
from chantier.commands.cost.pricing import TO_DATE, sum_unpriced
from chantier.commands.cost.sessions import chief_line, cost_rows, foreman_uuid
from chantier.commands.registry import BATCH, BATCH_EPOCH, Subparsers, add_command
from chantier.core.batch import Batch, check_epoch, find_cr_batch, read_batch, resolve_batch
from chantier.core.batch_records import last_closed
from chantier.core.clock import age_minutes, now
from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.records import BatchRecord, CrEntry, round_limit
from chantier.core.repo import Repo
from chantier.history import last_closed_text
from chantier.lifecycle.convert import open_repo
from chantier.lifecycle.session import RenderedBatch
from chantier.lifecycle.stages import changes_lock
from chantier.rails import held, not_priced, spent_text, usd_text, waits_all
from chantier.rails_release import record_ask
from chantier.status.words import shape_word, steering_word


def _stop_heartbeat(repo: Repo, batch: str, epoch: int | None) -> list[str]:
    """The steering session records that it ended its loop: `status` says "heartbeat stopped"
    until the next wake (`status --refresh --epoch`) clears it."""
    with RenderedBatch(repo, batch, actor="foreman") as b:
        check_epoch(b, epoch)
        if epoch is None:
            raise ChantierError(
                "--stop-heartbeat carries --epoch <n>: the steering session's own", EXIT_USAGE
            )
        b.record.heartbeat_stopped = now()
        b.log("heartbeat_stopped", None)
    return [
        f"heartbeat stopped recorded for {batch}; the next `status --refresh --epoch "
        f"{epoch}` clears it"
    ]


def _refresh(repo: Repo, batch: str, epoch: int | None) -> tuple[list[str], int, str | None]:
    """The facts the state cannot keep by itself: the activity of each working CR and the spend
    the budget reads. With `--epoch`, it is the Foreman's wake, and the batch records it. The
    last value is the heartbeat the wake overwrote (None: no wake, or the first one)."""
    prev = None
    with (
        changes_lock(repo),
        RenderedBatch(repo, batch, actor="foreman" if epoch is not None else "chief-of-staff") as b,
    ):
        check_epoch(b, epoch)
        if epoch is not None:
            prev = b.record.heartbeat
            b.record.heartbeat = now()
            b.record.heartbeat_stopped = None
            b.log("heartbeat", None)
        data = b.record.model_copy(deep=True)
    lines = activity(repo, data)
    try:
        rows = cost_rows(repo, data, data.host, foreman_uuid(data))
    except ChantierError as e:
        return [*lines, f"spend not updated: {e}"], e.code, prev
    with RenderedBatch(
        repo, batch, actor="foreman" if epoch is not None else "chief-of-staff"
    ) as b:
        total = record_costs(repo, b, rows)
        if b.record.status == "paused":  # the header and the Cost section read one figure
            b.record.summary = [
                *cost_summary(
                    b.record,
                    rows,
                    cost_groups(repo, b.id, rows, "cr"),
                    cost_groups(repo, b.id, rows, "driver"),
                    chief_line(repo, b.record),
                ),
                TO_DATE,
            ]
    floor = sum_unpriced(rows)
    return (
        [*lines, f"spent {usd_text(total, floor)}" + (f"; {not_priced(floor)}" if floor else "")],
        0,
        prev,
    )


def record_costs(repo: Repo, b: Batch, rows: list[dict[str, Any]]) -> float:
    """The spend the budget check reads, and each CR's share, shown in its STATUS.md."""
    total: float = sum(r["usd"] for r in rows)
    b.record.spent_usd = round(total, 4)  # the priced part: the budget reads it as it is
    b.record.unpriced = sum_unpriced(rows)  # model -> calls left out of it: a floor, said so
    by_cr = cost_groups(repo, b.id, rows, "cr")
    for c in b.record.crs:
        if c.id in by_cr:
            c.cost_usd = round(by_cr[c.id][1], 4)
            if by_cr[c.id][2]:
                c.cost_unpriced = by_cr[c.id][2]
            else:
                c.unset("cost_unpriced")
    b.log("cost", None, usd=total)
    return total


def _heartbeat_text(d: BatchRecord, prev: str | None) -> str:
    hb = age_minutes(d.heartbeat)
    if d.heartbeat_stopped:
        return "stopped"
    if hb is None:
        return "never"
    text = f"{hb:.0f} min"
    since = age_minutes(prev) if prev else None
    if since is not None:  # a wake's own line: the gap since the wake before
        text += f" ({since - hb:.0f} min since the last)"
    return text


def _cr_row(d: BatchRecord, c: CrEntry, notes: bool) -> str:
    row = f"{c.id} {c.status} r{c.round}/{round_limit(d, c)} {c.pr or '-'}"
    if c.kind == "release":
        row += f" release{' ' + c.released if c.released else ''}"
        row += "".join(f" | draft {p}" for p in c.drafts[-2:])
    elif c.kind == "fix":
        row += f" fix for {c.fix_for}"
    waits = waits_all(d.crs, c, d.mode) if c.status == "queued" else []
    if waits:
        row += f" | waits for {', '.join(waits)}"
    if c.status == "working" and not c.agent:
        row += " | no Driver recorded"
    if c.status == "blocked" and c.blocked_reason:
        row += f" | blocked: {c.blocked_reason[:70]}"
    elif c.notes and (notes or c.status == "queued"):
        row += f" | {c.notes[-1][:60]}"
    usd = c.cost_usd
    return f"{row} | {'-' if usd is None else f'${usd:.2f}'}"


def _order_lines(d: BatchRecord) -> list[str]:
    open_orders = [o for o in d.orders if not o.done]
    lines = []
    for applied, head in (
        (False, "orders pending: "),
        (True, "orders the CLI applied, the Foreman marks each `order done <O-k>`: "),
    ):
        group = [o for o in open_orders if bool(o.applied) is applied]
        if group:
            lines.append(
                head
                + "; ".join(
                    f"{o.id} {o.kind}{' ' + o.cr if o.cr != '-' else ''}"
                    f"{' ' + o.note[:40] if o.note else ''}"
                    for o in group
                )
            )
    return lines


def _batch_line(d: BatchRecord, hb_text: str) -> str:
    queued = sum(1 for c in d.crs if c.status == "queued")
    return (
        f"{d.id} {d.status} steering {steering_word(d.steering)} "
        f"shape {shape_word(d.mode)} live {len(held(d))}/{d.slots} queued {queued} "
        f"foreman {d.foreman or 'none'} e{d.foreman_epoch} "
        f"heartbeat {hb_text}"
        f" spent {spent_text(d)}"
        + (f" of ${d.budget_usd:g}" if d.budget_usd else "")
        + (" (paused, cost to date)" if d.status == "paused" else "")
    )


def status(args: argparse.Namespace) -> tuple[list[str], int]:
    repo = open_repo()
    batch = resolve_batch(repo, args.batch)
    extra, code, prev = [], 0, None
    if args.stop_heartbeat:
        extra = _stop_heartbeat(repo, batch, args.epoch)
    elif args.refresh:
        extra, code, prev = _refresh(repo, batch, args.epoch)
    d = read_batch(repo, batch)
    lines = [_batch_line(d, _heartbeat_text(d, prev)), last_closed_text(last_closed(repo))]
    lines += [_cr_row(d, c, args.notes) for c in sorted(d.crs, key=lambda c: c.order)]
    lines += _order_lines(d)
    unread = sum(1 for a in d.asks if not a.read)
    if unread:
        lines.append(f"{unread} asks unread: `chantier asks`")
    return lines + extra, code


def asks(args: argparse.Namespace) -> list[str]:
    """The Chief of Staff reads what the Foreman had to tell it, sent or not, and marks what it
    heard. With `text`, the Foreman records an ask of its own and gets the line to send."""
    repo = open_repo()
    text = " ".join(args.text)
    with RenderedBatch(
        repo, resolve_batch(repo, args.batch), actor="foreman" if text else "chief-of-staff"
    ) as b:
        if text:
            aid = record_ask(b, text)
            return [f"[foreman→chief-of-staff] ask {aid}: {text}"]
        if args.read:
            hit = [a for a in b.record.asks if not a.read and (args.read in ("all", a.id))]
            if not hit and args.read != "all":
                raise ChantierError(f"no unread ask {args.read}", EXIT_USAGE)
            for a in hit:
                a.read = now()
            if hit:
                b.log("asks-read", None, asks=[a.id for a in hit])
            return [f"read {len(hit)}"]
        unread = [a for a in b.record.asks if not a.read]
    return [f"{a.id}: {a.text}" for a in unread] or ["no unread ask"]


def agents(args: argparse.Namespace) -> list[str]:
    """The agent id a CR's Driver or the stack driver runs under: the Foreman records it after
    each start, so a restart and the cost know who ran what."""
    repo = open_repo()
    batch = (
        find_cr_batch(repo, args.cr, args.batch)
        if args.cr != "stack" and not args.cr.startswith("O-")
        else resolve_batch(repo, args.batch)
    )
    with RenderedBatch(repo, batch, actor="foreman") as b:
        check_epoch(b, args.epoch)
        if args.agent == "-":  # the agent ended: the next one may start
            args.agent = None
        if args.cr == "stack":
            b.record.stack_agent = args.agent
        elif args.cr.startswith("O-"):  # a QA order: its driver is a Driver of the batch for `cost`
            o = next((x for x in b.record.orders if x.id == args.cr), None)
            if o is None or o.kind != "qa":
                raise ChantierError(f"agents set {args.cr}: not a QA order of {b.id}", EXIT_USAGE)
            o.agent = args.agent
        else:
            b.touch(b.cr(args.cr), agent=args.agent)
        b.log("agent", args.cr, agent=args.agent)
    return [f"{args.cr} → {args.agent}"]


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "status",
        status,
        "one line per CR, the open orders (untouched, then applied), the unread asks; "
        "--refresh: the live facts; its line says `heartbeat N min` (since the last "
        "`--refresh --epoch`), `never` or `stopped`",
        BATCH_EPOCH,
    )
    s.add_argument("--notes", action="store_true", help="each CR's last note")
    s.add_argument(
        "--refresh",
        action="store_true",
        help="the activity of each working CR (age of its last event or session "
        "record, `gate running`, `gate queued behind <cr>`, `not measured`) "
        "and the spend (recorded); "
        "with --epoch, the steering session's wake: it records the heartbeat "
        "and prints the gap since the wake before; without, it moves nothing",
    )
    s.add_argument(
        "--stop-heartbeat",
        action="store_true",
        help="with --epoch: record that the steering session ended its loop "
        "(`heartbeat stopped`, until the next wake)",
    )

    s = add_command(
        sub, "asks", asks, "the Foreman's asks still unread; with text, record one", BATCH
    )
    s.add_argument("text", nargs="*", help="the Foreman's own ask")
    s.add_argument("--read", metavar="A-k|all", help="mark heard")

    s = add_command(sub, "agents", agents, "map a CR (or stack) to its agent id", BATCH_EPOCH)
    s.add_argument("action", choices=["set"])
    s.add_argument("cr")
    s.add_argument("agent", help="the agent id; `-` clears it")
