"""The parsers of `msg` and `inbox`; the handlers load when they run."""

from __future__ import annotations

from chantier.commands.registry import BATCH, BATCH_EPOCH, Subparsers, add_command, add_lease

PATH = "chantier.commands.msg"
MSG_HELP = (
    "a Driver tells the batch's steering session (the Foreman, or the Chief of Staff in direct "
    "mode) through its watcher: anomaly and blocked wake it, a note waits for its next wake"
)
INBOX_HELP = (
    "the steering session's unread messages from the batch's Drivers; --read marks them read"
)
KINDS = ("anomaly", "blocked", "note")


def register(sub: Subparsers) -> None:
    """Declare `msg` and `inbox`."""
    s = add_command(sub, "msg", f"{PATH}:msg", MSG_HELP, BATCH)
    s.add_argument("target", choices=["steering"], help="steering: the batch's steering session")
    s.add_argument("kind", choices=KINDS, help="anomaly and blocked wake it; a note does not")
    s.add_argument("text", nargs="+", help="the message, one line of at most 300 characters")
    s.add_argument("--cr", required=True, help="the unit whose lease you hold: a CR id, or stack")
    add_lease(s, required=True)
    s = add_command(sub, "inbox", f"{PATH}:inbox", INBOX_HELP, BATCH_EPOCH)
    s.add_argument(
        "--read",
        metavar="SEQ|all",
        help="mark that message read (its seq), or every unread one (all)",
    )
