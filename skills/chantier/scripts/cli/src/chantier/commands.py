"""The `chantier` commands. Each returns the lines to print; errors raise ChantierError with an exit code.

The CLI is the frame the agents work in: the CR lifecycle in `.agents/changes/` (the stages,
the batch folders, the record and the STATUS files), the batch's limits (slots, budget, rounds,
the user's word on an irreversible action), the means to synchronise (orders, asks, notes, the
long gate's lock) and a few tools (the project's rules, the cost). The agents do the work, git
and the forge included; the CLI names what they create (branches, worktrees), keeps the record,
and runs no git command that changes anything: it reads the head, the remote and the status to
say what is off, and no forge command at all. One named exception, in `board.py`: `chantier
board`, a read-only web view of this record for the user in remote; it writes no file, uses the
standard library only and knows no role.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

from . import __version__, costs, procs
from . import playbook as pb
from .lifecycle import (PRIORITIES, STATE_FOLDERS, archive_name, changes_lock, convert_old_tree,
                        cr_directory, done_cr, ensure_unclaimed, move_backlog_item, prepared_cr,
                        stage_layout, start_cr, trash_cr)
from .rails import (ENDED, MAX_GRANTED_FIXES, all_merged, merge_done, check_budget, check_grant,
                    check_granted_fix, check_idle, check_no_open_batch, check_round, check_slot, check_take,
                    alone, fix_go, held, is_release, live, parse_grant, record_ask, release_go,
                    release_merged, series_predecessor, spent_text, waits_all, waits_for)
from .rails import not_priced, usd_text
from .state import (EXIT_BUDGET, EXIT_CONFLICT, EXIT_EXTERNAL, EXIT_PRECONDITION, EXIT_USAGE, LIVE,
                    Batch, ChantierError, Repo, SurfaceChoice, chief_sessions, read_batch_json, read_text, _retry, _try_lock, _unlock,
                    write_json, age_minutes, check_epoch, default_branch, find_cr_batch, git, move_directory,
                    next_cr_number, normalize_batch, normalize_cr, now, read_batch, read_events, resolve_batch,
                    round_limit, stamp, RESTORED_NUMBER_FILE)
from .status import shape_word, steering_word, write_dashboard, write_final_pages

HOSTS = ("claude", "copilot")
AGENT_VERSION = re.compile(r"^# chantier-agent: (\S+)$", re.M)
INSTRUCTIONS = ("AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md")
CR_IN_NAME = re.compile(r"\bCR-\d+\b")
MD_LINK = re.compile(r"\]\(([^)\s#]+\.md)(?:#[^)]*)?\)|^\[[^\]]+\]:\s*(\S+\.md)\s*$", re.M)
LONG_GATE_WAIT_S = 3600


def skill_dir() -> Path:
    """The skill folder: `CHANTIER_SKILL_DIR`, else the nearest parent of this file with SKILL.md."""
    env = os.environ.get("CHANTIER_SKILL_DIR")
    if env:
        return Path(env).resolve()
    for p in Path(__file__).resolve().parents:
        if (p / "SKILL.md").exists():
            return p
    raise ChantierError("cannot find the chantier skill folder; set CHANTIER_SKILL_DIR", EXIT_PRECONDITION)


def plugin_root() -> Path | None:
    """The plugin this skill ships in, or None for a skill installed on its own.

    `CHANTIER_PLUGIN_ROOT` wins (empty: no plugin); else the folder two levels above the skill,
    when it holds a plugin manifest.
    """
    env = os.environ.get("CHANTIER_PLUGIN_ROOT")
    if env is not None:
        return Path(env).resolve() if env else None
    root = skill_dir().parents[1]
    return root if (root / ".claude-plugin" / "plugin.json").exists() \
        or (root / ".github" / "plugin" / "plugin.json").exists() else None


def cli_command(repo: Repo | None = None) -> str:
    """How every agent runs this CLI: the exact command, with the absolute path."""
    option = f' --project "{repo.project_dir.as_posix()}"' if repo and repo.external else ""
    return f'uv run --script "{(skill_dir() / "scripts" / "cli" / "chantier.py").as_posix()}"{option}'


def detect_host(explicit: str | None = None) -> str:
    """The host: `CHANTIER_HOST`, then the host's own environment."""
    host = explicit or os.environ.get("CHANTIER_HOST")
    if host:
        if host not in HOSTS:
            raise ChantierError(f"unknown host `{host}`: one of {', '.join(HOSTS)}", EXIT_USAGE)
        return host
    if os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
        return "claude"
    if (os.environ.get("COPILOT_CLI") or os.environ.get("COPILOT_AGENT_SESSION_ID")
            or os.environ.get("AI_AGENT", "").startswith("github_copilot")):
        return "copilot"
    raise ChantierError("cannot tell the host (Claude or Copilot): set CHANTIER_HOST", EXIT_USAGE)


def _shown(repo: Repo, path: Path) -> str:
    try:
        return path.relative_to(repo.session_root).as_posix()
    except ValueError:
        return path.as_posix()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "cr"


def project_instructions(repo: Repo) -> Path | None:
    return next((repo.root / name for name in INSTRUCTIONS if (repo.root / name).is_file()), None)


def surface_instructions(repo: Repo) -> Path | None:
    """The surface's own rules (its sync, among others); none in-project."""
    if not repo.external:
        return None
    return next((repo.surface / n for n in INSTRUCTIONS if (repo.surface / n).is_file()), None)


def archive_path(repo: Repo, c: dict) -> str | None:
    """Where the CR's cleaned archive goes in its PR, in the project's repository; None when the
    mode is in-project or the project's setting says no."""
    if not (repo.external and repo.archive_in_pr):
        return None
    name = Path(c["path"]).name if c.get("path") else c["id"]
    return f".agents/changes/5-archives/{c.get('archive_stamp') or stamp()}-{name}/"


def _skill_version() -> str | None:
    m = re.search(r"^chantier-version: (\S+)$",
                  (skill_dir() / "SKILL.md").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else None


# ---- preflight --------------------------------------------------------------------------------

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
    return [p.name.removesuffix(".md").removesuffix(".agent").removeprefix("chantier-")
            if host == "copilot" else p.name.removesuffix(".md") for p in _agent_files(host)[1]]


def read_playbook(repo: Repo, host: str) -> tuple[dict | None, list[str]]:
    """The project's `chantier.yaml`, resolved for this host: `(None, [])` when absent, else the
    playbook, or the problems found."""
    return pb.load(repo.root / pb.FILE, host, plugin_roles(host))


def _agent_problems(host: str) -> list[str]:
    """The plugin's agents for this host, all at this version; the CLI knows no role, only that
    the files the plugin installs match it."""
    folder, files = _agent_files(host)
    if folder is None:
        return ["the chantier plugin is not installed (a skill alone has no agents): install the "
                "plugin and restart the session"]
    if not files:
        return [f"no plugin agent in {folder}"]
    return [f"plugin agent {p.name} is not version {__version__}" for p in files
            if (m := AGENT_VERSION.search(p.read_text(encoding="utf-8"))) is None
            or m[1] != __version__]


# The commands the cards make the agents write, filled with realistic values, each tied to the
# recommended allow rule that covers it and to a group. P10 asks whether some allow rule of the
# user's settings lets each one through (as Claude Code matches rules), whatever the rule's form.
_SHA = "0123456789abcdef0123456789abcdef01234567"
_BRANCH = "chantier/batch-01/cr-101-example"
_TREE = "/work/project.worktrees/batch-01-CR-101"
# (group, command, recommended rule); ` origin ` stands for the project's remote name. The order
# is the order of the table in hosts/claude-code.md; SendMessage, a bare tool, comes last.
_SAMPLES = (
    ("always", f"git push -u origin {_BRANCH}", "git push -u origin chantier/*"),
    ("always", f"git -C {_TREE} push -u origin {_BRANCH}", "git -C * push -u origin chantier/*"),
    ("always", f"git push --force-with-lease -u origin {_BRANCH}",
     "git push --force-with-lease -u origin chantier/*"),
    ("always", f"git -C {_TREE} push --force-with-lease -u origin {_BRANCH}",
     "git -C * push --force-with-lease -u origin chantier/*"),
    ("always", f"git push --force-with-lease={_BRANCH}:{_SHA} origin {_SHA}:refs/heads/{_BRANCH}",
     "git push --force-with-lease=chantier/* origin *chantier/*"),
    ("always", "uv run --script /plugin/skills/chantier/scripts/cli/chantier.py status",
     "uv run --script *chantier.py *"),
    ("github", "gh pr create --draft --body-file /tmp/body.md", "gh pr create*"),
    ("github", "gh pr edit 12 --body-file /tmp/body.md", "gh pr edit*"),
    ("github", "gh pr edit 12 --base chantier/batch-01/cr-100-base", "gh pr edit*"),
    ("github", "gh pr ready 12", "gh pr ready*"),
    ("github", "gh pr ready 12 --undo", "gh pr ready*"),
    ("github", "gh pr checks 12", "gh pr checks*"),
    ("github", "gh pr view 12", "gh pr view*"),
    ("gh-stack", "gh stack view", "gh stack*"),
    ("gh-release", "gh release create v1.2.3 --title v1.2.3 --verify-tag --notes-file /tmp/n.md",
     "gh release create*"),
    ("gitlab", "glab mr create --draft --description-file /tmp/body.md", "glab mr create*"),
    ("gitlab", "glab mr update 12 --target-branch main", "glab mr update*"),
    ("gitlab", "glab mr view 12", "glab mr view*"),
    ("gitlab", "glab ci status", "glab ci status*"),
    ("glab-release", "glab release create v1.2.3 --notes-file /tmp/n.md", "glab release create*"),
)

# The allow rules hosts/claude-code.md recommends, in its table's order (a test compares them).
RECOMMENDED_ALLOW = tuple(f"{tool}({rule})" for rule in dict.fromkeys(s[2] for s in _SAMPLES)
                          for tool in ("Bash", "PowerShell")) + ("SendMessage",)

_SETTINGS_SHOWN = "~/.claude/settings.json, .claude/settings.json, .claude/settings.local.json"

# Rules auto mode drops on entry (hosts/claude-code.md, "What not to add"): they do not count.
_DROPPED = re.compile(
    r"\*?|(python3?|node|ruby|perl|bash|sh|zsh|pwsh|powershell|cmd|php|deno|bun|env|sudo|xargs"
    r"|npx|bunx)( ?\*)?|(uv|npm|pnpm|yarn|pip|pipx|poetry|bun)( run)?( ?\*)?", re.I)
_RULE = re.compile(r"([^()]+?)\s*(?:\((.*)\))?", re.S)


def _glob(pattern: str, text: str, fold: bool) -> bool:
    regex = ".*".join(re.escape(part) for part in pattern.split("*"))
    return re.fullmatch(regex, text, re.S | (re.I if fold else 0)) is not None


def rule_matches(rule: str, tool: str, command: str = "") -> bool:
    """Whether a permission rule `Tool(pattern)` (or a bare tool name) covers this tool use, as
    Claude Code documents: `*` matches any text, `cmd *` also matches the bare `cmd`, the legacy
    `:*` suffix reads as ` *`, PowerShell matches without case, a bare tool name matches all."""
    m = _RULE.fullmatch(rule.strip())
    if not m or m[1] != tool:
        return False
    if m[2] is None:
        return True
    pattern = m[2].strip()
    if pattern.endswith(":*"):
        pattern = pattern[:-2] + " *"
    fold = tool == "PowerShell"
    if pattern.endswith(" *") and _glob(pattern[:-2], command, fold):
        return True
    return _glob(pattern, command, fold)


def _counts_as_allow(rule: str) -> bool:
    """False for an allow rule auto mode drops on entry: it protects nothing unattended."""
    m = _RULE.fullmatch(rule.strip())
    if not m:
        return False
    if m[1] in ("Bash", "PowerShell"):
        return m[2] is not None and not _DROPPED.fullmatch(m[2].strip())
    return not m[1].startswith(("Agent", "Monitor"))


def _settings_rules(repo: Repo | None) -> tuple[dict[str, list[str]], list[str]]:
    """The `permissions` allow, deny and ask strings of the user's three settings files, and the
    files that could not be read. A file that is absent holds nothing."""
    files = [Path.home() / ".claude" / "settings.json"]
    if repo:
        files += [repo.session_root / ".claude" / "settings.json",
                  repo.session_root / ".claude" / "settings.local.json"]
    rules: dict[str, list[str]] = {"allow": [], "deny": [], "ask": []}
    unreadable: list[str] = []
    for path in files:
        if not path.is_file():
            continue
        try:
            permissions = json.loads(read_text(path)).get("permissions", {})
            for kind in rules:
                rules[kind] += [r for r in permissions.get(kind, []) if isinstance(r, str)]
        except (OSError, ValueError, AttributeError):
            unreadable.append(str(path))
    return rules, unreadable


def _sample_groups(repo: Repo | None, remote: str) -> set[str]:
    """The sample groups that apply: the remote's forge, the `gh stack` extension when installed,
    the publication when the project's rules name it."""
    url = git("remote", "get-url", remote, check=False).lower()
    host = re.sub(r"^.*?(?:://|@)", "", url).split("/")[0].split(":")[0]
    groups = {"always"}
    if "gitlab" in host:
        groups.add("gitlab")
    elif "github" in host:
        groups.add("github")
    else:
        groups |= {"github", "gitlab"}
    text = ""
    if repo:
        seen: list[Path] = []
        for first, root in ((project_instructions(repo), repo.root),
                            (surface_instructions(repo), repo.surface)):
            if first:
                seen.append(first.resolve())
                _linked(first.resolve(), root.resolve(), seen, 2)
        text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in seen)
    if "github" in groups and "gh release create" in text:
        groups.add("gh-release")
    if "gitlab" in groups and "glab release create" in text:
        groups.add("glab-release")
    data = [os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")]
    if os.environ.get("LOCALAPPDATA"):
        data.append(os.environ["LOCALAPPDATA"])
    if "github" in groups and any((Path(d) / sub / "extensions" / "gh-stack").exists()
                                  for d in data for sub in ("gh", "GitHub CLI")):
        groups.add("gh-stack")
    return groups


def commands_not_allowed(repo: Repo | None) -> tuple[int, int, list[str], list[str], list[str]]:
    """The applicable sample commands that the settings do not let through: how many of how many;
    what to add; what a deny or ask rule catches; the unreadable files."""
    remote = "origin"
    if repo:
        with contextlib.suppress(Exception):
            remote = repo.config.get("remote") or remote
    remotes = git("remote", check=False).split()
    if remote not in remotes and remotes:
        remote = "origin" if "origin" in remotes else remotes[0]
    rules, unreadable = _settings_rules(repo)
    allow = [r for r in rules["allow"] if _counts_as_allow(r)]
    tools = ("Bash", "PowerShell") if os.name == "nt" else ("Bash",)
    groups = _sample_groups(repo, remote)
    wanted = [s for s in _SAMPLES if s[0] in groups]
    adds: dict[str, list[str]] = {}
    blocked: list[str] = []
    missing = 0
    for _, command, rule in wanted:
        command, rule = command.replace(" origin ", f" {remote} "), rule.replace(" origin ", f" {remote} ")
        short = command if len(command) < 60 else command[:57] + "..."
        lacking, held_back = [], False
        for tool in tools:
            hit = next(((kind, r) for kind in ("deny", "ask") for r in rules[kind]
                        if rule_matches(r, tool, command)), None)
            if hit:
                held_back = True
                note = f"{short} by {hit[1]}" + (" (asks)" if hit[0] == "ask" else "")
                if note not in blocked:
                    blocked.append(note)
            elif not any(rule_matches(r, tool, command) for r in allow):
                lacking.append(f"{tool}({rule})")
        if lacking:
            adds.setdefault(", ".join(lacking), []).append(short)
        missing += bool(lacking) or held_back
    if not any(rule_matches(r, "SendMessage") for r in rules["allow"]):
        adds["SendMessage"] = ["SendMessage"]
        missing += 1
    named = [f"{' / '.join(samples)} (add {add})" for add, samples in adds.items()]
    return missing, len(wanted) + 1, named, blocked, unreadable


def preflight(args) -> tuple[list[str], int]:
    lines, ok = [], True

    def check(tag: str, passed: bool, good: str, bad: str, warn: bool = False):
        nonlocal ok
        if not warn:
            ok &= passed
        state = "ok  " if passed else "warn" if warn else "FAIL"
        lines.append(f"{tag} {state} {good if passed else bad}")

    try:
        host = detect_host()
    except ChantierError:
        host = None
    entry = os.environ.get("CLAUDE_CODE_ENTRYPOINT", "")
    if host == "copilot":
        check("P1", bool(os.environ.get("COPILOT_AGENT_SESSION_ID")),
              "host is a Copilot agent session",
              "host is Copilot but COPILOT_AGENT_SESSION_ID is empty: not a Copilot agent session")
    elif getattr(args, "direct", False):  # the Chief of Staff steers: no session to start
        check("P1", bool(entry), f"host is Claude Code ({entry})",
              "host is unknown (CLAUDE_CODE_ENTRYPOINT is empty), not a Claude Code or a "
              "Copilot agent session")
    else:
        check("P1", entry == "claude-desktop", "host is Claude Desktop",
              f"host is {entry or 'unknown'} (CLAUDE_CODE_ENTRYPOINT), not claude-desktop "
              "or a Copilot agent session")
    try:
        repo = Repo.find(Path(os.getcwd()))
    except SurfaceChoice as e:  # a surface: the projects are listed, a command names one
        repo = None
        lines.append(f"P6 ok   a planning surface with projects {', '.join(e.names)}: "
                     "pass --project <name>")
    except ChantierError as e:
        repo = None
        check("P6", False, "", str(e))
    if host:
        problems = _agent_problems(host)
        check("P4", not problems, f"the plugin's agents are at {__version__} on {host}",
              "; ".join(problems))
    else:
        check("P4", False, "", "unknown host: no agents to check")
    missing = [t for t in ("uv", "git") if shutil.which(t) is None]
    sv = _skill_version()
    check("P5", not missing and sv == __version__, f"chantier {__version__}, uv and git found",
          f"{', '.join(missing) + ' missing' if missing else 'uv and git found'}; "
          f"CLI {__version__}, SKILL.md {sv}")
    if repo:
        top = Path(git("rev-parse", "--show-toplevel", check=False) or ".").resolve()
        where = repo.session_root
        check("P6", top == where.resolve(), f"in the main checkout of {where.name}",
              f"session folder {top} is not the repository root {where}")
        gitdir = Path(git("rev-parse", "--path-format=absolute", "--git-dir", check=False)
                      or ".").resolve()
        check("P7", gitdir == repo.git_dir, "not a linked worktree",
              "this session runs in a linked worktree: the Foreman must start in the main checkout")
        found = project_instructions(repo)
        if repo.external and not repo.clone_dir.is_dir():
            text = (repo.project_dir / "project.md")
            remote = re.search(r"^\W*remote\W*:?\s*(\S+)", read_text(text),
                               re.I | re.M) if text.is_file() else None
            check("P8", False, "", f"no clone of the project at {repo.clone_dir.as_posix()} "
                  f"(remote {remote[1] if remote else 'see project.md'}): clone it there")
        else:
            check("P8", found is not None, f"project instructions: {found.name if found else ''}",
                  f"no {', '.join(INSTRUCTIONS)}: ask the user how the project builds and tests")
        if host:
            made, problems = read_playbook(repo, host)
            check("P12", not problems,
                  f"{pb.FILE} valid: {len(made['roles'])} roles configured" if made
                  else f"no {pb.FILE}: the plugin's agents and models",
                  f"{problems[0] if problems else ''}"
                  f"{f' (and {len(problems) - 1} more)' if len(problems) > 1 else ''}: "
                  "run `$CHANTIER playbook`")
        if repo.external:
            here = git("branch", "--show-current", check=False)
            main = default_branch(repo.surface)
            check("P11", not main or here == main, f"the surface is on its default branch ({here})",
                  f"the surface is on {here or 'no branch'}, its default branch is {main}: it is "
                  "always worked on its default branch", warn=True)
    if host == "claude":
        count, total, named, blocked, unreadable = commands_not_allowed(repo)
        note = f" (unreadable: {', '.join(unreadable)})" if unreadable else ""
        check("P10", not count, f"the commands chantier's agents run are allowed by your settings{note}",
              f"{count} of {total} commands chantier's agents run are not allowed by your settings "
              f"({_SETTINGS_SHOWN}){note}: {'; '.join(named)}"
              f"{'; denied: ' + '; '.join(blocked) if blocked else ''}; the block is in "
              'hosts/claude-code.md, "Allow rules"', warn=True)
    own = "P3, P9" if getattr(args, "direct", False) else "P2, P3, P9"
    lines.append(f"{own} and 'not unattended' are the Chief of Staff's own checks")
    lines.append("preflight passed" if ok else "preflight FAILED: start nothing")
    return lines, 0 if ok else EXIT_PRECONDITION


# ---- init -------------------------------------------------------------------------------------

def init(args) -> list[str]:
    """Create the eight stage folders, empty; leave the ones that exist; write nothing else."""
    try:
        repo = Repo.find(convert=False)
    except ChantierError as e:
        raise ChantierError(f"no git repository found ({e}): chantier needs one; "
                            "run `git init` first", EXIT_PRECONDITION) from e
    gitdir = Path(git("rev-parse", "--path-format=absolute", "--git-dir", check=False)
                  or ".").resolve()
    if gitdir != repo.git_dir:  # preflight's P7
        raise ChantierError("this is a linked worktree: init runs in the main checkout "
                            f"({repo.session_root})", EXIT_PRECONDITION)
    convert_old_tree(repo)  # an older tree first, so that its folders are not made twice
    repo.changes.mkdir(parents=True, exist_ok=True)
    repo.ensure_gitignore()
    lines = []
    for key, folder in stage_layout(repo).items():
        if key == "batches":  # the parent of the three state folders, made with them
            continue
        existed = folder.is_dir()
        folder.mkdir(parents=True, exist_ok=True)
        lines.append(f"{'exists ' if existed else 'created'} {_shown(repo, folder)}")
    return lines


# ---- CR folders -------------------------------------------------------------------------------

def _new_request(repo: Repo, slug: str, raw: bytes, hint: str = "file it again with --slug "
                 "<other>") -> Path:
    """A new inbox folder, the request kept as received. The caller holds `changes_lock`."""
    folder = stage_layout(repo)["inbox"] / slug
    folder.parent.mkdir(parents=True, exist_ok=True)
    try:
        folder.mkdir()
    except FileExistsError as e:
        raise ChantierError(f"CR folder already exists: {_shown(repo, folder)}; {hint}",
                            EXIT_PRECONDITION) from e
    try:
        (folder / "intake").mkdir()
        (folder / "intake" / "request.md").write_bytes(raw)
    except OSError as e:
        raise ChantierError(f"could not finish filing {folder}; preserve it for recovery: {e}",
                            EXIT_EXTERNAL) from e
    return folder


def file_cr(args) -> list[str]:
    repo = Repo.find()
    paths = stage_layout(repo)
    if args.item.startswith("@"):
        source = Path(args.item[1:]).expanduser()
        if not source.is_absolute():
            source = (Path.cwd() if repo.external else repo.root) / source
        try:
            raw = source.read_bytes()
            text = raw.decode("utf-8-sig")
        except (OSError, UnicodeError) as e:
            raise ChantierError(f"cannot read the request {source}: {e}", EXIT_USAGE) from e
    else:
        text = args.item
        raw = text.encode("utf-8")
    if not text.strip():
        raise ChantierError("the request is empty", EXIT_USAGE)
    title = next(line.lstrip("# ").strip() for line in text.splitlines() if line.strip())
    slug = args.slug or _slug(title)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,80}", slug):
        raise ChantierError("CR slug: lowercase letters, digits and hyphens", EXIT_USAGE)
    with changes_lock(repo):
        folder = _new_request(repo, slug, raw)
        write_dashboard(repo, paths)
    return [f"filed {_shown(repo, folder)}; write the intent and grill the CR here"]


