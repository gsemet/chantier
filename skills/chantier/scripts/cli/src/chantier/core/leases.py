"""Leases: a Driver's, the stack driver's and a QA driver's short hold on the unit `take` (or
`order qa`) gave them, kept in `batch.json` (local, never published).

A lease is **live** while it has not ended and one of: it expires in the future (a `lease hold`
sets the expiry ahead, 45 minutes by default and 90 at most), or a long gate of the CR runs or
waits in the queue. Else it is **not confirmed**
(it expired: its holder may only be waiting for its worker, and can still renew it as long as
nobody took the unit again) or **ended**. In the code an expired lease is `not confirmed`, the
words every text uses. Every time in a text is UTC. Every "now" goes through `core/clock.py`."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, NamedTuple

from chantier.core.clock import after, now, seconds_until
from chantier.core.errors import (
    EXIT_CONFLICT,
    EXIT_PRECONDITION,
    EXIT_USAGE,
    ChantierError,
)
from chantier.core.files import rel_in
from chantier.core.records import BatchRecord, Lease
from chantier.core.repo import Repo

if TYPE_CHECKING:
    from chantier.core.batch import Batch

TTL_S = 10 * 60
RENEW_S = 3 * 60
TEST_TTL = "CHANTIER_LEASE_TEST_TTL"  # seconds; read here only
TEST_MINUTE = "CHANTIER_LEASE_TEST_MINUTE"  # seconds a hold's minute lasts (60); read here only
HOLD_DEFAULT, HOLD_MAX = 45, 90  # a hold's minutes: the default and the most
MINUTE_S = 60
LIVE, NOT_CONFIRMED, ENDED = "live", "not confirmed", "ended"


def ttl_seconds() -> int:
    """The lease's life: `TTL_S`, or the test seam's value."""
    raw = os.environ.get(TEST_TTL)
    if not raw:
        return TTL_S
    try:
        return max(1, int(float(raw)))
    except ValueError as e:
        raise ChantierError(f"{TEST_TTL} is seconds, not {raw!r}", EXIT_USAGE) from e


def minute_seconds() -> float:
    """What a hold's minute lasts: 60 seconds, or the test seam's value."""
    raw = os.environ.get(TEST_MINUTE)
    if not raw:
        return MINUTE_S
    try:
        return max(0.1, float(raw))
    except ValueError as e:
        raise ChantierError(f"{TEST_MINUTE} is seconds, not {raw!r}", EXIT_USAGE) from e


def hms(ts: str) -> str:
    return ts[11:19]


def hm(ts: str) -> str:
    return ts[11:16]


def minutes_ago(ts: str) -> int:
    return int(max(0.0, -seconds_until(ts)) // 60)


def is_order(unit: str) -> bool:
    return unit.startswith("O-")


def lease_of(d: BatchRecord, unit: str) -> Lease | None:
    """The unit's last lease (a CR, `stack` or an order `O-k`); None for a unit that never had
    one, and for a batch opened before leases."""
    if unit == "stack":
        return d.stack_lease
    if is_order(unit):
        o = next((x for x in d.orders if x.id == unit), None)
        if o is None:
            raise ChantierError(
                f"unknown order {unit}: `status` shows the batch's CRs and orders", EXIT_USAGE
            )
        return o.lease
    c = next((x for x in d.crs if x.id == unit), None)
    if c is None:
        raise ChantierError(
            f"unknown CR {unit}: `status` shows the batch's CRs and orders", EXIT_USAGE
        )
    return c.lease


def unit_for(d: BatchRecord, cr: str, number: int | None) -> str:
    """The unit a `--lease <number>` on a command about the CR claims: the stack's, when the CR is
    in a stack batch's chain and the stack's lease (not ended) has that number; else an open QA
    order's on the CR with that number; else the CR's own. A stack driver's or a QA driver's number
    is never read against the CR's own lease."""
    from chantier.stacks import chain  # noqa: PLC0415 - imports the rails

    if number is None:
        return cr
    stack = d.stack_lease
    if stack is not None and stack.n == number and not stack.ended:  # noqa: SIM102
        if cr in {x.id for x in chain(d)}:
            return "stack"
    for o in d.orders:
        mine = o.kind == "qa" and o.cr == cr and o.done is None
        if mine and o.lease is not None and o.lease.n == number and not o.lease.ended:
            return o.id
    return cr


