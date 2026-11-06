"""Price the Foreman's session and its subagents.

Claude: the transcripts, priced here. Copilot: the per-call billed
records of `copilot-session-usage` >= 1 (its `calls` command), which uv fetches from the inline
metadata of `scripts/cli/session_usage.py`; no pricing here.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .state import EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError

SESSION_USAGE_SCRIPT = Path(__file__).resolve().parents[2] / "session_usage.py"
UV_INDEX_VARIABLES = ("UV_INDEX", "UV_DEFAULT_INDEX", "UV_INDEX_URL", "UV_EXTRA_INDEX_URL",
                      "UV_FIND_LINKS")

# $/MTok: input, 5-min write, 1-h write, cache read, output, per exact model (a dated id of the
# same model, `claude-sonnet-5-5-20261001`, has the same price). Any other model is refused.
CACHE_5M, CACHE_1H = 300, 3600  # seconds a cache write lives, by the write used
PRICE = {
    "claude-opus-5-5": (4, 5, 8, 0.20, 20),
    "claude-sonnet-5-5": (2, 2.5, 4, 0.10, 10),
    "claude-haiku-5-5": (0.10, 0.125, 0.20, 0.01, 0.50),
    "claude-haiku-5-5>100k": (0.50, 0.625, 1, 0.05, 2.50),
}


def projects_dir() -> Path:
    """`CHANTIER_CLAUDE_PROJECTS`, else the host's own ~/.claude/projects."""
    env = os.environ.get("CHANTIER_CLAUDE_PROJECTS")
    return Path(env).expanduser() if env else Path.home() / ".claude" / "projects"


def transcript_path(repo_root: Path, session_uuid: str) -> Path:
    base = projects_dir()
    if not base.is_absolute():
        base = repo_root / base
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(repo_root))
    path = base / slug / f"{session_uuid}.jsonl"
    if not path.exists():  # long folder names get a shortened slug: find the uuid instead
        path = next(base.glob(f"*/{session_uuid}.jsonl"), path)
    return path


def _family(model: str, prompt: int) -> str:
    for f in ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"):
        if re.fullmatch(rf"{f}(-\d{{8}})?", model):
            return f"{f}>100k" if f"{f}>100k" in PRICE and prompt > 100_000 else f
    raise ChantierError(f"no Claude price for model {model!r}: add it to chantier's price table",
                        EXIT_EXTERNAL)


def _transcript_lines(path: Path):
    try:
        with path.open(encoding="utf-8") as transcript:
            yield from transcript
    except (OSError, UnicodeError) as e:
        raise ChantierError(f"cannot read Claude transcript {path}: {e}", EXIT_EXTERNAL) from e


def _wakes(record: dict) -> bool:
    """Whether a user record starts a turn, rather than carrying a tool's result."""
    content = (record.get("message") or {}).get("content")
    return not (isinstance(content, list) and content
                and all(isinstance(p, dict) and p.get("type") == "tool_result" for p in content))


def _when(text, path: Path, number: int) -> datetime | None:
    """A record's time, to compare as a time and not as text; none when it has none."""
    if not text:
        return None
    try:
        when = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError as e:
        raise ChantierError(f"unreadable timestamp at {path}:{number}", EXIT_EXTERNAL) from e
    return when if when.tzinfo else when.replace(tzinfo=timezone.utc)


