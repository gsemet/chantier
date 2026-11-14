"""The parser of the `cost` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "cost",
        "chantier.commands.cost.command:cost",
        "price the Foreman's transcript and its subagents",
        BATCH,
    )
    s.add_argument(
        "--by",
        choices=["role", "cr"],
        default="role",
        help="role: the Foreman, each Driver type, each worker type; cr: a CR's own",
    )
    s.add_argument(
        "--explain",
        action="store_true",
        help="under each line: agents, model, shares of cost, calls after the cache "
        "expired, restarted Drivers; ends with what the figures do not count",
    )
    s.add_argument(
        "--summary",
        action="store_true",
        help="total, budget, Foreman, Drivers and workers, the costliest CRs",
    )
