"""The parser of the `gate` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH_EPOCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "gate",
        "chantier.commands.gate:gate",
        "run the long gate in the CR worktree, as many at once as chantier.yaml's "
        "long_gate.parallel (1 by default), the others wait their turn, first come first "
        "served; --stop stops this CR's running one; --first --epoch moves a waiting one first",
        BATCH_EPOCH,
    )
    s.add_argument("cr")
    s.add_argument(
        "command",
        nargs="*",
        help="the long gate's commands, from the project's rules: "
        "one per argument, never chained with ; or &&; they stop at the first failure",
    )
    s.add_argument(
        "--stop",
        action="store_true",
        help="stop this CR's running long gate: its suite, the gate lock; recorded "
        "`stopped`, no pass; nothing else changes",
    )
    s.add_argument(
        "--first",
        action="store_true",
        help="the steering session's: put this CR's waiting long gate at the head of the queue",
    )
