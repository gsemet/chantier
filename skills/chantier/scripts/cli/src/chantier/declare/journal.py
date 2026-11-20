"""The parser of the `journal` command; the handler loads when it runs."""

from __future__ import annotations

import argparse

from chantier.commands.registry import NO_BATCH, Subparsers, add_command, lazy

HELP = (
    "append one event an outside poller read on a tracker to this project's journal: only "
    "issue@1, only for an issue a CR's issue: line names; --json - reads the payload from stdin"
)
PATH = "chantier.hub.journal_add"


def register(sub: Subparsers) -> None:
    """Declare `journal` and its one action, `add`."""
    s = add_command(sub, "journal", f"{PATH}:needs_action", HELP, NO_BATCH)
    s.description = HELP
    actions = s.add_subparsers(dest="action", required=True, metavar="add")
    p: argparse.ArgumentParser = actions.add_parser("add", help="append one issue@1 event")
    p.set_defaults(fn=lazy(f"{PATH}:add"))
    p.add_argument("--project", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    p.add_argument("--skill", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    p.add_argument("type", help="the event's type: issue@1")
    p.add_argument(
        "--json",
        required=True,
        metavar="PAYLOAD",
        help="the payload as a JSON object, or - to read it from stdin (UTF-8)",
    )
