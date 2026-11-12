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

from .playbook import PRICE_NAMES as PRICE_KEYS
from .state import EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError

SESSION_USAGE_SCRIPT = Path(__file__).resolve().parents[2] / "session_usage.py"
UV_INDEX_VARIABLES = ("UV_INDEX", "UV_DEFAULT_INDEX", "UV_INDEX_URL", "UV_EXTRA_INDEX_URL",
                      "UV_FIND_LINKS")

# $/MTok: input, 5-min write, 1-h write, cache read, output, per exact model (a dated id of the
# same model, `claude-sonnet-5-5-20261001`, has the same price). Each price is the provider's
# published one, never inferred. A model not here is not refused: its calls are counted and named
# as not priced, and a project adds its price under `prices:` in `chantier.yaml`.
CACHE_5M, CACHE_1H = 300, 3600  # seconds a cache write lives, by the write used
PRICE = {
    "claude-opus-5-5": (4, 5, 8, 0.20, 20),
    "claude-sonnet-5-5": (2, 2.5, 4, 0.10, 10),
    "claude-fable-5-2": (8, 10, 16, 0.20, 40),
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


def _price(model: str, prompt: int, extra: dict | None = None) -> tuple | None:
    """The $/MTok of a model: the project's entry (`extra`, from `chantier.yaml`) above the
    built-in table, by the same id or by it without a trailing `-YYYYMMDD`. Nothing else matches:
    no prefix, no family, no nearest model. None: no price, so the calls are not priced. The
    long-context tier applies when the entry has one and the prompt is above its threshold."""
    ids = [model]
    dated = re.fullmatch(r"(.+)-\d{8}", model)
    if dated:
        ids.append(dated.group(1))
    for i in ids:
        entry = (extra or {}).get(i)
        if entry:
            tier = entry.get("long_context")
            if tier and prompt > tier["above"]:
                entry = tier
            return tuple(entry[k] for k in PRICE_KEYS)
        if i in PRICE:
            tier = PRICE.get(f"{i}>100k")
            return tier if tier and prompt > 100_000 else PRICE[i]
    return None


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


GRILL_NAMES = ("01-intent.md", "02-answers.md", "03-change-spec.md", "work/specifying")


def _grill_use(block) -> bool:
    """Whether a tool use belongs to the grill and the specifications: its input names a CR's
    intent, answers, specification or `work/specifying` marker, or it starts a spec-writer."""
    if not isinstance(block, dict) or block.get("type") != "tool_use":
        return False
    given = block.get("input")
    if isinstance(given, dict) and str(given.get("subagent_type", "")).endswith("spec-writer"):
        return True
    text = json.dumps(given).replace("\\\\", "/")  # a Windows path, escaped by JSON
    return any(name in text for name in GRILL_NAMES)


def _new_row() -> dict:
    return {"calls": 0, "usd": 0.0, "model": "?", "models": set(), "w5m": 0, "w1h": 0, "read": 0,
            "out": 0, "wakes": 0, "wake_context": 0, "peak_context": 0, "last_context": 0,
            "usd_in": 0.0, "usd_write": 0.0, "usd_read": 0.0, "usd_out": 0.0,  # dollars by kind
            "compactions": 0, "timed": 0, "expired": 0, "untimed": 0,
            "unpriced": {}}  # model id -> calls of a model with no price


def _add(row: dict, c: dict) -> None:
    t = c["tokens"]
    row["model"] = c["model"]
    row["models"].add(c["model"])
    if c["parts"] is None:  # no price: counted apart, never in the dollars or the priced calls
        row["unpriced"][c["model"]] = row["unpriced"].get(c["model"], 0) + 1
    else:
        row["calls"] += 1
        for k, v in zip(("w5m", "w1h", "read", "out"), t[1:]):
            row[k] += v
        row["usd"] += sum(c["parts"])
        row["usd_in"] += c["parts"][0]
        row["usd_write"] += c["parts"][1] + c["parts"][2]
        row["usd_read"] += c["parts"][3]
        row["usd_out"] += c["parts"][4]
    if c["expired"] is not None:  # measured: the gap since the agent's previous call
        row["timed"] += 1
        row["expired"] += c["expired"]
    row["peak_context"] = max(row["peak_context"], sum(t[:4]))
    row["last_context"] = sum(t[:4])
    if c["woke"]:
        row["wakes"] += 1
        row["wake_context"] += sum(t[:4])


def usage(path: Path, since: str = "", until: str = "", split: bool = False,
          prices: dict | None = None) -> dict:
    """A transcript's calls from `since` to `until`: a session can have run another batch.

    `split`: the calls of the turns that grill with the user or write specifications (a turn is
    from a wake to the next, attributed whole) go to `row["grill"]`, a row of the same shape; the
    row itself keeps the others. `prices`: the project's, above the built-in table; a call of a
    model with none is counted in `row["unpriced"]`, by model. A call with no time cannot be placed in a window: with `split`
    and a window it is in neither, and `untimed` counts it."""
    row = _new_row()
    start, end = _when(since, path, 0), _when(until, path, 0)
    seen = set()
    calls: list[dict] = []
    grill_turns: set[int] = set()
    turn = 0
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
        inside = not ((start and when and when < start) or (end and when and when > end))
        if d.get("type") == "user" and _wakes(d):
            turn += 1
        if d.get("type") == "assistant" and isinstance(d.get("message"), dict):
            content = d["message"].get("content")  # one record per block, the same message id
            if isinstance(content, list) and any(_grill_use(b) for b in content):
                grill_turns.add(turn)
        if not inside:
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
        rate = _price(model, sum(t[:4]), prices)
        calls.append({"turn": turn, "when": when, "model": model, "tokens": t, "woke": woken,
                      "parts": None if rate is None else [a * b / 1e6 for a, b in zip(t, rate)]})
        woken = False
    grill = _new_row() if split else None
    previous, lifetime = None, 0  # the last call's time, and how long its cache write lives
    for c in calls:
        c["expired"] = None
        if previous and c["when"] and lifetime:
            c["expired"] = (c["when"] - previous).total_seconds() > lifetime
        previous = c["when"]
        t = c["tokens"]
        lifetime = CACHE_1H if t[2] else CACHE_5M if t[1] else lifetime
        row["untimed"] += c["when"] is None
        if split and c["when"] is None and (start or end):
            continue  # not placed in the window: counted, in neither share
        _add(grill if split and c["turn"] in grill_turns else row, c)
    if split:
        row["grill"] = grill
    return row


def _held(row: dict) -> int:
    """The calls of a row, priced or not."""
    return row["calls"] + sum(row["unpriced"].values())


def session_costs(main: Path, since: str = "", until: str = "", kind: str = "foreman",
                  allow_empty: bool = False, split: bool = False,
                  prices: dict | None = None) -> list[dict]:
    """One row for the main transcript (`kind`: the Foreman or the Chief of Staff) and one per
    subagent with calls in the window. A window without a call is an error unless allowed."""
    label = kind.replace("-", " ").capitalize()
    if not main.is_file():
        raise ChantierError(f"{label} transcript not found: {main}", EXIT_EXTERNAL)
    foreman = usage(main, since, until, split, prices)
    if not _held(foreman) + (_held(foreman["grill"]) if split else 0) and not allow_empty:
        raise ChantierError(f"no priced calls in {label} transcript: {main}", EXIT_EXTERNAL)
    rows = [{"agent": "main", "type": kind, "description": "", **foreman}]
    sub = main.with_suffix("") / "subagents"
    if sub.exists():
        for f in sorted(sub.glob("agent-*.jsonl")):
            meta_path = f.with_suffix("").with_suffix(".meta.json")
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            row = usage(f, since, until, prices=prices)
            if _held(row):
                rows.append({"agent": f.stem.removeprefix("agent-"),
                             "type": meta.get("agentType", "?"),
                             "parent": meta.get("parentAgentId"),
                             "description": meta.get("description", ""), **row})
    return rows


def without_spec_writers(rows: list[dict]) -> list[dict]:
    """The Chief of Staff's subagents of type spec-writer (`spec-writer`, `chantier:spec-writer`,
    `chantier-spec-writer`) belong to no batch: they stay on the Chief of Staff's own line."""
    return [r for r in rows if not is_spec_writer(r)]


def is_spec_writer(row: dict) -> bool:
    return str(row.get("type", "")).endswith("spec-writer")


def copilot_home() -> Path:
    return Path(os.environ.get("COPILOT_HOME") or Path.home() / ".copilot").expanduser()


def idle_seconds(root: Path, host: str, sessions: list[str],
                 own: list[str] | None = None) -> list[tuple[str, float | None]]:
    """How long ago each session record of the batch was last written, whatever the agent.

    Claude: the Foreman's transcript and every `subagents/agent-*.jsonl` beside it, a Driver, a
    worker, a QA or a user's own one alike. Copilot: the session's `events.jsonl`, the only record
    the CLI reads, subagents included. A file's time is its modification time: many records carry
    no time of their own. None: a file that is not there, so the time is not measured. `own`: the
    sessions that ask (every Chief of Staff session of a direct batch): a file of its own is written
    by the very call that asks, so only the subagents count."""
    own = own or []
    found: list[tuple[str, float | None]] = []
    clock = datetime.now(timezone.utc).timestamp()

    def age(path: Path) -> float | None:
        try:
            return max(0.0, clock - path.stat().st_mtime)
        except OSError:
            return None

    for session in sessions:
        if host == "copilot":
            path = copilot_home() / "session-state" / session / "events.jsonl"
            if session not in own:
                found.append((f"Copilot session {session}", age(path)))
            continue
        main = transcript_path(root, session)
        if session not in own:
            found.append((f"transcript {session}", age(main)))
        for f in sorted((main.with_suffix("") / "subagents").glob("agent-*.jsonl")):
            found.append((f"transcript {session} {f.stem}", age(f)))
    return found


def agent_records(root: Path, sessions: list[str]) -> dict[str, tuple[str | None, float | None]]:
    """Claude: agent id -> (parent agent id, seconds since its record was last written), for every
    `subagents/agent-<id>.jsonl` beside each steering transcript. None: a record that cannot be
    read, so its time is not measured."""
    clock = datetime.now(timezone.utc).timestamp()
    found: dict[str, tuple[str | None, float | None]] = {}
    for session in sessions:
        folder = transcript_path(root, session).with_suffix("") / "subagents"
        for f in sorted(folder.glob("agent-*.jsonl")):
            try:
                age: float | None = max(0.0, clock - f.stat().st_mtime)
            except OSError:
                age = None
            try:
                meta = json.loads(f.with_suffix("").with_suffix(".meta.json")
                                  .read_text(encoding="utf-8"))
            except (OSError, ValueError):
                meta = {}
            found[f.stem.removeprefix("agent-")] = (meta.get("parentAgentId"), age)
    return found


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
