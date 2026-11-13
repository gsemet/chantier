"""The plugin's own files: the skill, the host, the agents, the project's instructions."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from chantier import __version__
from chantier.core.clock import stamp
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.repo import Repo
from chantier.playbook.config import FILE, load

HOSTS = ("claude", "copilot")


AGENT_VERSION = re.compile(r"^# chantier-agent: (\S+)$", re.M)


INSTRUCTIONS = ("AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md")


def skill_dir() -> Path:
    """The skill folder: `CHANTIER_SKILL_DIR`, else the nearest parent of this file with
    SKILL.md."""
    env = os.environ.get("CHANTIER_SKILL_DIR")
    if env:
        return Path(env).resolve()
    for p in Path(__file__).resolve().parents:
        if (p / "SKILL.md").exists():
            return p
    raise ChantierError(
        "cannot find the chantier skill folder; set CHANTIER_SKILL_DIR", EXIT_PRECONDITION
    )


def plugin_root() -> Path | None:
    """The plugin this skill ships in, or None for a skill installed on its own.

    `CHANTIER_PLUGIN_ROOT` wins (empty: no plugin); else the folder two levels above the skill,
    when it holds a plugin manifest.
    """
    env = os.environ.get("CHANTIER_PLUGIN_ROOT")
    if env is not None:
        return Path(env).resolve() if env else None
    root = skill_dir().parents[1]
    return (
        root
        if (root / ".claude-plugin" / "plugin.json").exists()
        or (root / ".github" / "plugin" / "plugin.json").exists()
        else None
    )


def cli_command(repo: Repo | None = None) -> str:
    """How every agent runs this CLI: the exact command, with the absolute path."""
    option = f' --project "{repo.project_dir.as_posix()}"' if repo and repo.external else ""
    return (
        f'uv run --script "{(skill_dir() / "scripts" / "cli" / "chantier.py").as_posix()}"{option}'
    )


def detect_host(explicit: str | None = None) -> str:
    """The host: `CHANTIER_HOST`, then the host's own environment."""
    host = explicit or os.environ.get("CHANTIER_HOST")
    if host:
        if host not in HOSTS:
            raise ChantierError(f"unknown host `{host}`: one of {', '.join(HOSTS)}", EXIT_USAGE)
        return host
    if os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
        return "claude"
    if (
        os.environ.get("COPILOT_CLI")
        or os.environ.get("COPILOT_AGENT_SESSION_ID")
        or os.environ.get("AI_AGENT", "").startswith("github_copilot")
    ):
        return "copilot"
    raise ChantierError("cannot tell the host (Claude or Copilot): set CHANTIER_HOST", EXIT_USAGE)


def project_instructions(repo: Repo) -> Path | None:
    return next((repo.root / name for name in INSTRUCTIONS if (repo.root / name).is_file()), None)


def surface_instructions(repo: Repo) -> Path | None:
    """The surface's own rules (its sync, among others); none in-project."""
    if not repo.external:
        return None
    return next((repo.surface / n for n in INSTRUCTIONS if (repo.surface / n).is_file()), None)


def archive_path(repo: Repo, c: dict[str, Any]) -> str | None:
    """Where the CR's cleaned archive goes in its PR, in the project's repository; None when the
    mode is in-project or the project's setting says no."""
    if not (repo.external and repo.archive_in_pr):
        return None
    name = Path(c["path"]).name if c.get("path") else c["id"]
    return f".agents/changes/5-archives/{c.get('archive_stamp') or stamp()}-{name}/"


def skill_version() -> str | None:
    m = re.search(
        r"^chantier-version: (\S+)$", (skill_dir() / "SKILL.md").read_text(encoding="utf-8"), re.M
    )
    return m.group(1) if m else None


def _agent_files(host: str) -> tuple[Path | None, list[Path]]:
    """The plugin's folder for this host and the agent files it installs."""
    root = plugin_root()
    if not root:
        return None, []
    folder = root / "agents" if host == "claude" else root / "com.github.copilot" / "agents"
    return folder, sorted(folder.glob("*.md")) if folder.is_dir() else []


def plugin_roles(host: str) -> list[str]:
    """The roles of the plugin's agents for this host, from the installed files, in their order:
    the CLI knows no role by itself."""
    return [
        p.name.removesuffix(".md").removesuffix(".agent").removeprefix("chantier-")
        if host == "copilot"
        else p.name.removesuffix(".md")
        for p in _agent_files(host)[1]
    ]


def read_playbook(repo: Repo, host: str) -> tuple[dict[str, Any] | None, list[str]]:
    """The project's `chantier.yaml`, resolved for this host: `(None, [])` when absent, else the
    playbook, or the problems found."""
    return load(repo.root / FILE, host, plugin_roles(host))


def agent_problems(host: str) -> list[str]:
    """The plugin's agents for this host, all at this version; the CLI knows no role, only that
    the files the plugin installs match it."""
    folder, files = _agent_files(host)
    if folder is None:
        return [
            "the chantier plugin is not installed (a skill alone has no agents): install the "
            "plugin and restart the session"
        ]
    if not files:
        return [f"no plugin agent in {folder}"]
    return [
        f"plugin agent {p.name} is not version {__version__}"
        for p in files
        if (m := AGENT_VERSION.search(p.read_text(encoding="utf-8"))) is None or m[1] != __version__
    ]
