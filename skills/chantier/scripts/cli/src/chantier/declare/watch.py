"""The parser of the `watch` command; the handler loads when it runs."""

from __future__ import annotations

from chantier.commands.registry import NO_BATCH, Subparsers, add_command

HELP = (
    "wait in the background for the events of this project, subscribed to the surface server "
    "(chantier serve): the forge's (merges, CI red on a PR ready to merge), the board's writes "
    "(backlog, configuration) and the issue events an outside poller writes, with or without a "
    "batch; with no server running it starts one, detached, when the project's seat is this "
    "session's, else it ends and says why; every event is addressed (its audience: project, "
    "role:<name>, cr:<id>, session:<key> or user) and a watcher reads the lines for it: the "
    "project's, its own session's and each --for value; 20 s after the last new event for it "
    "that wakes, and no sooner than events.wake_every after its start or its last telling, it "
    "tells the events it gathered and ends, or with --stream prints them with a still watching "
    "line and runs on; it ends when the project's seat is another session's, and, while no batch "
    "runs and none is paused with an open PR, 2 h after the latest of its start, its last event "
    "that wakes and the last moment such a batch ran or was paused so; run by the session that "
    "the running or paused batch records as its Foreman, it is the Foreman's watcher: it reads "
    "only that batch's merge, red-CI and wait-met lines, starts no server (it ends at once when "
    "none runs), and never ends on the seat but when the batch records another Foreman or "
    "closes; the server alone reads the forge, every 20 s while observed; --once --after SEQ "
    "prints the journal's lines for it past SEQ and exits"
)


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(sub, "watch", "chantier.hub.watch_cmd:watch", HELP, NO_BATCH)
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
        "no lock, reach no server, start nothing",
    )
    s.add_argument(
        "--stream",
        action="store_true",
        help="run through several events: print each block with a still watching line and run "
        "on, ending only on another session's seat, the 2 h with no batch in flight or a lost "
        "board (the form the CLI prints on Claude Code); not with --once",
    )
