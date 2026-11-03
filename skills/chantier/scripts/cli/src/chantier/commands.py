"""The `chantier` commands. Each returns the lines to print; errors raise ChantierError with an exit code."""
from __future__ import annotations

import hashlib
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
from .decide import decide, fill_slots
from .models import (CR_IN_NAME, INHERIT, ROLES, Models, brief_overrides, copilot_events,
                     copilot_session, copilot_spawns, detect_host, expected)
from .state import (DONE, EXIT_CONFLICT, EXIT_EXTERNAL, EXIT_PRECONDITION, EXIT_USAGE, LIVE,
                    Batch, ChantierError,
                    Repo, age_minutes, check_epoch, find_cr_batch, git, next_cr_number, now,
                    read_batch, resolve_batch)

DRIVER_TEMPLATES = ("cr-driver", "stack-driver", "qa-driver")
TEMPLATES = ("foreman",) + DRIVER_TEMPLATES + ("investigator", "coder", "inspector", "debugger",
                                               "verifier", "conflict-resolver")
TEMPLATE_VERSION = re.compile(r"^# chantier-template: (\S+)$", re.M)


def skill_dir() -> Path:
    """The skill folder: `CHANTIER_SKILL_DIR`, else the nearest parent of this file with SKILL.md."""
    env = os.environ.get("CHANTIER_SKILL_DIR")
    if env:
        return Path(env).resolve()
    for p in Path(__file__).resolve().parents:
        if (p / "SKILL.md").exists():
            return p
    raise ChantierError("cannot find the chantier skill folder; set CHANTIER_SKILL_DIR", EXIT_PRECONDITION)


def chantier_prefix() -> str:
    return f"uv run --script {skill_dir() / 'scripts' / 'cli' / 'chantier.py'}"


# How the agents shipped in the Claude Code plugin name the skill: Claude Code substitutes the
# plugin's install folder in agent bodies.
PLUGIN_SKILL = "${CLAUDE_PLUGIN_ROOT}/skills/chantier"
PLUGIN_CHANTIER = f"uv run --script {PLUGIN_SKILL}/scripts/cli/chantier.py"
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


def plugin_agent(name: str) -> Path | None:
    """The plugin's own agent file for a role, if this skill ships in the plugin."""
    root = plugin_root()
    path = root / "agents" / f"{name}.md" if root else None
    return path if path and path.exists() else None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "cr"


# ---- setup and preflight ----------------------------------------------------------------------

def load_models(repo: Repo | None, host: str) -> Models:
    legacy = (repo.config.get("models") or None) if repo else None
    return Models(host, skill_dir(), repo.root if repo else None, legacy)


def agent_path(repo: Repo, host: str, name: str) -> Path:
    if host == "copilot":
        return repo.root / ".github" / "agents" / f"{name}.agent.md"
    return repo.root / ".claude" / "agents" / f"{name}.md"


def agent_name(repo: Repo, host: str, name: str) -> str:
    """The agent to spawn for a role: the repository's own file wins, else the plugin's."""
    if host == "claude" and not agent_path(repo, host, name).exists() and plugin_agent(name):
        return f"{PLUGIN_NAME}:{name}"
    return name


def render_plugin_agents() -> dict[str, str]:
    """The agent files the Claude Code plugin ships: the skill's base list, no override."""
    models = Models("claude", skill_dir(), None, base_only=True)
    if models.errors:
        raise ChantierError("models: " + "; ".join(models.errors))
    return {n: _render_template(n, models, PLUGIN_SKILL, PLUGIN_CHANTIER) for n in TEMPLATES}


def _render_local(name: str, models: Models) -> str:
    return _render_template(name, models, str(skill_dir()), chantier_prefix())


def _plugin_fits(name: str, models: Models) -> bool:
    """The plugin ships this role's agent with the model, effort and tools configured here."""
    shipped = plugin_agent(name) if models.host == "claude" else None
    return bool(shipped) and _pinned(shipped.read_text()) == _pinned(
        _render_template(name, models, PLUGIN_SKILL, PLUGIN_CHANTIER))


