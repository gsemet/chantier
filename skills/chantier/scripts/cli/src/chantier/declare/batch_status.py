"""The parser of the `batch_status` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH, BATCH_EPOCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    _register_status(sub)
    s = add_command(
        sub,
        "asks",
        "chantier.commands.batch_status:asks",
        "the Foreman's asks still unread; with text, record one "
        "(a readiness ask marks the CR's earlier unread one read); in a stack batch, a per-CR "
        "ready-to-merge is refused while another CR of the stack has an open PR or a stacked CR "
        'is open; a CR not in the stack\'s chain asks alone; --outside-stack "O-<k>: <why>" '
        "records it on an open order on that CR that carries the user's word",
        BATCH,
    )
    s.add_argument("text", nargs="*", help="the Foreman's own ask")
    s.add_argument("--read", metavar="A-k|all", help="mark heard")
    s.add_argument(
        "--outside-stack",
        metavar="O-k: why",
        help="records a per-CR ready-to-merge that the stack guard refuses, on an open order "
        "on that CR that carries the user's word",
    )
    _register_agents(sub)


def _register_status(sub: Subparsers) -> None:
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
        "--since",
        type=int,
        metavar="SEQ",
        help="only what changed since this event sequence of the batch (`0`: everything); "
        "merged and cancelled CRs as counts; the last line gives the sequence for next time; "
        "it records nothing",
    )
    s.add_argument(
        "--stop-heartbeat",
        action="store_true",
        help="needs --epoch: record that the steering session ended its loop "
        "(`heartbeat stopped`, until the next wake)",
    )


def _register_agents(sub: Subparsers) -> None:
    s = add_command(
        sub,
        "agents",
        "chantier.commands.agents:agents",
        "map a CR (or stack) to its agent id",
        BATCH_EPOCH,
    )
    s.add_argument("action", choices=["set"])
    s.add_argument("cr")
    s.add_argument(
        "agent",
        help="the agent id; `-` clears it (and ends the unit's live lease, so a restart does "
        "not wait)",
    )
    s.add_argument(
        "--reclaim",
        action="store_true",
        help="a QA order's restart over a live (only on the user's word) or not confirmed lease: "
        "ends it and starts the next",
    )