def usage(path: Path, since: str = "", until: str = "") -> dict:
    """A transcript's calls from `since` to `until`: a session can have run another batch."""
    row = {"calls": 0, "usd": 0.0, "model": "?", "models": set(), "w5m": 0, "w1h": 0, "read": 0,
           "out": 0, "wakes": 0, "wake_context": 0, "peak_context": 0, "last_context": 0,
           "usd_in": 0.0, "usd_write": 0.0, "usd_read": 0.0, "usd_out": 0.0,  # dollars by kind
           "compactions": 0, "timed": 0, "expired": 0}
    start, end = _when(since, path, 0), _when(until, path, 0)
    seen = set()
    previous, lifetime = None, 0  # the last call's time, and how long its cache write lives
    woken = False  # a prompt, a message or a notification came in; a tool result is the same turn
    for number, line in enumerate(_transcript_lines(path), 1):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except ValueError as e:
            raise ChantierError(f"unreadable Claude transcript record {path}:{number}",
                                EXIT_EXTERNAL) from e
        if not isinstance(d, dict):
            raise ChantierError(f"invalid Claude transcript record {path}:{number}",
                                EXIT_EXTERNAL)
        when = _when(d.get("timestamp"), path, number)
        if (start and when and when < start) or (end and when and when > end):
            continue  # outside the window: neither a call nor a wake
        if d.get("type") == "system" and d.get("subtype") == "compact_boundary":
            row["compactions"] += 1  # the compaction call itself leaves no priced record
        if d.get("type") == "user":
            woken = woken or _wakes(d)
        if d.get("type") != "assistant":
            continue
        m = d.get("message")
        if not isinstance(m, dict):
            raise ChantierError(f"invalid Claude assistant record {path}:{number}", EXIT_EXTERNAL)
        if not m.get("usage") or m.get("model") == "<synthetic>":
            continue  # an API error or a session limit: no tokens, no price
        message_id, model, u = m.get("id"), m.get("model"), m["usage"]
        if not isinstance(message_id, str) or not message_id:
            raise ChantierError(f"Claude usage has no message id at {path}:{number}", EXIT_EXTERNAL)
        if message_id in seen:
            continue
        if not isinstance(model, str) or not model or not isinstance(u, dict):
            raise ChantierError(f"invalid Claude usage at {path}:{number}", EXIT_EXTERNAL)
        cc = u.get("cache_creation") or {}
        if not isinstance(cc, dict):
            raise ChantierError(f"invalid Claude cache usage at {path}:{number}", EXIT_EXTERNAL)
        t = (u.get("input_tokens", 0), cc.get("ephemeral_5m_input_tokens", 0),
             cc.get("ephemeral_1h_input_tokens", 0), u.get("cache_read_input_tokens", 0),
             u.get("output_tokens", 0))
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in t):
            raise ChantierError(f"invalid Claude token counts at {path}:{number}", EXIT_EXTERNAL)
        if not any(t):
            continue  # a record without tokens
        seen.add(message_id)
        row["model"] = model
        row["calls"] += 1
        for k, v in zip(("w5m", "w1h", "read", "out"), t[1:]):
            row[k] += v
        row["models"].add(model)
        parts = [a * b / 1e6 for a, b in zip(t, PRICE[_family(model, sum(t[:4]))])]
        row["usd"] += sum(parts)
        row["usd_in"] += parts[0]
        row["usd_write"] += parts[1] + parts[2]
        row["usd_read"] += parts[3]
        row["usd_out"] += parts[4]
        if previous and when and lifetime:  # measured: the gap since this agent's previous call
            row["timed"] += 1
            row["expired"] += (when - previous).total_seconds() > lifetime
        previous = when
        lifetime = CACHE_1H if t[2] else CACHE_5M if t[1] else lifetime
        row["peak_context"] = max(row["peak_context"], sum(t[:4]))
        row["last_context"] = sum(t[:4])
        if woken:
            row["wakes"] += 1
            row["wake_context"] += sum(t[:4])
            woken = False
    return row


def session_costs(main: Path, since: str = "", until: str = "", kind: str = "foreman",
                  allow_empty: bool = False) -> list[dict]:
    """One row for the main transcript (`kind`: the Foreman or the Chief of Staff) and one per
    subagent with calls in the window. A window without a call is an error unless allowed."""
    label = kind.replace("-", " ").capitalize()
    if not main.is_file():
        raise ChantierError(f"{label} transcript not found: {main}", EXIT_EXTERNAL)
    foreman = usage(main, since, until)
    if not foreman["calls"] and not allow_empty:
        raise ChantierError(f"no priced calls in {label} transcript: {main}", EXIT_EXTERNAL)
    rows = [{"agent": "main", "type": kind, "description": "", **foreman}]
    sub = main.with_suffix("") / "subagents"
    if sub.exists():
        for f in sorted(sub.glob("agent-*.jsonl")):
            meta_path = f.with_suffix("").with_suffix(".meta.json")
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            row = usage(f, since, until)
            if row["calls"]:
                rows.append({"agent": f.stem.removeprefix("agent-"),
                             "type": meta.get("agentType", "?"),
                             "parent": meta.get("parentAgentId"),
                             "description": meta.get("description", ""), **row})
    return rows


def copilot_home() -> Path:
    return Path(os.environ.get("COPILOT_HOME") or Path.home() / ".copilot").expanduser()


def _copilot_agents(session: str) -> dict[str, dict]:
    """agentId → agentType and name, from the session's `subagent.started` events."""
    path = copilot_home() / "session-state" / session / "events.jsonl"
    agents: dict[str, dict] = {}
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
                "description": f"{d.get('agentDisplayName', '')} {d.get('agentDescription', '')}"}
    return agents


def _split(command: str) -> list[str]:
    """A command line into argv; on Windows, backslashes are path separators, not escapes."""
    if sys.platform != "win32":
        return shlex.split(command)
    return [a[1:-1] if len(a) > 1 and a[0] == a[-1] == '"' else a
            for a in shlex.split(command, posix=False)]


def copilot_session_costs(session: str) -> list[dict]:
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
        raise ChantierError(f"`{cmd[0]}` not found: chantier needs uv to run "
                            "copilot-session-usage on Copilot", EXIT_PRECONDITION)
    argv = [*cmd, "--agent", "cli", "--session-root", str(copilot_home() / "session-state"),
            "calls", "--name", f"^{re.escape(session)}$"]
    p = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env)
    if p.returncode != 0:
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
