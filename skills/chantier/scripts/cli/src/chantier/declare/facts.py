"""The parser of the `facts` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "handoff",
        "chantier.commands.facts:handoff",
        "the CR's facts, for any agent; changes nothing",
        BATCH,
    )
    s.add_argument("cr")
