"""The inbox: `init`, `file`, `triage`, `abandon` and `restore`."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from chantier.commands.crs import new_request, shown, slugify
from chantier.commands.opening import cr_slug
from chantier.core.batch import RESTORED_NUMBER_FILE, move_directory
from chantier.core.clock import stamp
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.git import git
from chantier.core.records import (
    CrEntry,
    read_batch_json,
    read_restored_number,
    write_restored_number,
)
from chantier.core.repo import Repo
from chantier.lifecycle.convert import convert_old_tree, open_repo
from chantier.lifecycle.stages import (
    PRIORITIES,
    changes_lock,
    ensure_unclaimed,
    move_backlog_item,
    stage_layout,
)
from chantier.status.write import write_dashboard


def init(args: argparse.Namespace) -> list[str]:
    """Create the eight stage folders, empty; leave the ones that exist; write nothing else."""
    try:
        repo = open_repo()
    except ChantierError as e:
        raise ChantierError(
            f"no git repository found ({e}): chantier needs one; run `git init` first",
            EXIT_PRECONDITION,
        ) from e
    gitdir = Path(
        git("rev-parse", "--path-format=absolute", "--git-dir", check=False) or "."
    ).resolve()
    if gitdir != repo.git_dir:  # preflight's P7
        raise ChantierError(
            f"this is a linked worktree: init runs in the main checkout ({repo.session_root})",
            EXIT_PRECONDITION,
        )
    convert_old_tree(repo)  # an older tree first, so that its folders are not made twice
    repo.changes.mkdir(parents=True, exist_ok=True)
    repo.ensure_gitignore()
    lines = []
    for key, folder in stage_layout(repo).items():
        if key == "batches":  # the parent of the three state folders, made with them
            continue
        existed = folder.is_dir()
        folder.mkdir(parents=True, exist_ok=True)
        lines.append(f"{'exists ' if existed else 'created'} {shown(repo, folder)}")
    return lines


def file_cr(args: argparse.Namespace) -> list[str]:
    repo = open_repo()
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
    slug = args.slug or slugify(title)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,80}", slug):
        raise ChantierError("CR slug: lowercase letters, digits and hyphens", EXIT_USAGE)
    with changes_lock(repo):
        folder = new_request(repo, slug, raw)
        write_dashboard(repo, paths)
    return [f"filed {shown(repo, folder)}; write the intent and grill the CR here"]


def triage(args: argparse.Namespace) -> list[str]:
    repo = open_repo()
    with changes_lock(repo):
        target = move_backlog_item(
            repo, args.item, args.priority, stage_layout(repo), ready=args.ready
        )
        write_dashboard(repo, stage_layout(repo))
    return [f"triaged {shown(repo, target)}" + (f" ({args.priority})" if args.priority else "")]


def abandon(args: argparse.Namespace) -> list[str]:
    repo = open_repo()
    paths = stage_layout(repo)
    source = repo.planning_path(args.item, "CR folder")
    in_backlog = source.parent.parent == paths["backlog"] and source.parent.name in PRIORITIES
    in_batch = source.parent in (paths["pending"], paths["actives"])
    if source.parent not in (paths["inbox"], paths["ready"]) and not in_batch and not in_backlog:
        raise ChantierError(
            "only an inbox, backlog, 3-ready or unclaimed batch CR can be abandoned", EXIT_USAGE
        )
    with changes_lock(repo):
        ensure_unclaimed(repo, source)
        target = paths["trash"] / f"{stamp()}-{source.name}"
        move_directory(source, target)
        write_dashboard(repo, paths)
    return [f"abandoned {shown(repo, target)}"]


def _owners(repo: Repo, source: Path) -> tuple[tuple[str, CrEntry] | None, list[str]]:
    """The open batch's CR that owned this folder (batch id, CR), and the slugs of its other CRs."""
    known, batch_crs = None, []
    for batch_dir in repo.batch_folders():
        record = read_batch_json(batch_dir / "batch.json")
        for cr in (c for c in record.crs if c.path):
            path = cr.path or ""
            if repo.planning_path(path, "recorded CR path") == source:
                known = (record.id or "?", cr)
            else:
                batch_crs.append(cr_slug(Path(path).name))
    return known, batch_crs


def _restored_name(source: Path, known: object, slug: str | None) -> str:
    name = re.sub(r"^(?:\d{6}-\d{4}-)+", "", source.name)
    if known:  # a number is stripped only from a folder a batch record says is its CR's
        name = re.sub(r"^(?:CR-)?\d+-", "", name, flags=re.I)
    name = slug or name
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,80}", name):
        raise ChantierError(
            f"restore: {name!r} is not a CR slug (lowercase letters, digits "
            "and hyphens): restore again with --slug <name>",
            EXIT_USAGE,
        )
    return name


def _check_free(repo: Repo, paths: dict[str, Any], name: str, batch_crs: list[str]) -> None:
    taken = [
        paths["inbox"] / name,
        paths["ready"] / name,
        *(paths["backlog"] / p / name for p in PRIORITIES),
    ]
    clash = next((shown(repo, t) for t in taken if t.exists()), None) or (
        f"a CR of the open batch ({name})" if name in batch_crs else None
    )
    if clash:
        raise ChantierError(
            f"restore: the name {name} is already used by {clash}; "
            f"restore again with --slug <other>",
            EXIT_PRECONDITION,
        )


def _remember(repo: Repo, target: Path, known: tuple[str, CrEntry]) -> None:
    """Note on the folder what it was, and never give its number again."""
    number = re.fullmatch(r"CR-(\d+)", known[1].id)
    if number:  # the number is never given again, even once the batch is closed
        path = repo.changes / RESTORED_NUMBER_FILE
        write_restored_number(path, max(read_restored_number(path), int(number[1])))
    intent = target / "01-intent.md"
    with open(intent if intent.is_file() else target / "notes.md", "a", encoding="utf-8") as f:
        f.write(f"\nformerly {known[1].id} of {known[0]}\n")


def restore(args: argparse.Namespace) -> list[str]:
    """The reverse of `abandon`: a folder of `6-trash` comes back to `1-inbox`, whole, without its
    date (and without its number when an open batch's record says it was that batch's CR). Only on
    the user's word. A cancelled CR of an open batch stays cancelled there; its branch, worktree and
    PR are not touched."""
    repo = open_repo()
    paths = stage_layout(repo)
    source = repo.planning_path(args.item, "CR folder")
    if source.parent != paths["trash"] or not source.is_dir():
        raise ChantierError(
            f"restore takes a folder directly under 6-trash: {shown(repo, source)} is not one",
            EXIT_PRECONDITION,
        )
    with changes_lock(repo):
        known, batch_crs = _owners(repo, source)
        name = _restored_name(source, known, args.slug)
        _check_free(repo, paths, name, batch_crs)
        target = paths["inbox"] / name
        move_directory(source, target)
        if known:
            _remember(repo, target, known)
        write_dashboard(repo, paths)
    lines = [f"restored {shown(repo, target)}"]
    if known and known[1].status == "cancelled":
        cr = known[1]
        lines.append(
            f"{cr.id} stays cancelled in {known[0]}: its branch {cr.branch}, "
            f"worktree {cr.worktree} and PR {cr.pr or 'none'} are not "
            "touched; `order add` brings it back in a batch"
        )
    return lines
