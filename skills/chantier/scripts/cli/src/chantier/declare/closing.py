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
        "refused while anything of the batch runs (a held agent, the current Foreman included, "
        "whose transcript shows it still runs, or that cannot be read); the session's other "
        "subagents and replaced Foremans are listed, never a block; prints the final cost and "
        "what deleting a paused batch would remove; --yes deletes it; --stopped NAME passes a "
        "held agent that stopped without its hand-back, on the user's word",
        BATCH,
    )
    s.add_argument("--yes", action="store_true", help="on the user's word")
    s.add_argument(
        "--stopped",
        action="append",
        metavar="NAME",
        help="(repeatable) an agent the batch holds (`agents set`, or the current Foreman's "
        "session id) that the user declares stopped: its transcript reads as running but it "
        "ended without its hand-back; on the user's word only, recorded in the batch's record; "
        "it never passes a recorded stack agent, which always refuses: clear it with "
        "`agents set stack -`",
    )
