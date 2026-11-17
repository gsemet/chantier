"""The plugin's own files: the skill, the host, the agents, the project's instructions."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from chantier import __version__
from chantier.core.clock import stamp
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.repo import Repo
from chantier.playbook import escalation, layers, timing

if TYPE_CHECKING:
    from chantier.core.records import CrEntry

HOSTS = ("claude", "copilot")


AGENT_VERSION = re.compile(r"^# chantier-agent: (\S+)$", re.M)


INSTRUCTIONS = ("AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md")


SKILL: str | None = None  # `--skill`, set by the CLI before the command runs


def skill_dir() -> Path:
    """The skill folder, in order: `--skill`, `CHANTIER_SKILL_DIR`, else the nearest parent of
    this file with SKILL.md (chantier's own checkout, where the package is installed in place)."""
    given = SKILL or os.environ.get("CHANTIER_SKILL_DIR")
    if given:
        return Path(given).resolve()
    for p in Path(__file__).resolve().parents:
        if (p / "SKILL.md").exists():
            return p
    raise ChantierError(
        "cannot find the chantier skill folder: pass --skill <the skill's folder>",
        EXIT_PRECONDITION,
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


def is_dev_checkout() -> bool:
    """Whether the plugin root holds `.git` (a folder or a worktree's file): chantier's own
    checkout, as opposed to a host's plugin copy."""
    return (skill_dir().parents[1] / ".git").exists()


def cli_command(repo: Repo | None = None) -> str:
    """How every agent runs this CLI, by the mode of the install. In chantier's own checkout (the
    plugin root holds `.git`, a folder or a file) it runs the local code,
    `uv run --no-sync --project "<plugin root>" chantier` (the environment is synced at named
    moments by the steering session, with `sync_command()`, never by a command); anywhere else (a
    host's plugin copy) it runs the plugin's own folder,
    `uvx --from "<plugin root>" chantier --skill "<skill folder>"`.
    A planning surface adds `--project "<folder>"` after `chantier`."""
    skill = skill_dir()
    root = skill.parents[1]
    option = f' --project "{repo.project_folder.as_posix()}"' if repo and repo.external else ""
    if is_dev_checkout():
        return f'uv run --no-sync --project "{root.as_posix()}" chantier{option}'
    return f'uvx --from "{root.as_posix()}" chantier --skill "{skill.as_posix()}"{option}'


def sync_command() -> str | None:
    """The dev mode's sync line, `uv sync --locked --project "<plugin root>"`, run by the steering
    session at named moments; None in the plugin mode."""
    if not is_dev_checkout():
        return None
    return f'uv sync --locked --project "{skill_dir().parents[1].as_posix()}"'


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
    return next(
        (repo.surface_root / n for n in INSTRUCTIONS if (repo.surface_root / n).is_file()), None
    )


def archive_path(repo: Repo, c: CrEntry) -> str | None:
    """Where the CR's cleaned archive goes in its PR, in the project's repository; None when the
    mode is in-project or the project's setting says no."""
    if not (repo.external and repo.archive_in_pr):
        return None
    name = Path(c.path).name if c.path else c.id
    return f".agents/changes/5-archives/{c.archive_stamp or stamp()}-{name}/"


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


def plugin_role_descriptions(host: str) -> dict[str, str]:
    """Each role of the plugin's agents for this host mapped to its agent file's `description`
    (frontmatter), cut before its `Prompt starts with:` sentence. A file with no frontmatter, no
    description or one that does not parse gives no entry."""
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError

    found: dict[str, str] = {}
    for role, path in zip(plugin_roles(host), _agent_files(host)[1], strict=True):
        m = FRONTMATTER.match(path.read_text(encoding="utf-8"))
        if not m:
            continue
        try:
            data = YAML(typ="safe", pure=True).load(m[0][4:-4])
        except YAMLError:
            continue
        value = data.get("description") if isinstance(data, dict) else None
        text = value.split("Prompt starts with:")[0].strip() if isinstance(value, str) else ""
        if text:
            found[role] = text
    return found


CHIEF_SUBAGENT_LINE = re.compile(
    r"Prompt starts with: `(chantier ([a-z-]+) for the Chief of Staff, in the project <root>\.)`"
)


FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)


def _generic(entry: Any) -> bool:
    return isinstance(entry, dict) and entry.get("mode") == "generic"


def contract_lines(
    role: str,
    text: str,
    resolved: dict[str, Any] | None,
    escalated: dict[str, Any] | None = None,
) -> list[str]:
    """For a role the configuration starts as a generic agent (its model changed on a host that
    cannot start a named agent with one), or whose escalation model is applied as a generic agent
    (its escalation `mode` is `generic`, in the playbook `resolved` or in the escalation map
    `escalated`, which holds the shipped defaults' entries too), the plugin agent's file body, so
    the generic agent gets the whole contract in its prompt, rebuilt here and written nowhere: a
    heading, then the body after the frontmatter, each line indented by two spaces; printed once
    per role."""
    rec = (resolved or {}).get("roles", {}).get(role) or {}
    generic_escalation = _generic(rec.get("escalation")) or _generic((escalated or {}).get(role))
    if rec.get("start") != "generic" and not generic_escalation:
        return []
    body = FRONTMATTER.sub("", text, count=1).strip("\n")
    return [
        f"{role} contract (a generic agent: copy it unchanged, without the two leading spaces, "
        "after the opening lines):",
        *(f"  {line}" for line in body.splitlines()),
    ]


def chief_prompt_lines(
    host: str,
    root: str,
    started_by: str | None = None,
    resolved: dict[str, Any] | None = None,
    escalated: dict[str, Any] | None = None,
) -> list[str]:
    """The first line of each agent the Chief of Staff starts with a `<root>` and no batch, read
    from the agent files' descriptions (`<role> prompt, first line: …`), `<root>` filled in;
    with `started_by`, only the agents whose description says that parent starts them. A role the
    playbook `resolved` starts generic, or that escalates as a generic agent (`resolved` or the
    escalation map `escalated`), gets its contract lines after its first line."""
    lines = []
    for p in _agent_files(host)[1]:
        text = p.read_text(encoding="utf-8")
        m = CHIEF_SUBAGENT_LINE.search(text)
        if m and (started_by is None or f"Started by the {started_by}" in text):
            lines.append(f"{m[2]} prompt, first line: {m[1].replace('<root>', root)}")
            lines += contract_lines(m[2], text, resolved, escalated)
    return lines


WORKER_FIRST_LINE = re.compile(
    r"Prompt starts with: `(chantier ([a-z-]+) for <cr> \"<title>\" of batch <batch>, "
    r"in the project <root>\.)`"
)
WORKER_CARD_LINE = re.compile(r"^Your card is `([^`]+)`", re.M)


def worker_prompt_lines(root: str, cr: tuple[str, str], batch: str, record: Any) -> list[str]:
    """The opening three lines of each worker's prompt (a Driver starts it; `cr` is its id and
    title), read from the agent files of the batch `record`'s host: the description says
    `Started by a Driver.`, its first line holds `<cr> "<title>" of batch <batch>` and its body
    names its card. A role the record's playbook starts generic, or that escalates as a generic
    agent (its playbook or its escalation map, the shipped defaults' included), gets its contract
    lines after them. The CLI knows no role."""
    lines: list[str] = []
    refs = f"{skill_dir().as_posix()}/references"
    resolved, escalated = record.playbook, recorded_escalation(record)
    for p in _agent_files(record.host)[1]:
        text = p.read_text(encoding="utf-8")
        first, card = WORKER_FIRST_LINE.search(text), WORKER_CARD_LINE.search(text)
        if "Started by a Driver." not in text or not first or not card:
            continue
        filled = first[1]
        for key, value in (
            ("<cr>", cr[0]),
            ("<title>", cr[1]),
            ("<batch>", batch),
            ("<root>", root),
        ):
            filled = filled.replace(key, value)
        lines += [
            f"{first[2]} prompt, opening lines (copy them unchanged, without the two leading "
            "spaces, at the top of the prompt):",
            f"  {filled}",
            f"  Read {refs}/{card[1]};",
            "  the project's rules rank above it: run `$CHANTIER rules` first and read what "
            "touches your work.",
            *contract_lines(first[2], text, resolved, escalated),
        ]
    return lines


def read_playbook(repo: Repo, host: str) -> tuple[dict[str, Any] | None, list[str]]:
    """The configuration in layers (the plugin's shipped defaults, then the user's `chantier.yaml`
    files), resolved for this host: `(None, [])` when no user file is present, else the playbook,
    or the problems found."""
    root = plugin_root()
    defaults = root / "config" / "chantier.defaults.yml" if root else None
    return layers.load(repo, host, {h: plugin_roles(h) for h in HOSTS}, defaults)


def read_timing(repo: Repo, host: str) -> tuple[dict[str, Any] | None, list[str]]:
    """The timing of this host, resolved from the shipped defaults and the user's files (the
    defaults alone with no user file), or the problems found. None with no plugin."""
    root = plugin_root()
    defaults = root / "config" / "chantier.defaults.yml" if root else None
    found, problems = timing.load_timing(repo, {h: plugin_roles(h) for h in HOSTS}, defaults)
    return (found or {}).get(host), problems


def recorded_timing(record: Any) -> dict[str, Any] | None:
    """The timing a batch opened with; a record with none runs the plugin's shipped defaults."""
    if record.timing:
        held: dict[str, Any] = record.timing
        return held
    root = plugin_root()
    defaults = root / "config" / "chantier.defaults.yml" if root else None
    tree, _ = layers.read_defaults(defaults, {h: plugin_roles(h) for h in HOSTS})
    return timing.timing_from([], tree).get(record.host) if tree else None


def read_escalation(repo: Repo, host: str) -> tuple[dict[str, Any], list[str]]:
    """The escalation of each role on this host, from the shipped defaults and the user's files
    (the defaults alone with no user file), or the problems found."""
    root = plugin_root()
    defaults = root / "config" / "chantier.defaults.yml" if root else None
    roles_by_host = {h: plugin_roles(h) for h in HOSTS}
    defaults_tree, problems = layers.read_defaults(defaults, roles_by_host)
    found, more = layers.read_user(repo, roles_by_host)
    problems += more
    if problems:
        return {}, problems
    judged = layers.judge(found, host, roles_by_host, defaults_tree) if found else None
    if judged and judged.problems:
        return {}, judged.problems
    return escalation.escalation_map(defaults_tree, judged, host), []


def recorded_escalation(record: Any) -> dict[str, Any]:
    """The escalation a batch opened with; a record with none runs the shipped defaults'."""
    if record.escalation is not None:
        held: dict[str, Any] = record.escalation
        return held
    root = plugin_root()
    defaults = root / "config" / "chantier.defaults.yml" if root else None
    tree, _ = layers.read_defaults(defaults, {h: plugin_roles(h) for h in HOSTS})
    return escalation.escalation_map(tree, None, record.host)


user_files = layers.user_files


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
