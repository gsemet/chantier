"""The host, the team's roles, the agent each role runs and the prompt each spawn carries.

A role runs the plugin's agent unless the project profile names another one
(`chantier roles set`). A role that is not built in is an extra review step: the CR Driver runs
it after the Inspector approves, with the task recorded for it.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from .state import EXIT_PRECONDITION, EXIT_USAGE, ChantierError

HOSTS = ("claude", "copilot")
DRIVERS = ("cr-driver", "stack-driver", "qa-driver")
WORKERS = ("investigator", "coder", "inspector", "debugger", "verifier", "conflict-resolver")
ROLES = DRIVERS + WORKERS
RESERVED = {"foreman", "chief-of-staff", "driver", "worker", "stack", "qa"}
ROLE_NAME = re.compile(r"[a-z][a-z0-9-]{1,40}")
HEARTBEATS = {"claude": ("55m", 3300), "copilot": ("4m", 240)}
# The Foreman is a session, not an agent: its model is chosen here, per host.
FOREMAN = {"claude": ("claude-opus-5-5", "low"), "copilot": ("claude-opus-5.5", None)}
PLUGIN_NAME = "chantier"
CR_IN_NAME = re.compile(r"\bCR-\d+\b")


def detect_host(explicit: str | None = None) -> tuple[str, str]:
    """The host and why: `--host`, `CHANTIER_HOST`, then the host's environment."""
    if explicit:
        return check_host(explicit), "--host"
    if os.environ.get("CHANTIER_HOST"):
        return check_host(os.environ["CHANTIER_HOST"]), "CHANTIER_HOST"
    if os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
        return "claude", "CLAUDE_CODE_ENTRYPOINT"
    if (os.environ.get("COPILOT_CLI") or os.environ.get("COPILOT_AGENT_SESSION_ID")
            or os.environ.get("AI_AGENT", "").startswith("github_copilot")):
        return "copilot", "COPILOT_* environment"
    raise ChantierError("cannot tell the host (Claude or Copilot): set CHANTIER_HOST or pass --host",
                        EXIT_USAGE)


def check_host(host: str) -> str:
    if host not in HOSTS:
        raise ChantierError(f"unknown host `{host}`: one of {', '.join(HOSTS)}", EXIT_USAGE)
    return host


def check_role_name(role: str) -> str:
    if role in RESERVED or not ROLE_NAME.fullmatch(role):
        raise ChantierError(f"`{role}` cannot be a role: lowercase letters, digits and hyphens, "
                            f"not one of {', '.join(sorted(RESERVED))}", EXIT_USAGE)
    return role


def plugin_agent_id(role: str, host: str) -> str:
    """Claude namespaces plugin agents; Copilot names them by file, so ours carry a prefix that a
    project agent with the bare role name cannot shadow."""
    return f"{PLUGIN_NAME}:{role}" if host == "claude" else f"{PLUGIN_NAME}-{role}"


def plugin_agent_file(root: Path, role: str, host: str) -> Path:
    if host == "claude":
        return root / "agents" / f"{role}.md"
    return root / "com.github.copilot" / "agents" / f"{PLUGIN_NAME}-{role}.agent.md"


def local_agent_file(repo_root: Path, agent: str, host: str) -> Path | None:
    """A project or user agent file for a plain agent id, if one exists."""
    if ":" in agent:
        return None
    if host == "claude":
        places = [repo_root / ".claude" / "agents", Path.home() / ".claude" / "agents"]
        name = f"{agent}.md"
    else:
        places = [repo_root / ".github" / "agents", Path.home() / ".copilot" / "agents"]
        name = f"{agent}.agent.md"
    return next((p / name for p in places if (p / name).is_file()), None)


def agent_model(path: Path | None) -> str | None:
    """The model an agent file pins, as written (`[name, id]` lists give the id)."""
    if not path or not path.is_file():
        return None
    parts = path.read_text(encoding="utf-8").replace("\r\n", "\n").split("---\n", 2)
    if len(parts) != 3 or parts[0].strip():
        return None
    m = re.search(r"^model:[ \t]*(.+?)[ \t]*$", parts[1], re.M)
    if not m:
        return None
    model = m[1]
    if model.startswith("[") and model.endswith("]"):
        model = model[1:-1].split(",")[-1]
    return model.strip().strip("\"'") or None


def team(settings_agents: dict, host: str, plugin: Path | None, repo_root: Path) -> dict[str, dict]:
    """Every role of this host: its agent id, where it comes from, its model, and its task."""
    out: dict[str, dict] = {}
    chosen = settings_agents.get(host, {}) if isinstance(settings_agents, dict) else {}
    for role in ROLES:
        if role in chosen:
            agent = chosen[role]["agent"]
            path = local_agent_file(repo_root, agent, host)
            out[role] = {"agent": agent, "source": "project", "file": path,
                         "model": agent_model(path), "task": None}
        else:
            path = plugin_agent_file(plugin, role, host) if plugin else None
            out[role] = {"agent": plugin_agent_id(role, host), "source": "plugin",
                         "file": path if path and path.is_file() else None,
                         "model": agent_model(path), "task": None}
    for role, entry in sorted(chosen.items()):
        if role not in ROLES:
            path = local_agent_file(repo_root, entry["agent"], host)
            out[role] = {"agent": entry["agent"], "source": "extra", "file": path,
                         "model": agent_model(path), "task": entry.get("task")}
    return out


def extra_roles(roles: dict[str, dict]) -> list[str]:
    return [r for r, e in roles.items() if e["source"] == "extra"]


def role_entry(roles: dict[str, dict], role: str) -> dict:
    if role not in roles:
        raise ChantierError(f"unknown role `{role}` (roles: {', '.join(roles)})", EXIT_USAGE)
    entry = roles[role]
    if entry["source"] == "plugin" and not entry["file"]:
        raise ChantierError(f"the plugin's agent for {role} is missing: install the chantier "
                            "plugin and restart the session", EXIT_PRECONDITION)
    return entry
