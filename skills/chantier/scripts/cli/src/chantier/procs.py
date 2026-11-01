"""Find and stop the processes a cancelled CR leaves behind in its worktree."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def _cwds() -> dict[int, str]:
    """pid → current directory, for every process we can see."""
    out: dict[int, str] = {}
    if sys.platform.startswith("linux"):
        for p in Path("/proc").iterdir():
            if p.name.isdigit():
                try:
                    out[int(p.name)] = os.readlink(p / "cwd")
                except OSError:
                    pass
        return out
    try:
        res = subprocess.run(["lsof", "-a", "-d", "cwd", "-Fpn", "-u", str(os.getuid())],
                             capture_output=True, text=True, timeout=30)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return out
    pid = None
    for line in res.stdout.splitlines():
        if line.startswith("p"):
            pid = int(line[1:])
        elif line.startswith("n") and pid is not None:
            out[pid] = line[1:]
    return out


def _cmdlines() -> dict[int, str]:
    res = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True, text=True)
    out = {}
    for line in res.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[0].isdigit():
            out[int(parts[0])] = parts[1]
    return out


def find(worktree: Path) -> list[int]:
    """Processes running in the worktree, or naming it on their command line."""
    root = str(worktree.resolve())
    me = {os.getpid(), os.getppid()}
    pids = {pid for pid, cwd in _cwds().items()
            if cwd == root or cwd.startswith(root + os.sep)}
    pids |= {pid for pid, cmd in _cmdlines().items() if root in cmd}
    return sorted(pids - me)


def stop(pids: list[int], grace_s: float = 3.0) -> list[int]:
    """SIGTERM, then SIGKILL after the grace period. Returns the pids that were signalled."""
    hit = []
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            hit.append(pid)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass
    deadline = time.monotonic() + grace_s
    alive = list(hit)
    while alive and time.monotonic() < deadline:
        time.sleep(0.1)
        alive = [p for p in alive if _alive(p)]
    for pid in alive:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return hit


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:  # a zombie child counts as gone
        done, _ = os.waitpid(pid, os.WNOHANG)
        return done == 0
    except ChildProcessError:
        return True
