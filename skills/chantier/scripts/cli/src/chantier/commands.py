"""The `chantier` commands. Each returns the lines to print; errors raise ChantierError with an exit code.

The CLI is the frame the agents work in: the CR lifecycle in `.agents/changes/` (the stages,
the batch folders, the record and the STATUS files), the batch's limits (slots, budget, rounds,
the user's word on an irreversible action), the means to synchronise (orders, asks, notes, the
long gate's lock) and a few tools (the project's rules, the cost). The agents do the work, git
and the forge included; the CLI names what they create (branches, worktrees), keeps the record,
and runs no git command that changes anything: it reads the head, the remote and the status to
say what is off, and no forge command at all.
"""
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
from types import SimpleNamespace

from . import __version__, costs, procs
from .lifecycle import (PRIORITIES, archive_cr, changes_lock, cr_directory, ensure_unclaimed,
                        move_backlog_item, prepared_cr, stage_layout, trash_cr)
from .rails import (ENDED, MAX_GRANTED_FIXES, all_merged, archive_merged, check_budget, check_grant,
                    check_granted_fix, check_no_open_batch, check_round, check_slot, check_take,
                    fix_go, held, live, parse_grant, record_ask, release_go, release_merged, unmet)
from .state import (EXIT_BUDGET, EXIT_CONFLICT, EXIT_EXTERNAL, EXIT_PRECONDITION, EXIT_USAGE, LIVE,
                    Batch, ChantierError, Repo, _read_json, _retry, _try_lock, _unlock,
                    age_minutes, check_epoch, default_branch, find_cr_batch, git, move_directory,
                    next_cr_number, normalize_batch, now, project_path, read_batch, read_events, resolve_batch,
                    round_limit, stamp)
from .status import write_dashboard

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


def cli_command() -> str:
    """How every agent runs this CLI: the exact command, with the absolute path."""
    return f'uv run --script "{(skill_dir() / "scripts" / "cli" / "chantier.py").as_posix()}"'


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

def _agent_problems(host: str) -> list[str]:
    """The plugin's agents for this host, all at this version; the CLI knows no role, only that
    the files the plugin installs match it."""
    root = plugin_root()
    if not root:
        return ["the chantier plugin is not installed (a skill alone has no agents): install the "
                "plugin and restart the session"]
    folder = root / "agents" if host == "claude" else root / "com.github.copilot" / "agents"
    files = sorted(folder.glob("*.md")) if folder.is_dir() else []
    if not files:
        return [f"no plugin agent in {folder}"]
    return [f"plugin agent {p.name} is not version {__version__}" for p in files
            if (m := AGENT_VERSION.search(p.read_text(encoding="utf-8"))) is None
            or m[1] != __version__]


def preflight(args) -> tuple[list[str], int]:
    lines, ok = [], True

    def check(tag: str, passed: bool, good: str, bad: str):
        nonlocal ok
        ok &= passed
        lines.append(f"{tag} {'ok  ' if passed else 'FAIL'} {good if passed else bad}")

    try:
        host = detect_host()
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
    if host:
        problems = _agent_problems(host)
        check("P4", not problems, f"the plugin's agents are at {__version__} on {host}",
              "; ".join(problems))
    else:
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
    lines.append("P2, P3, P9 and 'not unattended' are the Chief of Staff's own checks")
    lines.append("preflight passed" if ok else "preflight FAILED: start nothing")
    return lines, 0 if ok else EXIT_PRECONDITION


# ---- CR folders -------------------------------------------------------------------------------

def _new_request(repo: Repo, slug: str, raw: bytes) -> Path:
    """A new inbox folder, the request kept as received. The caller holds `changes_lock`."""
    folder = stage_layout(repo)["inbox"] / slug
    folder.parent.mkdir(parents=True, exist_ok=True)
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
    return folder


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
    with changes_lock(repo):
        folder = _new_request(repo, slug, raw)
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


def _worktree(c: dict) -> Path:
    """The CR's worktree, once its Driver has created it; the CLI never does."""
    if not Path(c["worktree"]).is_dir():
        raise ChantierError(f"{c['id']}: no worktree at {c['worktree']}; its Driver creates it "
                            f"(`git worktree add -b {c['branch']} {c['worktree']} <base>`)",
                            EXIT_PRECONDITION)
    return Path(c["worktree"])


def _cr_events(repo: Repo, batch: str, cr_id: str) -> list[dict]:
    return [e for e in read_events(repo.batch_dir(batch)) if e.get("cr") == cr_id]


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
    source = project_path(repo.root, item, "fix")
    if not source.is_file() or cr_directory(repo, rel) not in source.parents:
        return item
    folder = _new_request(repo, f"{rel['id'].lower()}-{_slug(source.stem)}", source.read_bytes())
    shutil.copyfile(source, folder / "03-change-spec.md")
    return str(folder)


