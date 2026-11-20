"""The parser of the `sync` command; the handler loads when it runs."""

from __future__ import annotations

from chantier.commands.registry import NO_BATCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "sync",
        "chantier.commands.sync:sync",
        "the surface's writer: show its state, or `now` to ask for a cycle at once",
        NO_BATCH,
    )
    s.add_argument("action", nargs="?", choices=["now"], help="now: wake the writer and wait")
