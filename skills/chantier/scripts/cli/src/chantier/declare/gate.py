"""The parser of the `gate` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "gate",
        "chantier.commands.gate:gate",
        "run the long gate in the CR worktree, alone in the repository, "
        "a second one waits its turn, first come first served; --stop stops this CR's running one",
        BATCH,
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