def _render_template(name: str, models: Models, skill: str, chantier: str) -> str:
    text = (skill_dir() / "assets" / "agents" / f"{name}.md").read_text()
    text = text.replace("{{CHANTIER}}", chantier).replace("{{SKILL}}", skill)
    model = models.frontmatter_model(name)
    effort = models.effort_of(name)
    tools = models.tool_list(name)
    if models.host == "claude":
        text = text.replace("{{MODEL}}", model).replace("{{TOOLS}}", ", ".join(tools))
        if effort:
            text = re.sub(r"^(model: .*)$", rf"\1\neffort: {effort}", text, count=1, flags=re.M)
        return text
    # Copilot: name and description from the template, then Copilot's own keys.
    _, front, body = text.split("---\n", 2)
    keep = [ln for ln in front.splitlines() if ln.startswith(("name:", "description:"))]
    if model:
        keep += [f"model: {model}", "model-policy: required"]
    if effort:
        keep.append(f"reasoning-effort: {effort}")
    keep += ["tools: [" + ", ".join(f'"{t}"' for t in tools) + "]",
             "strict-tools-list: true",
             # The Foreman is the only agent a session is started as; the rest are subagents.
             f"user-invocable: {'true' if name == 'foreman' else 'false'}"]
    return "---\n" + "\n".join(keep) + "\n---\n" + body


# Frontmatter keys that come from the model config: a change in any of them is drift.
PINNED_KEYS = ("model", "model-policy", "effort", "reasoning-effort", "tools", "strict-tools-list")


def _pinned(text: str) -> dict[str, str]:
    front = text.split("---\n", 2)[1] if text.startswith("---\n") else ""
    return {m[1]: m[2].strip() for m in re.finditer(r"^([a-z-]+): (.+)$", front, re.M)
            if m[1] in PINNED_KEYS}


def setup(args) -> list[str]:
    repo = Repo.find()
    host, _ = detect_host(getattr(args, "host", None))
    models = load_models(repo, host)
    if models.errors:
        raise ChantierError("models: " + "; ".join(models.errors) + " (nothing installed)")
    out = []
    installed_path = repo.root / ".agents" / "chantier-installed.json"
    installed = json.loads(installed_path.read_text()) if installed_path.exists() else {}
    for name in TEMPLATES:
        target = agent_path(repo, host, name)
        rel = target.relative_to(repo.root).as_posix()
        key = name if host == "claude" else f"{host}/{name}"
        if _plugin_fits(name, models):
            # the plugin's agent is the one to run: a copy here would only shadow it
            if target.exists() and installed.get(key) == _digest(target.read_text()):
                target.unlink()
                installed.pop(key)
                out.append(f"removed {rel} (the plugin's agent fits the configuration)")
            continue
        text = _render_local(name, models)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_text() == text:
            installed[key] = _digest(text)
            continue
        edited = target.exists() and _digest(target.read_text()) != installed.get(key)
        if edited and not args.force:
            drift = _pinned(target.read_text()) != _pinned(text)
            out.append(f"kept {rel} (edited locally; --force to replace)"
                       + (" but its model, effort or tools differ from the config"
                          if drift else ""))
            continue
        target.write_text(text)
        installed[key] = _digest(text)
        out.append(f"installed {rel}")
    if installed:
        installed_path.parent.mkdir(parents=True, exist_ok=True)
        installed_path.write_text(json.dumps(installed, indent=2) + "\n")
    elif installed_path.exists():
        installed_path.unlink()
    out.append(f"setup done ({host})" if out else f"setup: nothing to change ({host})")
    out.append("restart the session if agent files changed: agents load at start")
    return out


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _version_of(path: Path) -> str | None:
    m = TEMPLATE_VERSION.search(path.read_text())
    return m.group(1) if m else None


