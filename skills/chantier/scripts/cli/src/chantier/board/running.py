"""The running board's record: `running` in `board.json`, next to the key. One board serves a
planning surface (or a repository): a new `board` reads this record before it binds anything."""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from chantier import procs
from chantier.core import clock
from chantier.core.files import read_text, write_json


def _read_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(read_text(path))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _store(path: Path, data: dict[str, Any]) -> None:
    write_json(path, data)
    os.chmod(path, 0o600)


def write(path: Path, host: str, port: int, version: str, served: str) -> None:
    """Record this process as the board that serves the folder, in `board.json`."""
    data = _read_file(path)
    data["running"] = {
        "pid": os.getpid(),
        "host": host,
        "port": port,
        "version": version,
        "served": served,
        "started": clock.now(),
    }
    _store(path, data)


def remove(path: Path, pid: int) -> None:
    """Remove the record when it still names this PID (a later board's record stays)."""
    data = _read_file(path)
    run = data.get("running")
    if isinstance(run, dict) and run.get("pid") == pid:
        del data["running"]
        _store(path, data)


def _epoch(started: object) -> float | None:
    try:
        return datetime.strptime(str(started), clock.FORMAT).replace(tzinfo=UTC).timestamp()
    except ValueError:
        return None


def live(path: Path) -> dict[str, Any] | None:
    """The record of a board whose process is alive and is the recorded one; a record whose
    process is gone (a board killed hard) is no record."""
    run = _read_file(path).get("running")
    if not isinstance(run, dict):
        return None
    pid, port, host = run.get("pid"), run.get("port"), run.get("host")
    when = _epoch(run.get("started"))
    if (
        not isinstance(pid, int)
        or not isinstance(port, int)
        or not isinstance(host, str)
        or when is None
    ):
        return None
    return run if procs.alive_since(pid, when, unreadable=True) else None


def stop_command(pid: int) -> str:
    """The platform's command; the CLI only prints it."""
    return f"taskkill /PID {pid} /T /F" if sys.platform == "win32" else f"kill {pid}"


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
