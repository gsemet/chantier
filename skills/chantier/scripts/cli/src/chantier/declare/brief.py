"""The parser of the `brief` command; the handler loads when it runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH_EPOCH, Subparsers, add_command

HELP = (
    "write one role's start brief (its card, the floor, its unit's facts, its host rows) in the "
    "git folder and print the short prompt that points at it; it records nothing and renews "
    "no lease"
)


def register(sub: Subparsers) -> None:
    """Declare `brief`."""
    s = add_command(sub, "brief", "chantier.commands.brief:brief", HELP, BATCH_EPOCH)
    s.add_argument("role", help="the role to brief")
    s.add_argument(
        "unit",
        nargs="?",
        help="the role's unit: a CR, the stack, a QA order (O-k) or a CR's folder; none for a "
        "role-only brief",
    )
    s.add_argument(
        "--lease",
        type=int,
        help="a Driver's lease number on its unit (checked, never renewed or taken)",
    )
    s.add_argument(
        "--cards",
        metavar="FOLDER",
        help="read the card and the floor from this folder (<card's file name>, floor.md)",
    )
