"""The surface's autosync, read: the four states, the lines, and that nothing is ever deleted."""

from __future__ import annotations

import json
from pathlib import Path

from chantier.autosync.lines import preflight_check, status_line
from chantier.autosync.records import read_group
from chantier.autosync.site import GUIDELINES, AutosyncSite
from chantier.autosync.view import AutosyncView, Names, classify

LIVE, DEAD = 111, 222


def _site(folder: Path) -> AutosyncSite:
    return AutosyncSite(folder, folder / "x.py", GUIDELINES, folder / "state", False)


def _put(folder: Path, name: str, data: dict[str, object]) -> None:
    path = folder / "state" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _view(folder: Path, names: Names | None = None) -> AutosyncView:
    return classify(read_group(folder / "state"), lambda pid: pid == LIVE, names)


def test_the_four_states_and_the_lines(tmp_path: Path) -> None:
    assert _view(tmp_path).no_group
    assert status_line(_view(tmp_path)) == "autosync: no group yet"
    for pid, session in ((LIVE, "s-chief"), (DEAD, "s-gone")):
        _put(tmp_path, f"participants/{pid}.json", {"pid": pid, "session_id": session})
    _put(tmp_path, "watcher.json", {"pid": LIVE})
    _put(tmp_path, "status.json", {"state": "synced", "updated_at": 1_700_000_000})
    names = Names(chief=frozenset({"s-chief"}))
    active = _view(tmp_path, names)
    assert (active.state, active.leader, len(active.participants)) == (
        "active",
        "chief-of-staff",
        1,
    )
    assert status_line(active).startswith(
        "autosync active, leader chief-of-staff, 1 participant, synced "
    )
    assert preflight_check(_site(tmp_path), active).passed
    _put(tmp_path, "control.json", {"enabled": False, "reason": "stopped by user"})
    assert _view(tmp_path).state == "stopped"
    _put(tmp_path, "control.json", {"enabled": False, "reason": "blocked: upstream moved"})
    blocked = _view(tmp_path)
    assert (blocked.state, blocked.reason) == ("blocked", "upstream moved")
    assert not preflight_check(_site(tmp_path), blocked).passed
    _put(
        tmp_path,
        "status.json",
        {"state": "approval_required", "incident": "staged-a", "message": "m"},
    )
    assert _view(tmp_path).state == "approval"
    assert (tmp_path / "state" / "participants" / f"{DEAD}.json").is_file(), "read-only"
