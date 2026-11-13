"""The cost of a Copilot session, through the `copilot-session-usage` helper."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError

SESSION_USAGE_SCRIPT = Path(__file__).resolve().parents[3] / "session_usage.py"


UV_INDEX_VARIABLES = (
    "UV_INDEX",
    "UV_DEFAULT_INDEX",
    "UV_INDEX_URL",
    "UV_EXTRA_INDEX_URL",
    "UV_FIND_LINKS",
)


def copilot_home() -> Path:
    return Path(os.environ.get("COPILOT_HOME") or Path.home() / ".copilot").expanduser()


def _copilot_agents(session: str) -> dict[str, dict[str, Any]]:
    """agentId → agentType and name, from the session's `subagent.started` events."""
    path = copilot_home() / "session-state" / session / "events.jsonl"
    agents: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return agents
    for line in path.open(encoding="utf-8"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "subagent.started" and e.get("agentId"):
            d = e.get("data") or {}
            agents[e["agentId"]] = {
                "type": d.get("agentType") or d.get("agentName") or "?",
                "description": f"{d.get('agentDisplayName', '')} {d.get('agentDescription', '')}",
            }
    return agents


def _split(command: str) -> list[str]:
    """A command line into argv; on Windows, backslashes are path separators, not escapes."""
    if sys.platform != "win32":
        return shlex.split(command)
    return [
        a[1:-1] if len(a) > 1 and a[0] == a[-1] == '"' else a
        for a in shlex.split(command, posix=False)
    ]


def copilot_session_costs(session: str) -> list[dict[str, Any]]:
    """One row per agent of a Copilot session, from `copilot-session-usage calls`.

    uv resolves copilot-session-usage from the inline metadata of `session_usage.py`; nothing to
    install. `--no-config` and the filtered index environment leave the script's own index
    (pypi.org) as the only one. Fails, never falls back: a failed run (uv offline, package
    unavailable) or a session without a priced call is an error.
    """
    cmd = _split(os.environ.get("CHANTIER_SESSION_USAGE") or "")
    env = None
    if not cmd:
        cmd = ["uv", "run", "--no-config", "--script", str(SESSION_USAGE_SCRIPT)]
        env = os.environ.copy()
        for variable in UV_INDEX_VARIABLES:
            env.pop(variable, None)
    if not shutil.which(cmd[0]):
        raise ChantierError(
            f"`{cmd[0]}` not found: chantier needs uv to run copilot-session-usage on Copilot",
            EXIT_PRECONDITION,
        )
    argv = [
        *cmd,
        "--agent",
        "cli",
        "--session-root",
        str(copilot_home() / "session-state"),
        "calls",
        "--name",
        f"^{re.escape(session)}$",
    ]
    p = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=False,
    )
    if p.returncode != 0:
        last = (p.stderr.strip().splitlines() or ["no output"])[-1]
        raise ChantierError(f"copilot-session-usage failed ({p.returncode}): {last}", EXIT_EXTERNAL)
    return _rows(session, p.stdout)


def _call(line: str) -> dict[str, Any]:
    try:
        c = json.loads(line)
    except ValueError as e:
        raise ChantierError(
            f"copilot-session-usage: unreadable record: {line[:80]}", EXIT_EXTERNAL
        ) from e
    if c.get("estimated_usd") is None:
        raise ChantierError(
            f"copilot-session-usage: a call has no price (model {c.get('model')})",
            EXIT_EXTERNAL,
        )
    return c


def _rows(session: str, output: str) -> list[dict[str, Any]]:
    """One row per agent, from the calls `copilot-session-usage` printed."""
    agents = _copilot_agents(session)
    rows: dict[str, dict[str, Any]] = {}
    for line in (x for x in output.splitlines() if x.strip()):
        c = _call(line)
        aid = c.get("agent_id") or "main"
        meta = agents.get(aid, {})
        row = rows.setdefault(
            aid,
            {
                "agent": aid,
                "type": "foreman" if aid == "main" else meta.get("type") or c.get("agent") or "?",
                "description": meta.get("description", c.get("agent") or ""),
                "calls": 0,
                "usd": 0.0,
                "estimated": 0,
            },
        )
        row["calls"] += c.get("llm_calls") or 1
        row["usd"] += c["estimated_usd"]
        row["estimated"] += c.get("cost_source") == "estimated"
    if not rows:
        raise ChantierError(
            f"copilot-session-usage found no priced call for session {session}", EXIT_EXTERNAL
        )
    return list(rows.values())
