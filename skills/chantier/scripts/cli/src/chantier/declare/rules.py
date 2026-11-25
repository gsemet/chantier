"""The parser of the `rules` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import (
    BATCH,
    IGNORED_LEASE,
    LEASE_IGNORED,
    Subparsers,
    add_command,
    add_lease,
)


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "rules",
        "chantier.commands.rules:rules",
        "the project's instruction file and the files it links",
        BATCH,
        LEASE_IGNORED,
    )
    add_lease(s, how=IGNORED_LEASE)

    s = add_command(
        sub,
        "playbook",
        "chantier.commands.rules:playbook",
        "the agent and model each role runs, from chantier.yaml (or, with --batch, as the batch "
        "opened); "
        "exit 2 if the file is invalid",
        BATCH,
    )
    s.add_argument(
        "--host",
        choices=["claude", "copilot"],
        help="the host to resolve for (default: the detected host); ignored with --batch",
    )
