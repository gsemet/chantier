"""Price the Foreman's session and its subagents.

Claude: the transcripts, priced here (design 5's claude_usage.py). Copilot: the per-call billed
records of the `copilot-session-usage` tool (>= 1.0, its `calls` command); no pricing here.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from .state import EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError

SESSION_USAGE_INSTALL = "uv tool install 'copilot-session-usage>=1'"

# $/MTok: input, 5-min write, 1-h write, cache read, output (design 2, prices-corrected.md).
PRICE = {
    "opus": (4, 5, 8, 0.20, 20),
    "sonnet": (2, 2.5, 4, 0.10, 10),
    "haiku": (0.10, 0.125, 0.20, 0.01, 0.50),
    "haiku>100k": (0.50, 0.625, 1, 0.05, 2.50),
}


def projects_dir(config: dict | None = None) -> Path:
    """`CHANTIER_CLAUDE_PROJECTS`, else `claude_projects_dir` of chantier.json, else ~/.claude/projects."""
    env = os.environ.get("CHANTIER_CLAUDE_PROJECTS") or (config or {}).get("claude_projects_dir")
    return Path(env).expanduser() if env else Path.home() / ".claude" / "projects"


def transcript_path(repo_root: Path, session_uuid: str, config: dict | None = None) -> Path:
    base = projects_dir(config)
    if not base.is_absolute():
        base = repo_root / base
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(repo_root))
    path = base / slug / f"{session_uuid}.jsonl"
    if not path.exists():  # long folder names get a shortened slug: find the uuid instead
        path = next(base.glob(f"*/{session_uuid}.jsonl"), path)
    return path


def _family(model: str, prompt: int) -> str:
    for f in ("opus", "sonnet", "haiku"):
        if f in model:
            return "haiku>100k" if f == "haiku" and prompt > 100_000 else f
    return "opus"


def usage(path: Path) -> dict:
    row = {"calls": 0, "usd": 0.0, "model": "?", "w5m": 0, "w1h": 0, "read": 0, "out": 0}
    seen = set()
    for line in path.open():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        m = d.get("message") or {}
        if d.get("type") != "assistant" or not m.get("usage") or m.get("id") in seen:
            continue
        seen.add(m.get("id"))
        u, cc = m["usage"], m["usage"].get("cache_creation") or {}
        t = (u.get("input_tokens", 0), cc.get("ephemeral_5m_input_tokens", 0),
             cc.get("ephemeral_1h_input_tokens", 0), u.get("cache_read_input_tokens", 0),
             u.get("output_tokens", 0))
        row["model"] = m.get("model", "?")
        row["calls"] += 1
        for k, v in zip(("w5m", "w1h", "read", "out"), t[1:]):
            row[k] += v
        row["usd"] += sum(a * b for a, b in zip(t, PRICE[_family(row["model"], sum(t[:4]))])) / 1e6
    return row


def session_costs(main: Path) -> list[dict]:
    """One row for the main transcript (the Foreman) and one per subagent."""
    rows = []
    if main.exists():
        rows.append({"agent": "main", "type": "foreman", "description": "", **usage(main)})
    sub = main.with_suffix("") / "subagents"
    if sub.exists():
        for f in sorted(sub.glob("agent-*.jsonl")):
            meta_path = f.with_suffix("").with_suffix(".meta.json")
            meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
            rows.append({"agent": f.stem.removeprefix("agent-"),
                         "type": meta.get("agentType", "?"),
                         "description": meta.get("description", ""), **usage(f)})
    return rows


def copilot_home() -> Path:
    return Path(os.environ.get("COPILOT_HOME") or Path.home() / ".copilot").expanduser()


def _copilot_agents(session: str) -> dict[str, dict]:
    """agentId → agentType and name, from the session's `subagent.started` events."""
    path = copilot_home() / "session-state" / session / "events.jsonl"
    agents: dict[str, dict] = {}
    if not path.exists():
        return agents
    for line in path.open():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "subagent.started" and e.get("agentId"):
            d = e.get("data") or {}
            agents[e["agentId"]] = {
                "type": d.get("agentType") or d.get("agentName") or "?",
                "description": f"{d.get('agentDisplayName', '')} {d.get('agentDescription', '')}"}
    return agents


def copilot_session_costs(session: str) -> list[dict]:
    """One row per agent of a Copilot session, from `copilot-session-usage calls`.

    Fails, never falls back: a missing or too old tool, a failed run or a session without a
    priced call is an error.
    """
    cmd = shlex.split(os.environ.get("CHANTIER_SESSION_USAGE") or "copilot-session-usage")
    if not cmd or not shutil.which(cmd[0]):
        raise ChantierError(f"`{cmd[0] if cmd else ''}` not found: chantier cost on Copilot needs "
                       f"copilot-session-usage >= 1.0 ({SESSION_USAGE_INSTALL}, or set "
                       "CHANTIER_SESSION_USAGE)", EXIT_PRECONDITION)
    argv = [*cmd, "--agent", "cli", "--session-root", str(copilot_home() / "session-state"),
            "calls", "--name", f"^{re.escape(session)}$"]
    p = subprocess.run(argv, capture_output=True, text=True)
    if p.returncode != 0:
        if "No such command 'calls'" in p.stderr:
            raise ChantierError(f"copilot-session-usage is older than 1.0 (no `calls` command): "
                           f"{SESSION_USAGE_INSTALL}", EXIT_PRECONDITION)
        last = (p.stderr.strip().splitlines() or ["no output"])[-1]
        raise ChantierError(f"copilot-session-usage failed ({p.returncode}): {last}", EXIT_EXTERNAL)
    agents = _copilot_agents(session)
    rows: dict[str, dict] = {}
    for line in p.stdout.splitlines():
        if not line.strip():
            continue
        try:
            c = json.loads(line)
        except ValueError as e:
            raise ChantierError(f"copilot-session-usage: unreadable record: {line[:80]}",
                           EXIT_EXTERNAL) from e
        if c.get("estimated_usd") is None:
            raise ChantierError(f"copilot-session-usage: a call has no price "
                           f"(model {c.get('model')})", EXIT_EXTERNAL)
        aid = c.get("agent_id") or "main"
        meta = agents.get(aid, {})
        row = rows.setdefault(aid, {
            "agent": aid, "type": "foreman" if aid == "main" else meta.get("type")
            or c.get("agent") or "?", "description": meta.get("description", c.get("agent") or ""),
            "calls": 0, "usd": 0.0, "estimated": 0})
        row["calls"] += c.get("llm_calls") or 1
        row["usd"] += c["estimated_usd"]
        row["estimated"] += c.get("cost_source") == "estimated"
    if not rows:
        raise ChantierError(f"copilot-session-usage found no priced call for session {session}",
                       EXIT_EXTERNAL)
    return list(rows.values())
