"""The texts of the writer (the spec's C.10 and C.8), written once: the `writer:` line by state,
the refusal of a write with no writer, and the line a command adds when its write is not pushed
yet. It imports no module that imports `core.repo`, so the store can use it."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from chantier import __version__
from chantier.board import running
from chantier.core import clock
from chantier.hub import state
from chantier.hub.sync_text import WAY_OUT, files_shown

START = (
    'start the watcher, which starts the surface server (the "watch: not running" line\'s '
    "command), or, on a host that cannot run the watcher, $CHANTIER serve --seat <session id> "
    "--forge-always"
)
LIVE_STATES = ("synced", "pending", "syncing")  # P13's `ok`


def older_board(git_dir: Path) -> dict[str, Any] | None:
    """A live `server` entry of another version than this one, when no live `writer` entry
    exists: an older board that serves the surface with no writer."""
    if state.live_entry(git_dir, state.WRITER) is not None:
        return None
    server = state.live_entry(git_dir, state.SERVER)
    return server if state.other_version(server, __version__) else None


def older_text(server: dict[str, Any]) -> str:
    return (
        f"chantier serve {server.get('version')} (PID {server.get('pid')}) serves this surface "
        f"with no writer"
    )


def _then(server: dict[str, Any]) -> str:
    stop = running.stop_command(int(server["pid"]))
    return f"ask the user to stop it ({stop}), then {START}"


def refused(git_dir: Path) -> bool:
    """No live writer, or one that died (`stopped`): a published write is refused."""
    entry = state.live_entry(git_dir, state.WRITER)
    return entry is None or entry.get("state") == "stopped"


def stopped_text(entry: dict[str, Any]) -> str:
    return (
        f"the surface's writer is stopped: {entry.get('text') or 'unknown'}; "
        f"for the Chief of Staff: restart: {START}"
    )


def refusal(command: str, git_dir: Path) -> str:
    """The error text of a published write with no live writer (C.8), without `error: `."""
    entry = state.live_entry(git_dir, state.WRITER)
    if entry is not None and entry.get("state") == "stopped":
        return f"{command}: {stopped_text(entry)}: nothing written"
    server = older_board(git_dir)
    if server is None:
        return (
            f"{command}: the surface's writer is not running: nothing written; "
            f"for the Chief of Staff: {START}"
        )
    return (
        f"{command}: the surface's writer is not running: {older_text(server)}: nothing written; "
        f"for the Chief of Staff: {_then(server)}"
    )


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _synced(entry: dict[str, Any]) -> str:
    push = (entry.get("last_push") or {}).get("at")
    if not push:
        return "writer: synced, never pushed"
    return f"writer: synced, pushed {clock.local_hhmm(push)}"


def _pending(entry: dict[str, Any]) -> str:
    since = clock.local_hhmm(entry.get("pending_since") or entry.get("unpushed_since"))
    return (
        f"writer: pending, {_count(entry.get('pending'))} paths changed since {since}, "
        f"{_count(entry.get('ahead'))} commits to push"
    )


def _offline(entry: dict[str, Any]) -> str:
    return (
        f"writer: offline since {clock.local_hhmm(entry.get('since'))}, "
        f"{_count(entry.get('ahead'))} commits not pushed: retries every 30 s"
    )


def _conflict(entry: dict[str, Any]) -> str:
    files = files_shown(list((entry.get("conflict") or {}).get("files") or []))
    return (
        f"writer: conflict with the remote on {files}: for the Chief of Staff: integrate by "
        "rebase in the surface's checkout, resolve each file to your best guess or ask the "
        "user; the writer pushes once integrated"
    )


def _blocked(entry: dict[str, Any]) -> str:
    reason = str(entry.get("reason") or "")
    way = WAY_OUT.get(reason, "read the text")
    return f"writer: blocked ({reason}): {entry.get('text')}; for the Chief of Staff: {way}"


def state_line(entry: dict[str, Any], older: dict[str, Any] | None = None) -> str:
    """The `writer:` line of an entry as `record.read` gives it (`{"state": "off"}` for none);
    `older` is the older board serving with no writer, when there is one."""
    kind = entry.get("state")
    lines = {
        "synced": _synced,
        "pending": _pending,
        "offline": _offline,
        "conflict": _conflict,
        "blocked": _blocked,
    }
    if kind == "syncing":
        return "writer: syncing"
    if kind == "stopped":
        return (
            f"writer: stopped: {entry.get('text') or 'unknown'}; writes to the surface are "
            f"refused; for the Chief of Staff: restart: {START}"
        )
    if kind in lines:
        return lines[kind](entry)
    if older is not None:
        return (
            f"writer: not running: {older_text(older)}; writes to the surface are refused; "
            f"for the Chief of Staff: {_then(older)}"
        )
    return (
        f"writer: not running: writes to the surface are refused; for the Chief of Staff: {START}"
    )


def pending_why(entry: dict[str, Any]) -> str | None:
    """Why a write is not pushed yet (the blocked reason, else the ahead count, else the paths
    changed); None for `synced`, `syncing` and no writer."""
    kind = entry.get("state")
    if kind not in ("pending", "offline", "blocked", "conflict"):
        return None
    if kind == "blocked":
        return str(entry.get("reason") or "")
    if _count(entry.get("ahead")):
        return f"{_count(entry.get('ahead'))} commits"
    return f"{_count(entry.get('pending'))} paths"


def note(entry: dict[str, Any]) -> str | None:
    """The line a command adds when it did a published write and the writer has not pushed it:
    `writer: <state>: not pushed yet (<reason or ahead count>)`; None for `synced`, `syncing`
    and no writer."""
    why = pending_why(entry)
    return None if why is None else f"writer: {entry.get('state')}: not pushed yet ({why})"


_WROTE: set[Path] = set()  # the git folders of the surfaces this command wrote to (published)


def wrote(git_dir: Path) -> None:
    """A published write passed the store's check: the command's output will say whether the
    writer has pushed it."""
    _WROTE.add(git_dir)


def forget() -> None:
    _WROTE.clear()


def notes() -> list[str]:
    """The `not pushed yet` lines of the surfaces this command wrote to, then forgotten."""
    found = [
        n
        for g in sorted(_WROTE)
        if (n := note(state.live_entry(g, state.WRITER) or {})) is not None
    ]
    _WROTE.clear()
    return found
