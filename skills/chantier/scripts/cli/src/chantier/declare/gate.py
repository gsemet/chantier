"""The parser of the `gate` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH_EPOCH, Subparsers, add_command, add_lease


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "gate",
        "chantier.commands.next_lines:gate",
        "run the long gate, by the names chantier.yaml's long_gate.commands gives, in the CR "
        "worktree, as many at once as chantier.yaml's "
        "long_gate.parallel (1 by default), the others wait their turn: the next "
        "merge's first, then those moved first, then arrival order; --stop stops this CR's "
        "running one; --first --epoch moves a waiting one first",
        BATCH_EPOCH,
    )
    s.add_argument("cr")
    s.add_argument(
        "name",
        nargs="*",
        help="the long gate's names from chantier.yaml's long_gate.commands, run in order, "
        "one per argument; they stop at the first failure",
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
    add_lease(s)