def add_cr(b: Batch, item: str, kind: str = "change") -> dict:
    """Move a prepared CR into requests and name its branch and worktree: the Driver creates
    them, on the fresh default branch, as its first step."""
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
    order = max((c["order"] for c in b.data["crs"]), default=0) + 1
    c = {"id": cr_id, "title": title, "kind": kind, "status": "queued", "order": order,
         "path": cdir.relative_to(repo.root).as_posix(),
         "specification": prepared.specification.name, "round": 0, "agent": None, "pr": None,
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
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ChantierError(f"{path}: not valid UTF-8 JSON ({e}); expected "
                            '{"after": ["<slug>", …]}') from e
    after = data.get("after", []) if isinstance(data, dict) else None
    if not isinstance(after, list) or not all(isinstance(s, str) and s.strip() for s in after):
        raise ChantierError(f'{path}: expected {{"after": ["<slug>", …]}}, slugs being folder '
                            "names without their number")
    return after


def archived_merged(repo: Repo, slug: str) -> bool:
    archives = stage_layout(repo)["archives"]
    for folder in sorted(archives.iterdir()) if archives.is_dir() else []:
        if folder.is_dir() and cr_slug(folder.name) == slug:
            try:
                state = json.loads((folder / "STATUS.json").read_text(encoding="utf-8")).get("state")
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
            if dep["status"] == "merged":  # archived: met, so not recorded
                continue
            if dep["id"] not in ids:
                ids.append(dep["id"])
        if ids:
            c["after"] = ids
            b.log("depends", c["id"], after=ids)
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
    selected = [prepared_cr(repo, item, paths).directory for item in args.items]
    if len(set(selected)) != len(selected):
        raise ChantierError("the same CR was selected more than once", EXIT_USAGE)
    data = {"id": None, "version": __version__, "created": now(), "status": "open",
            "host": host, "mode": "parallel" if args.parallel else "stack", "slots": args.slots,
            "budget_usd": args.budget, "spent_usd": 0.0,
            "foreman": None, "foreman_epoch": 0, "foreman_transcript": None,
            "foreman_transcripts": [],
            "chief_transcript": os.environ.get(
                "COPILOT_AGENT_SESSION_ID" if host == "copilot" else "CLAUDE_CODE_SESSION_ID")
            or None,
            "stack_agent": None, "heartbeat": None,
            "settings": settings, "orders": [], "asks": [], "crs": [], "release": release}
    with changes_lock(repo):
        check_no_open_batch(repo)
        with Batch(repo, None, actor="chief-of-staff", create=data) as b:
            brief = b.dir / "brief.md"
            for i, item in enumerate(args.items, 1):
                c = add_cr(b, item, kind="release" if i == args.release else "change")
                if release and c["kind"] == "release":
                    release["cr"] = c["id"]
            declare_dependencies(b, list(b.data["crs"]))
            brief.write_text(
                f"# {b.id}\n\n- Mode: {data['mode']}. Slots: {args.slots}. "
                f"Budget: {args.budget or 'none'}. Host: {host}.\n"
                "- CRs, in order:\n" +
                "".join(f"  - {c['id']}: {c['title']} ({c['path']})"
                        f"{' (release: starts once the others are merged)' if c['kind'] == 'release' else ''}"
                        f"{' (after ' + ', '.join(c['after']) + ')' if c.get('after') else ''}\n"
                        for c in b.data["crs"]) +
                (f"- Release grant: {grant_line(release)}\n" if release else "") +
                f"- Project instructions: {', '.join(n for n in INSTRUCTIONS if (repo.root / n).is_file()) or 'none'}.\n"
                "- Team (who runs which role):\n"
                "- Autonomous decisions:\n- Questions to bring back:\n",
                encoding="utf-8")
            b.log("open", None, crs=[c["id"] for c in b.data["crs"]])
    lines = [f"opened {b.id} on {host}: {len(args.items)} CRs, {args.slots} slots, "
             f"{data['mode']}"]
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
        b.log("foreman-transcript", None, transcript=args.value)
        return [f"transcript {args.value}"]


ORDER_KINDS = {"add", "after", "drop", "merged", "note", "rounds", "slots", "budget", "approve",
               "grant", "qa", "done"}
CR_ORDERS = {"after", "drop", "merged", "rounds", "approve", "grant"}


def _release_cr(b: Batch, kind: str, cr_id: str) -> dict:
    release = b.data.get("release") or {}
    if release.get("cr") != cr_id:
        raise ChantierError(f"order {kind} names the batch's release CR "
                            f"({release.get('cr') or 'none'})", EXIT_USAGE)
    return release


def _apply_order(b: Batch, kind: str, cr_id: str, note: str, fix_for: str | None,
                 own: bool = False) -> list[str]:
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
        added = add_cr(b, note)
        declare_dependencies(b, [added])
        waits = f", after {', '.join(added['after'])}" if added.get("after") else ""
        return [f"added {added['id']}, queued{waits}"]
    if kind == "after":
        usage = 'order after <cr> --note "<CR ids, comma separated, or - for none>"'
        if not note.strip():
            raise ChantierError(usage, EXIT_USAGE)
        if c["status"] != "queued":
            raise ChantierError(f"cannot change what {cr_id} waits for: it is {c['status']}, "
                                "not queued")
        ids: list[str] = []
        for dep in ([] if note.strip() == "-" else [s.strip() for s in note.split(",")]):
            if not any(x["id"] == dep for x in b.data["crs"]):
                raise ChantierError(f"order after: unknown CR {dep!r} in batch {b.id}")
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
        if c["status"] != "cancelled":
            trash_cr(b, c)
            b.touch(c, status="cancelled")
        return [f"dropped {cr_id}: {c['path']}"]
    if kind == "note":
        if not note.strip():
            raise ChantierError("order note [<cr>] --note \"<the user's word, in one line>\"",
                                EXIT_USAGE)
        if c:
            c.setdefault("notes", []).append(note.strip())
            b.touch(c)
        return [f"noted{' on ' + cr_id if c else ''}: the Foreman reads it in `status`"]
    if kind == "merged":
        if c["status"] == "merged":
            return [f"{cr_id} already merged"]
        if c["status"] == "cancelled":
            raise ChantierError(f"cannot mark cancelled {cr_id} merged")
        if c.get("kind") == "release":
            release_merged(b, c)
            return [f"merged {cr_id}: the procedure goes on with a new Release driver"]
        return archive_merged(b, c)
    if kind == "rounds":
        if not note.isdigit() or int(note) < 1:
            raise ChantierError("order rounds <cr> --note <n>", EXIT_USAGE)
        b.touch(c, rounds=int(note))
        return [f"{cr_id}: up to {note} rounds"]
    if kind == "slots":
        if not note.isdigit():
            raise ChantierError("order slots --note <n> (0 pauses: no new Driver starts)", EXIT_USAGE)
        b.data["slots"] = int(note)
        return [f"slots {note}"]
    if kind == "budget":
        if not re.fullmatch(r"\d+(\.\d+)?", note) or float(note) <= 0:
            raise ChantierError("order budget --note <usd>", EXIT_USAGE)
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
    if args.kind == "add" and not note.strip():
        raise ChantierError("order add --note <prepared-CR-folder-or-specification> "
                            "[--fix-for <release-cr>]", EXIT_USAGE)
    if args.kind == "qa" and not note.strip():
        raise ChantierError("order qa --note \"<what to test>\"", EXIT_USAGE)
    if args.kind in CR_ORDERS and (not args.cr or args.cr == "-"):
        raise ChantierError(f"order {args.kind} <cr>", EXIT_USAGE)
    repo = Repo.find()
    if args.kind == "done":
        return _order_done(repo, args)
    own = args.epoch is not None
    if own and args.kind != "merged" and not (args.kind == "add" and args.fix_for):
        raise ChantierError("only `order merged` and `order add --fix-for` take --epoch: the "
                            "Foreman's own merge or fix", EXIT_USAGE)
    with changes_lock(repo):
        with Batch(repo, resolve_batch(repo, args.batch),
                   actor="foreman" if own else "chief-of-staff") as b:
            check_epoch(b, args.epoch)
            cr = args.cr
            if args.kind == "qa":  # no CR: a work folder the QA driver fills, in the inbox
                check_budget(b)  # a QA driver is a Driver: refused before anything is created
                check_slot(b, "a QA driver")  # the open order holds the slot until `order done`
                cr = _shown(repo, _new_request(repo, f"qa-{stamp()}", f"# QA\n\n{note}\n".encode()))
            effect = _apply_order(b, args.kind, cr, note, args.fix_for, own)
            oid = f"O-{len(b.data['orders']) + 1}"
            b.data["orders"].append({"id": oid, "kind": args.kind, "cr": cr or "-",
                                     "note": note, "sent": now(), "done": now() if own else None,
                                     **({"fix_for": args.fix_for} if args.fix_for else {})})
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

def _refresh(repo: Repo, batch: str, epoch: int | None) -> tuple[list[str], int]:
    """The facts the state cannot keep by itself: the longest silent Driver and the spend the
    budget reads. With `--epoch`, it is the Foreman's wake, and the batch records it."""
    lines = []
    with changes_lock(repo):
        with Batch(repo, batch, actor="foreman" if epoch is not None else "chief-of-staff") as b:
            check_epoch(b, epoch)
            if epoch is not None:
                b.data["heartbeat"] = now()
                b.log("heartbeat", None)
            silent = [(c["id"], age_minutes(c.get("updated")) or 0) for c in live(b)]
            if silent:
                cr, age = max(silent, key=lambda x: x[1])
                lines.append(f"longest silent Driver {cr} {age:.0f} min")
            data = dict(b.data)
    try:
        rows = _cost_rows(repo, data, data["host"], _foreman_uuid(data))
    except ChantierError as e:
        return lines + [f"spend not updated: {e}"], e.code
    with Batch(repo, batch, actor="foreman" if epoch is not None else "chief-of-staff") as b:
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


def status(args) -> tuple[list[str], int]:
    repo = Repo.find()
    batch = resolve_batch(repo, args.batch)
    extra, code = _refresh(repo, batch, args.epoch) if args.refresh else ([], 0)
    d = read_batch(repo, batch)
    hb = age_minutes(d.get("heartbeat"))
    view = SimpleNamespace(data=d)  # the rails read only `.data`
    n_live = len(held(view))
    queued = sum(1 for c in d["crs"] if c["status"] == "queued")
    lines = [f"{d['id']} {d['status']} {d['mode']} live {n_live}/{d['slots']} queued {queued} "
             f"foreman {d.get('foreman') or 'none'} e{d.get('foreman_epoch', 0)} "
             f"heartbeat {'never' if hb is None else f'{hb:.0f} min'}"
             f" spent ${d.get('spent_usd', 0):.2f}"
             + (f" of ${d['budget_usd']:g}" if d.get("budget_usd") else "")]
    for c in sorted(d["crs"], key=lambda c: c["order"]):
        row = f"{c['id']} {c['status']} r{c['round']}/{round_limit(d, c)} {c.get('pr') or '-'}"
        if c.get("kind") == "release":
            row += f" release{' ' + c['released'] if c.get('released') else ''}"
            row += "".join(f" | draft {p}" for p in c.get("drafts", [])[-2:])
        elif c.get("kind") == "fix":
            row += f" fix for {c['fix_for']}"
        waits = unmet(view, c) if c["status"] == "queued" else []
        if waits:
            row += f" | waits for {', '.join(waits)}"
        if c["status"] == "blocked" and c.get("blocked_reason"):
            row += f" | blocked: {c['blocked_reason'][:70]}"
        elif c.get("notes") and (args.notes or c["status"] == "queued"):
            row += f" | {c['notes'][-1][:60]}"
        usd = c.get("cost_usd")
        lines.append(f"{row} | {'-' if usd is None else '$%.2f' % usd}")
    pending = [o for o in d.get("orders", []) if not o["done"]]
    if pending:
        lines.append("orders pending: " + "; ".join(
            f"{o['id']} {o['kind']}{' ' + o['cr'] if o['cr'] != '-' else ''}"
            f"{' ' + o['note'][:40] if o['note'] else ''}" for o in pending))
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
        if args.cr != "stack" else resolve_batch(repo, args.batch)
    with Batch(repo, batch, actor="foreman") as b:
        check_epoch(b, args.epoch)
        if args.agent == "-":  # the agent ended: the next one may start
            args.agent = None
        if args.cr == "stack":
            b.data["stack_agent"] = args.agent
        else:
            b.touch(b.cr(args.cr), agent=args.agent)
        b.log("agent", args.cr, agent=args.agent)
    return [f"{args.cr} → {args.agent}"]


def _chain(b_data: dict) -> list[dict]:
    """The stack as it stands: the CRs not ended, in order. A release CR and a fix CR sit
    outside it, on the default branch. What a partial merge leaves forms the next stack, so the
    first CR left stands on the default branch; a CR added by `order add` goes on top."""
    if b_data["mode"] != "stack":
        return []
    return [x for x in sorted(b_data["crs"], key=lambda x: x["order"])
            if x["status"] not in {"cancelled", "merged"} and x.get("kind") not in {"release", "fix"}]


def _start_base(b_data: dict, c: dict, repo: Repo) -> str:
    """The branch a CR starts on: that of its last dependency still open, in the order of
    `after`; with none open, the default branch, whatever its place in a stack."""
    default = repo.config["default_branch"]
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
    if c.get("after") and c.get("kind") not in {"release", "fix"}:
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
             f"cli: {cli_command()} <command> --batch {batch}",
             f"cards: {skill}/references/ (driver.md, worker.md, concepts.md); the project's "
             "rules rank above them: `rules`",
             f"project instructions: {found.as_posix() if found else 'none'}",
             f"specification: {(folder / c['specification']).as_posix()}",
             f"folder: {folder.as_posix()} (work/, evidence/)",
             f"worktree: {c['worktree']} branch {c['branch']} base {_base_of(d, c, repo)}"
             + ("" if made else "; not created yet: a Driver creates it first"),
             f"PR: {c.get('pr') or 'none'}; head {c.get('head') or '-'}",
             f"rounds: {c['round']} of {round_limit(d, c)}"]
    if c["status"] == "blocked":
        lines.append(f"blocked: {c.get('blocked_reason')}")
    if c.get("kind") == "release":
        lines.append(f"grant: {grant_line(d['release'])}; attempts {c.get('attempts', 0)}; "
                     f"approvals unused: {'; '.join(c.get('approvals', [])) or 'none'}")
    if c.get("after"):
        lines.append(f"after: {', '.join(c['after'])} (the base is the branch of the last one "
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
    gates = folder / "work" / "gates"
    logs = sorted(gates.glob("*.log")) if gates.is_dir() else []
    if logs:
        tail = logs[-1].read_text(encoding="utf-8", errors="replace").splitlines()[-5:]
        lines += [f"last gate log {logs[-1].name}:"] + [f"  {ln}" for ln in tail]
    return lines


def handoff(args) -> list[str]:
    """The CR's facts, for any agent; changes nothing."""
    repo = Repo.find()
    batch, d, c = _batch_cr(repo, args.cr, args.batch)
    return _facts(repo, batch, d, c)


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
                b.log("take", None, note=args.note)
                crs = _chain(d)
                return [f"the stack of batch {batch}: {' → '.join(x['id'] for x in crs)}"] + [
                    f"{x['id']} {x['status']} worktree {x['worktree']} branch {x['branch']} "
                    f"base {_stack_ref(d, x, repo)} PR {x.get('pr') or 'none'}" for x in crs]
            c = b.cr(args.cr)
            check_take(b, c, args.note)
            if c["status"] in {"ready", "blocked"}:
                c.setdefault("notes", []).append(f"back to a Driver: {args.note}")
            b.touch(c, status="working", blocked_reason=None)
            b.log("take", c["id"], note=args.note)
            _work(repo, c).mkdir(parents=True, exist_ok=True)
            facts = _facts(repo, batch, d, c)
    return [f"took {c['id']} ({len(held(b))} of {d['slots']} slots held)"] + facts


def round_(args) -> list[str]:
    """A Driver counts a round before it starts the round's Coder; past the batch's limit, or
    the one the user granted the CR, it is refused (exit 5)."""
    repo = Repo.find()
    batch = find_cr_batch(repo, args.cr, args.batch)
    with changes_lock(repo):
        with Batch(repo, batch, actor="driver") as b:
            c = b.cr(args.cr)
            if c["status"] not in LIVE:
                raise ChantierError(f"{args.cr} is {c['status']}: no Driver to run a round")
            limit = check_round(b, c)
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
                            "<pr>, fix: …; <path>, infra: …, budget: …, rounds: …, refused …",
                            EXIT_USAGE)
    with changes_lock(repo):
        with Batch(repo, find_cr_batch(repo, args.cr, args.batch), actor="driver") as b:
            c = b.cr(args.cr)
            if c["status"] not in LIVE:
                raise ChantierError(f"{args.cr} is {c['status']}: no Driver to hand it back")
            line = f"[driver {args.cr}→foreman] hand-back {args.result} {note}"
            if args.result == "blocked":
                b.log("handback", args.cr, result=args.result, note=note)
                b.touch(c, status="blocked", blocked_reason=note)
                return [line, f"{args.cr} blocked; the Foreman asks the Chief of Staff"]
            if c.get("kind") == "release":  # released: nothing is left to merge
                c["released"] = note.split()[0]
                b.log("handback", args.cr, result=args.result, note=note)
                archive_cr(b, c)
                b.touch(c, status="merged")
                return [line, f"{args.cr} released and archived"
                        + ("; every CR is merged or cancelled: `chantier land`"
                           if all_merged(b) else "")]
            if not c.get("pr"):
                raise ChantierError(f"{args.cr}: ready means a PR recorded (`chantier ship`)")
            b.log("handback", args.cr, result=args.result, note=note)
            b.touch(c, status="ready")
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


