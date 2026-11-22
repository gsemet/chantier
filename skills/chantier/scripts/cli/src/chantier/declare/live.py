"""The parser of the `live` command; the handler loads when it runs."""

from __future__ import annotations

from chantier.commands.registry import NO_BATCH, Subparsers, add_command

HELP = (
    "watch a running board live in the terminal, read-only: counts, projects and Drivers, the "
    "flow of events, the tasks with their lease time left"
)


def register(sub: Subparsers) -> None:
    """Declare `live`."""
    s = add_command(sub, "live", "chantier.commands.live:live", HELP, NO_BATCH)
    s.add_argument(
        "--url",
        action="append",
        default=[],
        metavar="LINK",
        help="a board's link (http(s)://host:port/[prefix/]?k=<key>), repeatable, at most 4; "
        "omitted: the board recorded as running for this surface or project",
    )
    s.add_argument(
        "--only",
        action="append",
        default=[],
        metavar="PROJECT",
        help="watch this project only (repeatable); omitted: every project, the first 15",
    )
    s.add_argument(
        "--transport",
        choices=("auto", "ws", "http"),
        default="auto",
        help="auto (default): the WebSocket, else the HTTP long-poll; ws or http: that one only",
    )
    s.add_argument(
        "--once",
        action="store_true",
        help="print the screen once as plain text and exit (for a test, a script or a bug report)",
    )
