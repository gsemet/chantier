"""The parsers of `login` and `logout`; the handlers load when they run."""

from __future__ import annotations

from chantier.commands.registry import NO_BATCH, OWN_PROJECT, Subparsers, add_command

LOGIN = (
    "log in to a chantier server (the link `chantier webui` prints): afterwards every command "
    "for the projects named runs on that server; with no link, list the profiles; "
    "--profile NAME names the profile (default `default`)"
)
LOGOUT = (
    "forget a profile (the default one, or the one --profile NAME names): commands run here again"
)


def register(sub: Subparsers) -> None:
    """Declare `login` and `logout`."""
    s = add_command(sub, "login", "chantier.commands.login:login", LOGIN, OWN_PROJECT)
    s.add_argument("link", nargs="?", help="the server's link, private or read-only")
    s.add_argument(
        "--project",
        dest="projects",
        action="append",
        default=[],
        metavar="ID",
        help="(repeatable) a project the server serves; omitted: the server's home project",
    )
    s.add_argument(
        "--no-default",
        action="store_true",
        help="store the profile without making it the default (use --profile NAME to run there)",
    )
    add_command(sub, "logout", "chantier.commands.login:logout", LOGOUT, NO_BATCH)
