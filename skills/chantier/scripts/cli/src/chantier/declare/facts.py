"""The parser of the `facts` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import (
    ALSO_LEASE,
    BATCH,
    LEASE_ALSO,
    Subparsers,
    add_command,
    add_lease,
)


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "handoff",
        "chantier.commands.facts:handoff",
        "the CR's facts, for any agent; changes nothing (with --lease: renews it)",
        BATCH,
        LEASE_ALSO,
    )
    s.add_argument("cr")
    add_lease(s, how=ALSO_LEASE)
