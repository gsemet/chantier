"""The board's Griller, the host side: what one run needs (`Run`), the flags of each proved host
(`HEADLESS`, with the candidate Claude flags in one table, `CLAUDE`), the seam (`command(run)` and
`environment(run)`, which a test replaces), what the board may offer (`availability`) and the
reading of a finished run's output. The conversations are in `griller.py`."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chantier import plugin_files
from chantier.board import griller_files as files
from chantier.board.projects import Project
from chantier.core.errors import ChantierError
from chantier.lifecycle.backlog import backlog_folder
from chantier.playbook import config, edit

ROLE = "board-griller"
ERROR_MAX = 2000

# the variables that would make the run look like the steering session or a nested one
CLEARED_ENV = (
    "CLAUDECODE",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_SESSION_ID",
    "CLAUDE_CODE_SSE_PORT",
    "CLAUDE_PROJECT_DIR",
    "CHANTIER_BATCH",
)

# the reasons (hosts/copilot.md and hosts/claude-code.md say the same words)
NOT_PROVED_COPILOT = (
    "the board's Griller is not proved on Copilot yet: grill in a session with the Griller skill"
)
NOT_PROVED = "the board's Griller's limits are not proved on this host"
NO_HOST = (
    "the board was started outside a Claude Code or Copilot session, so it cannot tell which CLI "
    "to run: start it from a session, or set CHANTIER_HOST before `chantier board`"
)


class Refused(Exception):
    """A request the engine refuses: the HTTP status the API answers, and the one line."""

    def __init__(self, status: int, text: str) -> None:
        super().__init__(text)
        self.status, self.text = status, text


@dataclass
class Run:
    """What one run needs: the item, the host and model, the conversation's id and the prompt."""

    project: Project
    slug: str
    folder: Path
    host: str
    cli: str  # the host's CLI, `claude`
    model: str
    agent: str
    session: str
    first: bool  # the first run of the id: `--session-id`, else `--resume`
    prompt: str
    cwd: Path  # the same folder at every run (a resume needs it)
    readable: list[Path]  # the folders the run reads: the working one first
    skill: Path
    plugin_root: Path
    cli_command: str  # `$CHANTIER`, as the brief names it


# --- Claude Code: the candidate flags, one table (hosts/claude-code.md: unproved until the trial)

CLAUDE: dict[str, Any] = {
    "print": ["-p", "--output-format", "json"],
    "agent": "--agent",
    "model": "--model",
    "new": "--session-id",
    "resume": "--resume",
    "no-settings": ["--setting-sources", ""],
    "plugin": "--plugin-dir",
    "no-mcp": ["--strict-mcp-config"],
    "refuse": ["--permission-mode", "dontAsk"],
    "allow": "--allowedTools",
    "add-dir": "--add-dir",
}


def _path_rule(tool: str, path: Path) -> str:
    return f"{tool}(//{path.resolve().as_posix().lstrip('/')}/**)"


def allow_list(run: Run) -> list[str]:
    """The run's only permissions, built from the absolute paths: the reads of the working
    folder, the clone and the skill folder; `Write` and `Edit` on the CR's folder; the four
    `chantier` commands, in Bash and in PowerShell. `summary set` is pinned to the CR's folder and
    to `--title`, so no rule matches it on `<cr>-x`, `<cr>/../<sibling>` or `<cr> --project <p>`."""
    rules = [_path_rule(t, d) for d in run.readable for t in ("Read", "Grep", "Glob")]
    rules += [_path_rule(t, run.folder) for t in ("Write", "Edit")]
    cli, cr = run.cli_command, run.folder.as_posix()
    shapes = [
        f"{cli} rules",
        f"{cli} access *",
        f"{cli} summary lint {cr}",
        f"{cli} summary set {cr} --title *",
    ]
    return rules + [f"{tool}({s})" for s in shapes for tool in ("Bash", "PowerShell")]


def _claude(run: Run, exe: str) -> list[str]:
    flags = CLAUDE
    argv = [exe, *flags["print"], flags["agent"], run.agent, flags["model"], run.model]
    argv += [flags["new"] if run.first else flags["resume"], run.session]
    argv += [*flags["no-settings"], flags["plugin"], str(run.plugin_root), *flags["no-mcp"]]
    argv += [*flags["refuse"], flags["allow"], *allow_list(run)]
    for folder in run.readable[1:]:
        argv += [flags["add-dir"], str(folder)]
    return argv


def _claude_saved(session: str) -> bool:
    """Whether the host saved a conversation for this id (the trial proves how: unproved)."""
    base = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
    return any(base.glob(f"*/{session}.jsonl"))


