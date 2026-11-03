"""The `chantier` commands. Each returns the lines to print; errors raise ChantierError with an exit code."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from . import __version__, costs, forge, procs
from .decide import decide, fill_slots
from .lifecycle import (PRIORITIES, STAGES, changes_lock, cr_directory, ensure_unclaimed,
                        move_backlog_item, prepared_cr, return_cr, stage_layout, stored_layout)
from .models import (CR_IN_NAME, INHERIT, ROLES, Models, copilot_events, copilot_session,
                     copilot_spawns, detect_host)
from .state import (DONE, EXIT_CONFLICT, EXIT_EXTERNAL, EXIT_PRECONDITION, EXIT_USAGE, LIVE,
                    Batch, ChantierError,
                    Repo, age_minutes, check_epoch, default_branch, find_cr_batch, git,
                    move_directory, next_cr_number, now, project_path, read_batch, resolve_batch)

DRIVER_AGENTS = ("cr-driver", "stack-driver", "qa-driver")
AGENT_VERSION = re.compile(r"^# chantier-agent: (\S+)$", re.M)


def skill_dir() -> Path:
    """The skill folder: `CHANTIER_SKILL_DIR`, else the nearest parent of this file with SKILL.md."""
    env = os.environ.get("CHANTIER_SKILL_DIR")
    if env:
        return Path(env).resolve()
    for p in Path(__file__).resolve().parents:
        if (p / "SKILL.md").exists():
            return p
    raise ChantierError("cannot find the chantier skill folder; set CHANTIER_SKILL_DIR", EXIT_PRECONDITION)


PLUGIN_NAME = "chantier"


def plugin_root() -> Path | None:
    """The Claude Code plugin this skill ships in, or None for a skill installed on its own.

    `CHANTIER_PLUGIN_ROOT` wins (empty: no plugin); else the folder two levels above the skill,
    when it holds `.claude-plugin/plugin.json`.
    """
    env = os.environ.get("CHANTIER_PLUGIN_ROOT")
    if env is not None:
        return Path(env).resolve() if env else None
    root = skill_dir().parents[1]
    return root if (root / ".claude-plugin" / "plugin.json").exists() else None


COPILOT_PLUGIN_AGENTS = "com.github.copilot/agents"


def plugin_agent(name: str, host: str = "claude") -> Path | None:
    """The plugin's own agent file for a role on this host, if this skill ships in the plugin."""
    root = plugin_root()
    if not root:
        return None
    path = (root / "agents" / f"{name}.md" if host == "claude"
            else root / COPILOT_PLUGIN_AGENTS / f"{name}.agent.md")
    return path if path.exists() else None


# `- chantier [<host>] <role> agent: <path>` selects the repository's own agent.
CUSTOM_AGENT = re.compile(r"^[ \t]*(?:[-*][ \t]+)?chantier[ \t]+"
                          r"(?:(?P<host>claude|copilot)[ \t]+)?(?P<role>[A-Za-z-]+)[ \t]+agent:"
                          r"[ \t]*(?P<path>.*?)[ \t]*$", re.M | re.I)


def custom_agents(repo: Repo, host: str) -> dict[str, Path]:
    """Roles this host runs with the repository's own agent files, from AGENTS.md."""
    f = repo.root / "AGENTS.md"
    if not f.exists():
        return {}
    out: dict[str, Path] = {}
    for m in CUSTOM_AGENT.finditer(f.read_text(encoding="utf-8")):
        if m["host"] and m["host"].lower() != host:
            continue
        role, raw = m["role"].lower(), m["path"].strip("`")
        if role not in ROLES or role == "foreman":
            raise ChantierError(f"AGENTS.md: `chantier {role} agent:` is not a role a Driver "
                                f"spawns (roles: {', '.join(r for r in ROLES if r != 'foreman')})")
        if not raw or re.search(r"[,\s]", raw):
            raise ChantierError(f"AGENTS.md: `chantier {role} agent:` takes one agent file, "
                                f"got `{raw}`")
        if role in out:
            raise ChantierError(f"AGENTS.md: two {host} agents for chantier {role}")
        path = project_path(repo.root, raw, f"chantier {host} {role} agent")
        directory = repo.root / (".claude/agents" if host == "claude" else ".github/agents")
        if path.parent != directory or not path.name.endswith(
                ".md" if host == "claude" else ".agent.md"):
            raise ChantierError(f"AGENTS.md: a {host} agent must be a file in "
                                f"{directory.relative_to(repo.root).as_posix()}")
        out[role] = path
    return out


@dataclass
class AgentRef:
    """The agent a role runs: `custom` (AGENTS.md), `local`, or `plugin`."""

    kind: str
    name: str
    path: Path | None


def _agent_id(path: Path, host: str) -> str:
    """How the host names an agent file: Copilot by its file name, Claude by its `name:`."""
    if host == "copilot":
        return path.name.removesuffix(".md").removesuffix(".agent")
    m = re.search(r"^name:[ \t]*(\S+)[ \t]*$", path.read_text(encoding="utf-8"), re.M)
    return m[1].strip("\"'") if m else path.stem


def resolve_agent(repo: Repo, host: str, role: str) -> AgentRef:
    """The repository's own agent, else a local copy, else the plugin's agent."""
    custom = custom_agents(repo, host).get(role)
    if custom:
        return AgentRef("custom", _agent_id(custom, host) if custom.exists() else custom.stem,
                        custom)
    local = agent_path(repo, host, role)
    if local.exists():
        return AgentRef("local", _agent_id(local, host), local)
    shipped = plugin_agent(role, host)
    if shipped:
        return AgentRef("plugin", f"{PLUGIN_NAME}:{role}" if host == "claude" else role, shipped)
    return AgentRef("missing", role, None)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "cr"


# ---- agents and preflight ---------------------------------------------------------------------

def load_models(repo: Repo, host: str) -> Models:
    refs = {role: resolve_agent(repo, host, role) for role in ROLES}
    paths = {role: ref.path for role, ref in refs.items()}
    custom = {role for role, ref in refs.items() if ref.kind in ("custom", "local")}
    return Models(host, paths, custom)


def agent_path(repo: Repo, host: str, name: str) -> Path:
    if host == "copilot":
        return repo.root / ".github" / "agents" / f"{name}.agent.md"
    return repo.root / ".claude" / "agents" / f"{name}.md"


