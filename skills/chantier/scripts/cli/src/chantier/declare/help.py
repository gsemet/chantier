"""The parser of the `help` command; the handler loads when it runs."""

from __future__ import annotations

from chantier.commands.registry import NO_BATCH, Subparsers, add_command

HELP = (
    "print a help topic whole, the rare case a refusal or a line named; with no topic, list "
    "them; --for lists one role's; reads only the plugin's cards, needs no batch and no project"
)


def register(sub: Subparsers) -> None:
    """Declare `help`."""
    s = add_command(sub, "help", "chantier.commands.help:show", HELP, NO_BATCH)
    s.add_argument("topic", nargs="?", help="the topic to print whole (none: list them all)")
    s.add_argument("--for", dest="role", help="list the topics that serve this role")
    s.add_argument(
        "--host",
        choices=["claude", "copilot"],
        help="the host whose readings to print (default: the detected host)",
    )