def _skill_version() -> str | None:
    m = re.search(r"^chantier-version: (\S+)$", (skill_dir() / "SKILL.md").read_text(), re.M)
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
        # The repository's own agent file wins; else the plugin's, if it ships one.
        local = {n: agent_path(repo, host, n) for n in TEMPLATES}
        paths = {n: local[n] if local[n].exists()
                 else (plugin_agent(n) if host == "claude" else None) for n in TEMPLATES}
        missing = [n for n in TEMPLATES if paths[n] is None]
        stale = [n for n in TEMPLATES if n not in missing
                 and _version_of(paths[n]) != __version__]
        no_ttl = [n for n in DRIVER_TEMPLATES if host == "claude" and n not in missing
                  and "cacheTtl: 1h" not in paths[n].read_text()]

        def wanted(n: str) -> str:
            return (_render_local(n, models) if paths[n] == local[n]
                    else _render_template(n, models, PLUGIN_SKILL, PLUGIN_CHANTIER))

        drift = [n for n in TEMPLATES if models and not model_errors and n not in missing
                 and _pinned(paths[n].read_text()) != _pinned(wanted(n))]
        problems = ([f"missing {', '.join(missing)}"] if missing else []) + \
                   ([f"old template {', '.join(stale)}"] if stale else []) + \
                   ([f"no 1h cache in {', '.join(no_ttl)}"] if no_ttl else []) + \
                   ([f"model, effort or tools differ from the config in {', '.join(drift)}"]
                    if drift else [])
        check("P4", not problems, "agent files installed and current",
              "; ".join(problems) + " (run `chantier setup`, then restart the session)")
        check("P8", not model_errors, f"models valid for {host}",
              "; ".join(model_errors) + " (fix the model files, then `chantier setup`)")
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
    lines.append("P2, P3 and 'not unattended' are the Chief of Staff's own checks")
    lines.append("preflight passed" if ok else "preflight FAILED: start nothing")
    return lines, 0 if ok else EXIT_PRECONDITION


# ---- batches and CRs --------------------------------------------------------------------------

def _base_ref(repo: Repo) -> str:
    remote, branch = repo.config["remote"], repo.config["default_branch"]
    if git("remote", cwd=repo.root, check=False).split().count(remote):
        git("fetch", "--quiet", remote, branch, cwd=repo.root, check=False)
        if git("rev-parse", "--verify", "--quiet", f"{remote}/{branch}", cwd=repo.root,
               check=False):
            return f"{remote}/{branch}"
    return branch


def add_cr(b: Batch, item: str, qa: bool = False) -> dict:
    """Create one CR: its folder, task, STATE.md, branch and worktree; queued."""
    repo = b.repo
    text, title = item, item
    path = Path(item[1:]) if item.startswith("@") else None
    if path is not None:
        if not path.is_absolute():
            path = repo.root / path
        if not path.exists():
            raise ChantierError(f"backlog item not found: {path}", EXIT_USAGE)
        text = path.read_text()
        title = next((ln.lstrip("# ").strip() for ln in text.splitlines() if ln.strip()),
                     path.stem)
    cr_id = f"CR-{next_cr_number(repo)}"
    cdir = b.dir / "crs" / cr_id
    (cdir / "scratch").mkdir(parents=True, exist_ok=True)
    (cdir / "task.md").write_text(text if text.endswith("\n") else text + "\n")
    branch = f"chantier/{b.id}/{cr_id.lower()}-{_slug(title)}"
    worktree = None
    if not b.data.get("no_worktrees"):
        worktree = repo.worktrees / f"{b.id}-{cr_id}"
        worktree.parent.mkdir(parents=True, exist_ok=True)
        git("worktree", "add", "--quiet", "-b", branch, str(worktree), _base_ref(repo),
            cwd=repo.root)
    order = max((c["order"] for c in b.data["crs"]), default=0) + 1
    c = {"id": cr_id, "title": title, "item": item, "status": "queued", "order": order,
         "round": 0, "qa": qa, "qa_done": False, "agent": None, "pr": None, "ci": None,
         "branch": branch, "worktree": str(worktree) if worktree else None, "pgids": [], "pids": [],
         "notes": [], "resumes": 0, "updated": now()}
    (cdir / "STATE.md").write_text(
        f"# {cr_id}: {title}\n\n- batch: {b.id}\n- branch: `{branch}`\n"
        f"- worktree: `{c['worktree']}`\n- status: queued\n")
    b.data["crs"].append(c)
    b.log("add", cr_id, title=title)
    return c