def set_lease(d: BatchRecord, unit: str, lease: Lease | None) -> None:
    if unit == "stack":
        d.stack_lease = lease
    elif is_order(unit):
        next(x for x in d.orders if x.id == unit).lease = lease
    else:
        next(x for x in d.crs if x.id == unit).lease = lease


def start(d: BatchRecord, unit: str) -> Lease:
    """A new lease of the unit: the unit's last number plus one (1 at the first)."""
    old = lease_of(d, unit)
    t = now()
    lease = Lease(
        n=old.n + 1 if old else 1, taken=t, renewed=t, expires=after(ttl_seconds()), ended=None
    )
    set_lease(d, unit, lease)
    return lease


def renew(lease: Lease) -> None:
    """A renewal: the expiry is the later of the current one (a hold's, maybe) and now + the TTL."""
    lease.renewed = now()
    if seconds_until(lease.expires) < ttl_seconds():
        lease.expires = after(ttl_seconds())


def hold(lease: Lease, minutes: int) -> None:
    """`lease hold`: the expiry is now + `minutes`, with no process behind it."""
    lease.renewed = now()
    lease.expires = after(max(1, round(minutes * minute_seconds())))


def end(lease: Lease | None) -> None:
    """End a lease that has not ended (its record keeps its number)."""
    if lease is not None and not lease.ended:
        lease.ended = now()


class Liveness(NamedTuple):
    state: str  # `live`, `not confirmed` or `ended`
    gate: str | None = None  # `gate running` or `gate queued`: a long gate of the CR keeps it


def gate_keeping(repo: Repo, unit: str) -> str | None:
    """`gate running` while a long gate slot names the CR and its process is that one; `gate
    queued` while a live ticket of the queue names it. Read-only."""
    if unit == "stack" or is_order(unit):
        return None
    from chantier.gate_queue import QUEUE, ticket_cr  # noqa: PLC0415 - imports the rails
    from chantier.gate_slots import holder_alive, slot_of  # noqa: PLC0415

    v = slot_of(repo, unit)
    store = repo.store
    if v is not None and v.holder is not None and holder_alive(store, v.slot.lock, v.holder, True):
        return "gate running"
    queue = repo.changes / QUEUE
    tickets = [queue / n for n in store.glob(rel_in(store.root, queue), "[0-9]*")]
    if any(ticket_cr(store, p, False) == unit for p in tickets):
        return "gate queued"
    return None


def liveness(repo: Repo, unit: str, lease: Lease) -> Liveness:
    if lease.ended:
        return Liveness(ENDED)
    gate = gate_keeping(repo, unit)
    if seconds_until(lease.expires) > 0 or gate:
        return Liveness(LIVE, gate)
    return Liveness(NOT_CONFIRMED, gate)


def line(repo: Repo, unit: str, lease: Lease | None) -> str:
    """The `lease <unit>` command's line."""
    if lease is None:
        return f"{unit}: no lease"
    live = liveness(repo, unit, lease)
    head = f"lease {lease.n} of {unit}: "
    if live.state == ENDED and lease.ended:
        return f"{head}ended at {hm(lease.ended)}"
    if live.state == NOT_CONFIRMED:
        return (
            f"{head}not confirmed since {hm(lease.expires)} ({minutes_ago(lease.expires)} min ago)"
        )
    text = f"{head}live until {hms(lease.expires)} (renewed {hms(lease.renewed)})"
    if live.gate:
        text += f", {live.gate}"
    return text


