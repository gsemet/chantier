"""Host detection, the models pinned by static agents, and Copilot model auditing."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .state import EXIT_PRECONDITION, EXIT_USAGE, ChantierError

HOSTS = ("claude", "copilot")
ROLES = ("foreman", "cr-driver", "stack-driver", "qa-driver", "investigator", "coder",
         "inspector", "debugger", "verifier", "conflict-resolver")
INHERIT = "inherit"
HEARTBEATS = {"claude": ("55m", 3300), "copilot": ("4m", 240)}
CR_IN_NAME = re.compile(r"\bCR-\d+\b")


def detect_host(explicit: str | None = None) -> tuple[str, str]:
    """The host and why: `--host`, `CHANTIER_HOST`, then the host's environment."""
    if explicit:
        return _check_host(explicit), "--host"
    if os.environ.get("CHANTIER_HOST"):
        return _check_host(os.environ["CHANTIER_HOST"]), "CHANTIER_HOST"
    if os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
        return "claude", "CLAUDE_CODE_ENTRYPOINT"
    if (os.environ.get("COPILOT_CLI") or os.environ.get("COPILOT_AGENT_SESSION_ID")
            or os.environ.get("AI_AGENT", "").startswith("github_copilot")):
        return "copilot", "COPILOT_* environment"
    raise ChantierError("cannot tell the host (Claude or Copilot): set CHANTIER_HOST or pass --host",
                        EXIT_USAGE)


def _check_host(host: str) -> str:
    if host not in HOSTS:
        raise ChantierError(f"unknown host `{host}`: one of {', '.join(HOSTS)}", EXIT_USAGE)
    return host


def agent_pin(path: Path, host: str) -> tuple[str, str | None]:
    """Read the plugin's one-line model and effort frontmatter, without interpreting a model ID."""
    text = path.read_text(encoding="utf-8")
    parts = text.split("---\n", 2)
    if len(parts) != 3 or parts[0].strip():
        raise ChantierError(f"{path}: agent frontmatter is missing", EXIT_PRECONDITION)
    front = parts[1]
    matches = re.findall(r"^model:[ \t]*(.+?)[ \t]*$", front, re.M)
    if len(matches) != 1:
        raise ChantierError(f"{path}: expected one model in agent frontmatter", EXIT_PRECONDITION)
    model = matches[0]
    if host == "copilot" and model.startswith("[") and model.endswith("]"):
        entries = [part.strip().strip("\"'") for part in model[1:-1].split(",")]
        if len(entries) != 2 or not all(entries):
            raise ChantierError(f"{path}: expected [display name, exact model id]", EXIT_PRECONDITION)
        model = entries[-1]
    else:
        model = model.strip("\"'")
    if not model or (host == "copilot" and model.startswith("[")):
        raise ChantierError(f"{path}: invalid model in agent frontmatter", EXIT_PRECONDITION)
    key = "reasoning-effort" if host == "copilot" else "effort"
    efforts = re.findall(rf"^{key}:[ \t]*(.+?)[ \t]*$", front, re.M)
    if len(efforts) > 1:
        raise ChantierError(f"{path}: duplicate {key} in agent frontmatter", EXIT_PRECONDITION)
    effort = efforts[0].strip("\"'") if efforts else None
    return model, None if effort in (None, INHERIT) else effort


class Models:
    """Model pins come from shipped agent files; repository agents decide for themselves."""

    def __init__(self, host: str, paths: dict[str, Path | None], custom: set[str]):
        self.host = _check_host(host)
        self.heartbeat, self._heartbeat_seconds = HEARTBEATS[host]
        self.roles: dict[str, str] = {}
        self.source: dict[str, str] = {}
        self.effort: dict[str, str | None] = {}
        self.errors: list[str] = []
        for role in ROLES:
            path = paths.get(role)
            if role in custom and role != "foreman":
                self.roles[role], self.effort[role], self.source[role] = INHERIT, None, "custom agent"
            elif not path:
                self.errors.append(f"missing agent for {role}")
            else:
                try:
                    self.roles[role], self.effort[role] = agent_pin(path, host)
                    self.source[role] = "agent"
                except (ChantierError, OSError, UnicodeError) as e:
                    self.errors.append(str(e))

    def heartbeat_seconds(self) -> int:
        return self._heartbeat_seconds

    def role(self, role: str) -> str:
        if role not in ROLES:
            raise ChantierError(f"unknown role `{role}` (roles: {', '.join(ROLES)})", EXIT_USAGE)
        if role not in self.roles:
            raise ChantierError(f"no valid agent model for {role}", EXIT_PRECONDITION)
        return self.roles[role]

    def effort_of(self, role: str) -> str | None:
        return self.effort.get(role)


def copilot_events(session: str) -> Path:
    home = Path(os.environ.get("COPILOT_HOME") or Path.home() / ".copilot").expanduser()
    return home / "session-state" / session / "events.jsonl"


def copilot_spawns(path: Path, agent_roles: dict[str, str] | None = None) -> list[dict]:
    """Read chantier spawns and the effort reported by their configured events."""
    if not path.exists():
        raise ChantierError(f"no Copilot event log at {path}", EXIT_PRECONDITION)
    spawns = []
    efforts: dict[str, str | None] = {}
    for line in path.open(encoding="utf-8"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("type") == "subagent.configured":
            efforts[e.get("agentId")] = (e.get("data") or {}).get("reasoningEffort")
            continue
        if e.get("type") != "subagent.started":
            continue
        d = e.get("data") or {}
        agent = d.get("agentType") or d.get("agentName")
        role = (agent_roles or {}).get(agent, agent)
        if role not in ROLES:
            continue
        name = f"{d.get('agentDisplayName', '')} {d.get('agentDescription', '')}"
        cr = CR_IN_NAME.search(name)
        spawns.append({"role": role, "cr": cr.group(0) if cr else None,
                       "model": d.get("model"), "selection": d.get("modelSelectionSource"),
                       "agent": e.get("agentId"), "name": d.get("agentDisplayName", "")})
    for spawn in spawns:
        spawn["effort"] = efforts.get(spawn["agent"])
    return spawns


def copilot_session(path: Path) -> dict:
    """Read the session's own model calls and recurring `/every` schedules."""
    if not path.exists():
        raise ChantierError(f"no Copilot event log at {path}", EXIT_PRECONDITION)
    calls: dict[tuple[str | None, str | None], int] = {}
    schedules: list[dict] = []
    for line in path.open(encoding="utf-8"):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        d = e.get("data") or {}
        if e.get("type") == "session.usage_record" and not e.get("agentId"):
            u = d.get("usage") or {}
            key = (u.get("model"), u.get("reasoningEffort"))
            calls[key] = calls.get(key, 0) + 1
        elif e.get("type") == "session.schedule_created":
            schedules.append({"id": d.get("id"), "prompt": d.get("prompt", ""),
                              "interval_ms": d.get("intervalMs"),
                              "recurring": d.get("recurring")})
        elif e.get("type") == "session.schedule_cancelled":
            schedules = [s for s in schedules if s["id"] != d.get("id")]
    return {"calls": calls, "schedules": schedules}