def open_batch(args) -> list[str]:
    repo = Repo.find()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", args.batch):
        raise ChantierError("batch id: lowercase letters, digits and hyphens", EXIT_USAGE)
    qa_all = args.qa == "all"
    qa_idx = set() if qa_all or not args.qa else {int(i) for i in args.qa.split(",")}
    data = {"id": args.batch, "version": __version__, "created": now(), "status": "open",
            "mode": "stack" if args.stack else "parallel", "slots": args.slots,
            "budget_usd": args.budget, "spent_usd": 0.0, "paused": False,
            "foreman": None, "foreman_epoch": 0, "foreman_transcript": None, "chief_of_staff": args.chief_of_staff,
            "no_worktrees": args.no_worktrees, "stack_live": False, "heartbeat": None,
            "orders": [], "crs": []}
    with Batch(repo, args.batch, actor="chief-of-staff", create=data) as b:
        for i, item in enumerate(args.items, 1):
            add_cr(b, item, qa=qa_all or i in qa_idx)
        brief = b.dir / "brief.md"
        brief.write_text(f"# Batch {args.batch}\n\n- Mode: {data['mode']}. Slots: {args.slots}. "
                         f"Budget: {args.budget or 'none'}.\n- CRs, in order:\n" +
                         "".join(f"  - {c['id']}: {c['title']}{' (QA)' if c['qa'] else ''}\n"
                                 for c in b.data["crs"]) +
                         "- Models (optional; `role=id` or `role@CR-n=id`, exact ids from "
                         "`chantier models`; empty = agent file default):\n"
                         "- Night policy card: one extra round per CR; a red PR goes to the top.\n"
                         "- Autonomous decisions:\n- Questions to bring back:\n")
        b.log("open", None, crs=[c["id"] for c in b.data["crs"]])
    lines = [f"opened {args.batch}: {len(args.items)} CRs, {args.slots} slots, {data['mode']}"]
    lines += [f"{c['id']} {c['title'][:60]}" for c in b.data["crs"]]
    lines.append(f"brief: {brief.relative_to(repo.root)}")
    return lines


def add(args) -> list[str]:
    repo = Repo.find()
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
    c = next(x for x in read_batch(repo, batch)["crs"] if x["id"] == args.cr)
    wt = _worktree(c)
    cmds = repo.config["gates"]["long" if args.long else "fast"]
    if not cmds:
        return [f"no {'long' if args.long else 'fast'} gates configured in .agents/chantier.json"], 0
    logdir = repo.batch_dir(batch) / "crs" / args.cr / "scratch" / "gates"
    logdir.mkdir(parents=True, exist_ok=True)
    log = logdir / f"{time.strftime('%Y%m%d-%H%M%S')}-{'long' if args.long else 'fast'}.log"
    with open(log, "w") as f:
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
                tail = log.read_text().splitlines()[-8:]
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
    remote = repo.config["remote"]
    if remote not in git("remote", cwd=wt).split():
        raise ChantierError(f"no remote {remote!r}", EXIT_EXTERNAL)
    base = _stack_base(d, c, repo)
    git("fetch", "--quiet", remote, cwd=wt)
    onto = f"{remote}/{base}" if base == repo.config["default_branch"] else base
    rb = subprocess.run(["git", "rebase", onto], cwd=wt, capture_output=True, text=True,
                        env={**os.environ, "GIT_EDITOR": "true"})
    if rb.returncode != 0:
        subprocess.run(["git", "rebase", "--abort"], cwd=wt, capture_output=True)
        raise ChantierError(f"{args.cr}: rebase on {onto} failed; aborted: "
                       f"{rb.stdout.strip()[-200:]}", EXIT_EXTERNAL)
    git("push", "--quiet", "--force-with-lease", "-u", remote, c["branch"], cwd=wt)
    body = repo.batch_dir(batch) / "crs" / args.cr / "pr-body.md"
    if not body.exists():
        raise ChantierError(f"write {body.relative_to(repo.root)} before `chantier ship`")
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
            text = Path(args.findings).read_text()
            n = sum(1 for ln in text.splitlines() if ln.lstrip().startswith(("- ", "* ")))
            c["qa_findings"] = str(Path(args.findings).resolve())
        b.touch(c)
        b.log("qa-done", args.cr, findings=n)
    return [f"qa done {args.cr}: {n} findings; tell the Foreman: "
            f"[qa {args.cr}→foreman] qa done {args.cr} {n} findings"]


