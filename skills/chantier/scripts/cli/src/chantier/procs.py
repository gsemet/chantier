"""Finding and stopping the processes of a worktree, through psutil (loaded on first use: only
`cancel` and `gate` need it)."""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

WINDOWS = sys.platform == "win32"
POLL_S = 0.1


def _snapshot() -> list[tuple[int, str, str]]:
    """(pid, current directory, command line) of every process we can see.

    Windows offers no supported way to read another process's directory, and the rule stays: there,
    a process is found by its command line only.
    """
    import psutil

    rows = []
    for p in psutil.process_iter(["pid", "cwd", "cmdline"]):
        info = p.info
        cwd = "" if WINDOWS else (info["cwd"] or "")
        rows.append((int(info["pid"]), cwd, " ".join(info["cmdline"] or [])))
    return rows


def find(worktree: Path) -> list[int]:
    """Processes running in the worktree, or naming it on their command line."""
    root = str(worktree.resolve())
    me = {os.getpid(), os.getppid()}
    # paths are case-insensitive on Windows, and may be written with either slash
    roots = {root.lower(), root.lower().replace("\\", "/")} if WINDOWS else {root}
    pids = set()
    for pid, cwd, cmd in _snapshot():
        named = cmd.lower() if WINDOWS else cmd
        if cwd == root or cwd.startswith(root + os.sep) or any(r in named for r in roots):
            pids.add(pid)
    return sorted(pids - me)


def _end_tree(pid: int) -> bool:
    """Windows has no SIGTERM for console programs: end the process and its children at once."""
    import psutil

    try:
        proc = psutil.Process(pid)
        for child in proc.children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                continue
        proc.kill()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False
    return True


def stop_group(pgid: int) -> bool:
    """Stop the process group of a running `chantier gate`; False if it is already gone."""
    if sys.platform == "win32":  # the group leader's tree stands for the group
        return _end_tree(pgid)
    try:
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _signal(pid: int, kill: bool) -> bool:
    import psutil

    try:
        proc: Any = psutil.Process(pid)
        if kill:
            proc.kill()
        else:
            proc.terminate()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False
    return True


def stop(pids: list[int], grace_s: float = 3.0) -> list[int]:
    """SIGTERM, then SIGKILL after the grace period. Returns the pids that were signalled.

    On Windows each process and its children are ended at once, with no grace period.
    """
    if WINDOWS:
        return [pid for pid in pids if _end_tree(pid)]
    hit = [pid for pid in pids if _signal(pid, kill=False)]
    deadline = time.monotonic() + grace_s
    left = list(hit)
    while left and time.monotonic() < deadline:
        time.sleep(POLL_S)
        left = [p for p in left if alive(p)]
    for pid in left:
        _signal(pid, kill=True)
    return hit


def alive(pid: int) -> bool:
    """Whether a process still runs; a zombie counts as gone."""
    import psutil

    try:
        proc = psutil.Process(pid)
        return bool(proc.is_running()) and proc.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        return True