def triage(args) -> list[str]:
    repo = Repo.find()
    with changes_lock(repo):
        target = move_backlog_item(repo, args.item, args.priority, stage_layout(repo),
                                   ready=args.ready)
        write_dashboard(repo, stage_layout(repo))
    return [f"triaged {_shown(repo, target)}" + (f" ({args.priority})" if args.priority else "")]


def abandon(args) -> list[str]:
    repo = Repo.find()
    paths = stage_layout(repo)
    source = repo.planning_path(args.item, "CR folder")
    in_backlog = source.parent.parent == paths["backlog"] and source.parent.name in PRIORITIES
    in_batch = source.parent in (paths["pending"], paths["actives"])
    if source.parent not in (paths["inbox"], paths["ready"]) and not in_batch and not in_backlog:
        raise ChantierError("only an inbox, backlog, 3-ready or unclaimed batch CR can be "
                            "abandoned", EXIT_USAGE)
    with changes_lock(repo):
        ensure_unclaimed(repo, source)
        target = paths["trash"] / f"{stamp()}-{source.name}"
        move_directory(source, target)
        write_dashboard(repo, paths)
    return [f"abandoned {_shown(repo, target)}"]


def restore(args) -> list[str]:
    """The reverse of `abandon`: a folder of `6-trash` comes back to `1-inbox`, whole, without its
    date (and without its number when an open batch's record says it was that batch's CR). Only on
    the user's word. A cancelled CR of an open batch stays cancelled there; its branch, worktree and
    PR are not touched."""
    repo = Repo.find()
    paths = stage_layout(repo)
    source = repo.planning_path(args.item, "CR folder")
    if source.parent != paths["trash"] or not source.is_dir():
        raise ChantierError("restore takes a folder directly under 6-trash: "
                            f"{_shown(repo, source)} is not one", EXIT_PRECONDITION)
    with changes_lock(repo):
        known, batch_crs = None, []  # the open batch's CR that owned this folder; all its CRs
        for batch_dir in repo.batch_folders():
            record = read_batch_json(batch_dir / "batch.json")
            for cr in record.get("crs", []):
                if not cr.get("path"):
                    continue
                if repo.planning_path(cr["path"], "recorded CR path") == source:
                    known = (record.get("id", "?"), cr)
                else:
                    batch_crs.append(cr_slug(Path(cr["path"]).name))
        name = re.sub(r"^(?:\d{6}-\d{4}-)+", "", source.name)
        if known:  # a number is stripped only from a folder a batch record says is its CR's
            name = re.sub(r"^(?:CR-)?\d+-", "", name, flags=re.I)
        name = args.slug or name
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,80}", name):
            raise ChantierError(f"restore: {name!r} is not a CR slug (lowercase letters, digits "
                                "and hyphens): restore again with --slug <name>", EXIT_USAGE)
        taken = [paths["inbox"] / name, paths["ready"] / name,
                 *(paths["backlog"] / p / name for p in PRIORITIES)]
        clash = next((_shown(repo, t) for t in taken if t.exists()), None) \
            or (f"a CR of the open batch ({name})" if name in batch_crs else None)
        if clash:
            raise ChantierError(f"restore: the name {name} is already used by {clash}; "
                                f"restore again with --slug <other>", EXIT_PRECONDITION)
        target = paths["inbox"] / name
        formerly = None
        if known:
            formerly = f"formerly {known[1]['id']} of {known[0]}"
            number = re.fullmatch(r"CR-(\d+)", known[1]["id"])
        move_directory(source, target)
        if known:
            number = re.fullmatch(r"CR-(\d+)", known[1]["id"])
            if number:  # the number is never given again, even once the batch is closed
                path = repo.changes / RESTORED_NUMBER_FILE
                try:
                    kept = int(json.loads(read_text(path))["last_number"])
                except (OSError, ValueError, KeyError, TypeError):
                    kept = 0
                path.write_text(json.dumps({"last_number": max(kept, int(number[1]))}) + "\n",
                                encoding="utf-8")
        if formerly:
            intent = target / "01-intent.md"
            with open(intent if intent.is_file() else target / "notes.md", "a",
                      encoding="utf-8") as f:
                f.write(f"\n{formerly}\n")
        write_dashboard(repo, paths)
    lines = [f"restored {_shown(repo, target)}"]
    if known and known[1].get("status") == "cancelled":
        cr = known[1]
        lines.append(f"{cr['id']} stays cancelled in {known[0]}: its branch {cr.get('branch')}, "
                     f"worktree {cr.get('worktree')} and PR {cr.get('pr') or 'none'} are not "
                     "touched; `order add` brings it back in a batch")
    return lines


def _batch_cr(repo: Repo, cr_id: str, batch: str | None) -> tuple[str, dict, dict]:
    cr_id = normalize_cr(cr_id)
    batch = find_cr_batch(repo, cr_id, batch)
    data = read_batch(repo, batch)
    c = next((x for x in data["crs"] if x["id"] == cr_id), None)
    if c is None:
        raise ChantierError(f"unknown CR {cr_id} in batch {batch}", EXIT_USAGE)
    return batch, data, c


def _work(repo: Repo, c: dict) -> Path:
    """The CR's work folder, inside its own folder: notes, gate logs, the PR body."""
    return cr_directory(repo, c) / "work"


def _worktree(c: dict) -> Path:
    """The CR's worktree, once its Driver has created it; the CLI never does."""
    if not Path(c["worktree"]).is_dir():
        raise ChantierError(f"{c['id']}: no worktree at {c['worktree']}; its Driver creates it "
                            f"(`git worktree add -b {c['branch']} {c['worktree']} <base>`)",
                            EXIT_PRECONDITION)
    return Path(c["worktree"])


def _cr_events(repo: Repo, batch: str, cr_id: str) -> list[dict]:
    return [e for e in read_events(repo.batch_dir(batch)) if e.get("cr") == cr_id]


def same_head(recorded: str | None, head: str | None) -> bool:
    """Heads are recorded as the full SHA. One recorded short before (an open batch from an older
    version) matches the full SHA it is a prefix of."""
    return bool(recorded and head) and (recorded == head or head.startswith(recorded)
                                        or recorded.startswith(head))


def _short(head: str | None) -> str:
    """A head for display only: 7 characters."""
    return (head or "")[:7]


def _dirty(wt: Path) -> str:
    """The worktree's tracked changes and untracked files, as `git status --porcelain` says."""
    return git("status", "--porcelain", "--untracked-files=normal", cwd=wt)


def gate_passed(events: list[dict], head: str | None) -> bool:
    """A long gate passed at a head: the last `gate` invocation at that head passed every command
    it was given. The events of one invocation share a `run`; it stops at its first failure, so
    its last event says. An event with no `run` (an older record) is an invocation by itself."""
    here = [e for e in events if e.get("kind") == "gate" and same_head(e.get("head"), head)]
    if not here:
        return False
    run = here[-1].get("run")
    if run is None:
        return here[-1].get("result") == "pass"
    return all(e.get("result") == "pass" for e in here if e.get("run") == run)


def last_verdict(events: list[dict], head: str | None) -> str | None:
    """The last verdict recorded at a head: it decides; a verdict at another head never counts."""
    seen = [e.get("result") for e in events
            if e.get("kind") == "verdict" and same_head(e.get("head"), head)]
    return seen[-1] if seen else None


# ---- batches ----------------------------------------------------------------------------------

def grant_line(release: dict) -> str:
    """What the user allowed the release to do without asking, in one line."""
    n, done = release.get("autonomous", 0), release.get("published", 0)
    return "; ".join([
        f"up to {n} releases without asking ({done} published)" if n
        else "every irreversible action waits for the user's approval",
        f"the Foreman starts and merges up to {MAX_GRANTED_FIXES} fixes" if release.get("fixes")
        else "the user starts and merges the fixes"])


def filed_fix(b: Batch, rel: dict, item: str) -> str:
    """A release's fix file is the fix's specification: it becomes a prepared CR in the inbox.
    Anything else is already a prepared CR."""
    repo = b.repo
    source = repo.planning_path(item, "fix")
    if not source.is_file() or cr_directory(repo, rel) not in source.parents:
        return item
    folder = _new_request(repo, f"{rel['id'].lower()}-{_slug(source.stem)}", source.read_bytes())
    shutil.copyfile(source, folder / "03-change-spec.md")
    return str(folder)


def add_cr(b: Batch, item: str, kind: str = "change") -> dict:
    """Move a prepared CR into `1-pending` and name its branch and worktree: the Driver creates
    them, on the fresh default branch, as its first step."""
    repo = b.repo
    paths = stage_layout(repo)
    prepared = prepared_cr(repo, item, paths)
    ensure_unclaimed(repo, prepared.directory)
    number = next_cr_number(repo, (paths["archives"], paths["trash"], paths["pending"],
                                   paths["actives"], paths["done"]))
    cr_id = f"CR-{number}"
    slug = re.sub(r"^(?:CR-)?\d+-", "", prepared.directory.name, flags=re.I)
    cdir = paths["pending"] / f"{number:03d}-{_slug(slug)}"
    origin = repo.rel(prepared.directory)
    b.move(prepared.directory, cdir)
    title = prepared.title
    branch = f"chantier/{b.id}/{cr_id.lower()}-{_slug(title)}"
    worktree = repo.worktrees / f"{b.id}-{cr_id}"
    order = max((c["order"] for c in b.data["crs"]), default=0) + 1
    c = {"id": cr_id, "title": title, "kind": kind, "status": "queued", "order": order,
         "path": repo.rel(cdir),
         "specification": prepared.specification.relative_to(prepared.directory).as_posix(),
         "round": 0, "agent": None, "pr": None,
         "branch": branch, "worktree": str(worktree), "notes": [], "updated": now()}
    b.data["crs"].append(c)
    b.log("add", cr_id, title=title, path=c["path"], origin=origin)
    return c


def cr_slug(folder_name: str) -> str:
    """A CR folder's name without its date and its number: how `depends.json` names it."""
    name = re.sub(r"^(?:\d{6}-\d{4}-)+", "", folder_name)
    return re.sub(r"^(?:CR-)?\d+-", "", name, flags=re.I)


def read_depends(folder: Path) -> list[str]:
    """The slugs of `depends.json`'s `after`; no file, no dependency."""
    path = folder / "depends.json"
    if not path.is_file():
        return []
    try:
        data = json.loads(read_text(path))
    except (OSError, ValueError) as e:
        raise ChantierError(f"{path}: not valid UTF-8 JSON ({e}); expected "
                            '{"after": ["<slug>", …]}') from e
    after = data.get("after", []) if isinstance(data, dict) else None
    if not isinstance(after, list) or not all(isinstance(s, str) and s.strip() for s in after):
        raise ChantierError(f'{path}: expected {{"after": ["<slug>", …]}}, slugs being folder '
                            "names without their number")
    return after


def archived_merged(repo: Repo, slug: str) -> bool:
    paths = stage_layout(repo)
    folders = [f for stage in (paths["archives"], paths["done"]) if stage.is_dir()
               for f in sorted(stage.iterdir())]
    for folder in folders:
        if folder.is_dir() and cr_slug(folder.name) == slug:
            try:
                state = json.loads(read_text(folder / "STATUS.json")).get("state")
            except (OSError, ValueError):
                state = "merged"  # an archive holds only merged CRs
            if state == "merged":
                return True
    return False


def declare_dependencies(b: Batch, added: list[dict]) -> None:
    """Record the `after` of each CR just added, as CR ids, once all of them are in the batch.
    A slug archived as merged is met and not recorded; the rest is refused, naming the slug."""
    for c in added:
        ids = []
        for slug in read_depends(cr_directory(b.repo, c)):
            key = _slug(slug)
            dep = next((x for x in b.data["crs"] if cr_slug(Path(x["path"]).name) == key), None)
            if dep is None:
                if archived_merged(b.repo, key):
                    continue
                raise ChantierError(f"{c['id']}: depends.json names {slug!r}, which is in "
                                    "neither the batch nor the archives as merged")
            if is_release(dep) and dep["id"] != c["id"]:
                raise ChantierError(f"{c['id']}: depends.json names {slug!r}, the batch's release "
                                    f"CR {dep['id']}, which waits for every other CR: a cycle. "
                                    "Remove it from depends.json")
            if dep["status"] == "merged":  # archived: met, so not recorded
                continue
            if dep["id"] not in ids:
                ids.append(dep["id"])
        if ids:
            c["after"] = ids
            b.log("depends", c["id"], after=ids)
    check_cycles(b)


def check_series_order(b: Batch) -> None:
    """A series runs in the order given: a CR cannot come before one it depends on."""
    place = {x["id"]: x["order"] for x in b.data["crs"]}
    for c in b.data["crs"]:
        if c.get("kind") in {"release", "fix"}:
            continue
        for dep in c.get("after", []):
            if place.get(dep, 0) > c["order"]:
                raise ChantierError(f"{c['id']} depends on {dep}: it cannot come before it in the "
                                    "series")


def _release_tag(b: Batch, c: dict) -> str:
    if alone(b.data["crs"], c):
        return " (release, alone in its batch: it starts when taken)"
    return (" (release: starts once every other CR is ready (stack, series) or merged "
            "(parallel); its PR is the user's to merge)")


def release_waits_for_all(b: Batch) -> None:
    """The release CR's `after` holds every other CR of the batch that has not ended, fix CRs
    excepted (`pending_fixes` rules those); the CLI keeps the list, and an entry that ends stays
    as history."""
    for rel in b.data["crs"]:
        if not is_release(rel) or rel["status"] in ENDED:
            continue
        after = rel.setdefault("after", [])
        after += [x["id"] for x in b.data["crs"] if x["id"] != rel["id"]
                  and x.get("kind") != "fix" and x["status"] not in ENDED and x["id"] not in after]
        if not after:
            rel.pop("after")
    check_cycles(b)


def check_cycles(b: Batch) -> None:
    graph = {x["id"]: x.get("after", []) for x in b.data["crs"]}
    done: set[str] = set()

    def visit(node: str, path: list[str]) -> None:
        if node in path:
            cycle = path[path.index(node):] + [node]
            raise ChantierError(f"dependency cycle: {' → '.join(cycle)}")
        if node in done:
            return
        for nxt in graph.get(node, []):
            visit(nxt, path + [node])
        done.add(node)

    for node in graph:
        visit(node, [])