def cancel(args) -> list[str]:
    repo = Repo.find()
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
        b.touch(c, status="cancelled", agent=None, pgids=[], pids=[])
        b.log("cancel", args.cr, killed=killed)
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
        cleaned = []
        for c in b.data["crs"]:
            if c["status"] in {"merged", "cancelled"} and c.get("worktree"):
                git("worktree", "remove", "--force", c["worktree"], cwd=repo.root, check=False)
                git("branch", "-D", c["branch"], cwd=repo.root, check=False)
                cleaned.append(c["id"])
        rows = "".join(f"| {c['id']} | {c['title']} | {c['status']} | {c.get('pr') or '-'} | "
                       f"{c['round']} |\n" for c in sorted(b.data["crs"], key=lambda c: c["order"]))
        report_path = b.dir / "report.md"
        report_path.write_text(
            f"# Batch {batch}: report\n\n- Landed: {now()}\n- Spent: ${b.data.get('spent_usd', 0):.2f}"
            f"\n\n| CR | Title | Status | PR | Rounds |\n| --- | --- | --- | --- | ---: |\n{rows}")
        b.data["status"] = "landed"
        b.log("land", None, cleaned=cleaned)
    return [f"landed {batch}: cleaned {len(cleaned)} worktrees",
            f"report: {report_path.relative_to(repo.root)}"]


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

def _batch_context(repo: Repo, batch: str | None, models: Models) -> tuple[dict, dict]:
    """The brief's model overrides and the agent id → CR map, or empty ones without a batch."""
    try:
        batch_id = resolve_batch(repo, batch)
    except ChantierError:
        if batch:
            raise
        return {}, {}
    overrides = brief_overrides(repo.batch_dir(batch_id) / "brief.md", models)
    d = read_batch(repo, batch_id)
    agent_cr = {}
    for c in d.get("crs", []):
        for key in ("agent", "qa_agent"):
            if c.get(key):
                agent_cr[c[key]] = c["id"]
    return overrides, agent_cr


def _locked(models: Models, role: str, want: str) -> str | None:
    """Why a spawn cannot run `want` on Copilot, where agent files pin with model-policy."""
    pinned = models.role(role)
    if models.host != "copilot" or role == "foreman" or pinned == INHERIT or want == pinned:
        return None
    return (f"brief asks {role}={want} but the {role} agent file requires {pinned} "
            "(model-policy: required, Copilot refuses the spawn): set it under `roles` in "
            ".agents/chantier.models.yml, run `chantier setup`, restart the session")


