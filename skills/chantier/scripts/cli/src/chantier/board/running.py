"""What a new `chantier board` needs of a server it did not start: the command that stops it
and the PID of one that listens on a port. The surface server's own record is its `server` entry
of `chantier/server.json` (`hub/state.py`): one server serves a planning surface (or a
repository), and a new `board` reads that entry before it binds anything."""

from __future__ import annotations

import sys
from typing import Any


def stop_command(pid: int) -> str:
    """The platform's command; the CLI only prints it."""
    return f"taskkill /PID {pid} /T /F" if sys.platform == "win32" else f"kill {pid}"


def silent_text(run: dict[str, Any]) -> str:
    """The sentence for a live-recorded board that does not answer, said alike by a new `board`
    and by a watcher."""
    return (
        f"a chantier board {run.get('version')} (PID {run['pid']}) holds this surface at "
        f"{run['host']}:{run['port']} and does not answer: stop it "
        f"({stop_command(run['pid'])}), then run board again"
    )


def find_pid(port: int) -> int | None:
    """The PID of this user's `chantier board` process that listens on the port, if any."""
    import psutil

    try:
        for proc in psutil.process_iter(["pid", "cmdline"]):
            cmd = proc.info.get("cmdline") or []
            if "chantier" not in " ".join(cmd) or "board" not in cmd:
                continue
            try:
                conns = proc.net_connections(kind="inet")
            except (psutil.Error, OSError):
                continue
            if any(
                c.status == psutil.CONN_LISTEN and c.laddr and c.laddr.port == port for c in conns
            ):
                return int(proc.info["pid"])
    except (psutil.Error, OSError):
        return None
    return None