def open_batch(args) -> list[str]:
    repo = Repo.find()
    host = detect_host()
    team, problems = read_playbook(repo, host)  # before any folder moves
    if problems:
        raise ChantierError("\n".join(problems), EXIT_PRECONDITION)
    if args.slots < 1 or (args.budget is not None and args.budget <= 0):
        raise ChantierError("slots and budget must be positive", EXIT_USAGE)
    if args.remote not in git("remote", cwd=repo.root).split():
        raise ChantierError(f"no remote {args.remote!r}: pass --remote <remote>", EXIT_EXTERNAL)
    branch = args.default_branch or default_branch(repo.root, args.remote)
    if not branch:
        raise ChantierError(f"Git does not know the default branch of {args.remote!r}: read "
                            "AGENTS.md or ask the user, then pass --default-branch")
    settings = {"default_branch": branch, "remote": args.remote,
                "max_rounds": repo.config["max_rounds"]}
    repo.config.update(settings)
    paths = stage_layout(repo)
    release = None
    if args.release is not None:
        if not 1 <= args.release <= len(args.items):
            raise ChantierError("--release: the item number of the release CR", EXIT_USAGE)
        release = {"autonomous": args.autonomous_releases, "fixes": args.grant_fixes,
                   "published": 0}
        check_grant(release, args.budget)
    elif args.autonomous_releases or args.grant_fixes:
        raise ChantierError("--autonomous-releases and --grant-fixes need --release", EXIT_USAGE)
    chief = _own_transcript(host)
    if args.direct and not chief:
        raise ChantierError("--direct needs the Chief of Staff's own session id "
                            "(CLAUDE_CODE_SESSION_ID or COPILOT_AGENT_SESSION_ID): none is known, "
                            "so a Foreman's claim could not be told from the Chief of Staff's",
                            EXIT_PRECONDITION)
    selected = [prepared_cr(repo, item, paths).directory for item in args.items]
    if len(set(selected)) != len(selected):
        raise ChantierError("the same CR was selected more than once", EXIT_USAGE)
    data = {"id": None, "version": __version__, "created": now(), "status": "running",
            "host": host, "mode": args.mode, "slots": args.slots,
            "budget_usd": args.budget, "spent_usd": None,
            "foreman": None, "foreman_epoch": 0, "foreman_transcript": None,
            "foreman_transcripts": [], "foreman_claims": [],
            "steering": "direct" if args.direct else "foreman",
            "chief_transcript": chief, "chief_transcripts": [chief] if chief else [],
            "stack_agent": None, "heartbeat": None, "heartbeat_stopped": None,
            "settings": settings, "orders": [], "asks": [], "crs": [], "release": release}
    if team:  # a running batch keeps the playbook it opened with
        # the prices are read live at each pricing, not frozen with the roles
        data["playbook"] = {k: v for k, v in team.items() if k != "prices"}
    with changes_lock(repo):
        check_no_open_batch(repo)
        with Batch(repo, None, actor="chief-of-staff", create=data) as b:
            brief = b.dir / "brief.md"
            for i, item in enumerate(args.items, 1):
                c = add_cr(b, item, kind="release" if i == args.release else "change")
                if release and c["kind"] == "release":
                    release["cr"] = c["id"]
            declare_dependencies(b, list(b.data["crs"]))
            release_waits_for_all(b)
            if args.mode == "series":
                check_series_order(b)
            brief.write_text(
                f"# {b.id}\n\n- Mode: {data['mode']}. Slots: {args.slots}. "
                f"Budget: {args.budget or 'none'}. Host: {host}. "
                f"Steering: {data['steering']}.\n"
                "- CRs, in order:\n" +
                "".join(f"  - {c['id']}: {c['title']} ({c['path']})"
                        f"{_release_tag(b, c) if c['kind'] == 'release' else ''}"
                        f"{' (after ' + ', '.join(c['after']) + ')' if c.get('after') and c['kind'] != 'release' else ''}\n"
                        for c in b.data["crs"]) +
                (f"- Release grant: {grant_line(release)}\n" if release else "") +
                f"- Project instructions: {', '.join(n for n in INSTRUCTIONS if (repo.root / n).is_file()) or 'none'}"
                + (f"; the surface's: {', '.join(n for n in INSTRUCTIONS if (repo.surface / n).is_file()) or 'none'}"
                   if repo.external else "") + ".\n"
                "- Team (who runs which role):\n"
                "- Autonomous decisions:\n- Questions to bring back:\n",
                encoding="utf-8")
            b.log("open", None, crs=[c["id"] for c in b.data["crs"]])
    lines = [f"opened {b.id} on {host}: {len(args.items)} CRs, {args.slots} slots, "
             f"{data['mode']}, steering {data['steering']}"]
    short = lambda p: str(p).replace("\\", "/").split("changes/")[-1]  # noqa: E731
    # the next step comes before the CR list: past ten lines it is the list that is cut
    lines.append(f"next: complete the brief {_shown(repo, brief)}, then "
                 + ("steer it yourself" if args.direct else "start the Foreman"))
    lines += [f"{c['id']} {c['title'][:40]}: {short(src)} -> {short(c['path'])}"
              for c, src in zip(b.data["crs"], selected)]
    return lines


# ---- the Foreman and orders -------------------------------------------------------------------

def foreman(args) -> list[str]:
    repo = Repo.find()
    batch = resolve_batch(repo, args.batch)
    if args.action == "get":
        d = read_batch(repo, batch)
        return [f"{d.get('foreman') or 'none'} epoch {d.get('foreman_epoch', 0)}"]
    with Batch(repo, batch, actor="foreman") as b:
        if args.action == "set":
            if not args.value or args.epoch is None:
                raise ChantierError("foreman set <session-id> --epoch <n>", EXIT_USAGE)
            current = b.data.get("foreman_epoch", 0)
            if args.epoch != current + 1:  # one session per epoch: the first to claim it runs it
                raise ChantierError(f"epoch {args.epoch} cannot be claimed: batch {b.id} is at "
                                    f"epoch {current}; stop now", EXIT_CONFLICT)
            b.data["foreman"] = args.value
            b.data["foreman_epoch"] = args.epoch
            b.data["foreman_transcript"] = None
            b.log("foreman", None, session=args.value, epoch=b.data["foreman_epoch"])
            return [f"foreman {args.value} epoch {b.data['foreman_epoch']}"]
        check_epoch(b, args.epoch)
        if not args.value:
            raise ChantierError("foreman transcript <session-uuid>", EXIT_USAGE)
        claimed = b.data.get("foreman_transcript")
        if claimed and claimed != args.value:
            # One epoch, one Foreman: a second session that starts as Foreman must not take over.
            raise ChantierError(f"epoch {b.data.get('foreman_epoch', 0)} of batch {b.id} is already run "
                                f"by transcript {claimed}; stop now", EXIT_CONFLICT)
        b.data["foreman_transcript"] = args.value
        seen = b.data.setdefault("foreman_transcripts", [])  # a relay keeps the earlier ones
        if args.value not in seen:
            seen.append(args.value)
            # each steering transcript is priced from its claim to the next one
            b.data.setdefault("foreman_claims", []).append(
                {"transcript": args.value, "since": now()})
        if (b.data.get("steering") == "direct" and b.data.get("chief_transcript")
                and args.value != b.data["chief_transcript"]):
            b.data["steering"] = "foreman"  # a Foreman took the batch over from the Chief of Staff
            b.log("steering", None, steering="foreman", transcript=args.value)
        b.log("foreman-transcript", None, transcript=args.value)
        return [f"transcript {args.value}"]


def _own_transcript(host: str) -> str | None:
    """This session's transcript id, from the host's environment; None when unknown."""
    return os.environ.get(
        "COPILOT_AGENT_SESSION_ID" if host == "copilot" else "CLAUDE_CODE_SESSION_ID") or None


def _read_seat(repo: Repo) -> dict | None:
    path = repo.changes / "seat.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(read_text(path))
    except ValueError as e:
        raise ChantierError(f"{path} is not valid JSON: {e}", EXIT_PRECONDITION) from e
    return data if data.get("session") else None


def seat(args) -> list[str]:
    """The repository's Chief of Staff session: it records a session and refuses a silent
    take-over; who may take it is the cards' to say."""
    repo = Repo.find()
    path = repo.changes / "seat.json"
    if args.action == "get":
        held = _read_seat(repo)
        if not held:
            return ["seat none"]
        return [f"seat {held['session']} env {held.get('env') or 'unknown'} "
                f"title \"{held.get('title') or ''}\" link {held.get('link') or 'unknown'}",
                f"transcript {held.get('transcript') or 'unknown'}"]
    if not args.session:
        raise ChantierError(f"seat {args.action} <session-id>", EXIT_USAGE)
    with changes_lock(repo):
        held = _read_seat(repo)
        if args.action == "leave":
            if not held:
                return ["seat none"]
            if held["session"] != args.session:
                raise ChantierError(f"the seat is held by {held['session']}", EXIT_PRECONDITION)
            path.unlink()
            return ["seat none"]
        if held and held["session"] != args.session and args.over != held["session"]:
            raise ChantierError(f"the seat is held by {held['session']} "
                                f"({held.get('link') or 'unknown'}): take it over only on the "
                                f"user's word, with --over {held['session']}", EXIT_PRECONDITION)
        transcript = _own_transcript(detect_host())
        write_json(path, {"session": args.session, "transcript": transcript, "env": args.env,
                          "title": args.title, "link": args.link})
        lines = [f"seat {args.session}"]
        # the batch's files exist until `close`: it is the (single) non-closed batch
        for batch_id in (repo.batch_ids() if transcript else []):
            with Batch(repo, batch_id, actor="chief-of-staff") as b:
                if transcript != b.data.get("chief_transcript"):
                    seen = chief_sessions(b.data)  # before the old one is replaced
                    if transcript not in seen:
                        seen.append(transcript)
                    b.data["chief_transcript"] = transcript
                    b.data["chief_transcripts"] = seen
                    b.log("chief", None, transcript=transcript)
                    lines.append(f"{b.id}: Chief of Staff transcript {transcript}")
    return lines


ORDER_KINDS = {"add", "after", "drop", "merged", "note", "rounds", "slots", "budget", "approve",
               "grant", "confirm", "qa", "done", "mode"}
CR_ORDERS = {"after", "drop", "merged", "rounds", "approve", "grant", "confirm"}


def _release_cr(b: Batch, kind: str, cr_id: str) -> dict:
    release = b.data.get("release") or {}
    if release.get("cr") != cr_id:
        raise ChantierError(f"order {kind} names the batch's release CR "
                            f"({release.get('cr') or 'none'})", EXIT_USAGE)
    return release


def _refused(usage: str, value: str, wanted: str) -> ChantierError:
    why = f"{value!r} is not {wanted}" if value.strip() else f"no value given: {wanted}"
    return ChantierError(f"{usage}: {why}", EXIT_USAGE)


_cr_arg = normalize_cr  # `order after`'s list is split here; every other argument is read by `main`


def _started(c: dict) -> bool:
    """A release has started when it ran an attempt or a Driver holds it or it is handed back; a
    merged release PR puts it back to `queued`, which `attempts` still tells."""
    return c.get("attempts", 0) > 0 or c["status"] != "queued"


def _add_release(b: Batch, note: str) -> list[str]:
    """`order add --release`: the batch's release CR, with the default grant, waiting for every
    other CR; the grant and the approvals are the user's word after (`order grant`, `approve`)."""
    open_ = next((x for x in b.data["crs"] if is_release(x) and x["status"] != "cancelled"), None)
    if open_:
        raise ChantierError(f"order add --release: {open_['id']} is already the release CR of "
                            f"{b.id}; a batch has one. Put the second release in the next batch, "
                            "once this one is closed")
    c = add_cr(b, note, kind="release")
    b.data["release"] = {"autonomous": 0, "fixes": False, "published": 0, "cr": c["id"]}
    declare_dependencies(b, [c])
    release_waits_for_all(b)
    waits = f", after {', '.join(c['after'])}" if c.get("after") else ""
    word = "" if alone(b.data["crs"], c) else (
        "; it starts once every other CR is ready (stack, series) or merged (parallel), and its "
        "PR is the user's to merge")
    return [f"added {c['id']} (release), queued{waits}; each irreversible action waits for the "
            f"merge of the release PR (`order grant` changes it){word}"]


def _join_release(b: Batch, added: dict) -> None:
    """A CR joined the batch: the release waits for it, and the user's word to run the procedure
    given before no longer holds, since what ships changed. A release that started takes no new
    CR."""
    rel = next((x for x in b.data["crs"] if is_release(x) and x["status"] not in ENDED), None)
    if rel is None:
        return
    release_waits_for_all(b)
    if rel.pop("procedure", None):
        rel.setdefault("notes", []).append(f"procedure word voided: {added['id']} was added")
        b.touch(rel)
        b.log("confirm-void", rel["id"], added=added["id"])


def _check_release_open(b: Batch) -> None:
    rel = next((x for x in b.data["crs"] if is_release(x) and x["status"] not in ENDED), None)
    if rel and _started(rel):
        raise ChantierError(f"order add: {rel['id']} has started ({rel['status']}, attempts "
                            f"{rel.get('attempts', 0)}) and ships the work under it. Add "
                            f"a fix with `order add --fix-for {rel['id']}`, or put the new work "
                            "in the next batch")


def _apply_order(b: Batch, kind: str, cr_id: str, note: str, fix_for: str | None,
                 own: bool = False, release: bool = False) -> list[str]:
    """The user's word, recorded at once: a folder moves, a number changes, a note is kept. Who
    takes a CR next, and when, is the Foreman's decision from `status`. `own` is the Foreman
    acting under the user's grant."""
    if kind == "after" and not any(x["id"] == cr_id for x in b.data["crs"]):
        raise ChantierError(f"order after: unknown CR {cr_id} in batch {b.id}")
    c = b.cr(cr_id) if kind in CR_ORDERS or (kind == "note" and cr_id != "-") else None
    if kind == "add":
        if fix_for:
            _release_cr(b, "add --fix-for", fix_for)
            rel = b.cr(fix_for)
            if own:
                check_granted_fix(b, rel)
            fix = add_cr(b, filed_fix(b, rel, note), kind="fix")
            fix["fix_for"] = fix_for
            rel.setdefault("notes", []).append(f"fix: {fix['id']} must merge first; then the "
                                               "procedure starts again from its first step")
            b.touch(rel)
            return [f"added {fix['id']} (fix for {fix_for}), queued"]
        if release:
            return _add_release(b, note)
        _check_release_open(b)
        added = add_cr(b, note)
        declare_dependencies(b, [added])
        _join_release(b, added)
        waits = f", after {', '.join(added['after'])}" if added.get("after") else ""
        return [f"added {added['id']}, queued{waits}"]
    if kind == "after":
        usage = 'order after <cr> --note "<CR ids, comma separated, or - for none>"'
        if not note.strip():
            raise ChantierError(usage, EXIT_USAGE)
        if is_release(c):
            raise ChantierError(f"order after: {cr_id} is the release CR: the CLI keeps what it "
                                "waits for (every other CR of the batch)")
        if c["status"] != "queued":
            raise ChantierError(f"cannot change what {cr_id} waits for: it is {c['status']}, "
                                "not queued")
        ids: list[str] = []
        for dep in ([] if note.strip() == "-" else [s.strip() for s in note.split(",")]):
            if not any(x["id"] == dep for x in b.data["crs"]):
                raise ChantierError(f"order after: unknown CR {dep!r} in batch {b.id}")
            if is_release(b.cr(dep)):
                raise ChantierError(f"order after: {dep} is the release CR, which waits for every "
                                    f"other CR: {cr_id} waiting for it is a cycle")
            if dep == cr_id:
                raise ChantierError(f"order after: {cr_id} cannot wait for itself")
            if b.cr(dep)["status"] != "merged" and dep not in ids:  # merged: met, not recorded
                ids.append(dep)
        previous = c.get("after", [])
        if ids:
            c["after"] = ids
        else:
            c.pop("after", None)
        try:
            check_cycles(b)
        except ChantierError:
            if previous:
                c["after"] = previous
            else:
                c.pop("after", None)
            raise
        b.touch(c)
        b.log("depends", cr_id, after=ids)
        return [f"{cr_id} now waits for {', '.join(ids)}" if ids else f"{cr_id} waits for nothing"]
    if kind == "drop":
        if c["status"] == "merged":
            raise ChantierError(f"cannot drop {cr_id}: it is already merged")
        if c["status"] in LIVE:
            return [f"{cr_id} is live: the Foreman stops its Driver, then `chantier cancel {cr_id}`"]
        if c["status"] == "cancelled":
            raise ChantierError(f"{cr_id} is already dropped: {c['path']}", EXIT_PRECONDITION)
        trash_cr(b, c)
        b.touch(c, status="cancelled")
        return [f"dropped {cr_id}: {c['path']}"]
    if kind == "note":
        if not note.strip():
            raise ChantierError("order note [<cr>] --note \"<the user's word, in one line>\"",
                                EXIT_USAGE)
        if c and c["status"] == "cancelled":
            raise ChantierError(f"cannot note {cr_id}: it is cancelled", EXIT_PRECONDITION)
        if c:
            c.setdefault("notes", []).append(note.strip())
            b.touch(c)
        out = [f"noted{' on ' + cr_id if c else ''}: the Foreman reads it in `status`"]
        if c and c["status"] in ("ready", "blocked"):
            out.append(f"{c['id']} is {c['status']}: no Driver works on it until the Foreman "
                       f"takes it back (take {c['id']} --note \"<why>\")")
        return out
    if kind == "merged":
        if c["status"] == "merged":
            return [f"{cr_id} already merged"]
        if c["status"] == "cancelled":
            raise ChantierError(f"cannot mark cancelled {cr_id} merged")
        if c.get("kind") == "release":
            open_ = [x["id"] for x in b.data["crs"] if x["id"] != cr_id
                     and x.get("kind") != "fix" and x["status"] not in ENDED]
            if open_:
                raise ChantierError(f"order merged: {', '.join(open_)} not merged or cancelled: "
                                    "the release PR merges last")
            release_merged(b, c)
            return [f"merged {cr_id}: the procedure goes on with a new Release driver"]
        return merge_done(b, c)
    if kind == "rounds":
        if not note.isdigit() or int(note) < 1:
            raise _refused("order rounds <cr> --note <n>", note,
                           "a whole number of rounds, 1 or more")
        b.touch(c, rounds=int(note))
        return [f"{cr_id}: up to {note} rounds"]
    if kind == "slots":
        if not note.isdigit():
            raise ChantierError("order slots --note <n> (0 holds: no new Driver starts)", EXIT_USAGE)
        b.data["slots"] = int(note)
        return [f"slots {note}"]
    if kind == "budget":
        if not re.fullmatch(r"\d+(\.\d+)?", note) or float(note) <= 0:
            raise _refused("order budget --note <usd>", note, "a positive amount in dollars")
        b.data["budget_usd"] = float(note)
        return [f"budget ${float(note):g}"]
    if kind == "approve":
        _release_cr(b, kind, cr_id)
        if not note.strip():
            raise ChantierError("order approve <release-cr> --note \"<the action the user approved>\"",
                                EXIT_USAGE)
        c.setdefault("approvals", []).append(note.strip())
        c.setdefault("notes", []).append(f"approved: {note.strip()}")
        b.touch(c)
        return [f"approved: {note.strip()}"]
    if kind == "grant":
        release = _release_cr(b, kind, cr_id)
        grant = parse_grant(note)
        if "budget_usd" in grant:
            b.data["budget_usd"] = grant.pop("budget_usd")
        release.update(grant)
        check_grant(release, b.data.get("budget_usd"))
        c.setdefault("notes", []).append(f"grant: {note.strip()}")
        b.touch(c)
        return [f"granted: {grant_line(release)}"]
    if kind == "confirm":
        _release_cr(b, kind, cr_id)
        if not note.strip():
            raise ChantierError("order confirm <release-cr> --note \"<the user's word to run the "
                                "release procedure>\"", EXIT_USAGE)
        if c["status"] in ENDED:
            raise ChantierError(f"order confirm: {cr_id} is {c['status']}")
        open_ = [x["id"] for x in b.data["crs"] if x["id"] != cr_id and x.get("kind") != "fix"
                 and x["status"] not in ENDED]
        if open_:
            raise ChantierError(f"order confirm: {', '.join(open_)} not merged yet: the word to "
                                "run the release procedure comes once they are merged")
        if c.get("pr"):
            raise ChantierError(f"order confirm: the release PR {c['pr']} is not merged: the "
                                "word comes once it is merged (`order merged`), or for a "
                                "procedure with no release PR")
        c["procedure"] = note.strip()
        c.setdefault("notes", []).append(f"procedure: {note.strip()}")
        b.touch(c)
        return [f"{cr_id}: the user's word to run the release procedure is recorded: "
                f"{note.strip()}"]
    if kind == "mode":
        if b.data["mode"] != "series" or note.strip() != "stack":
            raise ChantierError("order mode: only a series batch switches, to a stack "
                                "(`order mode --note stack`)")
        b.data["mode"] = "stack"
        b.log("mode", None, mode="stack")
        return [f"{b.id} is a stack now: a queued CR waits only for its `after`; the stack "
                "driver stacks the PRs"]
    if kind == "qa":
        return [f"QA folder: {cr_id}; the Foreman starts its QA driver, which holds a slot "
                "until `order done`"]
    raise ChantierError(f"order kind: one of {', '.join(sorted(ORDER_KINDS))}", EXIT_USAGE)