def models_cmd(args) -> tuple[list[str], int]:
    repo = Repo.find()
    host, why = detect_host(args.host)
    models = load_models(repo, host)
    if args.action == "check":
        errors = list(models.errors)
        if not errors:
            try:
                overrides, _ = _batch_context(repo, args.batch, models)
                errors += [_locked(models, r, m) for (r, _c), m in overrides.items()
                           if _locked(models, r, m)]
            except ChantierError as e:
                errors.append(str(e))
        if errors:
            return [f"models FAILED ({host}): start nothing"] + errors, EXIT_PRECONDITION
        return [f"models ok ({host}): {len(ROLES)} roles, {len(models.catalog)} ids in catalog"], 0
    if models.errors:
        return [f"models FAILED ({host}): run `chantier models check`"] + models.errors, \
            EXIT_PRECONDITION
    overrides, agent_cr = _batch_context(repo, args.batch, models)
    if args.action == "show":
        groups: dict[str, list[str]] = defaultdict(list)
        for role in ROLES:
            src = models.source[role]
            effort = models.effort_of(role)
            label = role + (f" [{effort}]" if effort else "")
            groups[models.role(role)].append(label if src == "skill" else f"{label} ({src})")
        lines = [f"{host} models (host from {why}); exact ids only; [effort] when set"]
        lines += [f"{mid}: {', '.join(roles)}" for mid, roles in groups.items()]
        lines.append(f"heartbeat: {models.heartbeat}" + (
            "" if models.heartbeat_source == "skill" else f" ({models.heartbeat_source})"))
        if overrides:
            lines.append("brief: " + ", ".join(f"{r}{'@' + c if c else ''}={m}"
                                                for (r, c), m in overrides.items()))
        return lines, 0
    if args.action == "get":
        if not args.role:
            raise ChantierError("models get <role> [--cr CR-n]", EXIT_USAGE)
        want, src = expected(models, overrides, args.role, args.cr)
        pinned = models.role(args.role)
        level = models.effort_of(args.role)
        if args.role == "foreman" and host == "copilot":
            # create_session takes no effort and cannot select the foreman agent file.
            effort = (f"effort: omit ({level} is in the agent file; create_session cannot set "
                      "it, so the session's effort applies: accepted exception)" if level
                      else "effort: omit (the user's setting)")
        elif args.role == "foreman":
            effort = (f"effort: {level} (copy this level exactly)" if level
                      else "effort: omit (the user's setting)")
        else:
            effort = ("effort: omit (the agent file sets " + level + ")" if level
                      else "effort: omit (the user's setting)")
        tail = [effort]
        if args.role == "foreman":
            tail.append(f"heartbeat: {models.heartbeat} ({models.heartbeat_seconds()} s)")
        else:
            tail.append(f"agent: {agent_name(repo, host, args.role)} (spawn this agent exactly)")
        if args.role != "foreman" and want == pinned:
            return [f"model: omit (the agent file pins {pinned})", *tail], 0
        if want == INHERIT:
            if args.role == "foreman":
                return ["model: omit (inherit)", *tail], 0
            raise ChantierError(f"{src} asks `inherit` but the {args.role} agent file pins {pinned}: "
                           "a spawn cannot unpin it; ask the user", EXIT_PRECONDITION)
        if _locked(models, args.role, want):
            raise ChantierError(_locked(models, args.role, want), EXIT_PRECONDITION)
        return [f"model: {want} ({src}; copy this id exactly)", *tail], 0
    # audit
    if host != "copilot":
        raise ChantierError("models audit reads Copilot event logs only", EXIT_USAGE)
    try:
        batch = resolve_batch(repo, args.batch)
        data = read_batch(repo, batch)
    except ChantierError:
        batch, data = None, {}
    foreman_uuid = data.get("foreman_transcript")
    session = (args.session or foreman_uuid or os.environ.get("COPILOT_AGENT_SESSION_ID"))
    if not session:
        raise ChantierError("models audit --session <copilot session id>", EXIT_USAGE)
    spawns = copilot_spawns(copilot_events(session))
    bad, unchecked = [], 0
    notes = []
    if batch and session == foreman_uuid:
        notes, bad = _audit_foreman(models, overrides, batch, data, copilot_events(session))
    for s in spawns:
        cr = agent_cr.get(s["agent"]) or s["cr"]
        want, src = expected(models, overrides, s["role"], cr)
        if want == INHERIT:
            unchecked += 1
        elif s["model"] != want:
            bad.append(f"MISMATCH {s['role']} {cr or '-'} ran {s['model']}, expected {want} "
                       f"({src}; selection {s['selection']})")
        level = models.effort_of(s["role"])
        if level and s["effort"] != level:
            bad.append(f"MISMATCH {s['role']} {cr or '-'} ran effort {s['effort']}, "
                       f"expected {level}")
    lines = [f"audit {session}: {len(spawns)} chantier spawns, {len(bad)} mismatched"
             + (f", {unchecked} inherit (not checked)" if unchecked else "")]
    return lines + notes + bad, EXIT_PRECONDITION if bad else 0


def _audit_foreman(models: Models, overrides: dict, batch: str, data: dict,
                   events: Path) -> tuple[list[str], list[str]]:
    """The Foreman's own calls and heartbeat. A Foreman started with `create_session` runs at
    the session's effort (the tool takes no effort): reported as a note, not a mismatch."""
    facts = copilot_session(events)
    notes, bad = [], []
    want, src = expected(models, overrides, "foreman", None)
    level = models.effort_of("foreman")
    for (model, effort), n in sorted(facts["calls"].items(), key=lambda kv: -kv[1]):
        notes.append(f"foreman ran {model} effort {effort} ({n} calls)")
        if want != INHERIT and model != want:
            bad.append(f"MISMATCH foreman ran {model}, expected {want} ({src})")
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
