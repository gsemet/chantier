"""`chantier preflight`: the checks before a batch."""

from __future__ import annotations

import argparse
import os
import re
import shutil
from pathlib import Path

from chantier import __version__
from chantier.commands.permissions import SETTINGS_SHOWN, commands_not_allowed
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.files import read_text
from chantier.core.git import default_branch, git
from chantier.core.repo import Repo, SurfaceChoice
from chantier.lifecycle.convert import open_repo
from chantier.playbook.config import FILE
from chantier.plugin_files import (
    INSTRUCTIONS,
    agent_problems,
    detect_host,
    project_instructions,
    read_playbook,
    skill_version,
)


class _Report:
    """The lines of the report, and whether every check that can fail passed."""

    def __init__(self) -> None:
        self.lines: list[str] = []
        self.ok = True

    def check(self, tag: str, passed: bool, good: str, bad: str, warn: bool = False) -> None:
        if not warn:
            self.ok &= passed
        state = "ok  " if passed else "warn" if warn else "FAIL"
        self.lines.append(f"{tag} {state} {good if passed else bad}")


def _check_host(r: _Report, host: str | None, direct: bool) -> None:
    entry = os.environ.get("CLAUDE_CODE_ENTRYPOINT", "")
    if host == "copilot":
        r.check(
            "P1",
            bool(os.environ.get("COPILOT_AGENT_SESSION_ID")),
            "host is a Copilot agent session",
            "host is Copilot but COPILOT_AGENT_SESSION_ID is empty: not a Copilot agent session",
        )
    elif direct:  # the Chief of Staff steers: no session to start
        r.check(
            "P1",
            bool(entry),
            f"host is Claude Code ({entry})",
            "host is unknown (CLAUDE_CODE_ENTRYPOINT is empty), not a Claude Code or a "
            "Copilot agent session",
        )
    else:
        r.check(
            "P1",
            entry == "claude-desktop",
            "host is Claude Desktop",
            f"host is {entry or 'unknown'} (CLAUDE_CODE_ENTRYPOINT), not claude-desktop "
            "or a Copilot agent session",
        )


def _open_project(r: _Report) -> Repo | None:
    try:
        return open_repo(Path(os.getcwd()))
    except SurfaceChoice as e:  # a surface: the projects are listed, a command names one
        r.lines.append(
            f"P6 ok   a planning surface with projects {', '.join(e.names)}: pass --project <name>"
        )
    except ChantierError as e:
        r.check("P6", False, "", str(e))
    return None


def _check_agents(r: _Report, host: str | None) -> None:
    if not host:
        r.check("P4", False, "", "unknown host: no agents to check")
        return
    problems = agent_problems(host)
    r.check(
        "P4",
        not problems,
        f"the plugin's agents are at {__version__} on {host}",
        "; ".join(problems),
    )


def _check_tools(r: _Report) -> None:
    missing = [t for t in ("uv", "git") if shutil.which(t) is None]
    sv = skill_version()
    r.check(
        "P5",
        not missing and sv == __version__,
        f"chantier {__version__}, uv and git found",
        f"{', '.join(missing) + ' missing' if missing else 'uv and git found'}; "
        f"CLI {__version__}, SKILL.md {sv}",
    )


def _check_checkout(r: _Report, repo: Repo) -> None:
    top = Path(git("rev-parse", "--show-toplevel", check=False) or ".").resolve()
    where = repo.session_root
    r.check(
        "P6",
        top == where.resolve(),
        f"in the main checkout of {where.name}",
        f"session folder {top} is not the repository root {where}",
    )
    gitdir = Path(git("rev-parse", "--path-format=absolute", "--git-dir", check=False) or ".")
    r.check(
        "P7",
        gitdir.resolve() == repo.git_dir,
        "not a linked worktree",
        "this session runs in a linked worktree: the Foreman must start in the main checkout",
    )


def _check_instructions(r: _Report, repo: Repo) -> None:
    found = project_instructions(repo)
    if repo.external and not repo.clone.is_dir():
        text = repo.project_folder / "project.md"
        remote = (
            re.search(r"^\W*remote\W*:?\s*(\S+)", read_text(text), re.I | re.M)
            if text.is_file()
            else None
        )
        r.check(
            "P8",
            False,
            "",
            f"no clone of the project at {repo.clone.as_posix()} "
            f"(remote {remote[1] if remote else 'see project.md'}): clone it there",
        )
    else:
        r.check(
            "P8",
            found is not None,
            f"project instructions: {found.name if found else ''}",
            f"no {', '.join(INSTRUCTIONS)}: ask the user how the project builds and tests",
        )


def _check_playbook(r: _Report, repo: Repo, host: str) -> None:
    made, problems = read_playbook(repo, host)
    r.check(
        "P12",
        not problems,
        f"{FILE} valid: {len(made['roles'])} roles configured"
        if made
        else f"no {FILE}: the plugin's agents and models",
        f"{problems[0] if problems else ''}"
        f"{f' (and {len(problems) - 1} more)' if len(problems) > 1 else ''}: "
        "run `$CHANTIER playbook`",
    )


def _check_surface(r: _Report, repo: Repo) -> None:
    here = git("branch", "--show-current", check=False)
    main = default_branch(repo.surface_root)
    r.check(
        "P11",
        not main or here == main,
        f"the surface is on its default branch ({here})",
        f"the surface is on {here or 'no branch'}, its default branch is {main}: it is "
        "always worked on its default branch",
        warn=True,
    )


def _check_allow(r: _Report, repo: Repo | None) -> None:
    count, total, named, blocked, unreadable = commands_not_allowed(repo)
    note = f" (unreadable: {', '.join(unreadable)})" if unreadable else ""
    r.check(
        "P10",
        not count,
        f"the commands chantier's agents run are allowed by your settings{note}",
        f"{count} of {total} commands chantier's agents run are not allowed by your settings "
        f"({SETTINGS_SHOWN}){note}: {'; '.join(named)}"
        f"{'; denied: ' + '; '.join(blocked) if blocked else ''}; the block is in "
        'hosts/claude-code.md, "Allow rules"',
        warn=True,
    )


def _check_project(r: _Report, repo: Repo, host: str | None) -> None:
    _check_checkout(r, repo)
    _check_instructions(r, repo)
    if host:
        _check_playbook(r, repo, host)
    if repo.external:
        _check_surface(r, repo)


def preflight(args: argparse.Namespace) -> tuple[list[str], int]:
    r = _Report()
    direct = getattr(args, "direct", False)
    try:
        host = detect_host()
    except ChantierError:
        host = None
    _check_host(r, host, direct)
    repo = _open_project(r)
    _check_agents(r, host)
    _check_tools(r)
    if repo:
        _check_project(r, repo, host)
    if host == "claude":
        _check_allow(r, repo)
    own = "P3, P9" if direct else "P2, P3, P9"
    r.lines.append(f"{own} and 'not unattended' are the Chief of Staff's own checks")
    r.lines.append("preflight passed" if r.ok else "preflight FAILED: start nothing")
    return r.lines, 0 if r.ok else EXIT_PRECONDITION
