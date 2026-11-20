"""`lease`: a unit's lease, shown, renewed, or kept live while a background command runs."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

from chantier.core import leases
from chantier.core.batch import resolve_batch
from chantier.core.errors import EXIT_EXTERNAL, EXIT_USAGE, ChantierError
from chantier.core.ids import normalize_cr
from chantier.core.repo import Repo
from chantier.lifecycle.session import RenderedBatch

USAGE = "lease <unit> | lease <unit> renew --lease <n> | lease <unit> hold --lease <n> -- <command>"


_OPTIONS = ("--lease", "--batch", "--project", "--skill")


def _number(value: str) -> int:
    try:
        return int(value)
    except ValueError as e:
        raise ChantierError(f"--lease is a number, not {value!r}", EXIT_USAGE) from e


def _parse(rest: list[str]) -> tuple[str | None, int | None, str | None, list[str]]:
    """`[renew|hold] [--lease N] [--batch B]`, then `-- <command...>`: the action, the number,
    the batch and the command."""
    head, command = rest, []
    if "--" in rest:
        i = rest.index("--")
        head, command = rest[:i], rest[i + 1 :]
    action = number = batch = None
    words = iter(head)
    for word in words:
        if word in ("renew", "hold") and action is None:
            action = word
        elif word in _OPTIONS:
            value = next(words, None)
            if value is None:
                raise ChantierError(f"{word} needs a value; {USAGE}", EXIT_USAGE)
            number = _number(value) if word == "--lease" else number
            batch = value if word == "--batch" else batch
        else:
            raise ChantierError(f"lease: unexpected {word!r}; {USAGE}", EXIT_USAGE)
    return action, number, batch, command


def lease(args: argparse.Namespace) -> list[str] | tuple[list[str], int]:
    repo = Repo.find()
    action, number, batch, command = _parse(list(args.rest))
    unit = (
        args.unit if args.unit == "stack" or leases.is_order(args.unit) else normalize_cr(args.unit)
    )
    name = resolve_batch(repo, batch or args.batch)
    if action is None:
        if command or number is not None:
            raise ChantierError(f"lease {unit}: say `renew` or `hold`; {USAGE}", EXIT_USAGE)
        with RenderedBatch(repo, name, actor="driver") as b:
            return [leases.line(repo, unit, leases.lease_of(b.record, unit))]
    if action == "renew":
        if command:
            raise ChantierError(f"lease {unit} renew takes no command; {USAGE}", EXIT_USAGE)
        return [_renew(repo, name, unit, number)]
    if not command:
        raise ChantierError(f"lease {unit} hold needs `-- <command>`; {USAGE}", EXIT_USAGE)
    return _hold(repo, name, unit, number, command)


def _renew(repo: Repo, name: str, unit: str, number: int | None) -> str:
    with RenderedBatch(repo, name, actor="driver") as b:
        found = leases.lease_of(b.record, unit)
        if found is None:
            raise ChantierError(f"{unit}: no lease to renew", EXIT_USAGE)
        leases.claim(b, unit, number, what=f"lease {unit} renew", required=True)
        b.log("lease", unit, lease=number)
        return leases.line(repo, unit, found)


def _hold(
    repo: Repo, name: str, unit: str, number: int | None, command: list[str]
) -> tuple[list[str], int]:
    exe = shutil.which(command[0])
    if exe is None:
        raise ChantierError(f"lease hold: {command[0]!r} is not an executable", EXIT_EXTERNAL)
    _renew(repo, name, unit, number)  # a stale number stops here, before the command runs
    assert number is not None
    path = leases.write_hold(repo, unit, number, command)
    try:
        sys.stdout.flush()
        code = subprocess.run([exe, *command[1:]], check=False).returncode
    finally:
        path.unlink(missing_ok=True)
    lines: list[str] = []
    try:  # one renewal at the end, unless the lease ended or was taken again
        with RenderedBatch(repo, name, actor="driver") as b:
            current = leases.lease_of(b.record, unit)
            if current is not None and current.n == number and not current.ended:
                leases.renew(current)
                b.log("lease", unit, lease=number)
    except ChantierError as e:
        lines.append(f"warning: the lease was not renewed at the end: {e}")
    return lines, code
