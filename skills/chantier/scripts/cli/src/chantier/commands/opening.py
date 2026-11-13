"""`chantier open`: the batch's frame, its CRs and their dependencies."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from chantier.commands.crs import grant_line, shown, slugify
from chantier.commands.opening_record import (
    instruction_files,
    new_record,
    open_settings,
    release_grant,
)
from chantier.commands.registry import NO_BATCH, Subparsers, add_command
from chantier.commands.seat import own_transcript
from chantier.core.batch import Batch, next_cr_number
from chantier.core.clock import now
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.files import read_text
from chantier.core.repo import Repo
from chantier.lifecycle.convert import open_repo
from chantier.lifecycle.session import RenderedBatch
from chantier.lifecycle.stages import (
    changes_lock,
    cr_directory,
    ensure_unclaimed,
    prepared_cr,
    stage_layout,
)
from chantier.plugin_files import detect_host, read_playbook
from chantier.rails import ENDED, alone, check_no_open_batch, is_release


def add_cr(b: Batch, item: str, kind: str = "change") -> dict[str, Any]:
    """Move a prepared CR into `1-pending` and name its branch and worktree: the Driver creates
    them, on the fresh default branch, as its first step."""
    repo = b.repo
    paths = stage_layout(repo)
    prepared = prepared_cr(repo, item, paths)
    ensure_unclaimed(repo, prepared.directory)
    number = next_cr_number(
        repo, (paths["archives"], paths["trash"], paths["pending"], paths["actives"], paths["done"])
    )
    cr_id = f"CR-{number}"
    slug = re.sub(r"^(?:CR-)?\d+-", "", prepared.directory.name, flags=re.I)
    cdir = paths["pending"] / f"{number:03d}-{slugify(slug)}"
    origin = repo.rel(prepared.directory)
    b.move(prepared.directory, cdir)
    title = prepared.title
    branch = f"chantier/{b.id}/{cr_id.lower()}-{slugify(title)}"
    worktree = repo.worktrees / f"{b.id}-{cr_id}"
    order = max((c["order"] for c in b.data["crs"]), default=0) + 1
    c: dict[str, Any] = {
        "id": cr_id,
        "title": title,
        "kind": kind,
        "status": "queued",
        "order": order,
        "path": repo.rel(cdir),
        "specification": prepared.specification.relative_to(prepared.directory).as_posix(),
        "round": 0,
        "agent": None,
        "pr": None,
        "branch": branch,
        "worktree": str(worktree),
        "notes": [],
        "updated": now(),
    }
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
        raise ChantierError(
            f'{path}: not valid UTF-8 JSON ({e}); expected {{"after": ["<slug>", …]}}'
        ) from e
    after = data.get("after", []) if isinstance(data, dict) else None
    if not isinstance(after, list) or not all(isinstance(s, str) and s.strip() for s in after):
        raise ChantierError(
            f'{path}: expected {{"after": ["<slug>", …]}}, slugs being folder '
            "names without their number"
        )
    return after


def archived_merged(repo: Repo, slug: str) -> bool:
    paths = stage_layout(repo)
    folders = [
        f
        for stage in (paths["archives"], paths["done"])
        if stage.is_dir()
        for f in sorted(stage.iterdir())
    ]
    for folder in folders:
        if folder.is_dir() and folder.name != "batches" and cr_slug(folder.name) == slug:
            try:
                state = json.loads(read_text(folder / "STATUS.json")).get("state")
            except (OSError, ValueError):
                state = "merged"  # an archive holds only merged CRs
            if state == "merged":
                return True
    return False


def declare_dependencies(b: Batch, added: list[dict[str, Any]]) -> None:
    """Record the `after` of each CR just added, as CR ids, once all of them are in the batch.
    A slug archived as merged is met and not recorded; the rest is refused, naming the slug."""
    for c in added:
        ids = list(
            dict.fromkeys(
                dep
                for slug in read_depends(cr_directory(b.repo, c))
                if (dep := _dependency(b, c, slug))
            )
        )
        if ids:
            c["after"] = ids
            b.log("depends", c["id"], after=ids)
    check_cycles(b)


def _dependency(b: Batch, c: dict[str, Any], slug: str) -> str | None:
    """The id of the CR a `depends.json` slug names; None when it is met (archived as merged)."""
    key = slugify(slug)
    dep = next((x for x in b.data["crs"] if cr_slug(Path(x["path"]).name) == key), None)
    if dep is None:
        if archived_merged(b.repo, key):
            return None
        raise ChantierError(
            f"{c['id']}: depends.json names {slug!r}, which is in "
            "neither the batch nor the archives as merged"
        )
    if is_release(dep) and dep["id"] != c["id"]:
        raise ChantierError(
            f"{c['id']}: depends.json names {slug!r}, the batch's release "
            f"CR {dep['id']}, which waits for every other CR: a cycle. "
            "Remove it from depends.json"
        )
    return None if dep["status"] == "merged" else dep["id"]  # archived: met, so not recorded


def check_series_order(b: Batch) -> None:
    """A series runs in the order given: a CR cannot come before one it depends on."""
    place = {x["id"]: x["order"] for x in b.data["crs"]}
    for c in b.data["crs"]:
        if c.get("kind") in {"release", "fix"}:
            continue
        for dep in c.get("after", []):
            if place.get(dep, 0) > c["order"]:
                raise ChantierError(
                    f"{c['id']} depends on {dep}: it cannot come before it in the series"
                )


def _release_tag(b: Batch, c: dict[str, Any]) -> str:
    if alone(b.data["crs"], c):
        return " (release, alone in its batch: it starts when taken)"
    return (
        " (release: starts once every other CR is ready (stack, series) or merged "
        "(parallel); its PR is the user's to merge)"
    )


def release_waits_for_all(b: Batch) -> None:
    """The release CR's `after` holds every other CR of the batch that has not ended, fix CRs
    excepted (`pending_fixes` rules those); the CLI keeps the list, and an entry that ends stays
    as history."""
    for rel in b.data["crs"]:
        if not is_release(rel) or rel["status"] in ENDED:
            continue
        after = rel.setdefault("after", [])
        after += [
            x["id"]
            for x in b.data["crs"]
            if x["id"] != rel["id"]
            and x.get("kind") != "fix"
            and x["status"] not in ENDED
            and x["id"] not in after
        ]
        if not after:
            rel.pop("after")
    check_cycles(b)


def check_cycles(b: Batch) -> None:
    graph = {x["id"]: x.get("after", []) for x in b.data["crs"]}
    done: set[str] = set()

    def visit(node: str, path: list[str]) -> None:
        if node in path:
            cycle = [*path[path.index(node) :], node]
            raise ChantierError(f"dependency cycle: {' → '.join(cycle)}")
        if node in done:
            return
        for nxt in graph.get(node, []):
            visit(nxt, [*path, node])
        done.add(node)

    for node in graph:
        visit(node, [])


def _cr_line(b: Batch, c: dict[str, Any]) -> str:
    tag = _release_tag(b, c) if c["kind"] == "release" else ""
    after = f" (after {', '.join(c['after'])})" if c.get("after") and c["kind"] != "release" else ""
    return f"  - {c['id']}: {c['title']} ({c['path']}){tag}{after}\n"


def _brief_text(
    b: Batch, args: argparse.Namespace, host: str, release: dict[str, Any] | None
) -> str:
    repo = b.repo
    data = b.data
    instructions = f"- Project instructions: {instruction_files(repo.root)}"
    if repo.external:
        instructions += f"; the surface's: {instruction_files(repo.surface_root)}"
    return (
        f"# {b.id}\n\n- Mode: {data['mode']}. Slots: {args.slots}. "
        f"Budget: {args.budget or 'none'}. Host: {host}. "
        f"Steering: {data['steering']}.\n"
        "- CRs, in order:\n"
        + "".join(_cr_line(b, c) for c in data["crs"])
        + (f"- Release grant: {grant_line(release)}\n" if release else "")
        + instructions
        + ".\n"
        "- Team (who runs which role):\n"
        "- Autonomous decisions:\n- Questions to bring back:\n"
    )


def _open_crs(b: Batch, args: argparse.Namespace, release: dict[str, Any] | None) -> None:
    for i, item in enumerate(args.items, 1):
        c = add_cr(b, item, kind="release" if i == args.release else "change")
        if release and c["kind"] == "release":
            release["cr"] = c["id"]
    declare_dependencies(b, list(b.data["crs"]))
    release_waits_for_all(b)
    if args.mode == "series":
        check_series_order(b)


def _short(p: Path | str) -> str:
    return str(p).replace("\\", "/").split("changes/")[-1]


def open_batch(args: argparse.Namespace) -> list[str]:
    repo = open_repo()
    host = detect_host()
    team, problems = read_playbook(repo, host)  # before any folder moves
    if problems:
        raise ChantierError("\n".join(problems), EXIT_PRECONDITION)
    settings = open_settings(repo, args)
    repo.config.update(settings)
    paths = stage_layout(repo)
    release = release_grant(args)
    chief = own_transcript(host)
    if args.direct and not chief:
        raise ChantierError(
            "--direct needs the Chief of Staff's own session id "
            "(CLAUDE_CODE_SESSION_ID or COPILOT_AGENT_SESSION_ID): none is known, "
            "so a Foreman's claim could not be told from the Chief of Staff's",
            EXIT_PRECONDITION,
        )
    selected = [prepared_cr(repo, item, paths).directory for item in args.items]
    if len(set(selected)) != len(selected):
        raise ChantierError("the same CR was selected more than once", EXIT_USAGE)
    data = new_record(args, host, settings, release, chief)
    if team:  # a running batch keeps the playbook it opened with
        # the prices are read live at each pricing, not frozen with the roles
        data["playbook"] = {k: v for k, v in team.items() if k != "prices"}
    with changes_lock(repo):
        check_no_open_batch(repo)
        with RenderedBatch(repo, None, actor="chief-of-staff", create=data) as b:
            brief = b.dir / "brief.md"
            _open_crs(b, args, release)
            brief.write_text(_brief_text(b, args, host, release), encoding="utf-8")
            b.log("open", None, crs=[c["id"] for c in b.data["crs"]])
    lines = [
        f"opened {b.id} on {host}: {len(args.items)} CRs, {args.slots} slots, "
        f"{data['mode']}, steering {data['steering']}"
    ]
    # the next step comes before the CR list: past ten lines it is the list that is cut
    lines.append(
        f"next: complete the brief {shown(repo, brief)}, then "
        + ("steer it yourself" if args.direct else "start the Foreman")
    )
    lines += [
        f"{c['id']} {c['title'][:40]}: {_short(src)} -> {_short(c['path'])}"
        for c, src in zip(b.data["crs"], selected, strict=False)
    ]
    return lines


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(
        sub,
        "open",
        open_batch,
        "open a batch: each prepared CR gets its folder, and a branch and worktree name",
        NO_BATCH,
    )
    s.add_argument("items", nargs="+", help="path to a prepared CR folder or specification")
    s.add_argument("--slots", type=int, default=4)
    s.add_argument("--budget", type=float, help="USD; no Driver starts past it")
    s.add_argument(
        "--mode",
        choices=["parallel", "series", "stack"],
        default="parallel",
        help="parallel (default): independent CRs, each on the default branch; series: "
        "one after the other, in the order given, each on the previous one's "
        "branch; stack: independent CRs, then a stack driver stacks the PRs",
    )
    s.add_argument(
        "--release",
        type=int,
        metavar="N",
        help="the item number of the release CR; it waits for every other CR: prepared on top of a "
        "stack or a series once they are ready, after the merges in a parallel batch; its PR "
        "is the user's to merge",
    )
    s.add_argument(
        "--autonomous-releases",
        type=int,
        default=0,
        metavar="N",
        help="releases the user allows without asking (needs --budget)",
    )
    s.add_argument(
        "--grant-fixes",
        action="store_true",
        help="the Foreman starts and merges the release's fixes (needs --budget)",
    )
    s.add_argument(
        "--direct",
        action="store_true",
        help="no Foreman session: the Chief of Staff steers the batch itself",
    )
    s.add_argument("--default-branch", help="default: the remote's HEAD")
    s.add_argument("--remote", default="origin")
