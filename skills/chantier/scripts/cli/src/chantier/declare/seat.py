"""The parser of the `seat` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH_EPOCH, NO_BATCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "foreman",
        "chantier.commands.seat:foreman",
        "the Foreman claims its epoch (set) and records its transcript",
        BATCH_EPOCH,
    )
    s.add_argument("action", choices=["set", "get", "transcript"])
    s.add_argument("value", nargs="?")

    s = add_command(
        sub,
        "seat",
        "chantier.commands.seat:seat",
        "the repository's Chief of Staff session: show, take or leave the seat",
        NO_BATCH,
    )
    s.add_argument("action", nargs="?", choices=["get", "take", "leave"], default="get")
    s.add_argument("session", nargs="?", help="the session id, for take and leave")
    s.add_argument("--env", help="take: the machine's name, or Remote")
    s.add_argument("--title", help="take: the session's current title")
    s.add_argument("--link", help="take: the session's link")
    s.add_argument(
        "--over",
        metavar="SESSION",
        help="take: the session whose seat this one takes, on the user's word",
    )