def order(args) -> list[str]:
    """The Chief of Staff's word, in the state at once; the Foreman sees it in `status` and
    marks it `order done` once its own part is done. `order merged --epoch <n>` is the Foreman
    recording a merge it made itself, `order add --fix-for --epoch <n>` a fix it starts under
    the grant: done at once."""
    if args.kind not in ORDER_KINDS:
        raise ChantierError(f"order kind: one of {', '.join(sorted(ORDER_KINDS))}", EXIT_USAGE)
    note = args.note or ""
    new_release = bool(getattr(args, "release", False))
    if args.kind == "add" and not note.strip():
        raise ChantierError("order add --note <prepared-CR-folder-or-specification> "
                            "[--fix-for <release-cr> | --release]", EXIT_USAGE)
    if new_release and (args.kind != "add" or args.fix_for):
        raise ChantierError("--release goes with `order add` alone: it adds the batch's release "
                            "CR; a fix of it is `order add --fix-for <release-cr>`", EXIT_USAGE)
    if args.kind == "qa" and not note.strip():
        raise ChantierError("order qa --note \"<what to test>\"", EXIT_USAGE)
    if args.kind in CR_ORDERS and (not args.cr or args.cr == "-"):
        raise ChantierError("order rounds <cr> --note <n>" if args.kind == "rounds"
                            else f"order {args.kind} <cr>", EXIT_USAGE)
    repo = Repo.find()
    if args.kind == "done":
        return _order_done(repo, args)
    if args.kind in CR_ORDERS or args.kind == "note":
        args.cr = _cr_arg(args.cr)
    args.fix_for = _cr_arg(args.fix_for)
    if args.kind == "after" and note.strip() != "-":
        note = ", ".join(_cr_arg(s.strip()) for s in note.split(","))
    own = args.epoch is not None
    if own and args.kind != "merged" and not (args.kind == "add" and args.fix_for):
        raise ChantierError("only `order merged` and `order add --fix-for` take --epoch: the "
                            "Foreman's own merge or fix", EXIT_USAGE)
    with changes_lock(repo):
        with Batch(repo, resolve_batch(repo, args.batch),
                   actor="foreman" if own else "chief-of-staff") as b:
            check_epoch(b, args.epoch)
            if (args.kind == "qa" and b.data.get("steering") == "direct"
                    and b.data["status"] != "paused"):
                raise ChantierError("a running direct batch takes no QA: order it once the batch "
                                    "is paused (`pause`)", EXIT_PRECONDITION)
            cr = args.cr
            reopened = []
            if args.kind == "add" and b.data["status"] == "paused":
                # the batch stays paused: the first `take` sets it running again
                reopened = [f"{b.id} stays paused: the first `take` sets it running again"]
            elif args.kind == "qa" and b.data["status"] == "paused":
                # a QA driver holds a slot from the order on: the batch runs again, its pause and
                # cost to date are void
                b.data["status"] = "running"
                b.data.pop("paused", None)
                b.data.pop("summary", None)
                b.log("reopen", None)
                reopened = [f"{b.id} was paused: running again; `pause` runs again at the end"]
            if args.kind == "qa":  # no CR: a work folder the QA driver fills, in the inbox
                check_budget(b)  # a QA driver is a Driver: refused before anything is created
                check_slot(b, "a QA driver")  # the open order holds the slot until `order done`
                cr = _shown(repo, _new_request(
                    repo, f"qa-{stamp()}", f"# QA\n\n{note}\n".encode(),
                    "a QA folder of this minute exists: try again in a minute"))
            effect = reopened + _apply_order(b, args.kind, cr, note, args.fix_for, own, new_release)
            oid = f"O-{len(b.data['orders']) + 1}"
            # The CLI did its whole part, the Foreman only has to end the order: not a note (the
            # Foreman relays it), not a QA (it starts a driver), not the drop of a live CR.
            applied = args.kind not in {"note", "qa"} and not (
                args.kind == "drop" and b.cr(cr)["status"] in LIVE)
            b.data["orders"].append({"id": oid, "kind": args.kind, "cr": cr or "-",
                                     "note": note, "sent": now(), "done": now() if own else None,
                                     **({} if own else {"applied": applied}),
                                     **({"fix_for": args.fix_for} if args.fix_for else {}),
                                     **({"release": True} if new_release else {})})
            b.log("order", None if cr in (None, "-") else cr, order=oid,
                  order_kind=args.kind, note=note)
    if own:
        return effect
    target = f" {cr}" if cr and cr != "-" else ""
    text = f" {note}" if note else ""
    return [f"[chief-of-staff→foreman] order {oid}: {args.kind}{target}{text}"] + effect


def _order_done(repo: Repo, args) -> list[str]:
    if not args.cr or not args.cr.startswith("O-"):
        raise ChantierError("order done <O-k>", EXIT_USAGE)
    with Batch(repo, resolve_batch(repo, args.batch), actor="foreman") as b:
        check_epoch(b, args.epoch)
        o = next((x for x in b.data["orders"] if x["id"] == args.cr), None)
        if o is None:
            raise ChantierError(f"unknown order {args.cr}", EXIT_USAGE)
        if o["done"]:
            return [f"{args.cr} already done"]
        o["done"] = now()
        b.log("order-done", None, order=args.cr)
    return [f"{args.cr} done"]


# ---- state for every role ---------------------------------------------------------------------

def _activity(repo: Repo, d: dict) -> list[str]:
    """One line per working CR (and the stack driver, and each open QA order with an agent id):
    the age of its last activity, the most recent of its last event in the log and the last write
    of the session records that are its own. The CLI states the age and never judges it.
    A host with no per-agent record (Copilot) gives the session's age, said so. A record that
    cannot be read is `not measured`. A long gate the lock names for the CR is `gate running`."""
    events = read_events(repo.batch_dir(d["id"]))
    last: dict[str, float] = {}  # key (a CR, `stack`, an order) -> minutes since its last event
    owner: dict[str, str] = {}  # agent id -> key, from the `agent` events
    for e in events:
        age = age_minutes(e.get("t"))
        if e.get("cr") and age is not None:
            last[e["cr"]] = min(age, last.get(e["cr"], age))
        if e.get("kind") == "agent" and e.get("cr") and e.get("agent"):
            owner[e["agent"]] = e["cr"]
    targets = [(c["id"], c["id"]) for c in d["crs"] if c["status"] in LIVE]
    if d.get("stack_agent"):
        targets.append(("stack", "stack"))
    targets += [(o["id"], f"{o['id']} qa") for o in d.get("orders", [])
                if o["kind"] == "qa" and not o["done"] and o.get("agent")]
    if not targets:
        return []
    try:
        sessions = _foreman_uuid(d)
    except ChantierError:
        sessions = []
    copilot = d.get("host") == "copilot"
    session_min: float | None = None
    records: dict[str, tuple[str | None, float | None]] = {}
    if copilot:
        ages = [a for _, a in costs.idle_seconds(repo.session_root, "copilot", sessions)
                if a is not None]
        session_min = min(ages) / 60 if ages else None
    else:
        records = costs.agent_records(repo.session_root, sessions)

    def key_of(agent: str | None, hops: int = 0) -> str | None:
        if agent is None or hops > 5:
            return None
        return owner.get(agent) or key_of(records.get(agent, (None, None))[0], hops + 1)

    holder = _lock_holder(repo).split()
    out = []
    for key, label in targets:
        word = f"activity {label}"
        if holder and holder[0] == key:
            out.append(f"{word} gate running")
            continue
        ages = [last[key]] if key in last else []
        if copilot:
            if session_min is None:
                out.append(f"{word} not measured")
                continue
            out.append(f"{word} {min(ages + [session_min]):.0f} min (session-level)")
            continue
        mine = [i for i in records if key_of(i) == key]
        if any(v == key for v in owner.values()) and not any(records[i][1] is not None
                                                             for i in mine):
            out.append(f"{word} not measured")  # a Driver is recorded, its record cannot be read
            continue
        ages += [records[i][1] / 60 for i in mine if records[i][1] is not None]
        out.append(f"{word} {min(ages):.0f} min" if ages else f"{word} not measured")
    return out


def _stop_heartbeat(repo: Repo, batch: str, epoch: int | None) -> list[str]:
    """The steering session records that it ended its loop: `status` says "heartbeat stopped"
    until the next wake (`status --refresh --epoch`) clears it."""
    with Batch(repo, batch, actor="foreman") as b:
        check_epoch(b, epoch)
        if epoch is None:
            raise ChantierError("--stop-heartbeat carries --epoch <n>: the steering session's own",
                                EXIT_USAGE)
        b.data["heartbeat_stopped"] = now()
        b.log("heartbeat_stopped", None)
    return [f"heartbeat stopped recorded for {batch}; the next `status --refresh --epoch "
            f"{epoch}` clears it"]


def _refresh(repo: Repo, batch: str, epoch: int | None) -> tuple[list[str], int, str | None]:
    """The facts the state cannot keep by itself: the activity of each working CR and the spend
    the budget reads. With `--epoch`, it is the Foreman's wake, and the batch records it. The
    last value is the heartbeat the wake overwrote (None: no wake, or the first one)."""
    prev = None
    with changes_lock(repo):
        with Batch(repo, batch, actor="foreman" if epoch is not None else "chief-of-staff") as b:
            check_epoch(b, epoch)
            if epoch is not None:
                prev = b.data.get("heartbeat")
                b.data["heartbeat"] = now()
                b.data["heartbeat_stopped"] = None
                b.log("heartbeat", None)
            data = dict(b.data)
    lines = _activity(repo, data)
    try:
        rows = _cost_rows(repo, data, data["host"], _foreman_uuid(data))
    except ChantierError as e:
        return lines + [f"spend not updated: {e}"], e.code, prev
    with Batch(repo, batch, actor="foreman" if epoch is not None else "chief-of-staff") as b:
        total = _record_costs(repo, b, rows)
        if b.data["status"] == "paused":  # the header and the Cost section read one figure
            b.data["summary"] = _cost_summary(
                b.data, rows, _cost_groups(repo, b.id, rows, "cr"),
                _cost_groups(repo, b.id, rows, "driver"), _chief_line(repo, b.data)) + [TO_DATE]
    floor = _sum_unpriced(rows)
    return lines + [f"spent {usd_text(total, floor)}" + (f"; {not_priced(floor)}" if floor else "")], 0, prev


def _record_costs(repo: Repo, b: Batch, rows: list[dict]) -> float:
    """The spend the budget check reads, and each CR's share, shown in its STATUS.md."""
    total = sum(r["usd"] for r in rows)
    b.data["spent_usd"] = round(total, 4)  # the priced part: the budget reads it as it is
    b.data["unpriced"] = _sum_unpriced(rows)  # model -> calls left out of it: a floor, said so
    by_cr = _cost_groups(repo, b.id, rows, "cr")
    for c in b.data["crs"]:
        if c["id"] in by_cr:
            c["cost_usd"] = round(by_cr[c["id"]][1], 4)
            if by_cr[c["id"]][2]:
                c["cost_unpriced"] = by_cr[c["id"]][2]
            else:
                c.pop("cost_unpriced", None)
    b.log("cost", None, usd=total)
    return total


def status(args) -> tuple[list[str], int]:
    repo = Repo.find()
    batch = resolve_batch(repo, args.batch)
    extra, code, prev = [], 0, None
    if args.stop_heartbeat:
        extra = _stop_heartbeat(repo, batch, args.epoch)
    elif args.refresh:
        extra, code, prev = _refresh(repo, batch, args.epoch)
    d = read_batch(repo, batch)
    hb = age_minutes(d.get("heartbeat"))
    if d.get("heartbeat_stopped"):
        hb_text = "stopped"
    elif hb is None:
        hb_text = "never"
    else:
        hb_text = f"{hb:.0f} min"
        if prev:  # a wake's own line: the gap since the wake before
            hb_text += f" ({age_minutes(prev) - hb:.0f} min since the last)"
    view = SimpleNamespace(data=d)  # the rails read only `.data`
    n_live = len(held(view))
    queued = sum(1 for c in d["crs"] if c["status"] == "queued")
    lines = [f"{d['id']} {d['status']} steering {steering_word(d.get('steering'))} "
             f"shape {shape_word(d.get('mode'))} live {n_live}/{d['slots']} queued {queued} "
             f"foreman {d.get('foreman') or 'none'} e{d.get('foreman_epoch', 0)} "
             f"heartbeat {hb_text}"
             f" spent {spent_text(d)}"
             + (f" of ${d['budget_usd']:g}" if d.get("budget_usd") else "")
             + (" (paused, cost to date)" if d["status"] == "paused" else "")]
    for c in sorted(d["crs"], key=lambda c: c["order"]):
        row = f"{c['id']} {c['status']} r{c['round']}/{round_limit(d, c)} {c.get('pr') or '-'}"
        if c.get("kind") == "release":
            row += f" release{' ' + c['released'] if c.get('released') else ''}"
            row += "".join(f" | draft {p}" for p in c.get("drafts", [])[-2:])
        elif c.get("kind") == "fix":
            row += f" fix for {c['fix_for']}"
        waits = waits_all(d["crs"], c, d["mode"]) if c["status"] == "queued" else []
        if waits:
            row += f" | waits for {', '.join(waits)}"
        if c["status"] == "working" and not c.get("agent"):
            row += " | no Driver recorded"
        if c["status"] == "blocked" and c.get("blocked_reason"):
            row += f" | blocked: {c['blocked_reason'][:70]}"
        elif c.get("notes") and (args.notes or c["status"] == "queued"):
            row += f" | {c['notes'][-1][:60]}"
        usd = c.get("cost_usd")
        lines.append(f"{row} | {'-' if usd is None else '$%.2f' % usd}")
    open_orders = [o for o in d.get("orders", []) if not o["done"]]
    for applied, head in ((False, "orders pending: "), (True, "orders the CLI applied, the "
                                                              "Foreman marks each `order done <O-k>`: ")):
        group = [o for o in open_orders if bool(o.get("applied")) is applied]
        if group:
            lines.append(head + "; ".join(
                f"{o['id']} {o['kind']}{' ' + o['cr'] if o['cr'] != '-' else ''}"
                f"{' ' + o['note'][:40] if o['note'] else ''}" for o in group))
    unread = sum(1 for a in d.get("asks", []) if not a["read"])
    if unread:
        lines.append(f"{unread} asks unread: `chantier asks`")
    return lines + extra, code


def asks(args) -> list[str]:
    """The Chief of Staff reads what the Foreman had to tell it, sent or not, and marks what it
    heard. With `text`, the Foreman records an ask of its own and gets the line to send."""
    repo = Repo.find()
    text = " ".join(args.text)
    with Batch(repo, resolve_batch(repo, args.batch),
               actor="foreman" if text else "chief-of-staff") as b:
        if text:
            aid = record_ask(b, text)
            return [f"[foreman→chief-of-staff] ask {aid}: {text}"]
        if args.read:
            hit = [a for a in b.data.get("asks", [])
                   if not a["read"] and (args.read == "all" or a["id"] == args.read)]
            if not hit and args.read != "all":
                raise ChantierError(f"no unread ask {args.read}", EXIT_USAGE)
            for a in hit:
                a["read"] = now()
            if hit:
                b.log("asks-read", None, asks=[a["id"] for a in hit])
            return [f"read {len(hit)}"]
        unread = [a for a in b.data.get("asks", []) if not a["read"]]
    return [f"{a['id']}: {a['text']}" for a in unread] or ["no unread ask"]


def agents(args) -> list[str]:
    """The agent id a CR's Driver or the stack driver runs under: the Foreman records it after
    each start, so a restart and the cost know who ran what."""
    repo = Repo.find()
    batch = find_cr_batch(repo, args.cr, args.batch) \
        if args.cr != "stack" and not args.cr.startswith("O-") else resolve_batch(repo, args.batch)
    with Batch(repo, batch, actor="foreman") as b:
        check_epoch(b, args.epoch)
        if args.agent == "-":  # the agent ended: the next one may start
            args.agent = None
        if args.cr == "stack":
            b.data["stack_agent"] = args.agent
        elif args.cr.startswith("O-"):  # a QA order: its driver is a Driver of the batch for `cost`
            o = next((x for x in b.data["orders"] if x["id"] == args.cr), None)
            if o is None or o["kind"] != "qa":
                raise ChantierError(f"agents set {args.cr}: not a QA order of {b.id}", EXIT_USAGE)
            o["agent"] = args.agent
        else:
            b.touch(b.cr(args.cr), agent=args.agent)
        b.log("agent", args.cr, agent=args.agent)
    return [f"{args.cr} → {args.agent}"]


def _chain(b_data: dict) -> list[dict]:
    """The stack as it stands: the CRs not ended, in order, the release CR last whatever its
    `order` (it is the top piece). A fix CR sits outside it, on the default branch. What a
    partial merge leaves forms the next stack, so the first CR left stands on the default
    branch; a CR added by `order add` goes on top (under the release)."""
    if b_data["mode"] != "stack":
        return []
    return sorted([x for x in b_data["crs"] if x["status"] not in {"cancelled", "merged"}
                   and x.get("kind") != "fix"],
                  key=lambda x: (x.get("kind") == "release", x["order"]))


