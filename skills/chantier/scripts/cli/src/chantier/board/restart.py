"""`chantier serve --restart`: the guard of a surface a chantier dev session holds, the clean stop
of the board that runs (the private-key op `server.stop`), and the wait for its process to end.
Then `serve` goes on as it does with no board. Nothing is killed or signalled."""

from __future__ import annotations

import time
from http import HTTPStatus
from typing import Any

from chantier import procs
from chantier.board import running
from chantier.board.address import call_op, probe
from chantier.board.projects import Projects
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.hub import autostart, state

ASK_S = 20.0  # the board answers `server.stop` within this, else it is silent
WAIT_S = 120.0  # the stopped process ends within this (its writer's last cycle may fetch and push)
LOOK_S = 0.5
NONE_RUNNING = "board: none was running"


def refused(reason: str) -> ChantierError:
    return ChantierError(f"board not restarted: {' '.join(reason.split())}", EXIT_PRECONDITION)


def guard(projects: Projects) -> None:
    """Refuse while a chantier dev session of the surface holds its seat with another build than
    this process's: that build serves the surface."""
    found = autostart.other_dev_build(projects.home, state.build_source())
    if found is not None:
        session, build = found
        raise refused(
            f"a chantier dev session ({session}) holds its seat; its build ({build}) serves "
            "this surface"
        )


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _clock() -> float:
    return time.monotonic()


def _target(projects: Projects, key: str, host: str, port: int) -> dict[str, Any] | None:
    """The board to stop: the live `server` entry, else a board of this folder that answers at the
    configured address (its PID from its answer); None when none runs."""
    entry = state.live_entry(projects.home.git_dir, state.SERVER)
    if entry is not None:
        return entry
    found = probe(host, port, key) if port else None
    if isinstance(found, dict) and found.get("served") == projects.served.as_posix():
        return {
            "host": host,
            "port": port,
            "pid": found.get("pid"),
            "version": found.get("version"),
            "source": state.UNKNOWN,
        }
    return None


def _ask(entry: dict[str, Any], key: str, why: str) -> None:
    """Send `server.stop`; a refusal of any kind raises, with nothing stopped."""
    by_hand = (
        f"chantier serve {entry.get('version')} (PID {entry.get('pid')}) {{what}}; the user "
        f"stops it by hand ({running.stop_command(entry['pid']) if entry.get('pid') else why}), "
        "then run serve --restart again"
    )
    try:
        status, body = call_op(entry["host"], entry["port"], key, "server.stop", ASK_S)
    except (OSError, ValueError):
        raise refused(by_hand.format(what="does not answer")) from None
    if status == HTTPStatus.OK and (body.get("data") or {}).get("stopping") is True:
        return
    if status == HTTPStatus.CONFLICT and body.get("error"):
        raise ChantierError(str(body["error"]), EXIT_PRECONDITION)
    if status == HTTPStatus.NOT_FOUND:
        raise refused(by_hand.format(what="has no clean stop"))
    if status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
        raise refused(by_hand.format(what="refused the key"))
    raise refused(by_hand.format(what="does not answer"))


def _ended(projects: Projects, entry: dict[str, Any], key: str) -> bool:
    """The stopped process is gone, and its `server` entry with it (or naming another PID)."""
    pid = entry.get("pid")
    if isinstance(pid, int):
        if procs.alive(pid):
            return False
        now = state.read(projects.home.git_dir).get(state.SERVER)
        return not (isinstance(now, dict) and now.get("pid") == pid)
    return probe(entry["host"], entry["port"], key) is None


def restart_with_key(projects: Projects, host: str, port: int) -> None:
    """`restart` with the old board's own key, read before any new key is written."""
    old = state.read(projects.home.git_dir).get("key")
    restart(projects, old if isinstance(old, str) else "", host, port)


def restart(projects: Projects, key: str, host: str, port: int) -> None:
    """The board that runs, stopped cleanly, and its end waited for; its stop line printed. With
    none running: the line that says so. The caller then serves as `serve` does."""
    guard(projects)
    entry = _target(projects, key, host, port)
    if entry is None:
        print(NONE_RUNNING, flush=True)
        return
    _ask(entry, key, "end the process that listens on its port")
    deadline = _clock() + WAIT_S
    while not _ended(projects, entry, key):
        if _clock() >= deadline:
            raise refused(
                f"chantier serve {entry.get('version')} (PID {entry.get('pid')}) is still "
                f"stopping after {int(WAIT_S)} s (its writer's last cycle); run serve --restart "
                "again later"
            )
        _sleep(LOOK_S)
    print(
        f"board stopped: chantier {entry.get('version')} (PID {entry.get('pid')}, "
        f"{entry.get('source') or state.UNKNOWN})",
        flush=True,
    )
