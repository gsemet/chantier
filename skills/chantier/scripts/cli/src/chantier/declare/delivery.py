"""The parser of the `delivery` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "verdict",
        "chantier.commands.delivery:verdict",
        "the Verifier's verdict on the CR's worktree head: VERIFIED or \"NOT VERIFIED\"",
        BATCH,
    )
    s.add_argument("cr")
    s.add_argument("result", nargs="+", help="VERIFIED, or NOT VERIFIED (one argument or two)")

    s = add_command(
        sub,
        "ship",
        "chantier.commands.delivery:ship",
        "record the PR the Driver opened or updated; say what is off",
        BATCH,
    )
    s.add_argument("cr")
    s.add_argument("pr", help="the PR link")

    s = add_command(
        sub,
        "stack",
        "chantier.commands.delivery:stack",
        "the stack's order, as its driver set it",
        BATCH,
    )
    s.add_argument(
        "crs",
        nargs="*",
        help="the stack's order, as its driver set it, bottom first; naming only some CRs "
        "puts them at the bottom, the others above in their order; "
        "with no CR, print the stack as it stands (writes nothing)",
    )
