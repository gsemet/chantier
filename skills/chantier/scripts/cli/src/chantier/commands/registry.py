"""How a command module declares itself: `add_command` and the options every command shares."""

from __future__ import annotations

import argparse
import importlib
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    Subparsers = argparse._SubParsersAction[argparse.ArgumentParser]
else:
    Subparsers = argparse._SubParsersAction
Handler = Callable[[argparse.Namespace], Any]

NO_BATCH = "no-batch"  # the command reads no batch
OWN_PROJECT = "own-project"  # no batch, and its own `--project` (`login`: repeatable)
BATCH = "batch"  # `--batch` picks the batch
BATCH_EPOCH = "batch-epoch"  # `--batch`, and the Foreman's `--epoch`


def lazy(path: str) -> Handler:
    """The handler named `module:function`, imported when the command runs, not at start-up."""

    def run(args: argparse.Namespace) -> Any:
        module, _, name = path.partition(":")
        handler: Handler = getattr(importlib.import_module(module), name)
        return handler(args)

    return run


def add_lease(s: argparse.ArgumentParser, required: bool = False) -> None:
    """`--lease <n>`: the number `take` (or `order qa`) printed, on a Driver's command."""
    s.add_argument(
        "--lease",
        type=int,
        metavar="N",
        help=(
            "the lease number `take` printed: "
            + ("required" if required else "optional")
            + " when the unit has a lease; a valid one renews it, a stale one exits 3 "
            "(`claim lost`)"
        ),
    )


def add_command(
    sub: Subparsers, name: str, fn: str, help_: str, scope: str = BATCH
) -> argparse.ArgumentParser:
    """Add one command: its handler (`module:function`), `--project` and `--profile` (accepted after
    the command too), and its scope."""
    s: argparse.ArgumentParser = sub.add_parser(name, help=help_)
    s.set_defaults(fn=lazy(fn))
    if scope != OWN_PROJECT:
        s.add_argument("--project", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    s.add_argument("--profile", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    s.add_argument("--skill", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    if scope not in (NO_BATCH, OWN_PROJECT):
        s.add_argument(
            "--batch",
            help="batch number, 4 or batch-04 (default: $CHANTIER_BATCH, else the only running "
            "one)",
        )
    if scope == BATCH_EPOCH:
        s.add_argument(
            "--epoch",
            type=int,
            help=(
                "the steering session's number in the batch (Foreman n°<n>): missing on a "
                "steering command exits 2, stale exits 3"
            ),
        )
    return s