def _top_cr(b_data: dict) -> dict | None:
    """In an ordered batch (stack, series), the last open CR under the release, in order: the
    branch the release starts on and its PR sits on. A fix CR and the release are not in it."""
    if b_data["mode"] not in {"stack", "series"}:
        return None
    open_ = [x for x in b_data["crs"] if x["status"] not in ENDED
             and x.get("kind") not in {"release", "fix"}]
    return max(open_, key=lambda x: x["order"], default=None)


def _start_base(b_data: dict, c: dict, repo: Repo) -> str:
    """The branch a CR starts on: that of its last dependency still open, in the order of
    `after`; with none open, the default branch, whatever its place in a stack. A release in an
    ordered batch starts on the top CR's branch, with none open under it on the default branch;
    in a parallel batch, or alone, on the default branch."""
    default = repo.config["default_branch"]
    if c.get("kind") == "release":
        top = _top_cr(b_data)
        return top["branch"] if top else default
    if b_data["mode"] == "series":
        pred = series_predecessor(b_data["crs"], c)
        return pred["branch"] if pred and pred["status"] != "merged" else default
    if c.get("after") and c.get("kind") not in {"release", "fix"}:
        found = {x["id"]: x for x in b_data["crs"]}
        open_ = [found[i] for i in c["after"] if i in found and found[i]["status"] not in ENDED]
        return open_[-1]["branch"] if open_ else default
    return default


def _stack_base(b_data: dict, c: dict, repo: Repo, planned: bool = False) -> str:
    """The base its PR has: its place in the stack once `stack` marked the CR (`planned`: the
    place it will take); otherwise where it started. A CR sits on the one below it in the chain
    (the first on the default branch); a CR with an open dependency, on that dependency's branch."""
    default = repo.config["default_branch"]
    if c.get("kind") == "release":  # the top of the stack: on the top CR's branch
        return _start_base(b_data, c, repo)
    if c.get("after") and c.get("kind") != "fix":
        return _start_base(b_data, c, repo)
    if not (planned or c.get("stacked")):
        return _start_base(b_data, c, repo)
    order = _chain(b_data)
    ids = [x["id"] for x in order]
    i = ids.index(c["id"]) if c["id"] in ids else 0
    return order[i - 1]["branch"] if i > 0 else default


def _ref(repo: Repo, branch: str) -> str:
    return f"{repo.config['remote']}/{branch}" if branch == repo.config["default_branch"] else branch


def _base_of(d: dict, c: dict, repo: Repo) -> str:
    """The ref the CR's branch starts on: the remote's default branch, or the branch of its
    last open dependency."""
    return _ref(repo, _start_base(d, c, repo))


def _stack_ref(d: dict, c: dict, repo: Repo) -> str:
    """The ref under the CR's PR in the stack, which the stack driver sets."""
    return _ref(repo, _stack_base(d, c, repo, planned=True))


def _facts(repo: Repo, batch: str, d: dict, c: dict) -> list[str]:
    """Everything an agent needs to work on a CR, on one screen: the parent writes its prompt
    from these lines and the role's card."""
    folder = cr_directory(repo, c)
    found = project_instructions(repo)
    skill = skill_dir().as_posix()
    made = Path(c["worktree"]).is_dir()
    lines = [f"{c['id']} \"{c['title']}\" ({c['kind']}) {c['status']} in batch {batch} ({d['mode']})",
             f"cli: {cli_command(repo)} <command> --batch {batch}",
             f"cards: {skill}/references/ (driver.md, worker.md, concepts.md); the project's "
             "rules rank above them: `rules`",
             f"project instructions: {found.as_posix() if found else 'none'}",
             f"specification: {(folder / c['specification']).as_posix()}",
             f"folder: {folder.as_posix()} (work/, evidence/)",
             f"worktree: {c['worktree']} branch {c['branch']} base {_base_of(d, c, repo)}"
             + ("" if made else "; not created yet: a Driver creates it first"),
             *([f"clone: {repo.clone_dir.as_posix()} (`git -C` it to create the worktree)"]
               if repo.external else []),
             *([f"archive: in the PR at {archive_path(repo, c)}" if archive_path(repo, c)
                else "archive: not in the PR"] if repo.external else []),
             f"PR: {c.get('pr') or 'none'}; head {_short(c.get('head')) or '-'}",
             f"rounds: {c['round']} of {round_limit(d, c)}"]
    if c["status"] == "blocked":
        lines.append(f"blocked: {c.get('blocked_reason')}")
    if c.get("kind") == "release":
        lines.append(f"grant: {grant_line(d['release'])}; attempts {c.get('attempts', 0)}; "
                     f"approvals unused: {'; '.join(c.get('approvals', [])) or 'none'}")
    if c.get("after"):
        lines.append(f"after: {', '.join(c['after'])} (a release starts on the top CR's branch "
                     "in an ordered batch, on the default branch once the others are merged in a "
                     "parallel one)"
                     if c.get("kind") == "release" else
                     f"after: {', '.join(c['after'])} (the base is the branch of the last one "
                     "still open)")
    if c.get("kind") == "fix":
        lines.append(f"fix for {c['fix_for']}: the release starts again once this merges")
    if c.get("drafts"):
        lines.append("drafts: " + "; ".join(c["drafts"]))
    pending = [o for o in d.get("orders", []) if not o["done"] and o["cr"] == c["id"]]
    if pending:
        lines.append("orders pending: " + "; ".join(f"{o['id']} {o['kind']} {o['note']}".rstrip()
                                                    for o in pending))
    lines += ["notes:"] + [f"  {n}" for n in c["notes"][-10:]] if c.get("notes") \
        else ["notes: none"]
    if c.get("kind") not in {"release"}:
        events = _cr_events(repo, batch, c["id"])
        head = c.get("head")
        verdict = last_verdict(events, head)
        lines += [
            f"gates before handback ready, at the PR's head {head or 'not shipped yet'} "
            "(the full SHA; the gate log's first line names it):",
            f"  [{'x' if gate_passed(events, head) else ' '}] long gate passed (gate "
            f"{c['id']} \"<cmd>\" [\"<cmd>\"...]; none in the project's rules: handback "
            f"{c['id']} ready --no-gate \"<rule>\")",
            f"  [{'x' if verdict == 'VERIFIED' else ' '}] verdict "
            f"{verdict if verdict == 'NOT VERIFIED' else 'VERIFIED'} (the Verifier: verdict "
            f"{c['id']} VERIFIED|\"NOT VERIFIED\")"]
    gates = folder / "work" / "gates"
    logs = sorted(gates.glob("*.log")) if gates.is_dir() else []
    if logs:
        tail = logs[-1].read_text(encoding="utf-8", errors="replace").splitlines()[-5:]
        lines += [f"last gate log {logs[-1].name}:"] + [f"  {ln}" for ln in tail]
    return lines + pb.team_lines(d.get("playbook"))


def handoff(args) -> list[str]:
    """The CR's facts, for any agent; changes nothing."""
    repo = Repo.find()
    batch, d, c = _batch_cr(repo, args.cr, args.batch)
    return _facts(repo, batch, d, c)


def _reopen(b: Batch) -> list[str]:
    """A take on a paused batch sets it running again: its pause and cost to date are void."""
    if b.data["status"] != "paused":
        return []
    b.data["status"] = "running"
    b.data.pop("paused", None)
    b.data.pop("summary", None)
    b.log("reopen", None)
    return [f"{b.id} was paused: running again; `pause` runs again at the end"]


def _check_release_branch(repo: Repo, d: dict, c: dict) -> None:
    """A release in an ordered batch with CRs open under it starts only once one branch holds all
    the work it ships: the top CR's branch holds the recorded head of every other open CR under
    it. Read only (`git merge-base --is-ancestor`); the CLI changes nothing."""
    top = _top_cr(d)
    if c.get("kind") != "release" or top is None:
        return
    ref = top["branch"]
    if not git("rev-parse", "--verify", "--quiet", f"refs/heads/{ref}", cwd=repo.root, check=False):
        remote = f"{repo.config['remote']}/{ref}"
        if git("rev-parse", "--verify", "--quiet", remote, cwd=repo.root, check=False):
            ref = remote
    for x in sorted(d["crs"], key=lambda x: x["order"]):
        if (x["id"] in {c["id"], top["id"]} or x["status"] in ENDED
                or x.get("kind") in {"release", "fix"}):
            continue
        if not x.get("head"):
            raise ChantierError(f"{c['id']}: {x['id']} has no recorded head (`ship`): the stack "
                                f"driver stacks the CRs first (`take stack`)", EXIT_PRECONDITION)
        held_ = subprocess.run(["git", "merge-base", "--is-ancestor", x["head"], ref],
                               cwd=repo.root, capture_output=True).returncode == 0
        if not held_:
            raise ChantierError(f"{c['id']}: {top['branch']} does not hold {x['id']}'s head "
                                f"{_short(x['head'])}: the stack driver stacks the CRs first "
                                "(`take stack`)", EXIT_PRECONDITION)


def take(args) -> list[str]:
    """The Foreman gives a CR to a Driver (or the stack to its driver): the rails refuse what the
    batch does not allow (a slot, the budget, a CR that has nothing to do), the state records
    it, and the CR's facts are printed for the prompt. The Foreman chooses the agent."""
    repo = Repo.find()
    if args.cr == "stack":
        batch = resolve_batch(repo, args.batch)
    else:
        batch = find_cr_batch(repo, args.cr, args.batch)
    with changes_lock(repo):
        with Batch(repo, batch, actor="foreman") as b:
            check_epoch(b, args.epoch)
            d = b.data
            if args.cr == "stack":
                if d["mode"] != "stack":
                    raise ChantierError(f"batch {batch} is not a stack")
                if d.get("stack_agent"):
                    raise ChantierError(f"a stack driver is recorded ({d['stack_agent']}); one "
                                        "that ended: `agents set stack -` first")
                check_budget(b)
                reopened = _reopen(b)
                b.log("take", None, note=args.note)
                crs = _chain(d)
                return [f"the stack of batch {batch}: {' → '.join(x['id'] for x in crs)}"] + reopened + [
                    f"{x['id']} {x['status']} worktree {x['worktree']} branch {x['branch']} "
                    f"base {_stack_ref(d, x, repo)} PR {x.get('pr') or 'none'}" for x in crs]
            c = b.cr(args.cr)
            check_take(b, c, args.note)
            if c["status"] != "working":
                _check_release_branch(repo, d, c)
            reopened = _reopen(b)
            restart = c["status"] == "working"  # a new Driver on a CR already working
            if c["status"] in {"ready", "blocked", "working"}:
                c.setdefault("notes", []).append(f"back to a Driver: {args.note}")
            b.touch(c, status="working", blocked_reason=None)
            b.log("take", c["id"], note=args.note, **({"restart": True} if restart else {}))
            start_cr(b, c)  # `1-pending` to `2-actives`, before the Driver gets its facts
            if repo.external:
                c.setdefault("archive_stamp", stamp())  # the archive's name, kept from the first take
            _work(repo, c).mkdir(parents=True, exist_ok=True)
            facts = _facts(repo, batch, d, c)
    return [f"took {c['id']} ({len(held(b))} of {d['slots']} slots held)"] + reopened + facts


def round_(args) -> list[str]:
    """A Driver counts a round before it starts the round's Coder; once the budget is spent, or
    past the batch's limit or the one the user granted the CR, it is refused (exit 5), the
    budget first (its own message), the round count unchanged and nothing logged."""
    repo = Repo.find()
    batch = find_cr_batch(repo, args.cr, args.batch)
    with changes_lock(repo):
        with Batch(repo, batch, actor="driver") as b:
            c = b.cr(args.cr)
            if c["status"] not in LIVE:
                raise ChantierError(f"{args.cr} is {c['status']}: no Driver to run a round")
            limit = check_round(b, c)  # the budget first, then the limit
            b.touch(c, round=c.get("round", 0) + 1)
            b.log("round", c["id"], round=c["round"], note=args.note)
            _work(repo, c).mkdir(parents=True, exist_ok=True)
            facts = _facts(repo, batch, b.data, c)
    return [f"round {c['round']} of {limit} for {c['id']}"] + facts


def handback(args) -> list[str]:
    """A Driver's end, in the state first: `ready <link>` or `blocked <reason>`. Prints the line
    to send the Foreman, and what the state did with it."""
    repo = Repo.find()
    note = " ".join(args.note).strip()
    if args.result == "ready" and not note:
        raise ChantierError("handback <cr> ready <pr link, release link or tag>", EXIT_USAGE)
    if args.result == "blocked" and not note:
        raise ChantierError("handback <cr> blocked <reason>: question: …, approval: …, merge: "
                            "<pr>, fix: …; <path>, infra: …, budget: …, rounds: …, refused …, "
                            "waits: <what it waits for>, context: <where it stopped, what is "
                            "next>", EXIT_USAGE)
    no_gate = args.no_gate.strip() if args.no_gate is not None else None
    if no_gate is not None and (args.result != "ready" or not no_gate):
        raise ChantierError('handback <cr> ready <pr link> --no-gate "<the project\'s rule that '
                            'declares no long gate or exempts this CR>"', EXIT_USAGE)
    with changes_lock(repo):
        with Batch(repo, find_cr_batch(repo, args.cr, args.batch), actor="driver") as b:
            c = b.cr(args.cr)
            if c["status"] not in LIVE:
                if c["status"] in ("ready", "blocked"):
                    raise ChantierError(
                        f"{c['id']} is {c['status']}: no Driver holds it until the steering "
                        f"session takes it back (take {c['id']} --note \"<why>\"), then hand "
                        "back again")
                raise ChantierError(f"{args.cr} is {c['status']}: no Driver to hand it back")
            line = f"[driver {args.cr}→foreman] hand-back {args.result} {note}"
            if args.result == "blocked":
                b.log("handback", args.cr, result=args.result, note=note)
                b.touch(c, status="blocked", blocked_reason=note)
                if note.lower().startswith("waits:"):
                    return [line, f"{args.cr} waits; the Foreman takes it back when that lands"]
                if note.lower().startswith("context:"):
                    return [line, f"{args.cr} out of context; the Foreman restarts a fresh Driver "
                                  "from this state, with no ask to the Chief of Staff"]
                return [line, f"{args.cr} blocked; the Foreman asks the Chief of Staff"]
            # a release with an unmerged PR recorded: the release PR is prepared and waits for
            # its merge (the checks of a CR, no verdict); with none, it is released
            prepared = c.get("kind") == "release" and bool(c.get("pr"))
            if c.get("kind") == "release" and not prepared:  # released: nothing is left to merge
                c["released"] = note.split()[0]
                b.log("handback", args.cr, result=args.result, note=note)
                done_cr(b, c)
                b.touch(c, status="merged")
                return [line, f"{args.cr} released, in 3-done"
                        + ("; every CR is merged or cancelled: `chantier pause`"
                           if all_merged(b) else "")]
            if not c.get("pr"):
                raise ChantierError(f"{args.cr}: ready means a PR recorded (`chantier ship`)")
            events, head = _cr_events(repo, b.id, c["id"]), c.get("head")
            wt = _worktree(c)
            missing = []
            now_head = git("rev-parse", "HEAD", cwd=wt)
            if not same_head(head, now_head):  # alone: the gate and verdict are for another head
                raise ChantierError(
                    f"refused: the worktree's head {now_head[:7]} is not the head ship recorded "
                    f"({head or 'none'}): ship {c['id']} {c['pr']} again, then the long gate and "
                    "a verdict VERIFIED at the new head", EXIT_PRECONDITION)
            if _dirty(wt):
                missing.append("refused: the worktree has uncommitted changes or untracked "
                               "files: commit them, push, then `ship` again")
            remote = f"{repo.config['remote']}/{c['branch']}"
            pushed = git("rev-parse", "--verify", "--quiet", remote, cwd=wt, check=False)
            if not same_head(head, pushed):
                missing.append(f"refused: {remote} is "
                               f"{'at ' + _short(pushed) if pushed else 'not pushed'}, not at "
                               f"{_short(head) or 'the shipped head'}: push, then `ship` again")
            if no_gate is None and not gate_passed(events, head):
                missing.append(f"refused: no long gate passed at {head or 'any head'} (gate "
                               f"{c['id']} \"<cmd>\"..., or --no-gate \"<the project's rule>\")")
            if not prepared and last_verdict(events, head) != "VERIFIED":
                missing.append(f"refused: no verdict VERIFIED at {head or 'any head'} (the last "
                               f"verdict there: {last_verdict(events, head) or 'none'})")
            if missing:
                raise ChantierError("\n".join(missing), EXIT_PRECONDITION)
            if no_gate is not None:
                line = f"[driver {args.cr}→foreman] hand-back ready, no long gate: {no_gate} {note}"
            b.log("handback", args.cr, result=args.result, note=note,
                  **({"no_gate": no_gate} if no_gate is not None else {}))
            b.touch(c, status="ready")
            if prepared:
                return [line, f"{args.cr} ready: the release PR {c['pr']} waits for its merge"]
            return [line, f"{args.cr} ready"]


def note(args) -> list[str]:
    """A Driver's or worker's line in the CR's state: what was done or found, shown in its
    STATUS.md. `--draft <path>` names a file the user reviews and edits in place."""
    repo = Repo.find()
    text = " ".join(args.text).strip()
    if not text and not args.draft:
        raise ChantierError("note <cr> <text> | note <cr> --draft <path>", EXIT_USAGE)
    with Batch(repo, find_cr_batch(repo, args.cr, args.batch), actor="driver") as b:
        c = b.cr(args.cr)
        if args.draft:
            path = Path(args.draft).expanduser()
            if not path.is_file():
                raise ChantierError(f"note --draft <path of an existing file>, not {args.draft!r}",
                                    EXIT_USAGE)
            draft = path.resolve().as_posix()
            if draft not in c.setdefault("drafts", []):
                c["drafts"].append(draft)
            text = text or f"draft: {draft}"
        c.setdefault("notes", []).append(text)
        b.touch(c)
        b.log("note", args.cr, note=text)
    return ["ok"]


def log(args) -> list[str]:
    """The CR's events, readable: what happened and when."""
    repo = Repo.find()
    batch, _, c = _batch_cr(repo, args.cr, args.batch)
    lines = []
    for e in _cr_events(repo, batch, c["id"]):
        rest = {k: v for k, v in e.items()
                if k not in {"t", "actor", "kind", "cr"} and v not in (None, "", [])}
        lines.append(f"{e['t']} {e['actor']} {e['kind']}"
                     + (" " + " ".join(f"{k}={v}" for k, v in rest.items()) if rest else ""))
    return lines or [f"no event for {c['id']}"]


# ---- the project's rules ----------------------------------------------------------------------

def _linked(path: Path, root: Path, seen: list[Path], depth: int) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    for m in MD_LINK.finditer(text):
        target = m.group(1) or m.group(2)
        if target.startswith(("http://", "https://", "/")) or ".." in target.split("/"):
            continue
        for candidate in (path.parent / target, root / target):
            try:
                candidate = candidate.resolve()
            except OSError:
                continue
            if candidate.is_file() and candidate.is_relative_to(root) and candidate not in seen:
                seen.append(candidate)
                if depth > 1:
                    _linked(candidate, root, seen, depth - 1)
                break


