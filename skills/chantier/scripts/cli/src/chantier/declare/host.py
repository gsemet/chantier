"""The parser of the `host` command; the handler loads when it runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "host",
        "chantier.commands.host:host",
        "how this host does a capability, from the plugin's host rows; with no capability, "
        "every row",
        BATCH,
    )
    s.add_argument("capability", nargs="?", help="a capability id, e.g. start-driver")
