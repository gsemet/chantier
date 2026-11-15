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
        "refused while anything runs (an agent whose transcript shows it still runs, or that "
        "cannot be read); prints the final cost and what deleting a paused batch would remove; "
        "--yes deletes it; --stopped NAME passes an agent that stopped without its hand-back, "
        "on the user's word",
        BATCH,
    )
    s.add_argument("--yes", action="store_true", help="on the user's word")
    s.add_argument(
        "--stopped",
        action="append",
        metavar="NAME",
        help="(repeatable) an agent the user declares stopped: its transcript reads as running "
        "but it ended without its hand-back; on the user's word only, recorded in the batch's "
        "record",
    )