def playbook(args) -> tuple[list[str], int]:
    """The project's playbook: which agent and model each role of the plugin runs. Without
    `--batch` it reads `chantier.yaml` now, for the host; with it, the playbook the batch opened
    with (a batch with none recorded runs the plugin's agents and models)."""
    repo = Repo.find()
    if args.batch:
        d = read_batch(repo, resolve_batch(repo, args.batch))
        made, host = d.get("playbook"), d["host"]
        label = d.get("id") or args.batch
    else:
        host = detect_host(args.host)
        made, problems = read_playbook(repo, host)
        label = None
        if problems:
            return [f"playbook: {pb.FILE} is not valid ({len(problems)} problems)"] + problems, \
                EXIT_PRECONDITION
    lines = pb.playbook_lines(made, host, plugin_roles(host), label)
    if not args.batch:  # the Spec-writer's first line, to copy as printed
        lines.append("spec-writer prompt, first line: chantier spec-writer for the Chief of Staff, "
                     f"in the project {repo.root.as_posix()}.")
    lines.append(pb.escalate_line(host))
    return lines, 0


def rules(args) -> list[str]:
    """The project's rules: its instruction file and the local Markdown files it links, two
    levels deep. Every role reads them before its own card; they rank above it."""
    repo = Repo.find()
    found, outer = project_instructions(repo), surface_instructions(repo)
    if not found and not outer:
        raise ChantierError(f"no {', '.join(INSTRUCTIONS)} in {repo.session_root}: ask your parent")

    def listed(first: Path | None, root: Path) -> list[str]:
        if not first:
            return []
        seen = [first.resolve()]
        _linked(first.resolve(), root.resolve(), seen, 2)
        return [f"{p.as_posix()} ({sum(1 for _ in p.open(encoding='utf-8', errors='replace'))} lines)"
                for p in seen]

    if not repo.external:
        return listed(found, repo.root)
    return ["project:", *listed(found, repo.root), "surface:", *listed(outer, repo.surface)]


# ---- the long gate and the ship: the record of the Driver's own work ------------------------

def _lock_holder(repo: Repo) -> str:
    """Who holds the long gate, from its lock file: `<cr> pid <n> pg<m>`, or empty."""
    try:
        with open(repo.changes / ".long-gate.lock", encoding="utf-8") as f:
            f.seek(1)  # byte 0 is the lock: Windows refuses to read it
            return f.read().strip()
    except OSError:
        return ""


class _LongGateLock:
    """One long gate at a time in the repository: two full suites at once break each other
    (app windows, ports, shared caches). The lock file names who holds it and the suite's
    process: when the `gate` command dies, the OS frees the lock, but the suite may live on,
    so the next gate waits for that process too."""

    def __init__(self, repo: Repo, cr: str, log: Path):
        self.path = repo.changes / ".long-gate.lock"
        self.repo, self.cr, self.log = repo, cr, log

    def _wait_note(self, holder: str) -> None:
        with open(self.log, "a", encoding="utf-8") as f:
            f.write(f"waiting for the long gate of {holder}\n")

    # The queue: one ticket per waiting gate in `.long-gate.queue/`, named by arrival, content
    # `<cr> pid <pid>`. A gate tries the OS lock only when its ticket is the first live one; a
    # ticket whose pid is gone (a waiting `gate` command that ended) is deleted by whoever reads it.
    def _ticket_cr(self, p: Path) -> str | None:
        for _ in range(5):  # the other side may be writing it
            try:
                m = re.fullmatch(r"(\S+) pid (\d+)", p.read_text(encoding="utf-8").strip())
            except FileNotFoundError:
                return None
            except (OSError, ValueError):
                m = None
            if m:
                if procs.alive(int(m[2])):
                    return m[1]
                try:
                    p.unlink()
                except OSError:
                    pass
                return None
            time.sleep(0.05)
        return None

    def _ahead(self) -> list[str]:
        """The CRs of the live tickets before this gate's own."""
        out = []
        for p in sorted(self.queue.glob("[0-9]*")):
            if p.name >= self.ticket.name:
                break
            cr = self._ticket_cr(p)
            if cr is not None:
                out.append(cr)
        return out

    @staticmethod
    def _key(text: str) -> str:
        """The holder without its suite's `pg<m>`: a gate starting a command is not a new holder."""
        return re.sub(r"\s+pg\d+\b", "", text)

    def __enter__(self):
        self.f = open(self.path, "a+", encoding="utf-8")
        self.queue = self.repo.changes / ".long-gate.queue"
        self.queue.mkdir(exist_ok=True)
        self.ticket = self.queue / f"{time.time_ns():020d}-{os.getpid()}"
        tmp = self.queue / f".{self.ticket.name}.tmp"  # atomic: a reader never sees half a ticket
        tmp.write_text(f"{self.cr} pid {os.getpid()}", encoding="utf-8")
        os.replace(tmp, self.ticket)
        self.locked = False
        try:
            self._acquire()
        except BaseException:
            if self.locked:
                _unlock(self.f)
            self.f.close()
            raise
        finally:
            self.ticket.unlink(missing_ok=True)
        return self

    def _acquire(self) -> None:
        since, current, noted = time.monotonic(), None, None
        while True:
            ahead = self._ahead()
            if not ahead and _try_lock(self.f):
                self.locked = True
                break
            text = _lock_holder(self.repo)
            if self._key(text) and self._key(text) != current:  # a new holder: its hour starts
                current, since = self._key(text), time.monotonic()
            note = (current, tuple(ahead))
            if note != noted:
                noted = note
                queued = f"; queued ahead: {', '.join(ahead)}" if ahead else ""
                self._wait_note(f"{text or 'another CR'}{queued}")
            if time.monotonic() - since > LONG_GATE_WAIT_S and (text or not ahead):
                who = re.fullmatch(r"(\S+) pid (\d+)(?: pg\d+)?", text)
                more = f" and {', '.join(ahead)}" if ahead else ""
                if who:
                    raise ChantierError(f"the long gate of {who[1]} (pid {who[2]}) has held the "
                                        "lock for over an hour: check it; this gate was queued "
                                        f"behind it{more}")
                raise ChantierError("the long gate lock has been held for over an hour by a "
                                    "process that names no CR: check it")
            time.sleep(1)
        left = _lock_holder(self.repo)  # a gate that died without cleaning up: its suite may run on
        m = re.search(r"\bpg(\d+)\b", left)
        if m and procs.alive(int(m[1])):
            self._wait_note(f"{left} (its command still runs)")
            since = time.monotonic()
            while procs.alive(int(m[1])):
                if time.monotonic() - since > LONG_GATE_WAIT_S:
                    cr = _lock_holder(self.repo).split()[0:1] or ["another CR"]
                    raise ChantierError(f"the long gate of {cr[0]} has ended but its suite "
                                        f"(pg{m[1]}) still runs after an hour: check it")
                time.sleep(1)
        self.holding(f"{self.cr} pid {os.getpid()}")

    def holding(self, text: str) -> None:
        self.f.seek(0)
        self.f.truncate()
        self.f.write(f" {text}")
        self.f.flush()

    def __exit__(self, *exc):
        try:
            self.holding("")
        finally:
            _unlock(self.f)
            self.f.close()


# The run file `.long-gate.run` (planning folder, ignored like the lock) tells a `gate <cr> --stop`
# what the running gate is (run id, head, command, log, suite group) and tells the running gate it
# was stopped. The ask is a separate marker, `.long-gate.stop`, that the stopper creates and the gate
# never rewrites (the gate removes it when it starts and ends), so no write of the run file can
# lose it: the gate checks it before and right after each start, and after each wait, and then
# records `stopped`, never `fail`.
def _run_file(repo: Repo) -> Path:
    return repo.changes / ".long-gate.run"


def _stop_file(repo: Repo) -> Path:
    return repo.changes / ".long-gate.stop"


def _stop_asked(repo: Repo) -> bool:
    return _stop_file(repo).exists()


def _run_read(repo: Repo) -> dict:
    for _ in range(5):  # the other side may be writing it
        try:
            return json.loads(_run_file(repo).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            time.sleep(0.05)
    return {}


def _run_write(repo: Repo, data: dict) -> None:
    tmp = _run_file(repo).with_name(".long-gate.run.tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    for i in range(5):  # atomic: the stopper never reads half a file
        try:
            os.replace(tmp, _run_file(repo))
            return
        except PermissionError:  # Windows: a reader holds the file
            if i == 4:
                raise
            time.sleep(0.05)


def _gate_stop(args, repo: Repo, batch: str, wt: Path) -> tuple[list[str], int]:
    """`gate <cr> --stop`: stop this CR's running long gate (its suite, the lock) and record the
    run `stopped`: no pass, no failure. Nothing else of the CR changes."""
    holder = _lock_holder(repo)
    m = re.fullmatch(r"(\S+) pid (\d+)(?: pg(\d+))?", holder)
    if not m:
        return [f"no long gate running for {args.cr}: nothing to stop"], 0
    if m[1] != args.cr:
        return [f"the long gate running is {m[1]}'s: not stopped"], EXIT_PRECONDITION
    run = _run_read(repo)
    head = run.get("head") or git("rev-parse", "HEAD", cwd=wt)
    pg = int(m[3]) if m[3] else None
    gate_alive = procs.alive(int(m[2]))
    if gate_alive:
        _stop_file(repo).write_text("stop", encoding="utf-8")  # the running gate records it
    if pg is not None:
        procs.stop_group(pg)
    if not gate_alive:  # the gate is gone: the stopper records the run
        if run.get("log") and Path(run["log"]).exists():
            with open(run["log"], "a", encoding="utf-8") as f:
                f.write(f"result: stopped at {head}: no pass\n")
        if run:  # with no run record there is no run to record: the lock was stale
            with Batch(repo, batch, actor="driver") as b:
                b.log("gate", args.cr, result="stopped", head=head,
                      command=run.get("command", ""), run=run.get("run", ""))
        _run_file(repo).unlink(missing_ok=True)
    where = f" (pg{pg})" if pg is not None else ""
    return [f"stopped the long gate of {args.cr} at {_short(head)}{where}"], 0


def gate(args) -> tuple[list[str], int]:
    """The long gate: the command the project's rules name, run in the CR's worktree, alone in
    the repository (a second one waits), logged in the work folder, recorded with its head.
    `--stop` stops this CR's running gate (its suite and the lock): recorded `stopped`, no pass,
    no failure; the stopped gate exits 4; nothing else of the CR changes."""
    repo = Repo.find()
    batch, _, c = _batch_cr(repo, args.cr, args.batch)
    wt = _worktree(c)
    cmds = [x.strip() for x in args.command]
    if args.stop:
        if cmds:
            raise ChantierError(f"gate {args.cr} --stop takes no command", EXIT_USAGE)
        return _gate_stop(args, repo, batch, wt)
    if not cmds or not all(cmds):
        raise ChantierError("gate <cr> \"<command>\" [\"<command>\"...]: the long gate's commands "
                            "from the project's rules, one per argument", EXIT_USAGE)
    if _dirty(wt):  # a gate binds to a commit: nothing runs, nothing is logged
        raise ChantierError(f"{c['id']}: the worktree has uncommitted changes or untracked files: "
                            "a gate binds to a commit, commit first", EXIT_PRECONDITION)
    start = git("rev-parse", "HEAD", cwd=wt)  # the full SHA, before the first command
    logdir = _work(repo, c) / "gates"
    logdir.mkdir(parents=True, exist_ok=True)
    stamped = time.strftime('%Y%m%d-%H%M%S')
    log = logdir / f"{stamped}.log"
    run = f"{stamped}-{os.getpid()}"  # the events of this invocation share it
    ran: list[tuple[str, int]] = []
    with open(log, "a", encoding="utf-8") as f:  # the first line, before any waiting note
        f.write(f"gate {c['id']} branch {c['branch']} head {start}\n")
    stopped = ""  # the command that was running when a `--stop` came
    with _LongGateLock(repo, args.cr, log) as lock:
        _stop_file(repo).unlink(missing_ok=True)  # a stale ask is not this gate's
        _run_write(repo, {"cr": args.cr, "run": run, "head": start, "log": str(log),
                          "command": ""})
        for cmd in cmds:
            if _stop_asked(repo):  # stopped between two commands: none starts
                # the record names the previous command (the one that last ran), or the first
                stopped = ran[-1][0] if ran else cmd
                break
            # closed while the gate runs: a `cancel` must be able to move the CR's folder on Windows
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"$ {cmd}\n")
                f.flush()
                group = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                         if sys.platform == "win32" else {"start_new_session": True})
                p = subprocess.Popen(cmd, shell=True, cwd=wt, stdout=f, stderr=subprocess.STDOUT,
                                     **group)
            lock.holding(f"{args.cr} pid {os.getpid()} pg{p.pid}")
            _run_write(repo, {"cr": args.cr, "run": run, "head": start, "log": str(log),
                              "command": cmd, "pg": p.pid})
            if _stop_asked(repo):  # asked before the stopper could see this group: stop it here
                procs.stop_group(p.pid)
            rc = p.wait()
            if _stop_asked(repo):  # stopped: no pass, and no failure of the code
                stopped = cmd
                break
            ran.append((cmd, rc))
            if rc:
                break  # the commands after a failure are not run
        _run_file(repo).unlink(missing_ok=True)
        _stop_file(repo).unlink(missing_ok=True)
    if stopped:
        if log.exists():
            with open(log, "a", encoding="utf-8") as f:
                f.write(f"result: stopped at {start}: no pass\n")
        with Batch(repo, batch, actor="driver") as b:
            for cmd, rc in ran:
                b.log("gate", args.cr, result=("fail" if rc else "pass"), head=start,
                      command=cmd, run=run)
            b.log("gate", args.cr, result="stopped", head=start, command=stopped, run=run)
        return [f"STOPPED {stopped} at {_short(start)}: no pass", f"log {log}"], EXIT_EXTERNAL
    end = git("rev-parse", "HEAD", cwd=wt)
    moved = end != start  # a gate command committed: the run is no pass at either head
    failed = ran[-1][1]
    if failed:
        result = f"FAIL {ran[-1][0]} (exit {failed}) at {_short(start)}"
    elif moved:
        result = f"head moved during the run, from {start} to {end}: no pass at either head"
    else:
        result = f"pass at {start}"
    if moved and failed:
        result += f"; head moved from {start} to {end}"
    if log.exists():  # a `cancel` moves the CR's folder, log and all, while the gate runs
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"result: {result}\n")  # the log's last line
    with Batch(repo, batch, actor="driver") as b:
        for cmd, rc in ran:
            b.log("gate", args.cr, result=("fail" if rc else "moved" if moved else "pass"),
                  head=start, command=cmd, run=run)
        if moved:
            b.log("gate", args.cr, result="moved", head=end, command=ran[-1][0], run=run)
    lines = [f"{'pass' if rc == 0 and not moved else 'FAIL'} {cmd}"
             f"{'' if rc == 0 else f' (exit {rc})'} at {_short(start)}" for cmd, rc in ran]
    if moved:
        lines.append(f"head moved during the gate, from {_short(start)} to {_short(end)}: "
                     "no pass at either head")
    if failed or moved:
        # gates write in the console's code page: never fail on their bytes
        tail = (log.read_text(encoding="utf-8", errors="replace").splitlines()[-8:]
                if log.exists() else [])
        return lines + [f"log {log}"] + tail, EXIT_EXTERNAL
    return lines + [f"log {log}"], 0


VERDICTS = ("VERIFIED", "NOT VERIFIED")


def verdict(args) -> list[str]:
    """A verdict on the worktree's head, in the log: the last one at a head decides. It knows a
    verdict, not a role; a card says who runs it."""
    repo = Repo.find()
    result = " ".join(" ".join(args.result).upper().split())
    if result not in VERDICTS:
        raise ChantierError('verdict <cr> VERIFIED | "NOT VERIFIED"', EXIT_USAGE)
    try:
        batch, _, c = _batch_cr(repo, args.cr, args.batch)
    except ChantierError as e:
        raise ChantierError(str(e), EXIT_PRECONDITION) from e
    wt = _worktree(c)
    if git("status", "--porcelain", "--untracked-files=normal", cwd=wt):
        raise ChantierError(f"{c['id']}: the worktree has uncommitted work: a verdict binds to a "
                            "head, commit first", EXIT_PRECONDITION)
    head = git("rev-parse", "HEAD", cwd=wt)
    with Batch(repo, batch, actor="driver") as b:
        b.log("verdict", c["id"], result=result, head=head)
    return [f"verdict {c['id']} {result} at {_short(head)}"]


def ship(args) -> list[str]:
    """The Driver pushed and opened or updated the PR itself; this records the link at the
    worktree's head and says what is off: an uncommitted change, a head not pushed, no long gate
    passed at this head."""
    repo = Repo.find()
    batch, d, c = _batch_cr(repo, args.cr, args.batch)
    wt = _worktree(c)
    if "://" not in args.pr:
        raise ChantierError("ship <cr> <pr link>", EXIT_USAGE)
    off = []
    dirty = git("status", "--porcelain", "--untracked-files=normal", cwd=wt)
    if dirty:
        what = ("untracked files" if all(ln.startswith("??") for ln in dirty.splitlines())
                else "uncommitted changes")
        off.append(f"{what} in the worktree, not in the PR: "
                   f"{' '.join(ln.split(maxsplit=1)[-1] for ln in dirty.splitlines()[:5])}")
    head = git("rev-parse", "HEAD", cwd=wt)
    pushed = git("rev-parse", "--verify", "--quiet", f"{repo.config['remote']}/{c['branch']}",
                 cwd=wt, check=False)
    if pushed != head:
        off.append(f"{repo.config['remote']}/{c['branch']} is {'not pushed' if not pushed else 'at ' + pushed[:7]}, "
                   f"not this head: push with --force-with-lease, then ship again")
    short = _short(head)  # display only: the CR and the event keep the full SHA
    where = archive_path(repo, c)
    seen = None
    if where:
        seen = bool(git("ls-tree", "-d", "--name-only", head, where.rstrip("/"), cwd=wt,
                        check=False))
        if not seen:
            off.append(f"archive missing from the PR at {where}")
    if not gate_passed(_cr_events(repo, batch, c["id"]), head):
        off.append(f"no long gate passed at {short} (`chantier gate`)")
    base = _stack_base(d, c, repo)
    with Batch(repo, batch, actor="driver") as b:
        b.touch(b.cr(c["id"]), pr=args.pr, head=head, archive_seen=seen)
        b.log("ship", c["id"], pr=args.pr, base=base, head=head, off=off)
    return [f"recorded {args.pr} (base {base}, head {short})"] + [f"off: {x}" for x in off]


def stack(args) -> list[str]:
    """The stack's order, as its driver set it; each PR's base follows from it."""
    repo = Repo.find()
    batch = resolve_batch(repo, args.batch)
    with Batch(repo, batch, actor="stack") as b:
        if b.data["mode"] != "stack":
            raise ChantierError(f"batch {batch} is not a stack")
        place = {cr: i for i, cr in enumerate(args.crs, 1)}
        for cr in args.crs:
            below = [a for a in b.cr(cr).get("after", []) if place.get(a, 0) > place[cr]]
            if below:
                raise ChantierError(f"{cr} depends on {', '.join(below)}: it cannot sit below "
                                    f"{'it' if len(below) == 1 else 'them'}")
        for i, cr in enumerate(args.crs, 1):
            b.touch(b.cr(cr), order=i, stacked=True)
        b.log("stack-order", None, crs=args.crs)
    return [f"stack order: {' → '.join(args.crs)}"]


