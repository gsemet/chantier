"""The host, the team's roles, and the agent each role runs in a batch.

A role runs the plugin's agent unless the batch was opened with `--agent <role>=<agent>`, which
the Chief of Staff reads from the project's AGENTS.md. A review step (`--review
<name>=<agent>:<task>`) is an extra role: the CR Driver runs it after the Inspector approves.
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


def parse_team(agents: list[str], reviews: list[str]) -> tuple[dict, dict]:
    """`--agent role=agent` and `--review name=agent:task` into the batch's settings."""
    chosen, steps = {}, {}
    for value in agents:
        role, _, agent = value.partition("=")
        if role not in ROLES or not agent.strip():
            raise ChantierError(f"--agent {value}: <role>=<agent>, role one of {', '.join(ROLES)}",
                                EXIT_USAGE)
        chosen[role] = agent.strip()
    for value in reviews:
        name, _, rest = value.partition("=")
        agent, _, task = rest.partition(":")
        if (name in ROLES or name in RESERVED or not ROLE_NAME.fullmatch(name)
                or not agent.strip() or not task.strip()):
            raise ChantierError(f"--review {value}: <name>=<agent>:<what it checks>, the name in "
                                "lowercase letters, digits and hyphens, not a built-in role",
                                EXIT_USAGE)
        steps[name] = {"agent": agent.strip(), "task": task.strip()}
    return chosen, steps


def agent_for(settings: dict, role: str, host: str, plugin: Path | None) -> tuple[str, str | None]:
    """The agent a role runs in this batch, and the task of a review step."""
    if role in settings.get("reviews", {}):
        step = settings["reviews"][role]
        return step["agent"], step["task"]
    if role not in ROLES:
        names = [*ROLES, *settings.get("reviews", {})]
        raise ChantierError(f"unknown role `{role}` (roles: {', '.join(names)})", EXIT_USAGE)
    if role in settings.get("agents", {}):
        return settings["agents"][role], None
    if not plugin or not plugin_agent_file(plugin, role, host).is_file():
        raise ChantierError(f"the plugin's agent for {role} is missing: install the chantier "
                            "plugin and restart the session", EXIT_PRECONDITION)
    return plugin_agent_id(role, host), None