@dataclass(frozen=True)
class Headless:
    cli: str
    build: Callable[[Run, str], list[str]]
    saved: Callable[[str], bool]
    host_file: str


HEADLESS: dict[str, Headless] = {
    "claude": Headless("claude", _claude, _claude_saved, "claude-code")
}


# --- the seam ---------------------------------------------------------------------------------


def command(run: Run) -> list[str]:
    """The run's command line (the host CLI with its flags); a test replaces this function. A
    missing CLI is `FileNotFoundError`, the turn's `error`."""
    entry = HEADLESS[run.host]
    exe = shutil.which(entry.cli)
    if exe is None:
        raise FileNotFoundError(f"{entry.cli}: not found on this machine")
    return entry.build(run, exe)


def environment(run: Run) -> dict[str, str]:
    """The server's environment without the variables of a steering or a nested session, and
    `CHANTIER_HOST` set to the host."""
    cleared = {name.upper() for name in CLEARED_ENV}
    env = {k: v for k, v in os.environ.items() if k.upper() not in cleared}
    env["CHANTIER_HOST"] = run.host
    return env


# --- what the board may offer -----------------------------------------------------------------


def _role_refusal(host: str, row: dict[str, Any] | None) -> str | None:
    """Why the role's row on this host cannot start the board's Griller, else None."""
    if row is None:
        return f"role {ROLE!r} is not among the plugin's agents"
    if row["refusal"]:
        return str(row["refusal"])
    if (why := config.start_refusal(host, ROLE)) is not None:
        return why
    default = config.default_agent(host, ROLE)
    if row["agent"]["effective"] != default:
        return (
            f"role \"{ROLE}\": the board's Griller runs only the plugin's agent {default}: remove "
            f'"agent" for {ROLE} under hosts.{host}.roles ({row["agent"]["layer"]})'
        )
    if row["model"]["effective"] is None:
        return f'role "{ROLE}": no model is set (hosts.{host}.roles)'
    return None


def availability(project: Project) -> dict[str, Any]:
    """`available`, `reason` (one line, when not), `host`, `cli` and `model`: a host not told or
    not proved, the role's start refused, an agent other than the plugin's or a model that does
    not resolve refuse the action."""
    out: dict[str, Any] = {
        "available": False,
        "reason": None,
        "host": None,
        "cli": None,
        "model": None,
    }
    try:
        host = plugin_files.detect_host()
    except ChantierError:
        return out | {"reason": NO_HOST}
    out["host"] = host
    if host not in HEADLESS:
        return out | {"reason": NOT_PROVED_COPILOT if host == "copilot" else NOT_PROVED}
    out["cli"] = HEADLESS[host].cli
    rows = edit.config_view(project.repo)["hosts"][host]["roles"]
    row = next((r for r in rows if r["role"] == ROLE), None)
    out["reason"] = _role_refusal(host, row)
    if out["reason"] is None and row is not None:
        out["available"], out["model"] = True, row["model"]["effective"]["id"]
    return out


def end_tree(proc: Any) -> None:
    """The process and every child of it, at once."""
    import psutil

    if proc is None:
        return
    try:
        top = psutil.Process(proc.pid)
        for child in top.children(recursive=True):
            with contextlib.suppress(psutil.NoSuchProcess):
                child.kill()
        top.kill()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass


def tail(text: str) -> str:
    """The last lines of an output, cut to the error's size."""
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    return "\n".join(lines[-10:])[-ERROR_MAX:]


def result(out: bytes, err: bytes, code: int) -> tuple[str | None, str | None]:
    """`(answer, error)` of a finished run: the JSON `result` of the host CLI, else the CLI's own
    words (its error output, then its output)."""
    text = out.decode("utf-8", "replace")
    try:
        data = json.loads(text)
    except ValueError:
        data = None
    if isinstance(data, dict) and isinstance(data.get("result"), str):
        if data.get("is_error") or code != 0:
            return None, (data["result"].strip() or f"exit {code}")[-ERROR_MAX:]
        return data["result"], None
    said = tail(err.decode("utf-8", "replace")) or tail(text)
    return None, said or f"the CLI exited {code} with no result"


def item_folder(project: Project, item: str) -> Path:
    """The item's folder, among the inbox, `P1`...`P4` and `3-ready` only (`Refused` otherwise)."""
    repo = project.repo
    try:
        return backlog_folder(repo, item)
    except ChantierError:
        pass
    elsewhere = files.locate(repo, item)
    if not elsewhere:
        raise Refused(404, f"no item {item!r} in project {project.id}") from None
    raise Refused(
        409,
        "the board's Griller grills inbox, backlog and ready items only: "
        f"{item} is in {files.stage_of(repo, elsewhere[0])}",
    )