def _version_of(path: Path) -> str | None:
    m = AGENT_VERSION.search(path.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def _skill_version() -> str | None:
    m = re.search(r"^chantier-version: (\S+)$",
                  (skill_dir() / "SKILL.md").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else None


def preflight(args) -> tuple[list[str], int]:
    lines, ok = [], True

    def check(tag: str, passed: bool, good: str, bad: str):
        nonlocal ok
        ok &= passed
        lines.append(f"{tag} {'ok  ' if passed else 'FAIL'} {good if passed else bad}")

    try:
        host = detect_host()[0]
    except ChantierError:
        host = None
    entry = os.environ.get("CLAUDE_CODE_ENTRYPOINT", "")
    if host == "copilot":
        sid = os.environ.get("COPILOT_AGENT_SESSION_ID", "")
        check("P1", bool(sid), "host is Copilot (P2: create_session and send_message must load)",
              "host is Copilot but COPILOT_AGENT_SESSION_ID is empty: not a Copilot agent session")
    else:
        check("P1", entry == "claude-desktop", "host is Claude Desktop",
              f"host is {entry or 'unknown'} (CLAUDE_CODE_ENTRYPOINT), not claude-desktop "
              "or a Copilot SDK host")
    try:
        repo = Repo.find(Path(os.getcwd()))
    except ChantierError as e:
        repo = None
        check("P6", False, "", str(e))
    if repo:
        host = host or "claude"
        try:
            models = load_models(repo, host)
            model_errors = models.errors
        except ChantierError as e:
            models, model_errors = None, [str(e)]
        try:
            refs = {n: resolve_agent(repo, host, n) for n in ROLES}
        except ChantierError as e:
            refs, model_errors = {}, [*model_errors, str(e)]
        try:
            _batch_context(repo, None)
        except ChantierError as e:
            model_errors = [*model_errors, str(e)]
        missing = [n for n, r in refs.items() if r.kind == "missing"]
        no_custom = [f"{n} ({r.path})" for n, r in refs.items()
                     if r.kind == "custom" and not r.path.exists()]
        ours = {n: r for n, r in refs.items() if r.kind == "plugin"}
        stale = [n for n, r in ours.items() if _version_of(r.path) != __version__]
        no_ttl = [n for n, r in ours.items() if host == "claude" and n in DRIVER_AGENTS
                  and "cacheTtl: 1h" not in r.path.read_text(encoding="utf-8")]
        problems = ([f"missing {', '.join(missing)} (install the chantier plugin or copy "
                     "its static agent files into the repository)"]
                    if missing else []) + \
                   ([f"AGENTS.md names a missing agent: {', '.join(no_custom)}"]
                    if no_custom else []) + \
                   ([f"old plugin agent {', '.join(stale)}"] if stale else []) + \
                   ([f"no 1h cache in {', '.join(no_ttl)}"] if no_ttl else [])
        check("P4", not problems, "every role has a current agent",
              "; ".join(problems) + "; then restart the session")
        check("P8", not model_errors, f"agent models readable for {host}", "; ".join(model_errors))
    has_uv = shutil.which("uv") is not None
    sv = _skill_version()
    check("P5", has_uv and sv == __version__, f"chantier {__version__}, uv found",
          f"uv {'found' if has_uv else 'missing'}; CLI {__version__}, SKILL.md {sv}")
    if repo:
        top = Path(git("rev-parse", "--show-toplevel", check=False) or ".").resolve()
        check("P6", top == repo.root.resolve(), f"in the main checkout of {repo.root.name}",
              f"session folder {top} is not the repository root {repo.root}")
        gitdir = Path(git("rev-parse", "--path-format=absolute", "--git-dir", check=False)
                      or ".").resolve()
        common = (repo.root / ".git").resolve()
        check("P7", gitdir == common, "not a linked worktree",
              "this session runs in a linked worktree: the Foreman must start in the main checkout")
        instructions = repo.root / "AGENTS.md"
        check("P9", instructions.is_file(), "project AGENTS.md is available",
              "AGENTS.md is missing: ask the user for project instructions before starting")
    lines.append("P2, P3 and 'not unattended' are the Chief of Staff's own checks")
    lines.append("preflight passed" if ok else "preflight FAILED: start nothing")
    return lines, 0 if ok else EXIT_PRECONDITION


# ---- batches and CRs --------------------------------------------------------------------------

def _layout_args(repo: Repo, args) -> dict[str, Path]:
    overrides = {stage: getattr(args, stage) for stage in STAGES
                 if getattr(args, stage, None) is not None}
    return stage_layout(repo, overrides)


def file_cr(args) -> list[str]:
    repo = Repo.find()
    paths = _layout_args(repo, args)
    if args.item.startswith("@"):
        source = Path(args.item[1:]).expanduser()
        if not source.is_absolute():
            source = repo.root / source
        try:
            raw = source.read_bytes()
            text = raw.decode("utf-8")
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
    folder = paths["inbox"] / slug
    with changes_lock(repo):
        paths["inbox"].mkdir(parents=True, exist_ok=True)
        try:
            folder.mkdir()
        except FileExistsError as e:
            raise ChantierError(f"CR folder already exists: {folder}; choose another slug",
                                EXIT_CONFLICT) from e
        try:
            (folder / "intake").mkdir()
            (folder / "intake" / "request.md").write_bytes(raw)
        except OSError as e:
            raise ChantierError(f"could not finish filing {folder}; preserve it for recovery: {e}",
                                EXIT_EXTERNAL) from e
    return [f"filed {folder.relative_to(repo.root)}; write the intent and grill the CR here"]


def triage(args) -> list[str]:
    repo = Repo.find()
    paths = _layout_args(repo, args)
    with changes_lock(repo):
        target = move_backlog_item(repo, args.item, args.priority, paths)
    return [f"triaged {target.relative_to(repo.root)} ({args.priority})"]


def abandon(args) -> list[str]:
    repo = Repo.find()
    paths = _layout_args(repo, args)
    source = project_path(repo.root, args.item, "CR folder")
    in_backlog = source.parent.parent == paths["backlog"] and source.parent.name in PRIORITIES
    if source.parent not in (paths["inbox"], paths["requests"]) and not in_backlog:
        raise ChantierError("only an inbox, backlog, or unclaimed active CR can be abandoned",
                            EXIT_USAGE)
    with changes_lock(repo):
        ensure_unclaimed(repo, source)
        target = paths["trash"] / source.name
        move_directory(source, target)
    return [f"abandoned {target.relative_to(repo.root)}"]


def cr_path(args) -> list[str]:
    repo = Repo.find()
    batch = find_cr_batch(repo, args.cr, args.batch)
    data = read_batch(repo, batch)
    cr = next((c for c in data["crs"] if c["id"] == args.cr), None)
    if cr is None:
        raise ChantierError(f"unknown CR {args.cr} in batch {batch}", EXIT_USAGE)
    path = cr_directory(repo, batch, cr)
    if not path.is_dir():
        raise ChantierError(f"{args.cr}: recorded CR folder is missing: {path}")
    if args.spec:
        specification = cr.get("specification")
        if not specification or Path(specification).name != specification:
            raise ChantierError(f"{args.cr}: no valid Change Specification was recorded; "
                                "inspect the legacy CR folder")
        path = path / specification
        if not path.is_file():
            raise ChantierError(f"{args.cr}: recorded Change Specification is missing: {path}")
    return [path.relative_to(repo.root).as_posix() if args.relative else str(path)]


def _base_ref(repo: Repo) -> str:
    remote, branch = repo.config["remote"], repo.config["default_branch"]
    if not branch:
        raise ChantierError("the batch has no default branch; consult AGENTS.md and migrate or "
                            "reopen the batch")
    if remote not in git("remote", cwd=repo.root).split():
        raise ChantierError(f"no remote {remote!r}; check AGENTS.md or ask the user", EXIT_EXTERNAL)
    git("fetch", "--quiet", remote, branch, cwd=repo.root)
    ref = f"{remote}/{branch}"
    git("rev-parse", "--verify", ref, cwd=repo.root)
    return ref


def add_cr(b: Batch, item: str, qa: bool = False) -> dict:
    """Move a prepared CR into requests, then create its branch and worktree."""
    repo = b.repo
    paths = stage_layout(repo)
    prepared = prepared_cr(repo, item, paths)
    ensure_unclaimed(repo, prepared.directory)
    number = next_cr_number(repo, (paths["requests"], paths["archives"]))
    cr_id = f"CR-{number}"
    slug = re.sub(r"^(?:CR-)?\d+-", "", prepared.directory.name, flags=re.I)
    cdir = paths["requests"] / f"{number:03d}-{_slug(slug)}"
    origin = prepared.directory.relative_to(repo.root).as_posix()
    b.move(prepared.directory, cdir)
    specification = cdir / prepared.specification.name
    text, title = specification.read_text(encoding="utf-8"), prepared.title
    (cdir / "scratch").mkdir(parents=True, exist_ok=True)
    task = cdir / "task.md"
    if not task.exists():
        task.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    branch = f"chantier/{b.id}/{cr_id.lower()}-{_slug(title)}"
    worktree = None
    if not b.data.get("no_worktrees"):
        worktree = repo.worktrees / f"{b.id}-{cr_id}"
        worktree.parent.mkdir(parents=True, exist_ok=True)
        base = _base_ref(repo)
        head = git("rev-parse", base, cwd=repo.root)
        git("worktree", "add", "--quiet", "-b", branch, str(worktree), base, cwd=repo.root)
        b.created_worktree(worktree, branch, head)
    order = max((c["order"] for c in b.data["crs"]), default=0) + 1
    c = {"id": cr_id, "title": title, "item": item, "status": "queued", "order": order,
         "path": cdir.relative_to(repo.root).as_posix(), "origin": origin,
         "specification": specification.name, "priority": prepared.priority,
         "round": 0, "qa": qa, "qa_done": False, "agent": None, "pr": None, "ci": None,
         "branch": branch, "worktree": str(worktree) if worktree else None, "pgids": [], "pids": [],
         "notes": [], "resumes": 0, "updated": now()}
    state = cdir / "STATE.md"
    if not state.exists():
        state.write_text(f"# {cr_id}: {title}\n\nInitial record; use `chantier status` for "
                         f"current state.\n\n- batch: {b.id}\n- branch: `{branch}`\n"
                         f"- worktree: `{c['worktree']}`\n- status: queued\n", encoding="utf-8")
    b.data["crs"].append(c)
    b.log("add", cr_id, title=title, path=c["path"], origin=origin)
    return c


def open_batch(args) -> list[str]:
    repo = Repo.find()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", args.batch):
        raise ChantierError("batch id: lowercase letters, digits and hyphens", EXIT_USAGE)
    if not (repo.root / "AGENTS.md").is_file():
        raise ChantierError("AGENTS.md is missing: ask the user for the project instructions")
    if args.slots < 1 or (args.budget is not None and args.budget <= 0):
        raise ChantierError("slots and budget must be positive", EXIT_USAGE)
    if args.max_rounds < 1 or args.stale_minutes < 1 or args.first_cr_number < 1:
        raise ChantierError("round limit, stale interval and first CR number must be positive",
                            EXIT_USAGE)
    for kind, gates in (("fast", args.fast_gate), ("long", args.long_gate)):
        if not gates or any(not gate.strip() for gate in gates):
            raise ChantierError(f"no {kind} gate supplied: read AGENTS.md and ask the user "
                                f"if it is unclear; pass --{kind}-gate")
    paths = _layout_args(repo, args)
    qa_all = args.qa == "all"
    try:
        qa_idx = set() if qa_all or not args.qa else {int(i) for i in args.qa.split(",")}
    except ValueError as e:
        raise ChantierError("QA must be 'all' or comma-separated item numbers", EXIT_USAGE) from e
    if any(i < 1 or i > len(args.items) for i in qa_idx):
        raise ChantierError("QA item numbers must refer to the selected CRs", EXIT_USAGE)
    branch = args.default_branch or default_branch(repo.root, args.remote)
    if not branch:
        raise ChantierError(f"Git does not know the default branch of {args.remote!r}: "
                            "read AGENTS.md or ask the user, then pass --default-branch")
    selected = [prepared_cr(repo, item, paths).directory for item in args.items]
    if len(set(selected)) != len(selected):
        raise ChantierError("the same CR was selected more than once", EXIT_USAGE)
    settings = {"remote": args.remote, "default_branch": branch, "first_cr_number": args.first_cr_number,
                "worktrees_dir": args.worktrees_dir or "",
                "forge": "github", "max_rounds": args.max_rounds, "stale_minutes": args.stale_minutes,
                "gates": {"fast": args.fast_gate, "long": args.long_gate},
                "layout": stored_layout(repo, paths), "claude_projects_dir": args.claude_projects_dir}
    data = {"id": args.batch, "version": __version__, "created": now(), "status": "open",
            "mode": "stack" if args.stack else "parallel", "slots": args.slots,
            "budget_usd": args.budget, "spent_usd": 0.0, "paused": False,
            "foreman": None, "foreman_epoch": 0, "foreman_transcript": None, "chief_of_staff": args.chief_of_staff,
            "no_worktrees": args.no_worktrees, "stack_live": False, "heartbeat": None,
            "settings": settings, "orders": [], "crs": []}
    with changes_lock(repo):
        with Batch(repo, args.batch, actor="chief-of-staff", create=data) as b:
            brief = b.dir / "brief.md"
            if brief.exists() or brief.is_symlink():
                raise ChantierError(f"refusing to overwrite an existing batch brief: {brief}",
                                    EXIT_CONFLICT)
            for i, item in enumerate(args.items, 1):
                add_cr(b, item, qa=qa_all or i in qa_idx)
            brief.write_text(f"# Batch {args.batch}\n\n- Mode: {data['mode']}. Slots: {args.slots}. "
                             f"Budget: {args.budget or 'none'}.\n- CRs, in order:\n" +
                             "".join(f"  - {c['id']}: {c['title']} ({c['path']})"
                                     f"{' (QA)' if c['qa'] else ''}\n" for c in b.data["crs"]) +
                             "- Project instructions: AGENTS.md and its referenced guidelines.\n"
                             f"- Fast gates: {', '.join(args.fast_gate)}\n"
                             f"- Long gates: {', '.join(args.long_gate)}\n"
                             "- Night policy card: one extra round per CR; a red PR goes to the top.\n"
                             "- Autonomous decisions:\n- Questions to bring back:\n", encoding="utf-8")
            b.log("open", None, crs=[c["id"] for c in b.data["crs"]])
    lines = [f"opened {args.batch}: {len(args.items)} CRs, {args.slots} slots, {data['mode']}"]
    lines += [f"{c['id']} {c['title'][:60]}" for c in b.data["crs"]]
    lines.append(f"brief: {brief.relative_to(repo.root)}")
    return lines


def add(args) -> list[str]:
    repo = Repo.find()
    with changes_lock(repo):
        with Batch(repo, resolve_batch(repo, args.batch), actor="chief-of-staff") as b:
            c = add_cr(b, args.item, qa=args.qa)
    return [f"added {c['id']} {c['title'][:60]} (queued)"]


# ---- the Foreman and orders -------------------------------------------------------------------

def foreman(args) -> list[str]:
    repo = Repo.find()
    batch = resolve_batch(repo, args.batch)
    if args.action == "get":
        d = read_batch(repo, batch)
        return [f"{d.get('foreman') or 'none'} epoch {d.get('foreman_epoch', 0)}"]
    with Batch(repo, batch, actor="chief-of-staff" if args.action == "set" else "foreman") as b:
        if args.action == "set":
            if not args.value:
                raise ChantierError("foreman set <session-id>", EXIT_USAGE)
            b.data["foreman"] = args.value
            b.data["foreman_epoch"] = b.data.get("foreman_epoch", 0) + 1
            b.data["foreman_transcript"] = None
            b.log("foreman", None, session=args.value, epoch=b.data["foreman_epoch"])
            return [f"foreman {args.value} epoch {b.data['foreman_epoch']}"]
        check_epoch(b, args.epoch)
        claimed = b.data.get("foreman_transcript")
        if claimed and claimed != args.value:
            # One epoch, one Foreman: a second session that starts as Foreman must not take over.
            raise ChantierError(f"epoch {b.data.get('foreman_epoch', 0)} of batch {b.id} is already run "
                           f"by transcript {claimed}; stop now", EXIT_CONFLICT)
        b.data["foreman_transcript"] = args.value
        b.log("foreman-transcript", None, transcript=args.value)
        return [f"transcript {args.value}"]


ORDER_KINDS = {"add", "drop", "first", "change", "merged", "pause", "resume"}


def order(args) -> list[str]:
    if args.kind not in ORDER_KINDS:
        raise ChantierError(f"order kind: one of {', '.join(sorted(ORDER_KINDS))}", EXIT_USAGE)
    if args.kind == "add" and not (args.note or "").startswith("@"):
        raise ChantierError("order add needs --note @<prepared-CR-folder-or-specification>",
                            EXIT_USAGE)
    repo = Repo.find()
    with Batch(repo, resolve_batch(repo, args.batch), actor="chief-of-staff") as b:
        oid = f"O-{len(b.data['orders']) + 1}"
        b.data["orders"].append({"id": oid, "kind": args.kind, "cr": args.cr or "-",
                                 "note": args.note or "", "sent": now(), "done": None})
        b.log("order", None if args.cr in (None, "-") else args.cr, order=oid, order_kind=args.kind)
    target = f" {args.cr}" if args.cr and args.cr != "-" else ""
    note = f" {args.note}" if args.note else ""
    return [f"[chief-of-staff→foreman] order {oid} {args.kind}{target}{note}"]


def event(args) -> list[str]:
    repo = Repo.find()
    batch = resolve_batch(repo, args.batch)
    with changes_lock(repo):
        with Batch(repo, batch, actor="foreman") as b:
            check_epoch(b, args.epoch)
            kind, cr, note = args.kind, args.cr, args.note or ""
            if args.order:
                o = next((x for x in b.data["orders"] if x["id"] == args.order), None)
                if o is None:
                    raise ChantierError(f"unknown order {args.order}", EXIT_USAGE)
                kind, cr, note = f"order-{o['kind']}", o["cr"], note or o["note"]
            if cr not in ("-", "stack") and not cr.startswith("qa:"):
                b.cr(cr)
            b.data["heartbeat"] = now()
            return decide(b, cr, kind, note, order=args.order)


def heartbeat(args) -> list[str]:
    repo = Repo.find()
    with Batch(repo, resolve_batch(repo, args.batch), actor="foreman") as b:
        check_epoch(b, args.epoch)
        b.data["heartbeat"] = now()
        b.log("heartbeat", None)
        pending = [o for o in b.data["orders"] if not o["done"]]
        live = [c for c in b.data["crs"] if c["status"] in LIVE]
        ages = [age_minutes(c.get("updated")) or 0 for c in live]
    lines = [f"heartbeat {b.id}: {len(live)} live, {len(pending)} orders pending"]
    if pending:
        lines.append(f"oldest pending order {pending[0]['id']} "
                     f"{age_minutes(pending[0]['sent']):.0f} min")
    if ages:
        lines.append(f"oldest silent Driver {max(ages):.0f} min")
    return lines


# ---- state for every role ---------------------------------------------------------------------

def status(args) -> list[str]:
    repo = Repo.find()
    d = read_batch(repo, resolve_batch(repo, args.batch))
    if args.json:
        return [json.dumps(d, indent=2)]
    hb = age_minutes(d.get("heartbeat"))
    lines = [f"{d['id']} {d['status']} {d['mode']} slots {d['slots']} "
             f"foreman {d.get('foreman') or 'none'} e{d.get('foreman_epoch', 0)} "
             f"heartbeat {'never' if hb is None else f'{hb:.0f} min'}"
             f"{' PAUSED' if d.get('paused') else ''} spent ${d.get('spent_usd', 0):.2f}"]
    for c in sorted(d["crs"], key=lambda c: c["order"]):
        row = f"{c['id']} {c['status']} r{c['round']} {c.get('pr') or '-'} ci {c.get('ci') or '-'}"
        if c["status"] == "blocked" and c.get("blocked_reason"):
            row += f" | blocked: {c['blocked_reason'][:70]}"
        elif args.notes and c.get("notes"):
            row += f" | {c['notes'][-1][:60]}"
        lines.append(row)
    pending = sum(1 for o in d.get("orders", []) if not o["done"])
    if pending:
        lines.append(f"{pending} orders pending")
    return lines


def agents(args) -> list[str]:
    repo = Repo.find()
    batch = find_cr_batch(repo, args.cr.removeprefix("qa:"), args.batch) \
        if args.cr != "stack" else resolve_batch(repo, args.batch)
    if args.action == "get":
        d = read_batch(repo, batch)
        if args.cr == "stack":
            return [d.get("stack_agent") or "none"]
        c = next(x for x in d["crs"] if x["id"] == args.cr.removeprefix("qa:"))
        return [(c.get("qa_agent") if args.cr.startswith("qa:") else c.get("agent")) or "none"]
    with Batch(repo, batch, actor="foreman") as b:
        check_epoch(b, args.epoch)
        if args.cr == "stack":
            b.data["stack_agent"] = args.agent
        else:
            c = b.cr(args.cr.removeprefix("qa:"))
            b.touch(c, **({"qa_agent": args.agent} if args.cr.startswith("qa:")
                          else {"agent": args.agent}))
        b.log("agent", args.cr, agent=args.agent)
    return [f"{args.cr} → {args.agent}"]


REPORT_KINDS = {"pr-opened", "ci-green", "ci-red", "ci-red-known", "round-done", "note"}


def report(args) -> list[str]:
    if args.kind not in REPORT_KINDS:
        raise ChantierError(f"report kind: one of {', '.join(sorted(REPORT_KINDS))}", EXIT_USAGE)
    repo = Repo.find()
    with Batch(repo, find_cr_batch(repo, args.cr, args.batch), actor="driver") as b:
        c = b.cr(args.cr)
        note = args.note or ""
        if args.kind == "pr-opened":
            b.touch(c, pr=note.split()[0] if note else c.get("pr"))
        elif args.kind.startswith("ci-"):
            b.touch(c, ci=args.kind.removeprefix("ci-"))
        elif args.kind == "round-done":
            b.touch(c, round=c.get("round", 0) + 1)
        else:
            b.touch(c)
        if note and args.kind != "pr-opened":
            c.setdefault("notes", []).append(f"{args.kind}: {note}")
        b.log("report", args.cr, report=args.kind, note=note)
    return ["ok"]


# ---- work in the CR worktree ------------------------------------------------------------------

def _worktree(c: dict) -> Path:
    if not c.get("worktree") or not Path(c["worktree"]).exists():
        raise ChantierError(f"{c['id']} has no worktree", EXIT_PRECONDITION)
    return Path(c["worktree"])


def _track_pgid(repo: Repo, batch: str, cr: str, pgid: int, add: bool, key: str = "pgids") -> None:
    """Record a process group (gates) or a pid (`chantier wait`) so `chantier cancel` can stop it."""
    with Batch(repo, batch, actor="cli") as b:
        c = b.cr(cr)
        pg = set(c.get(key, []))
        (pg.add if add else pg.discard)(pgid)
        c[key] = sorted(pg)
        b.log(f"{key[:-1]}-add" if add else f"{key[:-1]}-done", cr, **{key[:-1]: pgid})


def gate(args) -> tuple[list[str], int]:
    repo = Repo.find()
    batch = find_cr_batch(repo, args.cr, args.batch)
    data = read_batch(repo, batch)
    c = next(x for x in data["crs"] if x["id"] == args.cr)
    wt = _worktree(c)
    kind = "long" if args.long else "fast"
    gates = data.get("settings", {}).get("gates", {})
    cmds = gates.get(kind) if isinstance(gates, dict) else None
    if not isinstance(cmds, list) or not cmds or any(not isinstance(cmd, str) or not cmd.strip()
                                                   for cmd in cmds):
        raise ChantierError(f"{batch}: no {kind} gate was recorded from AGENTS.md; "
                            "ask the Chief of Staff to resolve it")
    logdir = cr_directory(repo, batch, c) / "scratch" / "gates"
    logdir.mkdir(parents=True, exist_ok=True)
    log = logdir / f"{time.strftime('%Y%m%d-%H%M%S')}-{'long' if args.long else 'fast'}.log"
    with open(log, "w", encoding="utf-8") as f:
        for cmd in cmds:
            f.write(f"$ {cmd}\n")
            f.flush()
            group = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                     if sys.platform == "win32" else {"start_new_session": True})
            p = subprocess.Popen(cmd, shell=True, cwd=wt, stdout=f, stderr=subprocess.STDOUT,
                                 **group)
            _track_pgid(repo, batch, args.cr, p.pid, True)
            try:
                rc = p.wait()
            finally:
                _track_pgid(repo, batch, args.cr, p.pid, False)
            if rc != 0:
                f.flush()
                # gates write in the console's code page: never fail on their bytes
                tail = log.read_text(encoding="utf-8", errors="replace").splitlines()[-8:]
                return ([f"FAIL {cmd} (exit {rc}); log {log.relative_to(repo.root)}"] + tail,
                        EXIT_EXTERNAL)
    return [f"pass {len(cmds)} {'long' if args.long else 'fast'} gates; "
            f"log {log.relative_to(repo.root)}"], 0


def wait(args) -> tuple[list[str], int]:
    if args.what != "ci":
        raise ChantierError("wait: only `ci` is supported; run long suites with `chantier gate --long`",
                       EXIT_USAGE)
    repo = Repo.find()
    batch = find_cr_batch(repo, args.cr, args.batch)
    c = next(x for x in read_batch(repo, batch)["crs"] if x["id"] == args.cr)
    if not c.get("pr"):
        raise ChantierError(f"{args.cr} has no PR yet", EXIT_PRECONDITION)
    interval = float(os.environ.get("CHANTIER_WAIT_INTERVAL", "60"))
    pid = os.getpid()  # our own pid only: our process group may hold the Driver's shell
    _track_pgid(repo, batch, args.cr, pid, True, "pids")
    deadline = time.monotonic() + args.max
    try:
        while True:
            checks = forge.pr_checks(c.get("worktree") or repo.root, repo.config, c["pr"])
            pending = [x for x in checks if x.get("bucket") == "pending"]
            if checks and not pending:
                failed = [x["name"] for x in checks if x.get("bucket") in {"fail", "cancel"}]
                result = "fail" if failed else "pass"
                break
            if time.monotonic() >= deadline:
                result, failed = "timeout", []
                break
            time.sleep(interval)
    finally:
        _track_pgid(repo, batch, args.cr, pid, False, "pids")
    with Batch(repo, batch, actor="driver") as b:
        b.touch(b.cr(args.cr), ci={"pass": "green", "fail": "red"}.get(result, "pending"))
        b.log("wait", args.cr, result=result)
    lines = [f"ci {result} {c['pr']}"] + ([f"failed: {', '.join(failed)}"] if failed else [])
    return lines, 0 if result == "pass" else (EXIT_EXTERNAL if result == "fail" else 0)


def ci_classify(args) -> list[str]:
    repo = Repo.find()
    batch = find_cr_batch(repo, args.cr, args.batch)
    c = next(x for x in read_batch(repo, batch)["crs"] if x["id"] == args.cr)
    if not c.get("pr"):
        raise ChantierError(f"{args.cr} has no PR yet", EXIT_PRECONDITION)
    if not repo.config.get("default_branch"):
        raise ChantierError("the batch has no default branch; consult AGENTS.md and migrate or "
                            "reopen the batch")
    cwd = c.get("worktree") or repo.root
    checks = forge.pr_checks(cwd, repo.config, c["pr"])
    red = forge.main_failures(cwd, repo.config, repo.config["default_branch"])
    logs = {x["name"]: forge.failed_log(cwd, repo.config, x.get("link", ""))
            for x in checks if x.get("bucket") == "fail"}
    tag = forge.classify(checks, red, logs)
    with Batch(repo, batch, actor="driver") as b:
        b.log("ci-classify", args.cr, tag=tag)
    failed = [x for x in checks if x.get("bucket") in {"fail", "cancel"}]
    return [tag] + [f"{x['name']} {x.get('link', '')}" for x in failed[:5]]


def _stack_base(b_data: dict, c: dict, repo: Repo) -> str:
    """In stack mode, a CR sits on the previous live CR of the stack; else on the default."""
    default = repo.config["default_branch"]
    if not default:
        raise ChantierError("the batch has no default branch; consult AGENTS.md and migrate or "
                            "reopen the batch")
    if b_data["mode"] != "stack":
        return default
    order = [x for x in sorted(b_data["crs"], key=lambda x: x["order"])
             if x["status"] not in {"cancelled", "merged", "landed"}]
    ids = [x["id"] for x in order]
    i = ids.index(c["id"]) if c["id"] in ids else 0
    return order[i - 1]["branch"] if i > 0 else default


def ship(args) -> list[str]:
    repo = Repo.find()
    batch = find_cr_batch(repo, args.cr, args.batch)
    d = read_batch(repo, batch)
    c = next(x for x in d["crs"] if x["id"] == args.cr)
    wt = _worktree(c)
    dirty = git("status", "--porcelain", "--untracked-files=normal", cwd=wt)
    if dirty:
        what = ("untracked files" if all(ln.startswith("??") for ln in dirty.splitlines())
                else "uncommitted changes")
        raise ChantierError(f"{args.cr}: {what} in the worktree; commit them (or add them to "
                       f".gitignore) first: "
                       f"{' '.join(ln.split(maxsplit=1)[-1] for ln in dirty.splitlines()[:5])}")
    body = cr_directory(repo, batch, c) / "pr-body.md"
    if not body.is_file():
        raise ChantierError(f"write {body.relative_to(repo.root)} before `chantier ship`")
    remote = repo.config["remote"]
    if remote not in git("remote", cwd=wt).split():
        raise ChantierError(f"no remote {remote!r}", EXIT_EXTERNAL)
    base = _stack_base(d, c, repo)
    git("fetch", "--quiet", remote, cwd=wt)
    onto = f"{remote}/{base}" if base == repo.config["default_branch"] else base
    rb = subprocess.run(["git", "rebase", onto], cwd=wt, capture_output=True, text=True,
                        encoding="utf-8", errors="replace",
                        env={**os.environ, "GIT_EDITOR": "true"})
    if rb.returncode != 0:
        subprocess.run(["git", "rebase", "--abort"], cwd=wt, capture_output=True)
        raise ChantierError(f"{args.cr}: rebase on {onto} failed; aborted: "
                       f"{rb.stdout.strip()[-200:]}", EXIT_EXTERNAL)
    git("push", "--quiet", "--force-with-lease", "-u", remote, c["branch"], cwd=wt)
    if c.get("pr"):
        forge.pr_edit(wt, repo.config, c["pr"], body_file=str(body), base=base)
        link, verb = c["pr"], "updated"
    else:
        link = forge.pr_create(wt, repo.config, base, c["branch"], args.title or c["title"],
                               str(body))
        verb = "opened"
    with Batch(repo, batch, actor="driver") as b:
        b.touch(b.cr(args.cr), pr=link, ci="pending")
        b.log("ship", args.cr, pr=link, base=base)
    return [f"{verb} {link} (base {base})"]


def stack(args) -> list[str]:
    repo = Repo.find()
    batch = resolve_batch(repo, args.batch)
    if args.action == "order":
        with Batch(repo, batch, actor="stack") as b:
            for i, cr in enumerate(args.crs, 1):
                b.touch(b.cr(cr), order=i)
            b.log("stack-order", None, crs=args.crs)
        return [f"stack order: {' → '.join(args.crs)}"]
    d = read_batch(repo, batch)
    if d["mode"] != "stack":
        raise ChantierError(f"batch {batch} is not a stack")
    affected = []
    for c in sorted(d["crs"], key=lambda x: x["order"]):
        if c["status"] in {"cancelled", "merged", "landed"} or not c.get("pr"):
            continue
        ship(type("A", (), {"cr": c["id"], "batch": batch, "title": None})())
        affected.append(c["id"])
        d = read_batch(repo, batch)
    with Batch(repo, batch, actor="stack") as b:
        b.log("restack", None, crs=affected)
    return [f"restacked {len(affected)}: {' '.join(affected) or 'none'}"]


def qa(args) -> list[str]:
    repo = Repo.find()
    with Batch(repo, find_cr_batch(repo, args.cr, args.batch), actor="qa") as b:
        c = b.cr(args.cr)
        if args.action == "start":
            b.touch(c, status="qa")
            b.log("qa-start", args.cr)
            return ["ok"]
        n = 0
        if args.findings:
            text = Path(args.findings).read_text(encoding="utf-8")
            n = sum(1 for ln in text.splitlines() if ln.lstrip().startswith(("- ", "* ")))
            c["qa_findings"] = str(Path(args.findings).resolve())
        b.touch(c)
        b.log("qa-done", args.cr, findings=n)
    return [f"qa done {args.cr}: {n} findings; tell the Foreman: "
            f"[qa {args.cr}→foreman] qa done {args.cr} {n} findings"]


def cancel(args) -> list[str]:
    repo = Repo.find()
    with changes_lock(repo):
        with Batch(repo, find_cr_batch(repo, args.cr, args.batch), actor="foreman") as b:
            check_epoch(b, args.epoch)
            c = b.cr(args.cr)
            killed = []
            for pg in c.get("pgids", []):
                if procs.stop_group(pg):
                    killed.append(f"pg{pg}")
            killed += [str(p) for p in procs.stop(c.get("pids", []))]
            if c.get("worktree") and Path(c["worktree"]).exists():
                killed += [str(p) for p in procs.stop(procs.find(Path(c["worktree"])))]
            return_cr(b, c)
            b.touch(c, status="cancelled", agent=None, pgids=[], pids=[])
            b.log("cancel", args.cr, killed=killed, path=c.get("path"))
            actions = fill_slots(b)
    return [f"cancelled {args.cr}; stopped {len(killed)}: {' '.join(killed) or 'none'}"] + actions


def land(args) -> list[str]:
    repo = Repo.find()
    batch = resolve_batch(repo, args.batch)
    with Batch(repo, batch, actor="foreman") as b:
        check_epoch(b, args.epoch)
        live = [c["id"] for c in b.data["crs"] if c["status"] in LIVE]
        pending = [o["id"] for o in b.data["orders"] if not o["done"]]
        queued = [c["id"] for c in b.data["crs"] if c["status"] == "queued"]
        open_ = [c["id"] for c in b.data["crs"] if c["status"] in {"ready", "blocked"}]
        if live or pending or queued or open_ or b.data.get("stack_live"):
            raise ChantierError(f"cannot land {batch}: live {live or '-'}, queued {queued or '-'}, "
                           f"not merged {open_ or '-'}, orders pending {pending or '-'}, "
                           f"stack driver {'live' if b.data.get('stack_live') else 'done'}")
        cleaned, retained = [], []
        for c in b.data["crs"]:
            if c["status"] == "cancelled":
                if c.get("worktree") and Path(c["worktree"]).exists():
                    retained.append(f"{c['id']} worktree and branch (cancelled)")
                continue
            if c["status"] != "merged" or not c.get("worktree"):
                continue
            if Path(c["worktree"]).exists():
                git("worktree", "remove", c["worktree"], cwd=repo.root)
                cleaned.append(c["id"])
            if git("rev-parse", "--verify", "--quiet", c["branch"], cwd=repo.root, check=False):
                result = subprocess.run(["git", "branch", "-d", c["branch"]], cwd=repo.root,
                                        capture_output=True, text=True, encoding="utf-8",
                                        errors="replace")
                if result.returncode:
                    retained.append(f"{c['id']} branch ({result.stderr.strip()})")
        rows = "".join(f"| {c['id']} | {c['title']} | {c['status']} | {c.get('pr') or '-'} | "
                       f"{c['round']} |\n" for c in sorted(b.data["crs"], key=lambda c: c["order"]))
        report_path = b.dir / "report.md"
        report_path.write_text(
            f"# Batch {batch}: report\n\n- Landed: {now()}\n- Spent: ${b.data.get('spent_usd', 0):.2f}"
            f"\n- Retained: {', '.join(retained) or 'none'}"
            f"\n\n| CR | Title | Status | PR | Rounds |\n| --- | --- | --- | --- | ---: |\n{rows}",
            encoding="utf-8")
        b.data["status"] = "landed"
        b.log("land", None, cleaned=cleaned, retained=retained)
    lines = [f"landed {batch}: cleaned {len(cleaned)} worktrees",
             f"report: {report_path.relative_to(repo.root)}"]
    if retained:
        lines.append(f"retained for manual review: {'; '.join(retained)}")
    return lines


def cost(args) -> list[str]:
    repo = Repo.find()
    batch = resolve_batch(repo, args.batch)
    d = read_batch(repo, batch)
    host, _ = detect_host(args.host)
    uuid = args.transcript or d.get("foreman_transcript")
    if not uuid:
        var = "$COPILOT_AGENT_SESSION_ID" if host == "copilot" else "$CLAUDE_CODE_SESSION_ID"
        raise ChantierError(f"no Foreman transcript recorded: the Foreman runs "
                       f"`chantier foreman transcript {var}`")
    if host == "copilot":
        rows = costs.copilot_session_costs(uuid)
    else:
        rows = costs.session_costs(costs.transcript_path(repo.root, uuid, repo.config))
        if not rows:
            raise ChantierError(f"transcript {uuid} not found under {costs.projects_dir(repo.config)}",
                           EXIT_EXTERNAL)
    agent_cr = {}
    for c in d["crs"]:
        if c.get("agent"):
            agent_cr[c["agent"]] = c["id"]
        if c.get("qa_agent"):
            agent_cr[c["qa_agent"]] = c["id"]
    total = sum(r["usd"] for r in rows)
    if args.update:
        with Batch(repo, batch, actor="foreman") as b:
            b.data["spent_usd"] = round(total, 4)
            b.log("cost", None, usd=total)
    groups: dict[str, list] = defaultdict(lambda: [0, 0.0])
    for r in rows:
        if args.by == "cr":
            named = CR_IN_NAME.search(r.get("description") or "")
            key = ("foreman" if r["agent"] == "main"
                   else agent_cr.get(r["agent"]) or (named.group(0) if named else "other"))
        else:
            key = r["type"]
        groups[key][0] += r["calls"]
        groups[key][1] += r["usd"]
    estimated = sum(r.get("estimated", 0) for r in rows)
    lines = [f"{batch}: ${total:.3f} over {sum(r['calls'] for r in rows)} model calls"
             + (f" ({estimated} estimated, not billed)" if estimated else "")]
    lines += [f"{k}: ${v[1]:.3f} ({v[0]} calls)"
              for k, v in sorted(groups.items(), key=lambda kv: -kv[1][1])]
    return lines


# ---- models -----------------------------------------------------------------------------------

def _batch_context(repo: Repo, batch: str | None) -> tuple[dict, dict]:
    """The batch and its agent id → CR map, or empty ones without a batch."""
    try:
        batch_id = resolve_batch(repo, batch)
    except ChantierError:
        if batch:
            raise
        return {}, {}
    brief = repo.batch_dir(batch_id) / "brief.md"
    if brief.exists():
        for line in brief.read_text(encoding="utf-8").splitlines():
            if line.lstrip().startswith("- Models"):
                value = line.split("):", 1)[1] if "):" in line else line.split(":", 1)[-1]
                if value.strip():
                    raise ChantierError("brief model overrides are no longer supported: "
                                        "use a repository agent instead", EXIT_PRECONDITION)
    d = read_batch(repo, batch_id)
    agent_cr = {}
    for c in d.get("crs", []):
        for key in ("agent", "qa_agent"):
            if c.get(key):
                agent_cr[c[key]] = c["id"]
    return d, agent_cr


def models_cmd(args) -> tuple[list[str], int]:
    repo = Repo.find()
    host, why = detect_host(args.host)
    models = load_models(repo, host)
    if args.action == "check":
        errors = list(models.errors)
        if not errors:
            try:
                _batch_context(repo, args.batch)
                for role in ROLES:
                    ref = resolve_agent(repo, host, role)
                    if ref.kind == "custom" and not ref.path.exists():
                        errors.append(f"AGENTS.md names a missing agent: {ref.path}")
            except ChantierError as e:
                errors.append(str(e))
        if errors:
            return [f"models FAILED ({host}): start nothing"] + errors, EXIT_PRECONDITION
        return [f"models ok ({host}): {len(ROLES)} static or repository agents"], 0
    if models.errors:
        return [f"models FAILED ({host}): run `chantier models check`"] + models.errors, \
            EXIT_PRECONDITION
    data, agent_cr = _batch_context(repo, args.batch)
    if args.action == "show":
        groups: dict[str, list[str]] = defaultdict(list)
        for role in ROLES:
            src = models.source[role]
            effort = models.effort_of(role)
            label = role + (f" [{effort}]" if effort else "")
            groups["custom agent decides" if src == "custom agent" else models.role(role)].append(label)
        lines = [f"{host} models (host from {why}); exact ids only; [effort] when set"]
        lines += [f"{mid}: {', '.join(roles)}" for mid, roles in groups.items()]
        lines.append(f"heartbeat: {models.heartbeat}")
        return lines, 0
    if args.action == "get":
        if not args.role:
            raise ChantierError("models get <role> [--cr CR-n]", EXIT_USAGE)
        pinned = models.role(args.role)
        level = models.effort_of(args.role)
        if args.role != "foreman":
            ref = resolve_agent(repo, host, args.role)
            if ref.kind in ("custom", "local"):
                if not ref.path.exists():
                    raise ChantierError(f"agent for {args.role} not found: {ref.path}",
                                        EXIT_PRECONDITION)
                rel = ref.path.relative_to(repo.root).as_posix()
                origin = "from AGENTS.md" if ref.kind == "custom" else "repository copy"
                return ["model: omit (the repository's own agent decides)",
                        "effort: omit (the repository's own agent decides)",
                        f"agent: {ref.name} ({origin}: {rel}; spawn this agent exactly)"], 0
            if ref.kind == "missing":
                raise ChantierError(f"no agent for {args.role}: install the chantier plugin",
                                    EXIT_PRECONDITION)
            effort = (f"effort: omit (the agent file sets {level})" if level
                      else "effort: omit (the user's setting)")
            return [f"model: omit (the agent file sets {pinned})", effort,
                    f"agent: {ref.name} (spawn this agent exactly)"], 0
        if host == "copilot":
            effort = (f"effort: omit ({level} is in the agent file; create_session cannot set "
                      "it, so the session's effort applies: accepted exception)" if level
                      else "effort: omit (the user's setting)")
        else:
            effort = (f"effort: {level} (copy this level exactly)" if level
                      else "effort: omit (the user's setting)")
        model = ("model: omit (inherit)" if pinned == INHERIT
                 else f"model: {pinned} (agent file; copy this id exactly)")
        return [model, effort, f"heartbeat: {models.heartbeat} ({models.heartbeat_seconds()} s)"], 0
    # audit
    if host != "copilot":
        raise ChantierError("models audit reads Copilot event logs only", EXIT_USAGE)
    batch = data.get("id")
    foreman_uuid = data.get("foreman_transcript")
    session = (args.session or foreman_uuid or os.environ.get("COPILOT_AGENT_SESSION_ID"))
    if not session:
        raise ChantierError("models audit --session <copilot session id>", EXIT_USAGE)
    refs = {role: resolve_agent(repo, host, role) for role in ROLES}
    agent_roles = {ref.name: role for role, ref in refs.items()}
    spawns = copilot_spawns(copilot_events(session), agent_roles)
    bad, unchecked = [], 0
    notes = []
    if batch and session == foreman_uuid:
        notes, bad = _audit_foreman(models, batch, data, copilot_events(session))
    for s in spawns:
        cr = agent_cr.get(s["agent"]) or s["cr"]
        want = models.role(s["role"])
        if want == INHERIT:
            unchecked += 1
        elif s["model"] != want:
            bad.append(f"MISMATCH {s['role']} {cr or '-'} ran {s['model']}, expected {want} "
                       f"(agent file; selection {s['selection']})")
        level = models.effort_of(s["role"])
        if level and s["effort"] != level:
            bad.append(f"MISMATCH {s['role']} {cr or '-'} ran effort {s['effort']}, "
                       f"expected {level}")
    lines = [f"audit {session}: {len(spawns)} chantier spawns, {len(bad)} mismatched"
             + (f", {unchecked} custom or inherit (not checked)" if unchecked else "")]
    return lines + notes + bad, EXIT_PRECONDITION if bad else 0


def _audit_foreman(models: Models, batch: str, data: dict, events: Path) -> tuple[list[str], list[str]]:
    """The Foreman's own calls and heartbeat. A Foreman started with `create_session` runs at
    the session's effort (the tool takes no effort): reported as a note, not a mismatch."""
    facts = copilot_session(events)
    notes, bad = [], []
    want = models.role("foreman")
    level = models.effort_of("foreman")
    for (model, effort), n in sorted(facts["calls"].items(), key=lambda kv: -kv[1]):
        notes.append(f"foreman ran {model} effort {effort} ({n} calls)")
        if want != INHERIT and model != want:
            bad.append(f"MISMATCH foreman ran {model}, expected {want} (agent file)")
        if level and effort != level:
            notes.append(f"NOTE foreman effort {effort}, configured {level}: create_session "
                         "cannot set it (accepted exception)")
    prompt = f"chantier heartbeat {batch} epoch {data.get('foreman_epoch', 0)}"
    beats = [b for b in facts["schedules"] if b["prompt"] == prompt and b["recurring"]]
    if not beats:
        bad.append(f"MISSING heartbeat: no `/every` schedule with the prompt `{prompt}`")
    elif all(b["interval_ms"] != models.heartbeat_seconds() * 1000 for b in beats):
        bad.append(f"MISMATCH heartbeat every {beats[-1]['interval_ms'] // 1000} s, "
                   f"expected {models.heartbeat} ({models.heartbeat_seconds()} s)")
    return notes, bad
