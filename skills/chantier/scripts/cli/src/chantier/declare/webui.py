"""The parser of the `webui` command; the handler loads when it runs."""

from __future__ import annotations

from chantier.commands.registry import NO_BATCH, Subparsers, add_command

HELP = (
    "print the web board's link, with its key; start the surface server, detached, when none "
    "runs (it stops by itself 30 minutes after its last client)"
)


def register(sub: Subparsers) -> None:
    """Declare `webui`."""
    add_command(sub, "webui", "chantier.commands.webui:webui", HELP, NO_BATCH)