def rules(args) -> list[str]:
    """The project's rules: its instruction file and the local Markdown files it links, two
    levels deep. Every role reads them before its own card; they rank above it."""
    repo = Repo.find()
    found = project_instructions(repo)
    if not found:
        raise ChantierError(f"no {', '.join(INSTRUCTIONS)} in {repo.root}: ask your parent")
    root = repo.root.resolve()
    seen = [found.resolve()]
    _linked(found.resolve(), root, seen, 2)
    return [f"{p.as_posix()} ({sum(1 for _ in p.open(encoding='utf-8', errors='replace'))} lines)"
            for p in seen]


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

    def __enter__(self):
        self.f = open(self.path, "a+", encoding="utf-8")
        deadline = time.monotonic() + LONG_GATE_WAIT_S
        holder = None
        while not _try_lock(self.f):
            if holder is None:
                holder = _lock_holder(self.repo) or "another CR"
                self._wait_note(holder)
            if time.monotonic() > deadline:
                self.f.close()
                raise ChantierError(f"the long gate of {holder} has run for over an hour: "
                                    "check it")
            time.sleep(1)
        left = _lock_holder(self.repo)  # a gate that died without cleaning up: its suite may run on
        m = re.search(r"\bpg(\d+)\b", left)
        if m and procs.alive(int(m[1])):
            self._wait_note(f"{left} (its command still runs)")
            while procs.alive(int(m[1])):
                if time.monotonic() > deadline:
                    _unlock(self.f)
                    self.f.close()
                    raise ChantierError(f"the long gate of {left} has run for over an hour: "
                                        "check it")
                time.sleep(1)
        self.holding(f"{self.cr} pid {os.getpid()}")
        return self

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