def driver_line(unit: str, lease: Lease) -> str:
    """What `take` tells a CR's Driver about its lease."""
    return (
        f"lease: {lease.n} (pass --lease {lease.n} on your commands; renew at each wake: "
        f"lease {unit} renew --lease {lease.n})"
    )


def not_confirmed_text(lease: Lease) -> str:
    return f"lease not confirmed since {hm(lease.expires)} ({minutes_ago(lease.expires)} min ago)"


def not_confirmed(repo: Repo, unit: str, lease: Lease | None) -> str | None:
    """`lease not confirmed since ...` for a lease that expired, else None."""
    if lease is None or liveness(repo, unit, lease).state != NOT_CONFIRMED:
        return None
    return not_confirmed_text(lease)


def reclaim_command(unit: str, lease: Lease, *, short: bool = False) -> str:
    """The command that takes the unit from a lease that is not ended, by the unit's kind: a CR's
    `take`, the stack's `take stack`, a QA order's `agents set`. `short`: a CR's with `...`."""
    if unit == "stack":
        return "take stack --reclaim --epoch <n>"
    if is_order(unit):
        return f"agents set {unit} <id> --reclaim --epoch <n>"
    if short:
        return f"take {unit} --reclaim ..."
    return f'take {unit} --reclaim --note "resume: lease not confirmed" --epoch <n>'


def _late_ship_tail(repo: Repo, unit: str, lease: Lease) -> str:
    """What a refused `ship`, `stack` or `forge-stack` without `--lease` adds: the commands, by
    the lease's state (live, or not confirmed)."""
    if liveness(repo, unit, lease).state == LIVE:
        who = "the stack driver" if unit == "stack" else "its Driver"
        return (
            f"; {unit}'s lease {lease.n} is live until {hms(lease.expires)}: {who} ships it; "
            f"once the host shows that Driver ended, `agents set {unit} - --epoch <n>` ends the "
            "lease and `ship` with no --lease is accepted"
        )
    return (
        f"; {unit}'s lease {lease.n} not confirmed since {hm(lease.expires)} "
        f"({minutes_ago(lease.expires)} min ago): once the host shows its Driver ended, "
        f"`{reclaim_command(unit, lease)}` starts a new Driver, which ships it"
    )


def check_free(repo: Repo, d: BatchRecord, unit: str, reclaim: bool) -> Lease | None:
    """What `take` (and a QA driver's restart) asks of the unit's last lease: free when it has
    none or it ended. A live one (exit 3, "held") and a not confirmed one (exit 3, "check with the
    host") are refused unless `reclaim`: then the lease is returned, for `reclaim` to end."""
    lease = lease_of(d, unit)
    if lease is None or lease.ended:
        return None
    state = liveness(repo, unit, lease).state
    if reclaim:
        return lease
    if state == LIVE:
        raise ChantierError(
            f"{unit} is held: lease {lease.n} live until {hms(lease.expires)}; once the host shows "
            f"its holder ended, `agents set {unit} - --epoch <n>` ends it; "
            f"`{reclaim_command(unit, lease, short=True)}` only on the user's word (`help lease`)",
            EXIT_CONFLICT,
        )
    raise ChantierError(
        f"{unit}: lease {lease.n} {not_confirmed_text(lease).removeprefix('lease ')}; "
        f"check with the host that its Driver ended, then `{reclaim_command(unit, lease)}` "
        "(`help lease`)",
        EXIT_CONFLICT,
    )


def reclaim(b: Batch, unit: str, old: Lease | None) -> None:
    """End the lease a `--reclaim` takes the unit from, and log it with its number and state."""
    if old is None:
        return
    state = liveness(b.repo, unit, old).state
    end(old)
    b.log("reclaim", unit, lease=old.n, state=state)


