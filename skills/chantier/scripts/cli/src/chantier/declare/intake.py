"""The parser of the `intake` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import NO_BATCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    add_command(
        sub,
        "init",
        "chantier.commands.intake:init",
        "create the empty stage folders of the planning folder and its .gitignore; changes "
        "nothing else",
        NO_BATCH,
    )

    s = add_command(
        sub, "file", "chantier.commands.intake:file_cr", "file a request in the inbox", NO_BATCH
    )
    s.add_argument("item", help="request text, or @path to the raw request")
    s.add_argument("--slug", help="folder name when the inferred slug is already used")

    s = add_command(
        sub,
        "triage",
        "chantier.commands.intake:triage",
        "move an inbox, backlog or 3-ready CR to a priority of the backlog, or to 3-ready",
        NO_BATCH,
    )
    s.add_argument(
        "item",
        help="path to the CR folder: 1-inbox/<item>, 2-backlog/P<n>/<item> or 3-ready/<item>",
    )
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--priority", choices=["P1", "P2", "P3", "P4"])
    g.add_argument(
        "--ready", action="store_true", help="the CR waits in 3-ready for the next batch"
    )
    _register_trash(sub)


def _register_trash(sub: Subparsers) -> None:
    s = add_command(
        sub,
        "abandon",
        "chantier.commands.intake:abandon",
        "move an explicitly abandoned CR to trash",
        NO_BATCH,
    )
    s.add_argument("item", help="path to the unclaimed CR folder")

    s = add_command(
        sub,
        "restore",
        "chantier.commands.intake:restore",
        "bring a trashed CR back to the inbox",
        NO_BATCH,
    )
    s.add_argument("item", help="path to the folder directly under 6-trash")
    s.add_argument("--slug", help="the inbox name, when the old one is taken or to rename")
