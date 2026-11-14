"""The parser of the `closing` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH, BATCH_EPOCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    add_command(
        sub,
        "pause",
        "chantier.commands.closing:pause",
        "pause the batch once its work is done: refused while anything is live or already "
        "paused; prints the cost to date",
        BATCH_EPOCH,
    )

    s = add_command(
        sub,
        "close",
        "chantier.commands.closing:close",
        "refused while anything runs; prints the final cost and what deleting a paused batch "
        "would remove; --yes deletes it",
        BATCH,
    )
    s.add_argument("--yes", action="store_true", help="on the user's word")
