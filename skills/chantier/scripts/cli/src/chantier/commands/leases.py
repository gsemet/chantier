"""`lease`: a unit's lease, shown, renewed, or kept live for a bounded time (`hold`, which runs
nothing)."""

from __future__ import annotations

import argparse

from chantier.core import leases
from chantier.core.batch import resolve_batch
from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.ids import normalize_cr
from chantier.core.repo import Repo
from chantier.lifecycle.session import RenderedBatch

USAGE = (
    "lease <unit> | lease <unit> renew --lease <n> | "
    "lease <unit> hold --lease <n> [--minutes N] (N from 1 to 90, 45 by default)"
)


_OPTIONS = ("--lease", "--batch", "--project", "--skill", "--minutes")


def _number(value: str, option: str = "--lease") -> int:
    try:
        return int(value)
    except ValueError as e:
        raise ChantierError(f"{option} is a number, not {value!r}", EXIT_USAGE) from e


def _parse(rest: list[str]) -> tuple[str | None, int | None, str | None, int | None, list[str]]:
    """`[renew|hold] [--lease N] [--minutes M] [--batch B]`, then `-- <command...>` (refused by
    `hold`): the action, the number, the batch, the minutes and the command."""
    head, command = rest, []
    if "--" in rest:
        i = rest.index("--")
        head, command = rest[:i], rest[i + 1 :]
    action = number = batch = minutes = None
    words = iter(head)
    for word in words:
        if word in ("renew", "hold") and action is None:
            action = word
        elif word in _OPTIONS:
            value = next(words, None)
            if value is None:
                raise ChantierError(f"{word} needs a value; {USAGE}", EXIT_USAGE)
            number = _number(value) if word == "--lease" else number
            minutes = _number(value, word) if word == "--minutes" else minutes
            batch = value if word == "--batch" else batch
        else:
            raise ChantierError(f"lease: unexpected {word!r}; {USAGE}", EXIT_USAGE)
    return action, number, batch, minutes, command


def lease(args: argparse.Namespace) -> list[str] | tuple[list[str], int]:
    repo = Repo.find()
    action, number, batch, minutes, command = _parse(list(args.rest))
    unit = (
        args.unit if args.unit == "stack" or leases.is_order(args.unit) else normalize_cr(args.unit)
    )
    if args.lease is not None and number is not None and args.lease != number:
        raise ChantierError(
            f"lease {unit}: --lease given twice ({args.lease} and {number}); "
            f"`lease {unit} renew --lease <n>`",
            EXIT_USAGE,
        )
    number = args.lease if number is None else number
    if action is None and number is not None and not command:
        action = "renew"
    name = resolve_batch(repo, batch or args.batch)
    if action != "hold" and minutes is not None:
        raise ChantierError(f"lease {unit}: --minutes belongs to `hold`; {USAGE}", EXIT_USAGE)
    if action is None:
        if command or number is not None:
            raise ChantierError(f"lease {unit}: say `renew` or `hold`; {USAGE}", EXIT_USAGE)
        with RenderedBatch(repo, name, actor="driver") as b:
            return [leases.line(repo, unit, leases.lease_of(b.record, unit))]
    if command:
        what = "takes no command" if action == "renew" else "runs no command"
        raise ChantierError(
            f"lease {unit} {action} {what}: start your wait yourself, then run lease {unit} "
            f"hold --lease <n>; {USAGE}",
            EXIT_USAGE,
        )
    if action == "renew":
        return [_renew(repo, name, unit, number)]
    return [_hold(repo, name, unit, number, minutes)]


def _renew(repo: Repo, name: str, unit: str, number: int | None) -> str:
    with RenderedBatch(repo, name, actor="driver") as b:
        found = leases.lease_of(b.record, unit)
        if found is None:
            raise ChantierError(f"{unit}: no lease to renew", EXIT_USAGE)
        leases.claim(b, unit, number, what=f"lease {unit} renew", required=True)
        b.log("lease", unit, lease=number)
        return leases.line(repo, unit, found)


def _hold(repo: Repo, name: str, unit: str, number: int | None, minutes: int | None) -> str:
    """Keep the lease live for `minutes` (45 by default, 90 at most): the checks of a renewal,
    then the expiry set ahead. Nothing runs, nothing is written but the record and its event."""
    held = leases.HOLD_DEFAULT if minutes is None else minutes
    if not 1 <= held <= leases.HOLD_MAX:
        raise ChantierError(
            f"lease {unit} hold --minutes is a whole number from 1 to {leases.HOLD_MAX}, "
            f"not {held}; {USAGE}",
            EXIT_USAGE,
        )
    with RenderedBatch(repo, name, actor="driver") as b:
        found = leases.lease_of(b.record, unit)
        if found is None:
            raise ChantierError(f"{unit}: no lease to hold", EXIT_USAGE)
        leases.claim(b, unit, number, what=f"lease {unit} hold", required=True)
        leases.hold(found, held)
        b.log("lease", unit, lease=number, minutes=held)
        return leases.line(repo, unit, found)
