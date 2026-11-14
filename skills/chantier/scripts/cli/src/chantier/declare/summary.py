"""The parser of the `summary` command; the handlers load when one runs."""

from __future__ import annotations

import argparse

from chantier.commands.registry import NO_BATCH, Subparsers, add_command, lazy

# The limits of `core.records` (TITLE_MAX, SUMMARY_MAX, GROUP_MAX, TRACKERS), repeated here so
# the start-up imports no pydantic.
TITLE_MAX = 120
SUMMARY_MAX = 300
GROUP_MAX = 60
TRACKERS = ("github", "gitlab", "jira")

HELP = (
    "the CR's condensed JSON (title, summary, origin, labels, group): lint lists what is missing "
    "or late, set stores what an agent wrote, label and group link CRs"
)
PATH = "chantier.commands.summary"


def _action(actions: Subparsers, name: str, fn: str, help_: str) -> argparse.ArgumentParser:
    """One action of `summary`; `--project` is accepted after it too."""
    p: argparse.ArgumentParser = actions.add_parser(name, help=help_)
    p.set_defaults(fn=lazy(f"{PATH}:{fn}"))
    p.add_argument("--project", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    p.add_argument("--skill", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    return p


def register(sub: Subparsers) -> None:
    """Declare `summary` and its four actions."""
    s = add_command(sub, "summary", f"{PATH}:needs_action", HELP, NO_BATCH)
    s.description = HELP
    actions = s.add_subparsers(dest="action", required=True, metavar="lint|set|label|group")

    p = _action(actions, "lint", "lint", "list the CRs whose summary is missing or late")
    p.add_argument("folders", nargs="*", help="CR folders; none: every CR but the archives")

    p = _action(
        actions, "set", "set_summary", "store a CR's title and summary, and its checksums"
    )
    p.add_argument("folder", help="the CR's folder")
    p.add_argument("--title", help=f"one line, {TITLE_MAX} characters at most")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--summary", help=f"one line of plain text, {SUMMARY_MAX} characters at most")
    g.add_argument(
        "--unchanged", action="store_true", help="the changed files were read and it still holds"
    )
    p.add_argument(
        "--tracker", choices=TRACKERS, help="the issue: line's tracker, when its URL says not"
    )

    p = _action(actions, "label", "label", "add or remove labels on CRs")
    p.add_argument("folders", nargs="+", help="CR folders")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--add", help="comma-separated labels to add")
    g.add_argument("--remove", help="comma-separated labels to remove")

    p = _action(actions, "group", "group", "put CRs in a group, or take them out of theirs")
    p.add_argument("folders", nargs="+", help="CR folders")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--name", help=f"the group's name, one line, {GROUP_MAX} characters at most")
    g.add_argument("--clear", action="store_true", help="take the CRs out of their group")