def release(args) -> tuple[list[str], int]:
    """The release CR's attempts and its irreversible actions: none before every other CR is
    merged and the release PR is merged (the user's, or the steering session's under the grant);
    then the merge is the go, else each one is approved by the user, or allowed by the grant the
    user gave, within the budget. A fix's merge is an action too:
    `go` on the fix CR, under the grant alone."""
    repo = Repo.find()
    with Batch(repo, find_cr_batch(repo, args.cr, args.batch), actor="driver") as b:
        c = b.cr(args.cr)
        is_fix = c.get("kind") == "fix" and args.action == "go"
        if c.get("kind") != "release" and not is_fix:
            raise ChantierError(f"{args.cr} is not the batch's release CR", EXIT_USAGE)
        grant = b.data["release"]
        if args.action == "start":  # a new attempt, on the branch the Driver set on the base
            # a merged PR of an earlier attempt is not this one's
            # (a merged PR is already cleared by `release_merged`; an attempt refreshes the
            # recorded release PR, and a Driver that opens another records it with `ship`)
            b.touch(c, attempts=c.get("attempts", 0) + 1, head=None)
            b.log("release-start", args.cr)
            return [f"attempt {c['attempts']}: the procedure starts from its first step"], 0
        if not (args.note or "").strip():
            raise ChantierError(f"release {args.action} {args.cr} --note \"<…>\"", EXIT_USAGE)
        if args.action == "published":
            grant["published"] = grant.get("published", 0) + 1
            c.setdefault("notes", []).append(f"published: {args.note}")
            b.touch(c)
            b.log("release-published", args.cr, note=args.note)
            return [f"release {grant['published']} published: {args.note}"], 0
        result, why = fix_go(b, c, args.note) if is_fix else release_go(b, c, args.note)
        if is_fix and result == "ask":
            return [f"no grant for: {args.note}; the user merges it"], EXIT_PRECONDITION
        if result == "budget":
            return [f"no: the budget is spent ({spent_text(b.data)} of "
                    f"${b.data['budget_usd']}); only the user raises it"], EXIT_BUDGET
        if result == "fix":
            return [f"no: fix {why} is not merged"], EXIT_PRECONDITION
        if result == "merge":
            return [f"no: {why}"], EXIT_PRECONDITION
        if result == "ask":
            return [f"no approval for: {args.note}; the user's word comes as `order approve`"], \
                EXIT_PRECONDITION
        return [f"go: {args.note} ({why})"], 0


def cancel(args) -> list[str]:
    """A dropped CR, on the user's word: its gate and its stray processes stopped, its folder
    in the trash with its work."""
    if args.epoch is None:
        raise ChantierError("cancel <cr> --epoch <n>: the steering session's command for a CR the "
                            "user dropped; a Driver stops its own long gate with "
                            f"`gate {args.cr} --stop`", EXIT_PRECONDITION)
    repo = Repo.find()
    with changes_lock(repo):
        with Batch(repo, find_cr_batch(repo, args.cr, args.batch), actor="foreman") as b:
            check_epoch(b, args.epoch)
            c = b.cr(args.cr)
            if c["status"] == "merged":
                raise ChantierError(f"{args.cr} is merged: nothing to cancel")
            killed = []
            m = re.fullmatch(rf"{re.escape(args.cr)} pid \d+ pg(\d+)", _lock_holder(repo))
            if m and procs.stop_group(int(m[1])):
                killed.append(f"pg{m[1]}")
            if c.get("worktree") and Path(c["worktree"]).exists():
                killed += [str(p) for p in procs.stop(procs.find(Path(c["worktree"])))]
            trash_cr(b, c)
            b.touch(c, status="cancelled", agent=None)
            b.log("cancel", args.cr, killed=killed, path=c.get("path"))
            done = all_merged(b)
    return [f"cancelled {args.cr}; stopped {len(killed)}: {' '.join(killed) or 'none'}"] \
        + (["every CR is merged or cancelled: `chantier pause`"] if done else [])


def pause(args) -> list[str]:
    """The batch's end of work: it is paused, and the cost to date is computed and printed;
    `close` prices the final one. A paused batch is not paused again: `order add` adds work,
    the first `take` sets it running, then `pause` runs again."""
    repo = Repo.find()
    batch = resolve_batch(repo, args.batch)
    with Batch(repo, batch, actor="foreman") as b:
        check_epoch(b, args.epoch)
        if b.data["status"] == "paused":
            raise ChantierError(f"{batch} is already paused (at {b.data.get('paused')}): "
                                "`order add` adds work, the first `take` sets it running again, "
                                "then `pause` runs again")
        paused = now()
        live_ids = [c["id"] for c in b.data["crs"] if c["status"] in LIVE]
        pending = [o["id"] for o in b.data["orders"] if not o["done"]]
        queued = [c["id"] for c in b.data["crs"] if c["status"] == "queued"]
        open_ = [c["id"] for c in b.data["crs"] if c["status"] in {"ready", "blocked"}]
        if live_ids or pending or queued or open_ or b.data.get("stack_agent"):
            raise ChantierError(f"cannot pause {batch}: live {', '.join(live_ids) or '-'}, "
                                f"queued {', '.join(queued) or '-'}, "
                                f"not merged {', '.join(open_) or '-'}, orders pending "
                                f"{', '.join(pending) or '-'} (the Foreman ends each with "
                                "`order done <O-k>`), "
                                f"stack driver {b.data.get('stack_agent') or 'none'}")
        try:
            rows = _cost_rows(repo, b.data, b.data["host"], _foreman_uuid(b.data))
            _record_costs(repo, b, rows)
            summary = _cost_summary(b.data, rows, _cost_groups(repo, batch, rows, "cr"),
                                    _cost_groups(repo, batch, rows, "driver"),
                                    _chief_line(repo, b.data)) + [TO_DATE]
        except ChantierError as e:  # never a false $0.00
            summary = [f"Spent: unknown ({e})"]
        b.data.update(status="paused", paused=paused, summary=summary, heartbeat_stopped=paused)
        b.log("pause", None)
    return [f"paused {batch}: cost to date below", f"report: {b.dir / 'STATUS.md'}", *summary]


def _close_target(repo: Repo, batch: str | None) -> tuple[str, Path, dict]:
    """The batch `close` acts on: the project's one batch, named or not. One that is not paused is
    refused with what runs in it, or with "`pause` first"."""
    folders = repo.batch_folders()
    batch = normalize_batch(batch) if batch else batch
    datas = {d: read_batch_json(d / "batch.json") for d in folders}
    pick = [d for d in folders if not batch or datas[d]["id"] == batch]
    if len(pick) != 1:
        raise ChantierError(f"close names one batch; batches: "
                            f"{', '.join(d['id'] for d in datas.values()) or 'none'}", EXIT_USAGE)
    d = datas[pick[0]]
    if d.get("status") != "paused":
        check_idle(repo, d)
        raise ChantierError(f"cannot close {d['id']}: it is {d.get('status')}, not paused; "
                            "`pause` comes first. Nothing was deleted.", EXIT_PRECONDITION)
    return d["id"], pick[0], d


def _retro_target(repo: Repo, batch: str, folder: Path,
                  archived: list[tuple[dict, Path]]) -> Path | None:
    """Where `close` keeps `4-batch/retro.md`: `retro.md` in the archive of the CR merged last
    (the archive name that sorts last), or in `5-archives/<stamp>-<batch id>/` when no CR is
    archived. None when there is no retro: missing, or empty (no bytes, or whitespace only)."""
    retro = folder / "retro.md"
    try:
        if not retro.is_file() or not retro.read_bytes().strip():
            return None
    except OSError:
        return None
    archives = stage_layout(repo)["archives"]
    if archived:
        return archives / max(archive_name(c, source) for c, source in archived) / "retro.md"
    return archives / f"{stamp()}-{batch}" / "retro.md"


def _batch_files(folder: Path, kept: bool = False) -> list[Path]:
    """What `close` deletes: everything in `4-batch/` but the three state folders, and but
    `retro.md` when it is kept (`_retro_target`); an empty `retro.md` is deleted."""
    return sorted(p for p in folder.iterdir()
                  if p.name not in STATE_FOLDERS and not (kept and p.name == "retro.md"))


def close(args) -> tuple[list[str], int]:
    """The batch's own files go, but its `retro.md`, kept in the archive of the CR merged last (or
    in `5-archives/<date>-<batch>/` when none merged), and its merged CRs move from `3-done` to
    `5-archives`: the Chief
    of Staff shows the user what would happen, with the dropped CRs' worktrees and branches it
    removes itself on the same word, and passes `--yes`. Without it, nothing is touched. It
    refuses while anything runs or `1-pending` or `2-actives` holds a CR, with or without `--yes`,
    and it prices the batch up to now: this is the final cost, printed either way. It refuses,
    with or without `--yes`, when nothing can be priced (no Foreman transcript recorded, no priced
    call in the whole batch). Calls of a model with no price do not refuse it: the final cost is a
    floor, printed with the calls not priced."""
    repo = Repo.find()
    with changes_lock(repo):
        batch, folder, d = _close_target(repo, args.batch or os.environ.get("CHANTIER_BATCH"))
        check_idle(repo, d)
        paths = stage_layout(repo)
        held = [f"{stage}/{p.name}" for stage in ("1-pending", "2-actives")
                for p in sorted((folder / stage).iterdir() if (folder / stage).is_dir() else [])
                if p.is_dir()]
        if held:
            raise ChantierError(f"{batch} still holds {', '.join(held)} in 4-batch: nothing "
                                "was deleted")
        archived = [(c, cr_directory(repo, c)) for c in d["crs"]
                    if c.get("path") and cr_directory(repo, c).parent == paths["done"]]
        dropped = [f"{c['id']} worktree {c['worktree']} branch {c['branch']}"
                   for c in d["crs"] if c["status"] == "cancelled"]
        retro = _retro_target(repo, batch, folder, archived)
        own = _batch_files(folder, kept=retro is not None)
        where = _shown(repo, retro) if retro else None
        lines = [f"close {batch} deletes its files in {_shown(repo, folder)}: "
                 f"{', '.join(p.name for p in own) or 'none'}",
                 f"{len(archived)} CRs move from 3-done to 5-archives: "
                 f"{', '.join(c['id'] for c, _ in archived) or 'none'}",
                 (f"retro: {_shown(repo, folder / 'retro.md')} moves to {where}"
                  + ("" if archived else " (no CR archived)")) if retro else "retro: no retro",
                 "the dropped CRs, to remove on the same word where they still exist "
                 f"(`git {'-C ' + repo.clone_dir.as_posix() + ' ' if repo.external else ''}"
                 f"worktree remove --force`, `git branch -D`): {'; '.join(dropped) or 'none'}"]
        rows = _final_rows(repo, batch, d)
        lines += ["final cost, up to now (nothing runs):"] + _cost_summary(
            d, rows, _cost_groups(repo, batch, rows, "cr"), _cost_groups(repo, batch, rows, "driver"),
            _chief_line(repo, d))
        if not args.yes:
            return lines + ["ask the user, then `chantier close --yes`"], 0
        _archive_and_delete(repo, batch, folder, d, rows, archived, own, retro)
        write_dashboard(repo, paths)
    lines[2] = f"retro: kept in {where}" if retro else "retro: no retro"
    return [f"closed {batch}: its files are deleted, {len(archived)} CRs archived"] + lines[1:], 0


def _archive_and_delete(repo: Repo, batch: str, folder: Path, d: dict, rows: list[dict],
                        archived: list[tuple[dict, Path]], own: list[Path],
                        retro: Path | None = None) -> None:
    """All or nothing: each `3-done` CR is renamed into `5-archives` (named for its merge time),
    the batch's `retro.md` is kept by a rename to `retro` (never an overwrite), the final pages
    are written where the CRs are now, and the batch's own files go by a rename first. Any failure
    puts every rename back and removes a created retro folder."""
    archives = stage_layout(repo)["archives"]
    done: list[tuple[Path, Path]] = []
    made: Path | None = None
    try:
        record = {**d, "crs": [dict(c) for c in d["crs"]]}
        for c, source in archived:
            target = archives / archive_name(c, source)
            move_directory(source, target)
            done.append((source, target))
            next(x for x in record["crs"] if x["id"] == c["id"])["path"] = \
                repo.rel(target)
        if retro is not None:
            if not retro.parent.exists():  # no CR archived: a folder named for the batch
                retro.parent.mkdir(parents=True)
                made = retro.parent
            if retro.exists() or retro.is_symlink():
                raise ChantierError(f"refusing to overwrite {_shown(repo, retro)}: the retro of "
                                    f"{batch} stays in 4-batch, nothing was closed", EXIT_CONFLICT)
            try:
                _retry((folder / "retro.md").rename, retro)
            except OSError as e:
                raise ChantierError(f"retro.md of {_shown(repo, folder)} is in use, close what "
                                    f"holds it and run this again: {e}", EXIT_EXTERNAL) from e
            done.append((folder / "retro.md", retro))
        _final_pages(repo, batch, folder, record, rows)
        going = repo.changes / f".closing-{batch}"
        going.mkdir()
        try:  # a rename fails whole on a file in use; a delete would stop halfway
            for p in own:
                _retry(p.rename, going / p.name)
                done.append((p, going / p.name))
        except OSError as e:
            raise ChantierError(f"{p.name} of {_shown(repo, folder)} is in use, close what holds "
                                f"it and run this again: {e}", EXIT_EXTERNAL) from e
    except BaseException:
        for source, target in reversed(done):
            if target.exists() and not source.exists():
                _retry(target.rename, source)
        with contextlib.suppress(OSError):
            (repo.changes / f".closing-{batch}").rmdir()
        if made is not None:
            with contextlib.suppress(OSError):
                made.rmdir()
        raise
    shutil.rmtree(going)


def _final_rows(repo: Repo, batch: str, d: dict) -> list[dict]:
    """The batch priced to now, once, before anything is touched. Calls of a model with no price
    do not refuse the close: they are counted apart and the cost is a floor. It is refused (exit 2)
    with its cause when nothing can be priced (no Foreman transcript recorded, no priced call in
    the whole batch), never closed on a false $0.00."""
    try:
        return _cost_rows(repo, d, d["host"], _foreman_uuid(d))
    except ChantierError as e:
        raise ChantierError(f"cannot close {batch}: its final cost cannot be priced ({e}). "
                            "Nothing was deleted.", EXIT_PRECONDITION) from e


def _final_pages(repo: Repo, batch: str, folder: Path, d: dict, rows: list[dict]) -> None:
    """The archived CR pages outlive the batch: priced to now, they alone say the cost is final."""
    by_cr = _cost_groups(repo, batch, rows, "cr")
    crs = [{**c, "cost_usd": round(by_cr[c["id"]][1], 4), "cost_unpriced": by_cr[c["id"]][2]}
           if c["id"] in by_cr else c
           for c in d["crs"]]
    write_final_pages(repo, {**d, "crs": crs}, folder)

# ---- cost -------------------------------------------------------------------------------------

TO_DATE = "To date: it grows if the batch runs again; `close` prices the final cost"


def _prices(repo: Repo, host: str) -> dict | None:
    """The project's prices (`prices:` of `chantier.yaml`), read at each pricing and not frozen
    at `open`, so a price added mid-batch prices the next refresh. Not used on Copilot, whose
    records carry the price. A file that is not valid refuses, never silently ignored."""
    if host == "copilot":
        return None
    resolved, problems = read_playbook(repo, host)
    if problems:
        raise ChantierError("chantier.yaml is not valid, the prices cannot be read:\n"
                            + "\n".join(problems) + "\nrun `$CHANTIER playbook`", EXIT_PRECONDITION)
    return (resolved or {}).get("prices") or None


def _unpriced(r: dict) -> dict:
    return r.get("unpriced") or {}


def _add_unpriced(into: dict, un: dict) -> dict:
    for model, n in un.items():
        into[model] = into.get(model, 0) + n
    return into


def _sum_unpriced(rows: list[dict]) -> dict:
    """Calls of a model with no price, by model, summed over rows."""
    out: dict[str, int] = {}
    for r in rows:
        _add_unpriced(out, _unpriced(r))
    return out


def _minus(a: dict, b: dict) -> dict:
    return {m: n - b.get(m, 0) for m, n in a.items() if n - b.get(m, 0) > 0}


def _spend(usd: float, calls: int, un: dict, places: int = 2) -> str:
    """A priced amount, a floor (`at least`) when calls are not priced; no priced call at all
    is `not priced`, never $0.00."""
    return "not priced" if un and not calls else usd_text(usd, un, places)


def _hints(models) -> list[str]:
    return [f"{m} has no price: add it under prices: in chantier.yaml (exact id: {m})"
            for m in models]


def _cost_rows(repo: Repo, d: dict, host: str, uuids: list[str]) -> list[dict]:
    """Every Foreman of the batch, summed, from its opening to now: `pause` ends no window, a
    call made after it is spend. A call of a model with no price is counted in the row's
    `unpriced`, not refused."""
    prices = _prices(repo, host)
    rows: list[dict] = []
    chiefs = chief_sessions(d)
    # a Driver is an agent the log ties to a CR, the stack or a QA order; any other agent with no
    # parent is the steering session's own subagent
    drivers = {e["agent"] for e in read_events(repo.batch_dir(d["id"]))
               if e.get("kind") == "agent" and e.get("agent")}
    for uuid in uuids:
        steering = uuid in chiefs  # a Chief of Staff's own steering window
        if host == "copilot":
            got = costs.copilot_session_costs(uuid)  # no timestamps: the whole session
        else:
            since, until = _window(d, uuid)
            got = costs.session_costs(costs.transcript_path(repo.session_root, uuid), since, until,
                                      kind="chief-of-staff" if steering else "foreman",
                                      allow_empty=len(uuids) > 1, split=steering, prices=prices,
                                      steering=(since, until) if steering and uuid in _claimed(d)
                                      else None)
        if steering:
            got[0]["type"] = "chief-of-staff"
            got = costs.without_spec_writers(got)  # grill and specifications: their own line
        for r in got:
            if r["agent"] != "main" and "parent" in r and not r["parent"] \
                    and r["agent"] not in drivers:
                r["own"] = OWN_CHIEF if steering else OWN_FOREMAN
        rows += got
    if not any(r["calls"] for r in rows):
        raise ChantierError("no priced calls in the Foreman transcripts", EXIT_EXTERNAL)
    return rows


def _window(d: dict, uuid: str) -> tuple[str, str]:
    """The part of a steering transcript that belongs to the batch's steering: a Foreman's from
    the batch's opening (its startup is the batch's), the Chief of Staff's from its claim; each
    ends where the next claim begins. A batch with no recorded claims has no end."""
    claims = d.get("foreman_claims") or []
    names = [c["transcript"] for c in claims]
    if uuid not in names:
        return d.get("created", ""), ""
    i = names.index(uuid)
    since = claims[i]["since"] if uuid in chief_sessions(d) else d.get("created", "")
    return since, claims[i + 1]["since"] if i + 1 < len(claims) else ""


