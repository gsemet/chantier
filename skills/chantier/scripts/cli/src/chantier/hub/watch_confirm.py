"""The watcher confirms the server that answers its link: the one `server.json` records, which
holds the forge hub. A link answered by another process is not a link (`watch.py`)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from chantier.clients.tui.link import Linked
from chantier.hub.feed import Board


def recorded_pid(board: Board, git_dir: Path) -> int | None:
    """The PID of the live recorded server, or None."""
    found = board.recorded(git_dir)
    pid = None if found is None else found[0].get("pid")
    return pid if isinstance(pid, int) else None


def answering_pid(board: Board, entry: dict[str, Any], key: str, item: Linked) -> int | None:
    """The PID of the process that answered the link: the WebSocket's `welcome` says it, an HTTP
    link is probed; None when the server says nothing of itself."""
    pid = item.pid
    if pid is None:
        answer = board.probe(str(entry["host"]), int(entry["port"]), key)
        pid = answer.get("pid") if isinstance(answer, dict) else None
    return pid if isinstance(pid, int) else None


def other_than_recorded(
    board: Board, git_dir: Path, answered: int | None, linked: int | None
) -> int | None:
    """The answering PID when it is known and is not the recorded server (`linked`, the PID this
    watcher linked to, when none is recorded now); else None."""
    want = recorded_pid(board, git_dir) or linked
    return answered if answered is not None and want is not None and answered != want else None


def moved(board: Board, git_dir: Path, linked: int | None) -> bool:
    """The record names another live server than the one this watcher linked to (a restart)."""
    now = recorded_pid(board, git_dir)
    return now is not None and linked is not None and now != linked


def started_by(recorded: int, spawned: int | None) -> bool:
    """The recorded server is the process this watcher spawned, or one of its descendants (a
    launcher starts the server as its child); true when the spawn gave no PID."""
    if spawned is None or recorded == spawned:
        return True
    import psutil

    try:
        return any(p.pid == spawned for p in psutil.Process(recorded).parents())
    except psutil.Error:
        return False
