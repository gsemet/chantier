"""The parser of the `park` command; the handler loads when it runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH_EPOCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "park",
        "chantier.commands.park:park",
        "the Foreman parks a CR stuck on an outside wait: out of the slots and the stack",
        BATCH_EPOCH,
    )
    s.add_argument("cr", help="the CR id")
    s.add_argument(
        "--wait",
        action="append",
        metavar="TYPE[=REF]",
        help="a typed wait to record before the park (answer=<question>, approval, "
        "pipeline[=<sha>], merge[=<link>]); repeatable",
    )
    s.add_argument("--note", help="what it waits for (default: its earlier reason, or the waits)")
