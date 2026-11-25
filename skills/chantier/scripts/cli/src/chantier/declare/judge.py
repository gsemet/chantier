"""The parser of the `judge` command; the handler loads when it runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH_EPOCH, Subparsers, add_command

HELP = (
    "the steering session's ask to the user for a CR handed back, worded from the record (its "
    "readiness word, gaps, gate, waits, owed items); `--record` records it as `asks` does; it "
    "decides no merge and no take-back"
)


def register(sub: Subparsers) -> None:
    """Declare `judge`."""
    s = add_command(sub, "judge", "chantier.commands.judge:judge", HELP, BATCH_EPOCH)
    s.add_argument("cr", help="the CR handed back")
    s.add_argument(
        "--local-gate",
        action="store_true",
        help="the project's rules ask this CR for a local long-gate run: add its clause",
    )
    s.add_argument(
        "--record",
        nargs="?",
        const="",
        metavar="SENTENCE",
        help="record the ask as `asks` does, with your one sentence appended",
    )
