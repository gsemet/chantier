"""The sentences the writer's journal lines are told by (`sync-*@1` and `arrived@1`), and what the
Chief of Staff does about each reason the writer is blocked for."""

from __future__ import annotations

from typing import Any

from chantier.core import clock

# What the Chief of Staff does about each reason the writer is blocked for (the spec's C.6).
WAY_OUT = {
    "not-a-branch": "check out the default branch",
    "no-upstream": "set it (`git branch -u <remote>/<branch>`)",
    "git-busy": "finish or abort it",
    "nested-repo": (
        "move it out of the surface, or, when it is the project's code clone or worktrees "
        "folder, name it in the project's `checkout.yml`"
    ),
    "staged": "commit or unstage them by hand",
    "foreign-autosync": "stop the tool (`uv run scripts/ai-autosync-git.py stop .`)",
    "path-too-long": (
        "move it, or the folder that holds it, under its CR's `work/scratch/` (downloaded CI "
        "artifacts go there, never published), or shorten it; the next cycle that completes "
        "its git steps ends it (`sync now` runs one at once)"
    ),
    "git-error": (
        "read the text and repair it (a stash: tell the user where the edits are, "
        "`git stash list`); the next cycle that completes its git steps ends it "
        "(`sync now` runs one at once)"
    ),
}


def files_shown(files: list[str], at_most: int = 3) -> str:
    """The files a conflict names: at most three, then `and <k> more`."""
    shown = ", ".join(files[:at_most])
    return f"{shown} and {len(files) - at_most} more" if len(files) > at_most else shown


def sync_conflict_text(e: dict[str, Any]) -> str:
    return (
        f"writer saw a conflict with the remote on {files_shown(list(e.get('files') or []))}; "
        "for the Chief of Staff: integrate by rebase, resolve to your best guess or ask the user"
    )


def sync_blocked_text(e: dict[str, Any]) -> str:
    way = WAY_OUT.get(str(e.get("reason")), "read the text")
    return f"writer blocked ({e.get('reason')}): {e.get('text')}; for the Chief of Staff: {way}"


def sync_late_text(e: dict[str, Any]) -> str:
    return (
        f"writer late: {e.get('paths')} paths and {e.get('ahead')} commits not pushed since "
        f"{clock.local_hhmm(e.get('since'))}; for the Chief of Staff: read sync, tell the user "
        "if it lasts"
    )


def sync_resumed_text(e: dict[str, Any]) -> str:
    return f"writer resumed after {e.get('after')}"


def arrived_text(e: dict[str, Any]) -> str:
    """The line an `arrived@1` event is told by: a CR that reached the inbox or the backlog."""
    who = "surface pull brought" if e.get("via") == "pull" else "another session wrote"
    before = str(e.get("before") or "")
    if not before:
        what = f"new in {e.get('stage')}"
    elif before.startswith("3-ready/"):
        what = "back from 3-ready"
    else:
        what = f"moved from {before}"
    return (
        f"{who} {e.get('folder')} ({what}); for the Chief of Staff: tell the user, act on nothing"
    )
