"""The `next:` line at the end of the eight commands that move a CR or the batch: each handler here
runs the command's own, then reads the record again and adds the advice `chantier next` gives
(`status/advice.py`). A refusal raises before it: no `next:` line, the refusal names its command."""

from __future__ import annotations

import argparse

from chantier.commands import delivery, driver, orders
from chantier.commands import gate as gate_command
from chantier.commands import push as push_command
from chantier.core.batch import find_cr_batch, read_batch, resolve_batch
from chantier.core.errors import ChantierError
from chantier.core.repo import Repo
from chantier.status.advice import first_due, handed_back, next_line, step_after


def _step(args: argparse.Namespace, out: list[str]) -> list[str]:
    repo = Repo.find(readonly=True)
    batch = find_cr_batch(repo, args.cr, args.batch)
    return [*out, *step_after(repo, batch, read_batch(repo, batch), args.cr, out)]


def round_(args: argparse.Namespace) -> list[str]:
    return _step(args, driver.round_(args))


def push(args: argparse.Namespace) -> list[str]:
    return _step(args, push_command.push(args))


def ship(args: argparse.Namespace) -> list[str]:
    return _step(args, delivery.ship(args))


def verdict(args: argparse.Namespace) -> list[str]:
    return _step(args, delivery.verdict(args))


def gate(args: argparse.Namespace) -> tuple[list[str], int]:
    """The run form only, on a pass and on a FAIL; its exit code unchanged."""
    out, code = gate_command.gate(args)
    if args.first or args.stop:
        return out, code
    return _step(args, out), code


def handback(args: argparse.Namespace) -> list[str]:
    out = driver.handback(args)
    repo = Repo.find(readonly=True)
    d = read_batch(repo, find_cr_batch(repo, args.cr, args.batch))
    return [*out, *handed_back(d, out)]


def order(args: argparse.Namespace) -> list[str]:
    """`order merged` and `order done`, to the steering session only (`--epoch`, or a batch
    steered `direct`): the first due item. A Chief of Staff's order in a Foreman's batch: none."""
    out = orders.order(args)
    if args.kind not in ("merged", "done"):
        return out
    repo = Repo.find(readonly=True)
    try:
        d = read_batch(repo, resolve_batch(repo, args.batch, paused=True))
    except ChantierError:  # the batch ended: its own lines say what follows
        return out
    if args.epoch is None and d.steering != "direct":
        return out
    return [*out, *next_line(out, first_due(repo, d))]