def require(  # noqa: PLR0913 - the record, the unit and the command's words
    repo: Repo, d: BatchRecord, unit: str, number: int | None, what: str, *, ended_ok: bool = False
) -> None:
    """Refuse (exit 2) before any work a command whose unit holds a lease and which was given
    none: a Driver of this version passes the number `take` printed. `ended_ok`: the unit's
    lease ended and nobody took it again, so no Driver holds it (the stack driver's `ship` of a
    CR handed back needs none)."""
    held = lease_of(d, unit)
    if number is None and held is not None and not (ended_ok and held.ended):
        raise ChantierError(
            f"{what} needs --lease <n> (the number take printed); `lease {unit}` prints it"
            + (_late_ship_tail(repo, unit, held) if ended_ok else "")
            + " (`help lease`)",
            EXIT_PRECONDITION,
        )


def lost(unit: str, number: int, lease: Lease) -> ChantierError:
    if lease.n != number:
        text = f"{unit} was taken again (lease {lease.n}) at {hm(lease.taken)}"
    else:
        text = f"{unit}'s lease {number} ended at {hm(lease.ended or now())}"
    return ChantierError(
        f"claim lost: {text}; stop now: nothing recorded (`help lease`)", EXIT_CONFLICT
    )


def renew_read(  # noqa: PLR0913 - the keywords say what each is
    repo: Repo, batch: str, d: BatchRecord, cr: str, number: int | None, *, what: str
) -> None:
    """A command that only reads the CR, given `--lease`: renew the unit the number claims (a stale
    number exits 3), in a short session of its own. Without a number: nothing is written."""
    if number is not None:
        renewed_in_session(repo, batch, unit_for(d, cr, number), number, what=what, required=False)


def claim(  # noqa: PLR0913 - the keywords say what each is
    b: Batch,
    unit: str,
    number: int | None,
    *,
    what: str,
    required: bool,
    epoch: int | None = None,
    ended_ok: bool = False,
) -> Lease | None:
    """The lease check of a Driver's command, before anything is recorded. A unit with no lease
    (a batch opened before leases), and a command the steering session runs (`--epoch`), need no
    `--lease`. A required one that is missing: exit 2. A number that is not the unit's current
    one, or the current one ended: exit 3, `claim lost`. The current one, not confirmed and not
    taken again, is accepted (its Driver was only late) and logged `lease-late`. A valid one is
    renewed in the record: the command's own event saves it. Returns the lease it renewed. With
    `ended_ok`, an ended lease and no number is accepted: no Driver holds the unit."""
    lease = lease_of(b.record, unit)
    if lease is None or epoch is not None:
        return None
    if number is None:
        if required and not (ended_ok and lease.ended):
            raise ChantierError(
                f"{what} needs --lease <n> (the number take printed); `lease {unit}` prints it"
                + (_late_ship_tail(b.repo, unit, lease) if ended_ok else "")
                + " (`help lease`)",
                EXIT_PRECONDITION,
            )
        return None
    if lease.n != number or lease.ended:
        raise lost(unit, number, lease)
    if liveness(b.repo, unit, lease).state != LIVE:
        b.log("lease-late", unit, lease=lease.n, minutes=minutes_ago(lease.expires))
    renew(lease)
    return lease


def renewed_in_session(  # noqa: PLR0913
    repo: Repo,
    batch: str,
    unit: str,
    number: int | None,
    *,
    what: str,
    required: bool,
    ended_ok: bool = False,
) -> None:
    """`claim`, in a short session of its own, for a command that records nothing else (`gate`,
    `forge-stack`): the renewal is saved with a `lease` event."""
    from chantier.lifecycle.session import RenderedBatch  # noqa: PLC0415 - imports the rails

    with RenderedBatch(repo, batch, actor="driver") as b:
        if claim(b, unit, number, what=what, required=required, ended_ok=ended_ok) is not None:
            b.log("lease", unit, lease=number)
