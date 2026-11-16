"""The only code of the plugin that starts the surface's autosync tool: the board server's join,
and the three actions of the user (start, stop, approve). An argv comes from a fixed table; there
is no shell and no free text in it."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from chantier.autosync.site import AutosyncSite
from chantier.procs import alive_since

TIMEOUT_S = 30
INCIDENT = re.compile(r"(staged|secrets)-[0-9a-f]{20}")
SESSION_ID = "chantier-board"
ACTIONS = {
    "start": ("start", ".", "--enable-only"),
    "stop": ("stop", "."),
    "approve": ("approve", "."),
}


@dataclass(frozen=True)
class ToolResult:
    code: int
    line: str  # the last line the tool printed


def _argv(site: AutosyncSite, *words: str) -> list[str]:
    return ["uv", "run", site.script.relative_to(site.surface).as_posix(), *words]


def _last_line(out: str) -> str:
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def run_action(site: AutosyncSite, action: str, *args: str) -> ToolResult:
    """Run one of the user's actions to its end, from the surface's root."""
    if action not in ACTIONS or (action == "approve") != bool(args):
        return ToolResult(2, f"not an action of the board: {action}")
    if action == "approve" and not INCIDENT.fullmatch(args[0]):
        return ToolResult(2, "not an incident id")
    try:
        done = subprocess.run(
            _argv(site, *ACTIONS[action], *args),
            cwd=site.surface,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(124, f"the tool did not answer within {TIMEOUT_S} s")
    except OSError as e:
        return ToolResult(127, str(e))
    return ToolResult(done.returncode, _last_line(done.stderr + "\n" + done.stdout))


def _existing_join(site: AutosyncSite, session_id: str) -> bool:
    folder = site.state_dir / "participants"
    for path in folder.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            pid = int(data.get("pid", 0))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            continue
        if pid > 0 and data.get("session_id") == session_id:
            try:
                recorded = float(data.get("since", path.stat().st_mtime))
            except (OSError, TypeError, ValueError):
                continue
            if alive_since(pid, recorded, sys.platform == "win32"):
                return True
    return False


def spawn_join(site: AutosyncSite, owner_pid: int) -> subprocess.Popen[bytes] | None:
    """Start the board's join, detached, once. `--harness generic` makes the participant follow
    the server's process only. The participant leaves by itself once that process ends. Its
    Both output pipes are captured by observe_join/watch_join for failure diagnostics."""
    argv = _argv(
        site,
        *("join", ".", "--owner-pid", str(owner_pid), "--harness", "generic"),
        *("--session-id", SESSION_ID),
    )
    if _existing_join(site, SESSION_ID):
        return None
    if sys.platform == "win32":
        return subprocess.Popen(
            argv,
            cwd=site.surface,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
    return subprocess.Popen(
        argv,
        cwd=site.surface,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )


def observe_join(proc: subprocess.Popen[bytes], timeout: float = 0.25) -> str | None:
    """Return an exact early diagnostic, or None while a live join is watched.

    The reader threads are deliberately started before the early wait.  A join can
    print enough output to fill either pipe before it exits, so waiting on the
    process without draining both streams can deadlock it.
    """
    _start_capture(proc)
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    return _diagnostic(proc)


def watch_join(proc: subprocess.Popen[bytes], say: Callable[[str], None]) -> threading.Thread:
    """Drain and report one exact diagnostic if a live join later fails."""
    _start_capture(proc)

    def wait() -> None:
        code = proc.wait()
        _join_readers(proc)
        if code:
            say(f"board: autosync not joined: {_diagnostic(proc, code)}")

    watcher = threading.Thread(target=wait, daemon=True)
    watcher.start()
    return watcher


def _start_capture(proc: subprocess.Popen[bytes]) -> None:
    """Install idempotent background readers on both join pipes."""
    state = getattr(proc, "_chantier_join_capture", None)
    if state is not None:
        return
    output: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
    readers = []
    for name, target in output.items():
        stream = getattr(proc, name)
        if stream is None:
            continue
        reader = threading.Thread(target=_read_pipe, args=(stream, target), daemon=True)
        reader.start()
        readers.append(reader)
    proc._chantier_join_capture = output, readers  # type: ignore[attr-defined]


def _read_pipe(stream: Any, target: bytearray) -> None:
    for chunk in iter(stream.readline, b""):
        target.extend(chunk)
    stream.close()


def _join_readers(proc: subprocess.Popen[bytes]) -> None:
    state = getattr(proc, "_chantier_join_capture", None)
    if state is not None:
        for reader in state[1]:
            reader.join()


def _diagnostic(proc: subprocess.Popen[bytes], code: int | None = None) -> str:
    _join_readers(proc)
    output: dict[str, bytearray] = getattr(
        proc, "_chantier_join_capture", ({"stdout": bytearray(), "stderr": bytearray()}, [])
    )[0]
    data = bytes(output.get("stderr", bytearray()) or output.get("stdout", bytearray()))
    lines = data.decode(errors="replace").strip().splitlines()
    return (
        lines[-1]
        if lines
        else f"the join ended with exit code {proc.returncode if code is None else code}"
    )
