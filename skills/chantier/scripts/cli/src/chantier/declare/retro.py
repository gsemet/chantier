"""The parser of the `retro` command; the handler loads when it runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH_EPOCH, Subparsers, add_command

HELP = (
    "draft: the retro's draft points from the batch's events (asks, blocks, refusals, Driver "
    "restarts, red gates, cost outliers), each with `home:`, `count:` and `why not code:` for the "
    "author; printed, or appended to `retro.md` with `--write` when it has no draft section; it "
    "files no point"
)


def register(sub: Subparsers) -> None:
    """Declare `retro`."""
    s = add_command(sub, "retro", "chantier.commands.retro:retro", HELP, BATCH_EPOCH)
    s.add_argument("action", choices=["draft"])
    s.add_argument(
        "--since",
        type=int,
        metavar="SEQ",
        help="the batch's event sequence to start after (0: every event); default: the window "
        "of the current pause",
    )
    s.add_argument(
        "--write",
        action="store_true",
        help="append the draft section to 4-batch/retro.md when the file has none",
    )
