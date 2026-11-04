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
from pathlib import Path

from . import __version__, costs, forge, procs
from .decide import (check_grant, decide, driver_role, fill_slots, merged, parse_grant,
                     record_asks, release_go, release_merged)
from .lifecycle import (PRIORITIES, changes_lock, cr_directory, ensure_unclaimed,
                        move_backlog_item, prepared_cr, stage_layout, trash_cr)
from .roles import (CR_IN_NAME, DRIVERS, ROLES, agent_for, detect_host, local_agent_file,
                    parse_team, plugin_agent_file)
from .state import (EXIT_BUDGET, EXIT_CONFLICT, EXIT_EXTERNAL, EXIT_PRECONDITION, EXIT_USAGE, LIVE,
                    Batch, ChantierError, Repo, age_minutes, check_epoch, default_branch,
                    _read_json, _retry, find_cr_batch, git, move_directory, next_cr_number, now,
                    project_path, read_batch, resolve_batch, stamp)
from .status import write_dashboard

AGENT_VERSION = re.compile(r"^# chantier-agent: (\S+)$", re.M)
INSTRUCTIONS = ("AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md")
CARDS = {"cr-driver": ("driver", "CR Driver"), "stack-driver": ("driver", "Stack driver"),
         "qa-driver": ("driver", "QA driver"), "release-driver": ("driver", "Release driver"),
         "investigator": ("worker", "Investigator"),
         "coder": ("worker", "Coder"), "inspector": ("worker", "Inspector"),
         "debugger": ("worker", "Debugger"), "verifier": ("worker", "Verifier"),
         "conflict-resolver": ("worker", "Conflict resolver")}


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
        or (root / "plugin.json").exists() else None


def cli_command() -> str:
    """How every agent runs this CLI: the exact command, with the absolute path."""
    return f'uv run --script "{(skill_dir() / "scripts" / "cli" / "chantier.py").as_posix()}"'


def _shown(repo: Repo, path: Path) -> str:
    try:
        return path.relative_to(repo.root).as_posix()
    except ValueError:
        return path.as_posix()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "cr"


def project_instructions(repo: Repo) -> Path | None:
    return next((repo.root / name for name in INSTRUCTIONS if (repo.root / name).is_file()), None)


