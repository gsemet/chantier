"""The only code of the plugin that starts the surface's autosync tool: the board server's join,
and the three actions of the user (start, stop, approve). An argv comes from a fixed table; there
is no shell and no free text in it."""

from __future__ import annotations

import re
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass

from chantier.autosync.site import AutosyncSite

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


def spawn_join(site: AutosyncSite, owner_pid: int) -> subprocess.Popen[bytes]:
    """Start the board's join, detached, once. `--harness generic` makes the participant follow
    the server's process only. The participant leaves by itself once that process ends. Its
    output is discarded: the tool's state files say what it does."""
    argv = _argv(
        site,
        *("join", ".", "--owner-pid", str(owner_pid), "--harness", "generic"),
        *("--session-id", SESSION_ID),
    )
    if sys.platform == "win32":
        return subprocess.Popen(
            argv,
            cwd=site.surface,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
    return subprocess.Popen(
        argv,
        cwd=site.surface,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def watch_join(proc: subprocess.Popen[bytes], say: Callable[[str], None]) -> None:
    """Say once if the join process fails before the server ends (a first `uv run` offline, say)."""

    def wait() -> None:
        code = proc.wait()
        if code:
            say(f"board: autosync not joined: the join ended with exit code {code}")

    threading.Thread(target=wait, daemon=True).start()