def _claimed(d: dict) -> list[str]:
    return [c["transcript"] for c in d.get("foreman_claims") or []]


def _foreman_uuid(d: dict) -> list[str]:
    uuids = d.get("foreman_transcripts") or [d.get("foreman_transcript")]
    if not uuids[0]:
        raise ChantierError("no Foreman transcript recorded", EXIT_PRECONDITION)
    return uuids


OWN_CHIEF = "Chief of Staff's own subagents"
OWN_FOREMAN = "Foreman's own subagents"
STEER_OUT = "Chief of Staff, steering the batch (outside the budget)"
GRILL_OUT = "Chief of Staff, grill and specifications with the user (outside the budget)"
WHOLE = "Chief of Staff, whole session"


def _chief_unknown(cause: str) -> list[str]:
    """The Chief of Staff's lines when nothing can be measured: unknown, never $0.00."""
    why = f"unknown: {cause}" if cause.startswith("not measured") else f"unknown ({cause})"
    return [f"{STEER_OUT}: {why}", f"{GRILL_OUT}: {why}",
            f"{WHOLE}: {why}" + ("; compactions: not measured on this host"
                                 if "this host" in cause else "")]


def _chief_line(repo: Repo, d: dict) -> list[str]:
    """The Chief of Staff's session, priced apart from the spend and the budget, in the lines
    that add up: what it spent since the batch opened, steering and grilling apart, and the whole
    session. What a direct batch's steering row holds is that row's, never counted twice."""
    chiefs = chief_sessions(d)
    if d.get("host") == "copilot":
        return _chief_unknown("not measured on this host")
    if not chiefs:
        return _chief_unknown("no Chief of Staff transcript recorded")
    prices = _prices(repo, d["host"])
    steer = [0, 0.0, {}]  # calls, dollars, calls not priced, since the batch opened, the steering
    grill = [0, 0.0, {}]  # row's own left out
    writers = untimed = compactions = 0
    whole_usd, context, inside_calls, whole_un = 0.0, 0, 0, {}
    for uuid in chiefs:  # every Chief of Staff session of the batch, summed
        path = costs.transcript_path(repo.session_root, uuid)
        try:
            window = _window(d, uuid) if uuid in _claimed(d) else None  # strict rule inside it
            whole = costs.session_costs(path, kind="chief-of-staff", prices=prices)
            since = costs.session_costs(path, d.get("created", ""), kind="chief-of-staff",
                                        allow_empty=True, split=True, prices=prices,
                                        steering=window)
            steered = costs.without_spec_writers(costs.session_costs(
                path, *window, kind="chief-of-staff", allow_empty=True, split=True,
                prices=prices, steering=window)) if window else []
        except ChantierError as e:
            return _chief_unknown(str(e))
        main = since[0]
        for r in since:
            if costs.is_spec_writer(r):
                writers += 1
                grill[0] += r["calls"]
                grill[1] += r["usd"]
                _add_unpriced(grill[2], _unpriced(r))
            else:
                steer[0] += r["calls"]
                steer[1] += r["usd"]
                _add_unpriced(steer[2], _unpriced(r))
        grill[0] += main["grill"]["calls"]
        grill[1] += main["grill"]["usd"]
        _add_unpriced(grill[2], _unpriced(main["grill"]))
        compactions += main["compactions"]
        untimed += main["untimed"]
        inside = sum(r["usd"] for r in steered)  # the steering row: counted in the spend
        inside_un = _sum_unpriced(steered)
        steer[0] -= sum(r["calls"] for r in steered)
        steer[1] -= inside
        steer[2] = _minus(steer[2], inside_un)
        inside_calls += sum(r["calls"] for r in steered) + sum(inside_un.values())
        whole_usd += sum(r["usd"] for r in whole) - inside
        _add_unpriced(whole_un, _minus(_sum_unpriced(whole), inside_un))
        context = whole[0]["last_context"]  # the current session's, the last
    lines = []
    steer_held = steer[0] + sum(steer[2].values())
    why = lambda n, un: f"{n} calls" + (f"; {not_priced(un)}" if un else "")  # noqa: E731
    if not steer_held and untimed:  # the only calls of this part cannot be placed: unknown, not $0.00
        lines.append(f"{STEER_OUT}: unknown ({untimed} calls without a time, not placed)")
    elif steer_held or not inside_calls:  # a direct batch's steering is its row, not a line
        lines.append(f"{STEER_OUT}: {_spend(steer[1], steer[0], steer[2])} since the batch "
                     f"opened ({why(steer[0], steer[2])})")
    lines += [f"{GRILL_OUT}: {_spend(grill[1], grill[0], grill[2])} since the batch opened "
              f"({why(grill[0], grill[2])}, {writers} spec-writers)",
              f"{WHOLE}: {_spend(whole_usd, 1, whole_un)}, context {context:,} tokens; not "
              f"counted: {compactions} compactions since the batch opened, which leave no record "
              f"(about ${COMPACTION_USD:.2f} each)"
              + (f"; {not_priced(whole_un)}" if whole_un else "")]
    if untimed and steer_held:
        lines.append(f"Chief of Staff: {untimed} calls without a time, not placed")
    return lines + _hints(sorted(_add_unpriced(_add_unpriced(dict(steer[2]), grill[2]), whole_un)))


def _cost_groups(repo: Repo, batch: str, rows: list[dict], by: str) -> dict[str, list]:
    """Calls and dollars, by CR (`cr`) or by the Driver type a chain of parents leads back to."""
    agent_cr = {}  # every Driver a CR ever had, from the log: a replaced one keeps its CR
    qa_folder = {o["id"]: o["cr"] for o in read_batch(repo, batch).get("orders", [])
                 if o["kind"] == "qa"}  # a QA driver counts under its QA folder
    for e in read_events(repo.batch_dir(batch)):
        if e.get("kind") == "agent" and e.get("cr") and e["cr"] != "stack" and e.get("agent"):
            agent_cr[e["agent"]] = qa_folder.get(e["cr"], e["cr"])
    parents = {r["agent"]: r.get("parent") for r in rows}
    by_agent = {r["agent"]: r for r in rows if r["agent"] != "main"}

    def cr_of(agent: str | None, hops: int = 0) -> str | None:
        """A worker counts for the CR of the Driver that started it."""
        if agent is None or hops > 5:
            return None
        return agent_cr.get(agent) or cr_of(parents.get(agent), hops + 1)

    groups: dict[str, list] = defaultdict(lambda: [0, 0.0, {}])  # calls, dollars, not priced
    for r in rows:
        if by == "cr":
            named = CR_IN_NAME.search(r.get("description") or "")
            key = ("foreman" if r["agent"] == "main" or r.get("own")
                   else cr_of(r["agent"]) or (named.group(0) if named else "other"))
        else:  # "driver": the type of the agent a chain of parents leads back to
            root = r
            for _ in range(5):
                parent = by_agent.get(root.get("parent"))
                if root["agent"] == "main" or parent is None or parent["agent"] == "main":
                    break
                root = parent
            # the steering session's main row, a Foreman's or a Chief of Staff's, is never a Driver
            key = "foreman" if root.get("own") or root["agent"] == "main" else root["type"]
        groups[key][0] += r["calls"]
        groups[key][1] += r["usd"]
        _add_unpriced(groups[key][2], _unpriced(r))
    return groups


def _apportion(parts: list[float], whole: int) -> list[int]:
    """Whole units for each part, summing to `whole` exactly (largest remainder)."""
    sizes = sum(parts)
    exact = [whole * p / sizes if sizes else 0.0 for p in parts]
    out = [int(x) for x in exact]
    order = sorted(range(len(parts)), key=lambda i: out[i] - exact[i])
    for i in order[:whole - sum(out)] if sizes else []:
        out[i] += 1
    return out


COMPACTION_USD = 0.12  # what a compaction call costs, about: it leaves no record to price


def _kind(r: dict) -> str:
    """Who an agent is, from the record alone: the Foreman is the main agent, a Driver an agent
    with no parent, a worker one with a parent. No role name: the type is the host's own string.
    Where the host gives no parent link (Copilot), the agent is only an agent."""
    if r["agent"] == "main" or r.get("own"):
        return "Foreman"  # the steering session, and its own subagents; `_label` says whose
    if "parent" not in r:
        return "Agent"
    return "Worker" if r["parent"] else "Driver"


STEERING = "Chief of Staff, steering the batch"
UNSPLIT = "Chief of Staff, steering the batch, grill included (not split on this host)"


def _label(r: dict) -> str:
    """The steering row of a direct batch is the Chief of Staff's, a Foreman's is the Foreman's;
    their own subagents have a line of their own."""
    if r.get("own"):
        return r["own"]
    if r["agent"] == "main" and r.get("type") == "chief-of-staff":
        return STEERING if "grill" in r else UNSPLIT  # Copilot rows are not split
    return _kind(r)


def _steers(mains: list[dict]) -> str:
    names = list(dict.fromkeys(_label(r) for r in mains))
    return " and ".join(names) or "Foreman"


def _breakdown(rows: list[dict]) -> list[dict]:
    """One entry for the Foreman, then one per Driver type, per worker type (and per agent type
    where the parent link is not measured), each with its own calls and dollars only."""
    entries: dict[tuple[str, str], dict] = {}
    for r in rows:
        kind = _kind(r)
        e = entries.setdefault((kind, _label(r) if kind == "Foreman" else r["type"]), {
            "kind": kind, "label": _label(r) if kind == "Foreman" else f"{kind} {r['type']}",
            "rows": [], "calls": 0, "usd": 0.0, "unpriced": {}})
        e["rows"].append(r)
        e["calls"] += r["calls"]
        e["usd"] += r["usd"]
        _add_unpriced(e["unpriced"], _unpriced(r))
    order = ("Foreman", "Driver", "Worker", "Agent")
    return sorted((e for e in entries.values() if e["calls"] or e["unpriced"]),
                  key=lambda e: (order.index(e["kind"]), -e["usd"]))


def _restarted(repo: Repo, batch: str) -> set[str]:
    """The Drivers that came after another on the same CR, from the log's `agent` events."""
    seen: dict[str, list[str]] = {}
    for e in read_events(repo.batch_dir(batch)):
        if e.get("kind") == "agent" and e.get("cr") and e["cr"] != "stack" and e.get("agent"):
            ids = seen.setdefault(e["cr"], [])
            if e["agent"] not in ids:
                ids.append(e["agent"])
    return {a for ids in seen.values() for a in ids[1:]}


def _explain(entry: dict, restarted: set[str]) -> str:
    """What explains a line's figure, all measured; `not measured` where the host gives none."""
    rows = [r for r in entry["rows"] if r["calls"] or _unpriced(r)]
    n = len(rows)
    parts = [f"{n} agent{'s' if n != 1 else ''}, {entry['calls']} calls"]
    if not all("models" in r for r in rows):  # Copilot: per-call records, no token detail
        parts.append("model, shares of cost and calls after the cache expired: not measured")
    else:
        models = sorted(set().union(*(r["models"] for r in rows)))
        unpriced = set(entry["unpriced"])
        parts.append("model " + ", ".join(f"{m} (not priced)" if m in unpriced else m
                                          for m in models))
        total = sum(r["usd"] for r in rows)
        kinds = [sum(r[k] for r in rows) for k in ("usd_read", "usd_write", "usd_out", "usd_in")]
        shares = _apportion(kinds, 100) if total else [0] * 4
        parts.append("cost" + (" of the priced calls" if entry["unpriced"] else "") + ": "
                     + ", ".join(f"{name} {s}%" for name, s in zip(
                         ("cache reads", "cache writes", "output", "input"), shares)))
        timed, expired = sum(r["timed"] for r in rows), sum(r["expired"] for r in rows)
        parts.append(f"{expired} of {timed} timed calls after the cache expired" if timed
                     else "calls after the cache expired: not measured (no timestamps)")
    if entry["kind"] == "Driver":
        parts.append(f"{sum(r['agent'] in restarted for r in rows)} restarted on a CR that "
                     "already had one")
    elif entry["kind"] == "Agent":
        parts.append("restarts: not measured (no parent link)")
    return "  " + "; ".join(parts)


EXPIRY_NOTE = ("A cache has expired when the gap from the agent's previous call is over its "
               "lifetime: 5 min after a 5-minute cache write, 1 h after a 1-hour one")


def _cost_summary(d: dict, rows: list[dict], by_cr: dict[str, list],
                  by_driver: dict[str, list], chief: list[str]) -> list[str]:
    """What the user reads at the end of a batch; the detail is in `cost`. The split is the
    breakdown of `cost` summed by kind: the Foreman, the Drivers alone, the workers alone. The
    per-Driver figures say "with its workers". Amounts and shares add up as printed."""
    total = sum(r["usd"] for r in rows)
    un = _sum_unpriced(rows)  # calls of a model with no price: every figure is then a floor
    budget = d.get("budget_usd")
    entries = _breakdown(rows)
    mains = [r for r in rows if r["agent"] == "main"]  # one per steering session of the batch
    steer = _steers(mains)
    kinds = [(name, sum(e["usd"] for e in entries if e["kind"] == kind),
              _sum_unpriced([r for e in entries if e["kind"] == kind for r in e["rows"]]))
             for name, kind in ((steer, "Foreman"), ("Drivers", "Driver"),
                                ("workers", "Worker"), ("agents, Driver or worker not measured",
                                                         "Agent"))]
    kinds = [k for k in kinds if k[1] or k[2] or k[0] in (steer, "Drivers", "workers")]
    parts = [usd for _, usd, _ in kinds]
    cents = _apportion(parts, round(total * 100))
    shares = _apportion(parts, 100) if total else [0] * len(parts)
    split = ", ".join(f"{name} {usd_text(c / 100, kun)} ({'not measured' if un else f'{s}%'})"
                      for (name, _, kun), c, s in zip(kinds, cents, shares))
    measured = all("parent" in r for r in rows if r["agent"] != "main")
    top = sorted(((k, v[1], v[2]) for k, v in by_cr.items() if k != "foreman"),
                 key=lambda kv: -kv[1])
    n = sum(r.get("wakes", 0) for r in mains)
    wakes = [f"{steer}: {n} wakes, context "
             f"{sum(r.get('wake_context', 0) for r in mains) // n:,} tokens on average, "
             f"{max(r.get('peak_context', 0) for r in mains):,} at its peak"] if n else []
    lines = [f"Total: {usd_text(total, un)}" + (f" of a ${budget:g} budget" if budget else ", no budget")
             + (f"; {not_priced(un)}" if un else ""),
             split,
             "Most: " + (", ".join(f"{k} {usd_text(usd, kun)}" for k, usd, kun in top[:3]) or "-"),
             *wakes,
             *(f"Driver {k} with its workers: {usd_text(v[1], v[2])} ({v[0]} calls"
               + (f"; {not_priced(v[2])}" if v[2] else "") + ")" for k, v in
               sorted(by_driver.items(), key=lambda kv: -kv[1][1])
               if k != "foreman" and measured),
             *_hints(sorted(un)),
             *chief,
             f"Not counted: compaction calls, which leave no record (about ${COMPACTION_USD:.2f} "
             "each)"]
    return list(dict.fromkeys(lines))  # a model the Chief of Staff shares gets one hint


def _orchestration(d: dict, rows: list[dict], shares: list[int], un: dict) -> str:
    """The ratio of orchestration: the steering session (its own subagents with it) and the
    Drivers, from the shares printed on the lines, so the figures add up as printed."""
    head = "Orchestration (steering + Drivers):"
    if d.get("host") == "copilot":  # a Driver cannot be told from a worker there
        return f"{head} not measured (no parent link on this host)"
    if un:
        return f"{head} not measured (calls not priced)"
    kinds = [e["kind"] for e in _breakdown(rows)]
    return f"{head} {sum(s for k, s in zip(kinds, shares) if k in ('Foreman', 'Driver'))}% of the batch's spend"


def cost(args) -> list[str]:
    """The batch's spend, read from the Foreman's transcript on the batch's host; `status
    --refresh` and `pause` record it."""
    repo = Repo.find()
    batch = resolve_batch(repo, args.batch)
    d = read_batch(repo, batch)
    if not (d.get("foreman_transcripts") or d.get("foreman_transcript")):
        var = "$COPILOT_AGENT_SESSION_ID" if d["host"] == "copilot" else "$CLAUDE_CODE_SESSION_ID"
        raise ChantierError(f"no Foreman transcript recorded: the Foreman runs "
                            f"`chantier foreman transcript {var}`")
    rows = _cost_rows(repo, d, d["host"], _foreman_uuid(d))
    total = sum(r["usd"] for r in rows)
    un = _sum_unpriced(rows)
    chief = _chief_line(repo, d)
    if args.summary:
        return _cost_summary(d, rows, _cost_groups(repo, batch, rows, "cr"),
                             _cost_groups(repo, batch, rows, "driver"), chief)
    if args.explain and args.by == "cr":
        raise ChantierError("`--explain` explains the breakdown by role, not `--by cr`")
    if args.by == "cr":  # a CR's Driver and its workers
        lines = [(k, v[0], v[1], None, v[2]) for k, v in
                 sorted(_cost_groups(repo, batch, rows, "cr").items(), key=lambda kv: -kv[1][1])]
    else:  # the Foreman, each Driver type, each worker type: their own calls and dollars
        restarted = _restarted(repo, batch) if args.explain else set()
        lines = [(e["label"], e["calls"], e["usd"], _explain(e, restarted) if args.explain else None,
                  e["unpriced"]) for e in _breakdown(rows)]
    mills = ([round(usd * 1000) for _, _, usd, _, _ in lines] if args.by == "cr"  # each CR's own
             else _apportion([usd for _, _, usd, _, _ in lines], round(total * 1000)))  # add up
    shares = None if args.by == "cr" else _apportion([usd for _, _, usd, _, _ in lines], 100)
    estimated = sum(r.get("estimated", 0) for r in rows)
    calls_all = sum(r["calls"] for r in rows)
    out = [f"{batch}: at least ${total:.3f} over {calls_all} priced model calls; {not_priced(un)}"
           if un else f"{batch}: ${total:.3f} over {calls_all} model calls"
           + (f" ({estimated} estimated, not billed)" if estimated else "")]
    for i, ((label, calls, _, why, lun), m) in enumerate(zip(lines, mills)):
        share = None if shares is None else "share not measured" if un else f"{shares[i]}%"
        detail = ([f"{calls} calls" + (f", {share}" if share else "")] if calls or not lun else []) \
            + ([not_priced(lun)] if lun else [])
        out += [f"{label}: {_spend(m / 1000, calls, lun, 3)} ({'; '.join(detail)})"] \
            + ([why] if why else [])
    if shares is not None:
        out.append(_orchestration(d, rows, shares, un))
    out += _hints(sorted(un))
    out += chief
    if args.explain:
        n = sum(r.get("compactions", 0) for r in rows)
        out += [EXPIRY_NOTE if all("models" in r for r in rows) else
                "Cache expiry: not measured on this host",
                f"Not counted: {n} compaction calls, which leave no record (about "
                f"${COMPACTION_USD:.2f} each, ${n * COMPACTION_USD:.2f})" if all(
                    "compactions" in r for r in rows) else
                "Not counted: compaction calls are not measured on this host"]
    return list(dict.fromkeys(out))  # a model the Chief of Staff shares gets one hint