def _skill_version() -> str | None:
    m = re.search(r"^chantier-version: (\S+)$",
                  (skill_dir() / "SKILL.md").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else None


# ---- preflight --------------------------------------------------------------------------------

def _agent_problems(repo: Repo, host: str) -> list[str]:
    """What stops a role from running here: a missing or old plugin agent."""
    root = plugin_root()
    if not root:
        return ["the chantier plugin is not installed (a skill alone has no agents): install the "
                "plugin and restart the session"]
    problems = []
    for role in ROLES:
        path = plugin_agent_file(root, role, host)
        if not path.is_file():
            problems.append(f"missing plugin agent {_shown(repo, path)}")
        elif (m := AGENT_VERSION.search(path.read_text(encoding="utf-8"))) is None \
                or m[1] != __version__:
            problems.append(f"plugin agent {path.name} is not version {__version__}")
    return problems


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
        check("P1", bool(os.environ.get("COPILOT_AGENT_SESSION_ID")),
              "host is a Copilot agent session",
              "host is Copilot but COPILOT_AGENT_SESSION_ID is empty: not a Copilot agent session")
    else:
        check("P1", entry == "claude-desktop", "host is Claude Desktop",
              f"host is {entry or 'unknown'} (CLAUDE_CODE_ENTRYPOINT), not claude-desktop "
              "or a Copilot agent session")
    try:
        repo = Repo.find(Path(os.getcwd()))
    except ChantierError as e:
        repo = None
        check("P6", False, "", str(e))
    if repo and host:
        problems = _agent_problems(repo, host)
        check("P4", not problems, f"every role has its agent on {host}", "; ".join(problems))
    elif repo:
        check("P4", False, "", "unknown host: no agents to check")
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
        check("P7", gitdir == repo.git_dir, "not a linked worktree",
              "this session runs in a linked worktree: the Foreman must start in the main checkout")
        found = project_instructions(repo)
        check("P8", found is not None, f"project instructions: {found.name if found else ''}",
              f"no {', '.join(INSTRUCTIONS)}: ask the user how the project builds and tests")
        try:
            check("P9", True, f"forge {forge.check(repo.root, repo.config['remote'])}", "")
        except ChantierError as e:
            check("P9", False, "", f"{e} (another remote: `chantier open --remote <name>`)")
    lines.append("P2, P3 and 'not unattended' are the Chief of Staff's own checks")
    lines.append("preflight passed" if ok else "preflight FAILED: start nothing")
    return lines, 0 if ok else EXIT_PRECONDITION


# ---- CR folders -------------------------------------------------------------------------------

def file_cr(args) -> list[str]:
    repo = Repo.find()
    paths = stage_layout(repo)
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
        write_dashboard(repo, paths)
    return [f"filed {_shown(repo, folder)}; write the intent and grill the CR here"]


def triage(args) -> list[str]:
    repo = Repo.find()
    with changes_lock(repo):
        target = move_backlog_item(repo, args.item, args.priority, stage_layout(repo))
        write_dashboard(repo, stage_layout(repo))
    return [f"triaged {_shown(repo, target)} ({args.priority})"]


def abandon(args) -> list[str]:
    repo = Repo.find()
    paths = stage_layout(repo)
    source = project_path(repo.root, args.item, "CR folder")
    in_backlog = source.parent.parent == paths["backlog"] and source.parent.name in PRIORITIES
    in_requests = source.parent.parent == paths["requests"]
    if source.parent != paths["inbox"] and not in_requests and not in_backlog:
        raise ChantierError("only an inbox, backlog, or unclaimed active CR can be abandoned",
                            EXIT_USAGE)
    with changes_lock(repo):
        ensure_unclaimed(repo, source)
        target = paths["trash"] / f"{stamp()}-{source.name}"
        move_directory(source, target)
        write_dashboard(repo, paths)
    return [f"abandoned {_shown(repo, target)}"]


def _batch_cr(repo: Repo, cr_id: str, batch: str | None) -> tuple[str, dict, dict]:
    batch = find_cr_batch(repo, cr_id, batch)
    data = read_batch(repo, batch)
    c = next((x for x in data["crs"] if x["id"] == cr_id), None)
    if c is None:
        raise ChantierError(f"unknown CR {cr_id} in batch {batch}", EXIT_USAGE)
    return batch, data, c


def _work(repo: Repo, c: dict) -> Path:
    """The CR's work folder, inside its own folder: notes, gate logs, the PR body."""
    return cr_directory(repo, c) / "work"


def _specification(repo: Repo, c: dict) -> Path:
    path = cr_directory(repo, c) / c["specification"]
    if not path.is_file():
        raise ChantierError(f"{c['id']}: recorded Change Specification is missing: {path}")
    return path


# ---- batches ----------------------------------------------------------------------------------

def _base_ref(repo: Repo) -> str:
    remote, branch = repo.config["remote"], repo.config["default_branch"]
    if not branch:
        raise ChantierError("the batch has no default branch: open it with --default-branch")
    if remote not in git("remote", cwd=repo.root).split():
        raise ChantierError(f"no remote {remote!r}: open the batch with --remote <remote>",
                            EXIT_EXTERNAL)
    git("fetch", "--quiet", remote, branch, cwd=repo.root)
    ref = f"{remote}/{branch}"
    git("rev-parse", "--verify", ref, cwd=repo.root)
    return ref


def grant_line(release: dict) -> str:
    """What the user allowed the release to do without asking, in one line."""
    n, done = release.get("autonomous", 0), release.get("published", 0)
    return "; ".join([
        f"up to {n} releases without asking ({done} published)" if n
        else "every irreversible action waits for the user's approval",
        f"fixes merged by the CLI once ready ({release['auto_merge']})" if release.get("auto_merge")
        else "the user merges the fixes"])


def add_cr(b: Batch, item: str, qa: bool = False, kind: str = "change") -> dict:
    """Move a prepared CR into requests, then create its branch and worktree."""
    repo = b.repo
    paths = stage_layout(repo)
    prepared = prepared_cr(repo, item, paths)
    ensure_unclaimed(repo, prepared.directory)
    number = next_cr_number(repo, (paths["archives"], paths["trash"], b.dir, *repo.batch_folders()))
    cr_id = f"CR-{number}"
    slug = re.sub(r"^(?:CR-)?\d+-", "", prepared.directory.name, flags=re.I)
    cdir = b.dir / f"{number:03d}-{_slug(slug)}"
    origin = prepared.directory.relative_to(repo.root).as_posix()
    b.move(prepared.directory, cdir)
    title = prepared.title
    branch = f"chantier/{b.id}/{cr_id.lower()}-{_slug(title)}"
    worktree = repo.worktrees / f"{b.id}-{cr_id}"
    worktree.parent.mkdir(parents=True, exist_ok=True)
    base = _base_ref(repo)
    head = git("rev-parse", base, cwd=repo.root)
    git("worktree", "add", "--quiet", "-b", branch, str(worktree), base, cwd=repo.root)
    b.created_worktree(worktree, branch, head)
    order = max((c["order"] for c in b.data["crs"]), default=0) + 1
    c = {"id": cr_id, "title": title, "item": item, "kind": kind, "status": "queued", "order": order,
         "path": cdir.relative_to(repo.root).as_posix(),
         "specification": prepared.specification.name, "priority": prepared.priority,
         "round": 0, "qa": qa, "qa_done": False, "agent": None, "pr": None, "ci": None,
         "branch": branch, "worktree": str(worktree), "pgids": [], "pids": [],
         "notes": [], "resumes": 0, "updated": now()}
    b.data["crs"].append(c)
    b.log("add", cr_id, title=title, path=c["path"], origin=origin)
    return c


def open_batch(args) -> list[str]:
    repo = Repo.find()
    host, _ = detect_host()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", args.batch):
        raise ChantierError("batch id: lowercase letters, digits and hyphens", EXIT_USAGE)
    if args.slots < 1 or (args.budget is not None and args.budget <= 0):
        raise ChantierError("slots and budget must be positive", EXIT_USAGE)
    gates = {"fast": args.fast_gate or [], "long": args.long_gate or []}
    for kind, commands in gates.items():
        if not commands or any(not c.strip() for c in commands):
            raise ChantierError(f"no {kind} gate: read AGENTS.md (ask the user if it is unclear), "
                                f"then pass --{kind}-gate")
    branch = args.default_branch or default_branch(repo.root, args.remote)
    if not branch:
        raise ChantierError(f"Git does not know the default branch of {args.remote!r}: read "
                            "AGENTS.md or ask the user, then pass --default-branch")
    chosen, reviews = parse_team(args.agent or [], args.review or [])
    if host == "claude":  # Copilot names any agent like ours: nothing to look up
        for agent in [*chosen.values(), *(s["agent"] for s in reviews.values())]:
            if ":" not in agent and not local_agent_file(repo.root, agent, host):
                raise ChantierError(f"no agent `{agent}` in .claude/agents or ~/.claude/agents: "
                                    "check its name with the user", EXIT_USAGE)
    where = forge.check(repo.root, args.remote)
    settings = {"default_branch": branch, "remote": args.remote, "gates": gates,
                "agents": chosen, "reviews": reviews,
                "claude_projects_dir": args.claude_projects_dir,
                "max_rounds": repo.config["max_rounds"]}
    repo.config.update(settings)
    paths = stage_layout(repo)
    qa_all = args.qa == "all"
    try:
        qa_idx = set() if qa_all or not args.qa else {int(i) for i in args.qa.split(",")}
    except ValueError as e:
        raise ChantierError("QA must be 'all' or comma-separated item numbers", EXIT_USAGE) from e
    if any(i < 1 or i > len(args.items) for i in qa_idx):
        raise ChantierError("QA item numbers must refer to the selected CRs", EXIT_USAGE)
    release = None
    if args.release is not None:
        if not 1 <= args.release <= len(args.items) or qa_all or args.release in qa_idx:
            raise ChantierError("--release: the item number of the release CR, without QA",
                                EXIT_USAGE)
        release = {"autonomous": args.autonomous_releases, "auto_merge": args.auto_merge_fixes,
                   "published": 0}
        check_grant(release, args.budget)
    elif args.autonomous_releases or args.auto_merge_fixes:
        raise ChantierError("--autonomous-releases and --auto-merge-fixes need --release",
                            EXIT_USAGE)
    selected = [prepared_cr(repo, item, paths).directory for item in args.items]
    if len(set(selected)) != len(selected):
        raise ChantierError("the same CR was selected more than once", EXIT_USAGE)
    data = {"id": args.batch, "version": __version__, "created": now(), "status": "open",
            "host": host, "mode": "stack" if args.stack else "parallel", "slots": args.slots,
            "budget_usd": args.budget, "spent_usd": 0.0, "paused": False,
            "foreman": None, "foreman_epoch": 0, "foreman_transcript": None,
            "chief_of_staff": args.chief_of_staff,
            "stack_live": False, "heartbeat": None, "settings": settings, "orders": [], "crs": [],
            "release": release}
    with changes_lock(repo):
        with Batch(repo, args.batch, actor="chief-of-staff", create=data) as b:
            brief = b.dir / "brief.md"
            for i, item in enumerate(args.items, 1):
                c = add_cr(b, item, qa=qa_all or i in qa_idx,
                           kind="release" if i == args.release else "change")
                if release and c["kind"] == "release":
                    release["cr"] = c["id"]
            custom = [f"{r}={a}" for r, a in chosen.items()]
            custom += [f"{n}={s['agent']} ({s['task']})" for n, s in reviews.items()]
            brief.write_text(
                f"# Batch {args.batch}\n\n- Mode: {data['mode']}. Slots: {args.slots}. "
                f"Budget: {args.budget or 'none'}. Host: {host}. Forge: {where}.\n"
                "- CRs, in order:\n" +
                "".join(f"  - {c['id']}: {c['title']} ({c['path']})"
                        f"{' (QA)' if c['qa'] else ''}"
                        f"{' (release: starts once the others are merged)' if c['kind'] == 'release' else ''}\n"
                        for c in b.data["crs"]) +
                (f"- Release grant: {grant_line(release)}\n" if release else "") +
                f"- Project instructions: {', '.join(n for n in INSTRUCTIONS if (repo.root / n).is_file()) or 'none'}.\n"
                f"- Fast gates: {' ; '.join(settings['gates']['fast'])}\n"
                f"- Long gates: {' ; '.join(settings['gates']['long'])}\n"
                f"- Own agents and review steps: {', '.join(custom) or 'none'}\n"
                "- Night policy: one extra round per CR; a red PR goes to the top.\n"
                "- Autonomous decisions:\n- Questions to bring back:\n", encoding="utf-8")
            b.log("open", None, crs=[c["id"] for c in b.data["crs"]])
    lines = [f"opened {args.batch} on {host}: {len(args.items)} CRs, {args.slots} slots, "
             f"{data['mode']}, forge {where}"]
    lines += [f"{c['id']} {c['title'][:60]}" for c in b.data["crs"]]
    lines.append(f"brief: {brief}")
    return lines


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
        if not args.value:
            raise ChantierError("foreman transcript <session-uuid>", EXIT_USAGE)
        claimed = b.data.get("foreman_transcript")
        if claimed and claimed != args.value:
            # One epoch, one Foreman: a second session that starts as Foreman must not take over.
            raise ChantierError(f"epoch {b.data.get('foreman_epoch', 0)} of batch {b.id} is already run "
                                f"by transcript {claimed}; stop now", EXIT_CONFLICT)
        b.data["foreman_transcript"] = args.value
        b.log("foreman-transcript", None, transcript=args.value)
        return [f"transcript {args.value}"]


ORDER_KINDS = {"add", "drop", "first", "change", "merged", "pause", "resume", "fix", "approve",
               "grant"}


def _check_merged(repo: Repo, args) -> None:
    _, _, c = _batch_cr(repo, args.cr, args.batch)
    if not c.get("pr"):
        raise ChantierError(f"{args.cr} has no PR: nothing to mark merged", EXIT_PRECONDITION)
    if not forge.pr_merged(repo.root, repo.config, c["pr"]):
        raise ChantierError(f"{args.cr}: the forge says {c['pr']} is not merged", EXIT_PRECONDITION)


def order(args) -> list[str]:
    if args.kind not in ORDER_KINDS:
        raise ChantierError(f"order kind: one of {', '.join(sorted(ORDER_KINDS))}", EXIT_USAGE)
    if args.kind in ("add", "fix") and not (args.note or "").startswith("@"):
        raise ChantierError(f"order {args.kind} needs --note @<prepared-CR-folder-or-specification>",
                            EXIT_USAGE)
    if args.kind == "approve" and not (args.note or "").strip():
        raise ChantierError("order approve <release-cr> --note \"<the action the user approved>\"",
                            EXIT_USAGE)
    repo = Repo.find()
    if args.kind == "merged":  # refused here: nothing is archived on a word the forge denies
        _check_merged(repo, args)
    with Batch(repo, resolve_batch(repo, args.batch), actor="chief-of-staff") as b:
        if args.kind in ("fix", "approve", "grant") and \
                (b.data.get("release") or {}).get("cr") != args.cr:
            raise ChantierError(f"order {args.kind} names the batch's release CR "
                                f"({(b.data.get('release') or {}).get('cr') or 'none'})",
                                EXIT_USAGE)
        if args.kind == "grant":  # refused here: a recorded order that fails would stay pending
            grant = parse_grant(args.note)
            check_grant({**b.data["release"], **grant},
                        grant.get("budget_usd") or b.data.get("budget_usd"))
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
            actions = decide(b, cr, kind, note, order=args.order)
            record_asks(b, actions)
            return actions


def heartbeat(args) -> tuple[list[str], int]:
    """The Foreman's wake: liveness, pending orders, and the spend the budget check reads."""
    repo = Repo.find()
    batch = resolve_batch(repo, args.batch)
    with Batch(repo, batch, actor="foreman") as b:
        check_epoch(b, args.epoch)
        b.data["heartbeat"] = now()
        b.log("heartbeat", None)
        pending = [o for o in b.data["orders"] if not o["done"]]
        live = [c for c in b.data["crs"] if c["status"] in LIVE]
        ages = [age_minutes(c.get("updated")) or 0 for c in live]
        data = dict(b.data)
    lines = [f"heartbeat {batch}: {len(live)} live, {len(pending)} orders pending"]
    if pending:
        lines.append(f"oldest pending order {pending[0]['id']} "
                     f"{age_minutes(pending[0]['sent']):.0f} min")
    if ages:
        lines.append(f"oldest silent Driver {max(ages):.0f} min")
    try:
        rows = _cost_rows(repo, data, data["host"], _foreman_uuid(data))
    except ChantierError as e:
        return lines + [f"spend not updated: {e}"], e.code
    with Batch(repo, batch, actor="foreman") as b:
        total = _record_costs(repo, b, rows)
    return lines + [f"spent ${total:.2f}"], 0


def _record_costs(repo: Repo, b: Batch, rows: list[dict]) -> float:
    """The spend the budget check reads, and each CR's share, shown in its STATUS.md."""
    total = sum(r["usd"] for r in rows)
    b.data["spent_usd"] = round(total, 4)
    by_cr = _cost_groups(repo, b.id, rows, "cr")
    for c in b.data["crs"]:
        if c["id"] in by_cr:
            c["cost_usd"] = round(by_cr[c["id"]][1], 4)
    b.log("cost", None, usd=total)
    return total


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
        if c.get("kind") == "release":
            row += f" release{' ' + c['released'] if c.get('released') else ''}"
            row += "".join(f" | draft {p}" for p in c.get("drafts", [])[-2:])
        elif c.get("kind") == "fix":
            row += f" fix for {c['fix_for']}"
        if c["status"] == "blocked" and c.get("blocked_reason"):
            row += f" | blocked: {c['blocked_reason'][:70]}"
        elif args.notes and c.get("notes"):
            row += f" | {c['notes'][-1][:60]}"
        lines.append(row)
    pending = sum(1 for o in d.get("orders", []) if not o["done"])
    if pending:
        lines.append(f"{pending} orders pending")
    unread = sum(1 for a in d.get("asks", []) if not a["read"])
    if unread:
        lines.append(f"{unread} asks unread: `chantier asks`")
    return lines


def asks(args) -> list[str]:
    """The Chief of Staff reads what the Foreman had to tell it, sent or not. With `text`, the
    Foreman records an ask of its own and gets the line to send."""
    repo = Repo.find()
    with Batch(repo, resolve_batch(repo, args.batch),
               actor="foreman" if args.text else "chief-of-staff") as b:
        if args.text:
            text = " ".join(args.text)
            record_asks(b, [f"ask-chief-of-staff {text}"])
            b.log("ask", None, text=text)
            return [f"[foreman→chief-of-staff] ask {text}"]
        unread = [a for a in b.data.get("asks", []) if not a["read"]]
        for a in unread:
            a["read"] = now()
        if unread:
            b.log("asks-read", None, count=len(unread))
    return [f"ask {a['text']}" for a in unread] or ["no unread ask"]


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


def spawn(args) -> list[str]:
    """The agent a role runs for a CR and the whole prompt to give it: the role's contract
    travels in the prompt, so the plugin's agent and a project's own agent get the same one."""
    repo = Repo.find()
    if args.cr == "stack":
        batch = resolve_batch(repo, args.batch)
        d, c = read_batch(repo, batch), None
    else:
        batch, d, c = _batch_cr(repo, args.cr, args.batch)
    agent, task = agent_for(d["settings"], args.role, d["host"], plugin_root())
    if args.role == "stack-driver" and c is not None or args.role != "stack-driver" and c is None:
        raise ChantierError("the stack driver takes `stack`; every other role takes a CR",
                            EXIT_USAGE)
    if c and args.role in ("cr-driver", "release-driver") and args.role != driver_role(c):
        raise ChantierError(f"{c['id']} is driven by the {driver_role(c)}", EXIT_USAGE)
    skill = skill_dir().as_posix()
    card, section = CARDS.get(args.role, ("worker", "Extra review step"))
    what = f"{c['id']} \"{c['title']}\"" if c else "the stack"
    found = project_instructions(repo)
    prompt = [f"chantier {args.role} for {what} of batch {batch}, in the project {repo.root.as_posix()}.",
              f"First read {skill}/references/{card}.md (section \"{section}\") and "
              f"{skill}/references/concepts.md; read nothing else from the skill.",
              f"CLI ($CHANTIER): {cli_command()} <command> --batch {batch}",
              f"Project instructions: {found.as_posix() if found else 'none: ask your parent'}"]
    if c:
        work = _work(repo, c)
        work.mkdir(parents=True, exist_ok=True)
        prompt += [f"Worktree: {c['worktree']}",
                   f"Change Specification: {_specification(repo, c).as_posix()}",
                   f"Work folder: {work.as_posix()} (your notes and outputs)"]
        if args.role == "cr-driver":
            prompt.append(f"Rounds done: {c['round']} of {d['settings']['max_rounds']}")
        if args.role == "release-driver":
            prompt.append(f"Release grant: {grant_line(d['release'])}")
            if c.get("approvals"):
                prompt.append(f"Approved by the user, not yet used: {'; '.join(c['approvals'])}")
        if c.get("kind") == "fix" and args.role == "cr-driver":
            prompt.append(f"A fix the release {c['fix_for']} needs: it starts again once this merges")
    if task:
        prompt.append(f"Your review: {task}")
    reviews = d["settings"].get("reviews", {})
    if args.role == "cr-driver" and reviews:
        prompt.append("Extra review steps, after the Inspector approves, in order: "
                      + "; ".join(f"`$CHANTIER spawn {n} {c['id']}` ({s['task']})"
                                  for n, s in reviews.items()))
    if args.note:
        prompt.append(f"Note: {args.note}")
    mode = "background" if args.role in DRIVERS else "foreground"
    return [f"agent: {agent}", f"mode: {mode}",
            "pass no model and no effort: the agent file sets them", "prompt:"] + prompt


REPORT_KINDS = {"pr-opened", "ci-green", "ci-red", "ci-red-known", "round-done", "note", "draft",
                "investigated", "verified"}


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
        elif args.kind == "round-done":  # the CLI numbers rounds: a new Driver goes on counting
            b.touch(c, round=c.get("round", 0) + 1)
            note = f"r{c['round']} {note}".rstrip()
        elif args.kind == "draft":  # a file the user reviews and edits in place
            path = Path(note).expanduser()
            if not note or not path.is_file():
                raise ChantierError(f"report draft <path of an existing file>, not {note!r}",
                                    EXIT_USAGE)
            note = path.resolve().as_posix()
            if note not in c.setdefault("drafts", []):
                c["drafts"].append(note)
            b.touch(c)
        else:
            b.touch(c)
        if note and args.kind != "pr-opened":
            c.setdefault("notes", []).append(f"{args.kind}: {note}")
        b.log("report", args.cr, report=args.kind, note=note)
    return [f"round {c['round']} of {b.data['settings']['max_rounds']} done"
            if args.kind == "round-done" else "ok"]


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
    batch, data, c = _batch_cr(repo, args.cr, args.batch)
    wt = _worktree(c)
    kind = "long" if args.long else "fast"
    cmds = data["settings"]["gates"].get(kind)
    if not cmds:
        raise ChantierError(f"{batch}: no {kind} gate was recorded; ask the Chief of Staff")
    logdir = _work(repo, c) / "gates"
    logdir.mkdir(parents=True, exist_ok=True)
    log = logdir / f"{time.strftime('%Y%m%d-%H%M%S')}-{kind}.log"
    for cmd in cmds:
        # closed while the gate runs: a `cancel` must be able to move the CR's folder on Windows
        with open(log, "a", encoding="utf-8") as f:
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
            _log_gate(repo, batch, args.cr, kind, "fail", wt)
            # gates write in the console's code page: never fail on their bytes
            tail = (log.read_text(encoding="utf-8", errors="replace").splitlines()[-8:]
                    if log.exists() else [])
            return [f"FAIL {cmd} (exit {rc}); log {log}"] + tail, EXIT_EXTERNAL
    _log_gate(repo, batch, args.cr, kind, "pass", wt)
    return [f"pass {len(cmds)} {kind} gates; log {log}"], 0


def _log_gate(repo: Repo, batch: str, cr: str, kind: str, result: str, wt: Path) -> None:
    with Batch(repo, batch, actor="driver") as b:
        b.log("gate", cr, gate=kind, result=result, head=git("rev-parse", "--short", "HEAD", cwd=wt))


def wait(args) -> tuple[list[str], int]:
    if args.what != "ci":
        raise ChantierError("wait: only `ci` is supported; run long suites with `chantier gate --long`",
                            EXIT_USAGE)
    repo = Repo.find()
    batch, _, c = _batch_cr(repo, args.cr, args.batch)
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
    batch, _, c = _batch_cr(repo, args.cr, args.batch)
    if not c.get("pr"):
        raise ChantierError(f"{args.cr} has no PR yet", EXIT_PRECONDITION)
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
    if b_data["mode"] != "stack":
        return default
    order = [x for x in sorted(b_data["crs"], key=lambda x: x["order"])
             if x["status"] not in {"cancelled", "merged", "landed"}]
    ids = [x["id"] for x in order]
    i = ids.index(c["id"]) if c["id"] in ids else 0
    return order[i - 1]["branch"] if i > 0 else default


def _ship(repo: Repo, batch: str, cr_id: str, title: str | None = None) -> str:
    d = read_batch(repo, batch)
    c = next(x for x in d["crs"] if x["id"] == cr_id)
    wt = _worktree(c)
    dirty = git("status", "--porcelain", "--untracked-files=normal", cwd=wt)
    if dirty:
        what = ("untracked files" if all(ln.startswith("??") for ln in dirty.splitlines())
                else "uncommitted changes")
        raise ChantierError(f"{cr_id}: {what} in the worktree; commit them (or add them to "
                            f".gitignore) first: "
                            f"{' '.join(ln.split(maxsplit=1)[-1] for ln in dirty.splitlines()[:5])}")
    body = _work(repo, c) / "pr-body.md"
    if not body.is_file():
        raise ChantierError(f"write {body} before `chantier ship`")
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
        raise ChantierError(f"{cr_id}: rebase on {onto} failed; aborted: "
                            f"{rb.stdout.strip()[-200:]}", EXIT_EXTERNAL)
    git("push", "--quiet", "--force-with-lease", "-u", remote, c["branch"], cwd=wt)
    if c.get("pr"):
        forge.pr_edit(wt, repo.config, c["pr"], body_file=str(body), base=base)
        link, verb = c["pr"], "updated"
    else:
        link = forge.pr_create(wt, repo.config, base, c["branch"], title or c["title"], str(body))
        verb = "opened"
    with Batch(repo, batch, actor="driver") as b:
        b.touch(b.cr(cr_id), pr=link, ci="pending")
        b.log("ship", cr_id, pr=link, base=base)
    return f"{verb} {link} (base {base})"


def ship(args) -> list[str]:
    repo = Repo.find()
    return [_ship(repo, find_cr_batch(repo, args.cr, args.batch), args.cr, args.title)]


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
        _ship(repo, batch, c["id"])
        affected.append(c["id"])
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
        if not args.findings:
            raise ChantierError("qa done <cr> --findings <file> (one finding per bullet)",
                                EXIT_USAGE)
        evidence = repo.root / c["path"] / "evidence"
        if not evidence.is_dir() or not any(p.is_file() for p in evidence.rglob("*")):
            raise ChantierError(f"no proof in {_shown(repo, evidence)}: keep what you ran and saw "
                                "there (commands and their output), findings or not")
        text = Path(args.findings).read_text(encoding="utf-8")
        n = sum(1 for ln in text.splitlines() if ln.lstrip().startswith(("- ", "* ")))
        c["qa_findings"] = str(Path(args.findings).resolve())
        b.touch(c)
        b.log("qa-done", args.cr, findings=n)
    return [f"qa done {args.cr}: {n} findings; tell the Foreman: "
            f"[qa {args.cr}→foreman] qa done {args.cr} {n} findings"]


def release(args) -> tuple[list[str], int]:
    """The release CR's irreversible actions: each one is approved by the user, or allowed by the
    grant the user gave, within the budget."""
    repo = Repo.find()
    with Batch(repo, find_cr_batch(repo, args.cr, args.batch), actor="driver") as b:
        c = b.cr(args.cr)
        if c.get("kind") != "release":
            raise ChantierError(f"{args.cr} is not the batch's release CR", EXIT_USAGE)
        grant = b.data["release"]
        if args.action == "start":  # a new attempt: the release is built on what is merged now
            wt = _worktree(c)
            if git("status", "--porcelain", cwd=wt):
                raise ChantierError(f"{args.cr}: uncommitted changes in the worktree; keep what "
                                    "matters in the work folder, then clean it")
            ref = _base_ref(repo)
            git("checkout", "--quiet", "-B", c["branch"], ref, cwd=wt)
            head = git("rev-parse", "--short", "HEAD", cwd=wt)
            b.touch(c, attempts=c.get("attempts", 0) + 1, go=None)
            b.log("release-start", args.cr, head=head)
            return [f"attempt {c['attempts']}: {c['branch']} at {ref} {head}"], 0
        if not (args.note or "").strip():
            raise ChantierError(f"release {args.action} {args.cr} --note \"<…>\"", EXIT_USAGE)
        if args.action == "published":
            grant["published"] = grant.get("published", 0) + 1
            c.setdefault("notes", []).append(f"published: {args.note}")
            b.touch(c, go=None)
            b.log("release-published", args.cr, note=args.note)
            return [f"release {grant['published']} published: {args.note}"], 0
        result, why = release_go(b, c, args.note)
        if result == "budget":
            return [f"no: the budget is spent (${b.data.get('spent_usd', 0):.2f} of "
                    f"${b.data['budget_usd']}); send `[driver {args.cr}→foreman] hand-back blocked "
                    f"budget: {args.note}` and end"], EXIT_BUDGET
        if result == "ask":
            return [f"no approval: send `[driver {args.cr}→foreman] hand-back blocked approval: "
                    f"{args.note}` and end"], EXIT_PRECONDITION
        return [f"go: {args.note} ({why})"], 0


def merge(args) -> list[str]:
    """chantier merges only what the user allowed: a release's fix under the grant, and the
    release's own PR after `release go`. The Foreman runs it; when it is refused, the Chief of
    Staff runs it `--escalated`, then tells the Foreman with `order merged`."""
    repo = Repo.find()
    batch, d, c = _batch_cr(repo, args.cr, args.batch)
    grant = d.get("release") or {}
    if c.get("kind") == "fix":
        method = grant.get("auto_merge")
        if not method:
            raise ChantierError(f"{args.cr}: the user merges the release's fixes (no auto-merge "
                                "grant)", EXIT_USAGE)
        if c["status"] != "ready" or not c.get("pr"):
            raise ChantierError(f"{args.cr} is {c['status']}: only a ready PR is merged",
                                EXIT_PRECONDITION)
    elif c.get("kind") == "release":
        if not c.get("go") or not c.get("pr"):
            raise ChantierError(f"{args.cr}: merging the release PR is an irreversible action: "
                                "`chantier release go` first", EXIT_PRECONDITION)
        method = c.get("merge_method")
        if not method:
            raise ChantierError(f"{args.cr}: its Driver names the method: `hand-back blocked "
                                "merge: <method>`", EXIT_USAGE)
    else:
        raise ChantierError(f"{args.cr}: the user merges; chantier merges only a release's fixes "
                            "and its own PR, when the user allowed it", EXIT_USAGE)
    if args.epoch is not None and args.epoch != d.get("foreman_epoch", 0):  # before merging
        raise ChantierError(f"stale Foreman: epoch {args.epoch}, batch {batch} is at epoch "
                            f"{d.get('foreman_epoch', 0)}; stop now", EXIT_CONFLICT)
    forge.pr_merge(c.get("worktree") or repo.root, repo.config, c["pr"], method)
    with changes_lock(repo):
        with Batch(repo, batch, actor="chief-of-staff" if args.escalated else "foreman") as b:
            check_epoch(b, args.epoch)
            c = b.cr(args.cr)
            b.log("merge", args.cr, pr=c["pr"], method=method)
            if args.escalated:
                return [f"merged {args.cr} {c['pr']} ({method}): now `order merged {args.cr}`"]
            if c["kind"] == "release":
                actions = [f"ask-chief-of-staff merged {args.cr} {c['pr']}"] \
                    + release_merged(b, c, method)
            else:
                extra, follow = merged(b, c)
                actions = [f"ask-chief-of-staff merged {args.cr} {c['pr']}{extra}"] + follow
            record_asks(b, actions)
    return [f"merged {args.cr} {c['pr']} ({method})"] + actions


def cancel(args) -> list[str]:
    repo = Repo.find()
    with changes_lock(repo):
        with Batch(repo, find_cr_batch(repo, args.cr, args.batch), actor="foreman") as b:
            check_epoch(b, args.epoch)
            c = b.cr(args.cr)
            if c["status"] == "merged":
                raise ChantierError(f"{args.cr} is merged: nothing to cancel")
            killed = []
            for pg in c.get("pgids", []):
                if procs.stop_group(pg):
                    killed.append(f"pg{pg}")
            killed += [str(p) for p in procs.stop(c.get("pids", []))]
            if c.get("worktree") and Path(c["worktree"]).exists():
                killed += [str(p) for p in procs.stop(procs.find(Path(c["worktree"])))]
            trash_cr(b, c)
            b.touch(c, status="cancelled", agent=None, pgids=[], pids=[])
            b.log("cancel", args.cr, killed=killed, path=c.get("path"))
            actions = fill_slots(b)
            record_asks(b, actions)
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
            if c["status"] != "merged" or not c.get("worktree"):
                continue
            if Path(c["worktree"]).exists():
                if c.get("kind") == "release" and git("status", "--porcelain", cwd=c["worktree"]):
                    retained.append(f"{c['id']} worktree (what the procedure left in it)")
                    continue
                git("worktree", "remove", c["worktree"], cwd=repo.root)
                cleaned.append(c["id"])
            if git("rev-parse", "--verify", "--quiet", c["branch"], cwd=repo.root, check=False):
                result = subprocess.run(["git", "branch", "-d", c["branch"]], cwd=repo.root,
                                        capture_output=True, text=True, encoding="utf-8",
                                        errors="replace")
                if result.returncode:
                    retained.append(f"{c['id']} branch ({result.stderr.strip()})")
        try:
            rows = _cost_rows(repo, b.data, b.data["host"], _foreman_uuid(b.data))
            _record_costs(repo, b, rows)
            summary = _cost_summary(b.data, rows, _cost_groups(repo, batch, rows, "cr"))
        except ChantierError as e:  # never a false $0.00
            summary = [f"Spent: unknown ({e})"]
        b.data.update(status="landed", landed=now(), retained=retained, summary=summary)
        b.log("land", None, cleaned=cleaned, retained=retained)
    lines = [f"landed {batch}: cleaned {len(cleaned)} worktrees", f"report: {b.dir / 'STATUS.md'}"]
    if retained:
        lines.append(f"left for the user: {'; '.join(retained)}")
    return lines


def _landed_batch(repo: Repo, batch: str | None) -> tuple[str, Path, dict]:
    landed = [d for d in repo.batch_folders()
              if _read_json(d / "batch.json").get("status") == "landed"]
    named = [d for d in landed if not batch or _read_json(d / "batch.json")["id"] == batch]
    if len(named) != 1:
        raise ChantierError(f"close names one landed batch; landed: "
                            f"{', '.join(d.name for d in landed) or 'none'}", EXIT_USAGE)
    d = _read_json(named[0] / "batch.json")
    return d["id"], named[0], d


def close(args) -> tuple[list[str], int]:
    """The batch's folder goes, and what a dropped CR left: the Chief of Staff shows this to the
    user first, and passes `--yes` on their word. Without it, nothing is touched."""
    repo = Repo.find()
    with changes_lock(repo):
        batch, folder, d = _landed_batch(repo, args.batch or os.environ.get("CHANTIER_BATCH"))
        left = [p.name for p in folder.iterdir() if p.is_dir()]
        if left:
            raise ChantierError(f"{folder.name} still holds {', '.join(left)}: nothing was deleted")
        dropped = [c for c in d["crs"] if c["status"] == "cancelled"]
        trees = [c["worktree"] for c in dropped if c.get("worktree")
                 and Path(c["worktree"]).exists()]
        branches = [c["branch"] for c in dropped if c.get("branch") and git(
            "rev-parse", "--verify", "--quiet", c["branch"], cwd=repo.root, check=False)]
        plan = [f"folder {_shown(repo, folder)}", *(f"worktree {t}" for t in trees),
                *(f"branch {n}" for n in branches)]
        if not args.yes:
            return [f"close {batch} would delete:", *plan, "left for the user: "
                    f"{'; '.join(d.get('retained', [])) or 'nothing'}",
                    "ask the user, then `chantier close --yes`"], 0
        for tree in trees:
            git("worktree", "remove", "--force", tree, cwd=repo.root)
        for name in branches:
            git("branch", "-D", name, cwd=repo.root)
        going = folder.with_name(f".closing-{folder.name}")
        try:  # a rename fails whole on a file in use; a delete would stop halfway
            _retry(os.replace, folder, going)
        except OSError as e:
            raise ChantierError(f"{folder.name} is in use, close what holds it and run this again: "
                                f"{e}", EXIT_EXTERNAL) from e
        shutil.rmtree(going)
        write_dashboard(repo, stage_layout(repo))
    return [f"closed {batch}: deleted {len(plan)} items"], 0


def _cost_rows(repo: Repo, d: dict, host: str, uuid: str) -> list[dict]:
    if host == "copilot":
        return costs.copilot_session_costs(uuid)
    return costs.session_costs(costs.transcript_path(repo.root, uuid, d["settings"]))


def _foreman_uuid(d: dict) -> str:
    if not d.get("foreman_transcript"):
        raise ChantierError("no Foreman transcript recorded", EXIT_PRECONDITION)
    return d["foreman_transcript"]


def _cost_groups(repo: Repo, batch: str, rows: list[dict], by: str) -> dict[str, list]:
    """Calls and dollars, by role or by CR."""
    agent_cr = {}  # every Driver a CR ever had, from the log: a replaced one keeps its CR
    events = repo.batch_dir(batch) / "events.jsonl"
    for line in events.read_text(encoding="utf-8").splitlines() if events.exists() else []:
        e = json.loads(line)
        if e.get("kind") == "agent" and e.get("cr") and e["cr"] != "stack":
            agent_cr[e["agent"]] = e["cr"].removeprefix("qa:")
    parents = {r["agent"]: r.get("parent") for r in rows}

    def cr_of(agent: str | None, hops: int = 0) -> str | None:
        """A worker counts for the CR of the Driver that started it."""
        if agent is None or hops > 5:
            return None
        return agent_cr.get(agent) or cr_of(parents.get(agent), hops + 1)

    groups: dict[str, list] = defaultdict(lambda: [0, 0.0])
    for r in rows:
        if by == "cr":
            named = CR_IN_NAME.search(r.get("description") or "")
            key = ("foreman" if r["agent"] == "main"
                   else cr_of(r["agent"]) or (named.group(0) if named else "other"))
        else:
            key = r["type"]
        groups[key][0] += r["calls"]
        groups[key][1] += r["usd"]
    return groups


def _orchestrates(role: str) -> bool:
    """The Foreman and the Drivers that only run others; a QA driver does the work itself."""
    name = role.rsplit(":", 1)[-1]
    return name == "foreman" or (name in DRIVERS and name != "qa-driver")


def _cost_summary(d: dict, rows: list[dict], by_cr: dict[str, list]) -> list[str]:
    """What the user reads at the end of a batch; the detail is in `cost --by`."""
    total = sum(r["usd"] for r in rows)
    budget = d.get("budget_usd")
    run = sum(r["usd"] for r in rows if _orchestrates(r["type"]))
    share = round(100 * run / total) if total else 0
    top =sorted(((k, v[1]) for k, v in by_cr.items() if k != "foreman"), key=lambda kv: -kv[1])
    foreman = next((r for r in rows if r["agent"] == "main" and r.get("wakes")), None)
    wakes = [f"Foreman: {foreman['wakes']} wakes, context "
             f"{foreman['wake_context'] // foreman['wakes']:,} tokens on average, "
             f"{foreman['peak_context']:,} at its peak"] if foreman else []
    return [f"Total: ${total:.2f}" + (f" of a ${budget:g} budget" if budget else ", no budget"),
            f"Orchestration ${run:.2f} ({share}%), work ${max(total - run, 0):.2f} "
            f"({100 - share}%)",
            "Most: " + (", ".join(f"{k} ${usd:.2f}" for k, usd in top[:3]) or "-"),
            *wakes,
            "Not counted: the Chief of Staff's own session"]


def cost(args) -> list[str]:
    repo = Repo.find()
    batch = resolve_batch(repo, args.batch)
    d = read_batch(repo, batch)
    host = detect_host(args.host)[0] if args.host else d["host"]
    uuid = args.transcript or d.get("foreman_transcript")
    if not uuid:
        var = "$COPILOT_AGENT_SESSION_ID" if host == "copilot" else "$CLAUDE_CODE_SESSION_ID"
        raise ChantierError(f"no Foreman transcript recorded: the Foreman runs "
                            f"`chantier foreman transcript {var}`")
    rows = _cost_rows(repo, d, host, uuid)
    total = sum(r["usd"] for r in rows)
    if args.update:
        with Batch(repo, batch, actor="foreman") as b:
            b.data["spent_usd"] = round(total, 4)
            b.log("cost", None, usd=total)
    if args.summary:
        return _cost_summary(d, rows, _cost_groups(repo, batch, rows, "cr"))
    groups = _cost_groups(repo, batch, rows, args.by)
    estimated = sum(r.get("estimated", 0) for r in rows)
    lines = [f"{batch}: ${total:.3f} over {sum(r['calls'] for r in rows)} model calls"
             + (f" ({estimated} estimated, not billed)" if estimated else "")]
    lines += [f"{k}: ${v[1]:.3f} ({v[0]} calls)"
              for k, v in sorted(groups.items(), key=lambda kv: -kv[1][1])]
    return lines
