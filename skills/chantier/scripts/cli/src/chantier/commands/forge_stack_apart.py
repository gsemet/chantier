"""`forge-stack`: the batch's PRs kept off the stack, on the default branch (held, moved out of the
batch, dropped)."""

from __future__ import annotations

from typing import Any

from chantier.commands.forge_stack_gh import PR_LINK
from chantier.commands.forge_stack_gitlab import GITLAB_LINK
from chantier.core.records import BatchRecord
from chantier.stacks import is_held

Moved = dict[int, tuple[str, str]]


def held(data: BatchRecord) -> dict[int, str]:
    """The PR numbers (to their CR ids) of the batch's held CRs that have a PR: kept out of the
    stack, on the default branch."""
    found = {}
    for c in data.crs:
        link = (PR_LINK.match(c.pr) or GITLAB_LINK.match(c.pr)) if c.pr else None
        if is_held(c) and link:
            found[int(link.groups()[-1])] = c.id
    return found


def held_rows(rows: list[dict[str, Any]], held: dict[int, str]) -> list[dict[str, Any]]:
    """What `retarget` takes for the held PRs: each on the default branch."""
    return [
        {"number": n, "base": rows[0]["default"], "why": " (held out of the stack)"} for n in held
    ]


def moved(data: BatchRecord) -> Moved:
    """The PR numbers of the batch's CRs moved to the inbox or the backlog that have a PR (to
    their CR id and folder): their work is kept, they are left out of the stack, on main."""
    found = {}
    for c in data.crs:
        link = (PR_LINK.match(c.pr) or GITLAB_LINK.match(c.pr)) if c.pr else None
        if c.moved_to() and link:
            found[int(link.groups()[-1])] = (c.id, str(c.moved_to()))
    return found


def moved_rows(rows: list[dict[str, Any]], moved: Moved) -> list[dict[str, Any]]:
    """What `retarget` takes for the moved PRs: each on the default branch, with its reason."""
    return [
        {"number": n, "base": rows[0]["default"], "why": f" (moved to {dest})"}
        for n, (_, dest) in moved.items()
    ]


def dropped(data: BatchRecord) -> dict[int, str]:
    """The PR numbers (to their CR ids) of the batch's cancelled CRs that have a PR and went to
    the trash (or have no recorded destination), a fix CR apart: a dropped CR's PR is named
    apart from a foreign one."""
    found = {}
    for c in data.crs:
        link = (PR_LINK.match(c.pr) or GITLAB_LINK.match(c.pr)) if c.pr else None
        if c.status == "cancelled" and c.kind != "fix" and not c.moved_to() and link:
            found[int(link.groups()[-1])] = c.id
    return found
