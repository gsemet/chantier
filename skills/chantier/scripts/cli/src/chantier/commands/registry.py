"""How a command module declares itself: `add_command` and the options every command shares."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Any

Subparsers = argparse._SubParsersAction  # type: ignore[type-arg]
Handler = Callable[[argparse.Namespace], Any]

NO_BATCH = "no-batch"  # the command reads no batch
BATCH = "batch"  # `--batch` picks the batch
BATCH_EPOCH = "batch-epoch"  # `--batch`, and the Foreman's `--epoch`


def add_command(
    sub: Subparsers, name: str, fn: Handler, help_: str, scope: str = BATCH
) -> argparse.ArgumentParser:
    """Add one command: its handler, `--project` (accepted after the command too), and its scope."""
    s: argparse.ArgumentParser = sub.add_parser(name, help=help_)
    s.set_defaults(fn=fn)
    s.add_argument("--project", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    if scope != NO_BATCH:
        s.add_argument(
            "--batch",
            help="batch number, 4 or batch-04 (default: $CHANTIER_BATCH, else the only running "
            "one)",
        )
    if scope == BATCH_EPOCH:
        s.add_argument("--epoch", type=int, help="the Foreman's epoch; stale ones exit 3")
    return s
