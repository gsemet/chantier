"""The parser of the `watch` command; the handler loads when it runs."""

from __future__ import annotations

from chantier.commands.registry import NO_BATCH, Subparsers, add_command

HELP = (
    "wait in the background for the forge events of this project's running batch (merges, CI "
    "red on a PR ready to merge), read from the local journal; one process per surface and "
    "machine reads the forge for all, every 20 s"
)


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(sub, "watch", "chantier.hub.watch:watch", HELP, NO_BATCH)
    s.add_argument(
        "--after",
        type=int,
        metavar="SEQ",
        help="count the events whose seq is greater than this, including those written while no "
        "watcher ran (default: the journal's highest seq now)",
    )
