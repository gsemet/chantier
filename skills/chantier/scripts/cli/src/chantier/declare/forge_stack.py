"""The parser of the `forge_stack` command(s); the handlers load when one runs."""

from __future__ import annotations

from chantier.commands.registry import BATCH, Subparsers, add_command


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "forge-stack",
        "chantier.commands.forge_stack:forge_stack",
        "create: the stack batch's stack as it stands (the bottom CRs with a PR, drafts on top), "
        "on GitHub its native stack, on GitLab the chain of MRs each targeting the one below, "
        "bottom to top, the release last; "
        "show: read it back, one line per failed check (exit 2), else `stack #N ready to merge:`; "
        "rebuild: make the forge's "
        "stack match the record (GitHub unstacks, retargets and creates again, GitLab retargets)",
        BATCH,
    )
    s.add_argument("action", choices=["create", "show", "rebuild"])
    s.add_argument(
        "--stack",
        type=int,
        metavar="N",
        help="show: the stack's number (default: the one that holds the batch's PRs); GitHub only",
    )