def gate(args) -> tuple[list[str], int]:
    """The long gate: the command the project's rules name, run in the CR's worktree, alone in
    the repository (a second one waits), logged in the work folder, recorded with its head."""
    repo = Repo.find()
    batch, _, c = _batch_cr(repo, args.cr, args.batch)
    wt = _worktree(c)
    cmd = args.command.strip()
    if not cmd:
        raise ChantierError("gate <cr> \"<the long gate's command, from the project's rules>\"",
                            EXIT_USAGE)
    logdir = _work(repo, c) / "gates"
    logdir.mkdir(parents=True, exist_ok=True)
    log = logdir / f"{time.strftime('%Y%m%d-%H%M%S')}.log"
    with _LongGateLock(repo, args.cr, log) as lock:
        # closed while the gate runs: a `cancel` must be able to move the CR's folder on Windows
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"$ {cmd}\n")
            f.flush()
            group = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
                     if sys.platform == "win32" else {"start_new_session": True})
            p = subprocess.Popen(cmd, shell=True, cwd=wt, stdout=f, stderr=subprocess.STDOUT,
                                 **group)
        lock.holding(f"{args.cr} pid {os.getpid()} pg{p.pid}")
        rc = p.wait()
    head = git("rev-parse", "--short", "HEAD", cwd=wt)
    result = "pass" if rc == 0 else "fail"
    with Batch(repo, batch, actor="driver") as b:
        b.log("gate", args.cr, result=result, head=head, command=cmd)
    if rc:
        # gates write in the console's code page: never fail on their bytes
        tail = (log.read_text(encoding="utf-8", errors="replace").splitlines()[-8:]
                if log.exists() else [])
        return [f"FAIL {cmd} (exit {rc}) at {head}; log {log}"] + tail, EXIT_EXTERNAL
    return [f"pass {cmd} at {head}; log {log}"], 0


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
    short = head[:7]
    if not any(e.get("kind") == "gate" and e.get("result") == "pass" and e.get("head") == short
               for e in _cr_events(repo, batch, c["id"])):
        off.append(f"no long gate passed at {short} (`chantier gate`)")
    base = _stack_base(d, c, repo)
    with Batch(repo, batch, actor="driver") as b:
        b.touch(b.cr(c["id"]), pr=args.pr, head=short)
        b.log("ship", c["id"], pr=args.pr, base=base, head=short, off=off)
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
    """The release CR's attempts and its irreversible actions: each one is approved by the user,
    or allowed by the grant the user gave, within the budget. A fix's merge is an action too:
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
            b.touch(c, attempts=c.get("attempts", 0) + 1, pr=None, head=None)
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
            return [f"no: the budget is spent (${b.data.get('spent_usd', 0):.2f} of "
                    f"${b.data['budget_usd']}); only the user raises it"], EXIT_BUDGET
        if result == "fix":
            return [f"no: fix {why} is not merged"], EXIT_PRECONDITION
        if result == "ask":
            return [f"no approval for: {args.note}; the user's word comes as `order approve`"], \
                EXIT_PRECONDITION
        return [f"go: {args.note} ({why})"], 0


def cancel(args) -> list[str]:
    """A dropped CR, on the user's word: its gate and its stray processes stopped, its folder
    in the trash with its work."""
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
        + (["every CR is merged or cancelled: `chantier land`"] if done else [])


def land(args) -> list[str]:
    """The batch's end: the cost is final, the batch's STATUS.md is the report."""
    repo = Repo.find()
    batch = resolve_batch(repo, args.batch)
    with Batch(repo, batch, actor="foreman") as b:
        check_epoch(b, args.epoch)
        live_ids = [c["id"] for c in b.data["crs"] if c["status"] in LIVE]
        pending = [o["id"] for o in b.data["orders"] if not o["done"]]
        queued = [c["id"] for c in b.data["crs"] if c["status"] == "queued"]
        open_ = [c["id"] for c in b.data["crs"] if c["status"] in {"ready", "blocked"}]
        if live_ids or pending or queued or open_ or b.data.get("stack_agent"):
            raise ChantierError(f"cannot land {batch}: live {live_ids or '-'}, queued {queued or '-'}, "
                                f"not merged {open_ or '-'}, orders pending {pending or '-'}, "
                                f"stack driver {b.data.get('stack_agent') or 'none'}")
        try:
            rows = _cost_rows(repo, b.data, b.data["host"], _foreman_uuid(b.data))
            _record_costs(repo, b, rows)
            summary = _cost_summary(b.data, rows, _cost_groups(repo, batch, rows, "cr"),
                                    _cost_groups(repo, batch, rows, "driver"),
                                    _chief_line(repo, b.data))
        except ChantierError as e:  # never a false $0.00
            summary = [f"Spent: unknown ({e})"]
        b.data.update(status="landed", landed=now(), summary=summary)
        b.log("land", None)
    return [f"landed {batch}", f"report: {b.dir / 'STATUS.md'}"]


def _landed_batch(repo: Repo, batch: str | None) -> tuple[str, Path, dict]:
    landed = [d for d in repo.batch_folders()
              if _read_json(d / "batch.json").get("status") == "landed"]
    batch = normalize_batch(batch) if batch else batch
    named = [d for d in landed if not batch or _read_json(d / "batch.json")["id"] == batch]
    if len(named) != 1:
        raise ChantierError(f"close names one landed batch; landed: "
                            f"{', '.join(d.name for d in landed) or 'none'}", EXIT_USAGE)
    d = _read_json(named[0] / "batch.json")
    return d["id"], named[0], d


def close(args) -> tuple[list[str], int]:
    """The batch's folder goes: the Chief of Staff shows the user what would go, with the
    dropped CRs' worktrees and branches it removes itself on the same word, and passes `--yes`.
    Without it, nothing is touched."""
    repo = Repo.find()
    with changes_lock(repo):
        batch, folder, d = _landed_batch(repo, args.batch or os.environ.get("CHANTIER_BATCH"))
        held = [p.name for p in folder.iterdir() if p.is_dir()]
        if held:
            raise ChantierError(f"{folder.name} still holds {', '.join(held)}: nothing was deleted")
        dropped = [f"{c['id']} worktree {c['worktree']} branch {c['branch']}"
                   for c in d["crs"] if c["status"] == "cancelled"]
        lines = [f"close {batch} deletes the folder {_shown(repo, folder)}",
                 "the dropped CRs, to remove on the same word where they still exist "
                 f"(`git worktree remove --force`, `git branch -D`): {'; '.join(dropped) or 'none'}"]
        if not args.yes:
            return lines + ["ask the user, then `chantier close --yes`"], 0
        going = folder.with_name(f".closing-{folder.name}")
        try:  # a rename fails whole on a file in use; a delete would stop halfway
            _retry(os.replace, folder, going)
        except OSError as e:
            raise ChantierError(f"{folder.name} is in use, close what holds it and run this again: "
                                f"{e}", EXIT_EXTERNAL) from e
        shutil.rmtree(going)
        write_dashboard(repo, stage_layout(repo))
    return [f"closed {batch}: the folder is deleted"] + lines[1:], 0


# ---- cost -------------------------------------------------------------------------------------

def _cost_rows(repo: Repo, d: dict, host: str, uuids: list[str]) -> list[dict]:
    """Every Foreman of the batch, summed, from its opening to its landing."""
    rows: list[dict] = []
    for uuid in uuids:
        if host == "copilot":
            rows += costs.copilot_session_costs(uuid)
        else:
            rows += costs.session_costs(costs.transcript_path(repo.root, uuid),
                                        d.get("created", ""), d.get("landed", ""),
                                        allow_empty=len(uuids) > 1)
    if not any(r["calls"] for r in rows):
        raise ChantierError("no priced calls in the Foreman transcripts", EXIT_EXTERNAL)
    return rows


def _foreman_uuid(d: dict) -> list[str]:
    uuids = d.get("foreman_transcripts") or [d.get("foreman_transcript")]
    if not uuids[0]:
        raise ChantierError("no Foreman transcript recorded", EXIT_PRECONDITION)
    return uuids


def _chief_line(repo: Repo, d: dict) -> str:
    """The Chief of Staff's session, priced apart: it is never in `spent_usd` nor in the budget."""
    uuid = d.get("chief_transcript")
    if not uuid or d.get("host") == "copilot":
        return "Chief of Staff: not measured"
    path = costs.transcript_path(repo.root, uuid)
    try:
        whole = costs.session_costs(path, kind="chief-of-staff")
        since = costs.session_costs(path, d.get("created", ""), kind="chief-of-staff",
                                    allow_empty=True)
    except ChantierError as e:
        return f"Chief of Staff: not measured ({e})"
    return (f"Chief of Staff: ${sum(r['usd'] for r in since):.2f} since the batch opened, "
            f"${sum(r['usd'] for r in whole):.2f} the whole session, "
            f"context {whole[0]['last_context']:,} tokens")


