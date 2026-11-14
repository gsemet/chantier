"""The parser of the `rules` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    add_command(
        sub,
        "rules",
        "chantier.commands.rules:rules",
        "the project's instruction file and the files it links",
        BATCH,
    )

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
