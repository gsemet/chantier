"""The parser of the `conflicts` command; the handler loads when it runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH_EPOCH, Subparsers, add_command

HELP = (
    "the Foreman's early conflict check of a parallel batch, at a ready hand-back: the CR "
    "against each other ready PR on the default branch, by `git merge-tree` only; notes each "
    "conflict on the CR and prints the one ask to send"
)


def register(sub: Subparsers) -> None:
    """Declare `conflicts`."""
    s = add_command(sub, "conflicts", "chantier.commands.conflicts:conflicts", HELP, BATCH_EPOCH)
    s.add_argument("cr", help="the CR handed back ready, with its PR")
