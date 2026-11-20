"""The parser of the `watch` command; the handler loads when it runs."""

from __future__ import annotations

from chantier.commands.registry import NO_BATCH, Subparsers, add_command

HELP = (
    "wait in the background for the events of this project, read from the local journal: the "
    "forge's (merges, CI red on a PR ready to merge) and the board's writes (backlog, "
    "configuration), and the issue events an outside poller writes, with or without a batch; "
    "every event is addressed (its audience: project, "
    "role:<name>, cr:<id>, session:<key> or user) and a watcher reads the lines for it: the "
    "project's, its own session's and each --for value; it ends 20 s after the last new event "
    "for it that wakes, and no sooner than events.wake_every after its start, or when the "
    "project's seat is another session's; one process per surface and machine reads the "
    "forge for all, every 20 s; --once --after SEQ prints the lines for it past SEQ and exits"
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
    s.add_argument(
        "--for",
        dest="audience",
        action="append",
        metavar="AUDIENCE",
        help="also read the lines for this audience (repeatable): project, role:<name>, cr:<id>, "
        "session:<key> or user; none is the default, the project and this session",
    )
    s.add_argument(
        "--once",
        action="store_true",
        help="the pull path: print the journal's lines past --after and the next command, take "
        "no lock, read no forge, start nothing",
    )
