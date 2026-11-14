"""The texts that report the surface's autosync: the preflight's P13 and the line of `status`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from chantier.autosync.site import AutosyncSite
from chantier.autosync.view import AutosyncView

RESTART = "the Chief of Staff integrates, then start . --enable-only"
PREFLIGHT_CUT = 120
STATUS_CUT = 70


@dataclass(frozen=True)
class Check:
    """A check's outcome: `passed` is an `ok` line, else a `warn` line."""

    passed: bool
    text: str


def _cut(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _count(view: AutosyncView) -> str:
    n = len(view.participants)
    return f"{n} participant{'' if n == 1 else 's'}"


def _active_check(site: AutosyncSite, view: AutosyncView) -> Check:
    if not view.participants:
        return Check(
            False,
            f"the surface's autosync is active but has no live participant: join it "
            f"({site.guidelines})",
        )
    return Check(
        True,
        f"the surface's autosync is active: leader {view.leader or 'none'}, {_count(view)}",
    )


def preflight_check(site: AutosyncSite, view: AutosyncView) -> Check:
    """P13: the line for the surface's autosync (warn-only)."""
    if site.script_missing:
        return Check(
            False,
            "the surface names an autosync but scripts/ai-autosync-git.py is missing: "
            "no autosync until it is there",
        )
    if view.no_group:
        return Check(False, f"the surface's autosync has no group yet: join it ({site.guidelines})")
    if view.state == "approval":
        return Check(
            False,
            f"the surface's autosync waits for the user's approval of incident {view.incident}: "
            f"{_cut(view.incident_message, PREFLIGHT_CUT)}",
        )
    if view.state == "blocked":
        return Check(
            False,
            f"the surface's autosync is blocked: {_cut(view.reason, PREFLIGHT_CUT)}: {RESTART}",
        )
    if view.state == "stopped":
        return Check(
            True,
            f"the surface's autosync is stopped ({view.reason or 'no reason'}): "
            "commit the surface by hand",
        )
    return _active_check(site, view)


def _synced(view: AutosyncView) -> str:
    if view.last_push is None:
        return ""
    return f", synced {datetime.fromtimestamp(view.last_push).strftime('%H:%M')}"


def status_line(view: AutosyncView) -> str:
    """The line `status` shows right after the batch's first line."""
    if view.no_group:
        return "autosync: no group yet"
    if view.state == "approval":
        return (
            f"autosync waits for the user's approval: incident {view.incident}: "
            f"{_cut(view.incident_message, STATUS_CUT)}"
        )
    if view.state == "blocked":
        return f"autosync blocked: {_cut(view.reason, STATUS_CUT)}: {RESTART}"
    if view.state == "stopped":
        return f"autosync stopped ({view.reason or 'no reason'}): commit the surface by hand"
    if not view.participants:
        return "autosync active, no live participant: join it"
    local = ", local only" if view.local_only else ""
    return f"autosync active, leader {view.leader or 'none'}, {_count(view)}{_synced(view)}{local}"
