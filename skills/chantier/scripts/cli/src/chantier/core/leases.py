"""Leases: a Driver's, the stack driver's and a QA driver's short hold on the unit `take` (or
`order qa`) gave them, kept in `batch.json` (local, never published).

A lease is **live** while it has not ended and one of: it expires in the future, a long gate of
the CR runs or waits in the queue, or a `lease hold` of the unit runs. Else it is **not confirmed**
(it expired: its holder may only be waiting for its worker, and can still renew it as long as
nobody took the unit again) or **ended**. In the code an expired lease is `not confirmed`, the
words every text uses. Every time in a text is UTC. Every "now" goes through `core/clock.py`."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

from chantier import procs
from chantier.core.clock import after, now, seconds_until
from chantier.core.errors import (
    EXIT_CONFLICT,
    EXIT_PRECONDITION,
    EXIT_USAGE,
    ChantierError,
)
from chantier.core.files import read_json
from chantier.core.records import BatchRecord, Lease
from chantier.core.repo import Repo

if TYPE_CHECKING:
    from chantier.core.batch import Batch

TTL_S = 10 * 60
RENEW_S = 3 * 60
TEST_TTL = "CHANTIER_LEASE_TEST_TTL"  # seconds; read here only
LIVE, NOT_CONFIRMED, ENDED = "live", "not confirmed", "ended"
HOLD = ".lease-hold"
_HOLD_NAME = re.compile(r"\.lease-hold\.(.+)\.(\d+)\.run")


def ttl_seconds() -> int:
    """The lease's life: `TTL_S`, or the test seam's value."""
    raw = os.environ.get(TEST_TTL)
    if not raw:
        return TTL_S
    try:
        return max(1, int(float(raw)))
    except ValueError as e:
        raise ChantierError(f"{TEST_TTL} is seconds, not {raw!r}", EXIT_USAGE) from e


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
            raise ChantierError(f"unknown order {unit}", EXIT_USAGE)
        return o.lease
    c = next((x for x in d.crs if x.id == unit), None)
    if c is None:
        raise ChantierError(f"unknown CR {unit}", EXIT_USAGE)
    return c.lease


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
    lease.renewed = now()
    lease.expires = after(ttl_seconds())


def end(lease: Lease | None) -> None:
    """End a lease that has not ended (its record keeps its number)."""
    if lease is not None and not lease.ended:
        lease.ended = now()


class Liveness(NamedTuple):
    state: str  # `live`, `not confirmed` or `ended`
    holds: int = 0  # the `lease hold` runs of this lease
    gate: str | None = None  # `gate running` or `gate queued`: a long gate of the CR keeps it


def hold_records(
    repo: Repo, unit: str | None = None, drop: bool = True
) -> list[tuple[Path, dict[str, Any]]]:
    """The `.lease-hold.<unit>.<k>.run` records whose process is still the one that wrote them.
    A record whose process is gone holds nothing and is removed here (unless `drop` is False:
    a read-only caller leaves it); one that cannot be read is left alone."""
    found = []
    for p in sorted(repo.changes.glob(f"{HOLD}.*.run")):
        m = _HOLD_NAME.fullmatch(p.name)
        if not m or (unit is not None and m[1] != unit):
            continue
        try:
            data = read_json(p)
            pid = int(data["pid"])
            recorded = p.stat().st_mtime
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if procs.alive_since(pid, recorded, False):
            found.append((p, data))
        elif drop:
            p.unlink(missing_ok=True)
    return found


def gate_keeping(repo: Repo, unit: str) -> str | None:
    """`gate running` while a long gate slot names the CR and its process is that one; `gate
    queued` while a live ticket of the queue names it. Read-only."""
    if unit == "stack" or is_order(unit):
        return None
    from chantier.gate_queue import QUEUE, ticket_cr  # noqa: PLC0415 - imports the rails
    from chantier.gate_slots import holder_alive, slot_of  # noqa: PLC0415

    v = slot_of(repo, unit)
    if v is not None and v.holder is not None and holder_alive(v.slot.lock, v.holder, True):
        return "gate running"
    queue = repo.changes / QUEUE
    if any(ticket_cr(p, False) == unit for p in sorted(queue.glob("[0-9]*"))):
        return "gate queued"
    return None


def liveness(repo: Repo, unit: str, lease: Lease, drop: bool = True) -> Liveness:
    if lease.ended:
        return Liveness(ENDED)
    holds = sum(1 for _, rec in hold_records(repo, unit, drop) if rec.get("lease") == lease.n)
    gate = gate_keeping(repo, unit)
    if seconds_until(lease.expires) > 0 or holds or gate:
        return Liveness(LIVE, holds, gate)
    return Liveness(NOT_CONFIRMED, holds, gate)


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
    if live.holds:
        text += f", held by {live.holds} background task(s)"
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


def check_free(
    repo: Repo, d: BatchRecord, unit: str, reclaim: bool, drop: bool = True
) -> Lease | None:
    """What `take` (and a QA driver's restart) asks of the unit's last lease: free when it has
    none or it ended. A live one (exit 3, "held") and a not confirmed one (exit 3, "check with the
    host") are refused unless `reclaim`: then the lease is returned, for `reclaim` to end.
    `drop` False: read-only, no dead hold record is removed."""
    lease = lease_of(d, unit)
    if lease is None or lease.ended:
        return None
    state = liveness(repo, unit, lease, drop).state
    if reclaim:
        return lease
    if state == LIVE:
        raise ChantierError(
            f"{unit} is held: lease {lease.n} live until {hms(lease.expires)}; take it again "
            "with --reclaim only on the user's word",
            EXIT_CONFLICT,
        )
    raise ChantierError(
        f"{unit}: lease {lease.n} {not_confirmed_text(lease).removeprefix('lease ')}; "
        "check with the host that its Driver ended, then take it with --reclaim",
        EXIT_CONFLICT,
    )


def reclaim(b: Batch, unit: str, old: Lease | None) -> None:
    """End the lease a `--reclaim` takes the unit from, and log it with its number and state."""
    if old is None:
        return
    state = liveness(b.repo, unit, old).state
    end(old)
    b.log("reclaim", unit, lease=old.n, state=state)


def require(
    d: BatchRecord, unit: str, number: int | None, what: str, *, ended_ok: bool = False
) -> None:
    """Refuse (exit 2) before any work a command whose unit holds a lease and which was given
    none: a Driver of this version passes the number `take` printed. `ended_ok`: the unit's
    lease ended and nobody took it again, so no Driver holds it (the stack driver's `ship` of a
    CR handed back needs none)."""
    held = lease_of(d, unit)
    if number is None and held is not None and not (ended_ok and held.ended):
        raise ChantierError(
            f"{what} needs --lease <n> (the number take printed)", EXIT_PRECONDITION
        )


def lost(unit: str, number: int, lease: Lease) -> ChantierError:
    if lease.n != number:
        text = f"{unit} was taken again (lease {lease.n}) at {hm(lease.taken)}"
    else:
        text = f"{unit}'s lease {number} ended at {hm(lease.ended or now())}"
    return ChantierError(f"claim lost: {text}; stop now: nothing recorded", EXIT_CONFLICT)


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
                f"{what} needs --lease <n> (the number take printed)", EXIT_PRECONDITION
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


def write_hold(repo: Repo, unit: str, number: int, command: list[str]) -> Path:
    """`.lease-hold.<unit>.<k>.run`, `k` the first free number, written atomically."""
    from chantier.core.files import write_file  # noqa: PLC0415

    taken = {
        int(m[2]) for p in repo.changes.glob(f"{HOLD}.*.run")
        if (m := _HOLD_NAME.fullmatch(p.name)) and m[1] == unit
    }  # fmt: skip
    k = next(i for i in range(1, len(taken) + 2) if i not in taken)
    path = repo.changes / f"{HOLD}.{unit}.{k}.run"
    record = {
        "unit": unit,
        "lease": number,
        "pid": os.getpid(),
        "command": command,
        "started": now(),
    }
    write_file(path, json.dumps(record) + "\n")
    return path
