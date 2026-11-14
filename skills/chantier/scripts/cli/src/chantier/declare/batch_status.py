"""The parser of the `batch_status` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH, BATCH_EPOCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "status",
        "chantier.commands.batch_status:status",
        "one line per CR, the open orders (untouched, then applied), the unread asks; "
        "--refresh: the live facts; its line says `heartbeat N min` (since the last "
        "`--refresh --epoch`), `never` or `stopped`",
        BATCH_EPOCH,
    )
    s.add_argument("--notes", action="store_true", help="each CR's last note")
    s.add_argument(
        "--refresh",
        action="store_true",
        help="the activity of each working CR (age of its last event or session "
        "record, `gate running`, `gate queued behind <cr>`, `not measured`) "
        "and the spend (recorded); "
        "with --epoch, the steering session's wake: it records the heartbeat "
        "and prints the gap since the wake before; without, it moves nothing",
    )
    s.add_argument(
        "--stop-heartbeat",
        action="store_true",
        help="with --epoch: record that the steering session ended its loop "
        "(`heartbeat stopped`, until the next wake)",
    )

    s = add_command(
        sub,
        "asks",
        "chantier.commands.batch_status:asks",
        "the Foreman's asks still unread; with text, record one",
        BATCH,
    )
    s.add_argument("text", nargs="*", help="the Foreman's own ask")
    s.add_argument("--read", metavar="A-k|all", help="mark heard")

    s = add_command(
        sub,
        "agents",
        "chantier.commands.batch_status:agents",
        "map a CR (or stack) to its agent id",
        BATCH_EPOCH,
    )
    s.add_argument("action", choices=["set"])
    s.add_argument("cr")
    s.add_argument("agent", help="the agent id; `-` clears it")
