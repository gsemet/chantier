"""What the group's files say, as one value: the state, its reason, the leader and the members.
`classify` is pure; the process check is handed in."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from chantier.autosync.records import GroupFiles, Participant

BLOCKED = "blocked:"
APPROVAL = "approval_required"
SYNCED = "synced"
BOARD_SESSION = "chantier-board"
BOARD_NAME = "board"  # neutral: the page translates it ("autosync.who.board")


@dataclass(frozen=True)
class Names:
    """What names a participant: the board server's pid, and the sessions that are known."""

    server_pid: int | None = None
    chief: frozenset[str] = frozenset()
    foreman: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Member:
    name: str
    role: str


@dataclass(frozen=True)
class AutosyncView:
    """`state` is active, stopped, blocked or approval."""

    state: str
    reason: str = ""
    incident: str | None = None
    incident_message: str = ""
    leader: str | None = None
    participants: tuple[Member, ...] = ()
    last_push: float | None = None  # epoch seconds, while the status is `synced`
    local_only: bool = False
    no_group: bool = False


def name_participant(p: Participant, names: Names) -> str:
    """How a participant is called, in this order: the board server, the Chief of Staff, the
    Foreman, another session by its first 8 characters, else its harness and pid."""
    session = p.session_id
    if names.server_pid is not None and p.owner_pid == names.server_pid:
        return BOARD_NAME
    if session and session in names.chief:
        return "chief-of-staff"
    if session and session in names.foreman:
        return "foreman"
    if session:
        return f"session {session[:8]}"
    return f"{p.harness or 'unknown'} pid {p.pid}"


def _state_and_reason(files: GroupFiles) -> tuple[str, str, str | None]:
    """(state, reason, incident) from the control and status files."""
    status, control = files.status, files.control
    if status and status.state == APPROVAL and status.incident:
        return "approval", "", status.incident
    if "control.json" in files.unreadable:
        return "blocked", "unreadable: control.json", None
    if control is None or control.on:
        return "active", "", None
    if control.reason.startswith(BLOCKED):
        return "blocked", control.reason.removeprefix(BLOCKED).strip(), None
    return "stopped", control.reason, None


def _leader(files: GroupFiles, live: list[Participant], names: Names) -> str | None:
    pid = files.watcher.pid if files.watcher else None
    if pid is None:
        return None
    mine = next((p for p in live if p.pid == pid), None)
    return name_participant(mine, names) if mine else f"pid {pid}"


def classify(
    files: GroupFiles, alive: Callable[[int], bool], names: Names | None = None
) -> AutosyncView:
    """The group as one value. A state folder that does not exist yet is `no_group` (stopped)."""
    names = names or Names()
    if not files.exists:
        return AutosyncView("stopped", no_group=True)
    state, reason, incident = _state_and_reason(files)
    live = [p for p in files.participants if alive(p.pid)]
    status, control = files.status, files.control
    synced = bool(status and status.state == SYNCED)
    return AutosyncView(
        state=state,
        reason=reason,
        incident=incident,
        incident_message=status.message if incident and status else "",
        leader=_leader(files, live, names),
        participants=tuple(Member(name_participant(p, names), p.role) for p in live),
        last_push=status.updated_at if synced and status else None,
        local_only=bool(control and control.local_only),
    )