def _cost_groups(repo: Repo, batch: str, rows: list[dict], by: str) -> dict[str, list]:
    """Calls and dollars, by agent type (the role, as the host names the agent) or by CR."""
    agent_cr = {}  # every Driver a CR ever had, from the log: a replaced one keeps its CR
    for e in read_events(repo.batch_dir(batch)):
        if e.get("kind") == "agent" and e.get("cr") and e["cr"] != "stack":
            agent_cr[e["agent"]] = e["cr"]
    parents = {r["agent"]: r.get("parent") for r in rows}
    by_agent = {r["agent"]: r for r in rows if r["agent"] != "main"}

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
        elif by == "driver":  # the type of the agent a chain of parents leads back to
            root = r
            for _ in range(5):
                parent = by_agent.get(root.get("parent"))
                if root["agent"] == "main" or parent is None or parent["agent"] == "main":
                    break
                root = parent
            key = root["type"]
        else:
            key = r["type"]
        groups[key][0] += r["calls"]
        groups[key][1] += r["usd"]
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


def _cost_summary(d: dict, rows: list[dict], by_cr: dict[str, list],
                  by_driver: dict[str, list], chief: str) -> list[str]:
    """What the user reads at the end of a batch; the detail is in `cost --by`. The Foreman is
    the main agent, the Drivers every other agent that started one, from the transcripts'
    parent links, and the workers the rest. Amounts and shares add up as printed."""
    total = sum(r["usd"] for r in rows)
    budget = d.get("budget_usd")
    parents = {r.get("parent") for r in rows if r.get("parent")}
    foreman_usd = sum(r["usd"] for r in rows if r["agent"] == "main")
    drivers_usd = sum(r["usd"] for r in rows if r["agent"] != "main" and r["agent"] in parents)
    parts = [foreman_usd, drivers_usd, total - foreman_usd - drivers_usd]
    parts[2] = max(parts[2], 0.0)
    cents = _apportion(parts, round(total * 100))
    shares = _apportion(parts, 100) if total else [0, 0, 0]
    split = ", ".join(f"{name} ${c / 100:.2f} ({s}%)"
                      for name, c, s in zip(("Foreman", "Drivers", "workers"), cents, shares))
    top = sorted(((k, v[1]) for k, v in by_cr.items() if k != "foreman"), key=lambda kv: -kv[1])
    mains = [r for r in rows if r["agent"] == "main"]  # one per Foreman session of the batch
    n = sum(r.get("wakes", 0) for r in mains)
    wakes = [f"Foreman: {n} wakes, context "
             f"{sum(r.get('wake_context', 0) for r in mains) // n:,} tokens on average, "
             f"{max(r.get('peak_context', 0) for r in mains):,} at its peak"] if n else []
    return [f"Total: ${total:.2f}" + (f" of a ${budget:g} budget" if budget else ", no budget"),
            split,
            "Most: " + (", ".join(f"{k} ${usd:.2f}" for k, usd in top[:3]) or "-"),
            *wakes,
            *(f"Driver {k}: ${v[1]:.2f} ({v[0]} calls)" for k, v in
              sorted(by_driver.items(), key=lambda kv: -kv[1][1]) if k != "foreman"),
            chief,
            "Not counted: compaction calls, which leave no record (about $0.12 each)"]


