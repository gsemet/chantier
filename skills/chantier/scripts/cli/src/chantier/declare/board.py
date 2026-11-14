"""The parser of the `board` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import NO_BATCH, Subparsers, add_command

HELP = (
    "serve the web board (the record, the planning folder's files, the backlog) on this machine "
    "and the local network, behind a key in its URL"
)


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(sub, "board", "chantier.board.command:board", HELP, NO_BATCH)
    s.add_argument(
        "--host",
        help="the address to listen on (default: chantier.yaml's board.host, else 0.0.0.0, the "
        "local network)",
    )
    s.add_argument(
        "--port",
        type=int,
        help="the port, or 0 for a free one the system picks (default: chantier.yaml's "
        "board.port, else 8765)",
    )
    s.add_argument(
        "--seat",
        metavar="SESSION",
        help="the Chief of Staff session this board is for: the board follows its seats and "
        "stops when none of them names its session any more",
    )
    s.add_argument(
        "--clock",
        metavar="TIMESTAMP",
        help="answer as if it were this instant (UTC, YYYY-MM-DDTHH:MM:SSZ), for screenshots "
        "and tests",
    )
    s.add_argument(
        "--new-key",
        action="store_true",
        help="replace the board's key: the old link stops working",
    )
