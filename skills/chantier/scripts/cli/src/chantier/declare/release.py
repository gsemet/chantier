"""The parser of the `release` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH, BATCH_EPOCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "release",
        "chantier.commands.release:release",
        "release driver: start an attempt, go for an irreversible action, published",
        BATCH,
    )
    s.add_argument("action", choices=["start", "go", "published"])
    s.add_argument("cr")
    s.add_argument("--note", help="go: the irreversible action; published: version and link")

    s = add_command(
        sub,
        "cancel",
        "chantier.commands.release:cancel",
        "stop a CR's processes and mark it cancelled",
        BATCH_EPOCH,
    )
    s.add_argument("cr")