def cost(args) -> list[str]:
    """The batch's spend, read from the Foreman's transcript on the batch's host; `status
    --refresh` and `land` record it."""
    repo = Repo.find()
    batch = resolve_batch(repo, args.batch)
    d = read_batch(repo, batch)
    if not (d.get("foreman_transcripts") or d.get("foreman_transcript")):
        var = "$COPILOT_AGENT_SESSION_ID" if d["host"] == "copilot" else "$CLAUDE_CODE_SESSION_ID"
        raise ChantierError(f"no Foreman transcript recorded: the Foreman runs "
                            f"`chantier foreman transcript {var}`")
    rows = _cost_rows(repo, d, d["host"], _foreman_uuid(d))
    total = sum(r["usd"] for r in rows)
    chief = _chief_line(repo, d)
    if args.summary:
        return _cost_summary(d, rows, _cost_groups(repo, batch, rows, "cr"),
                             _cost_groups(repo, batch, rows, "driver"), chief)
    groups = _cost_groups(repo, batch, rows, args.by)
    estimated = sum(r.get("estimated", 0) for r in rows)
    lines = [f"{batch}: ${total:.3f} over {sum(r['calls'] for r in rows)} model calls"
             + (f" ({estimated} estimated, not billed)" if estimated else "")]
    lines += [f"{k}: ${v[1]:.3f} ({v[0]} calls)"
              for k, v in sorted(groups.items(), key=lambda kv: -kv[1][1])]
    return lines + [chief]
