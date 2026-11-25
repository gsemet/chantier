"""The inbox: `init`, `file`, `triage`, `abandon` and `restore`."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from chantier.board.projects import project_name
from chantier.core.batch import RESTORED_NUMBER_FILE, move_directory
from chantier.core.clock import stamp
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.records import (
    CrEntry,
    read_batch_json,
)
from chantier.core.repo import Repo
from chantier.hub import arrivals, journal
from chantier.lifecycle.backlog import file_idea_at, move_item
from chantier.lifecycle.filing import shown
from chantier.lifecycle.moveout import folder_taken, remember_cr
from chantier.lifecycle.running_batch import clear_mark, mark_running_batch
from chantier.lifecycle.stages import (
    PRIORITIES,
    TRIAGE_USAGE,
    changes_lock,
    cr_folder_arg,
    cr_slug,
    ensure_unclaimed,
    stage_layout,
)
from chantier.status.write import write_dashboard


def init(args: argparse.Namespace) -> list[str]:
    """Create the eight stage folders, empty; leave the ones that exist; write nothing else."""
    try:
        repo = Repo.find()
    except ChantierError as e:
        raise ChantierError(
            f"no git repository found ({e}): chantier needs one; run `git init` first",
            EXIT_PRECONDITION,
        ) from e
    here = repo.session_checkout()
    if here.linked:  # preflight's P7
        raise ChantierError(repo.linked_text(here, here.top), EXIT_PRECONDITION)
    repo.changes.mkdir(parents=True, exist_ok=True)
    repo.ensure_gitignore()
    lines = []
    stages = [f for k, f in stage_layout(repo).items() if k != "batches"]
    repo.check_publish(stages)
    for folder in stages:  # `batches` is the parent of the three state folders, made with them
        existed = folder.is_dir()
        repo.store.make_folder(repo.rel(folder), True)
        lines.append(f"{'exists ' if existed else 'created'} {shown(repo, folder)}")
    return lines


def file_cr(args: argparse.Namespace) -> list[str]:
    repo = Repo.find()
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
    folder, lines = file_idea_at(repo, text, args.slug, raw, args.title)
    _arrived(repo, folder.name, {}, arrivals.stage_of(repo, folder))
    return lines


def _arrived(repo: Repo, slug: str, before: dict[str, str], stage: str) -> None:
    """One `arrived@1` line (`via: session`) when a CR reached the inbox or the backlog, unless
    this run is chantier's own session (the seat's). The journal's append is not guarded: a
    refusal of it surfaces as the command's error, after the filing or the move was made."""
    found = arrivals.arrivals(before, {slug: stage})
    if not found or arrivals.own_session(repo):
        return
    events = [arrivals.event(project_name(repo), a, "session") for a in found]
    journal.append(repo, events, "cli")


def triage(args: argparse.Namespace) -> list[str]:
    """Move a CR between the inbox, the priorities and `3-ready`, or mark it for the running
    batch (`--running-batch`). `--ready` joins no batch: a CR joins one by `order add`."""
    marked = getattr(args, "running_batch", False)
    chosen = [
        args.priority,
        "3-ready" if args.ready else None,
        "inbox" if args.inbox else None,
        "running-batch" if marked else None,
    ]
    if sum(c is not None for c in chosen) != 1:
        raise ChantierError(TRIAGE_USAGE, EXIT_USAGE)
    repo = Repo.find()
    if marked:
        return mark_running_batch(repo, args.item)
    to = next(c for c in chosen if c)
    source = cr_folder_arg(repo, args.item)
    was = arrivals.stage_of(repo, source)
    lines = move_item(repo, args.item, to)
    after = "3-ready" if to == "3-ready" else "1-inbox" if to == "inbox" else f"2-backlog/{to}"
    if not was.startswith(arrivals.ELSEWHERE_ROOTS):  # a restore is no arrival
        _arrived(repo, source.name, {source.name: was}, after)
    return lines


def abandon(args: argparse.Namespace) -> list[str]:
    repo = Repo.find()
    paths = stage_layout(repo)
    source = cr_folder_arg(repo, args.item)
    in_backlog = source.parent.parent == paths["backlog"] and source.parent.name in PRIORITIES
    in_batch = source.parent in (paths["pending"], paths["actives"])
    if source.parent not in (paths["inbox"], paths["ready"]) and not in_batch and not in_backlog:
        raise ChantierError(
            "only an inbox, backlog, 3-ready or unclaimed batch CR can be abandoned", EXIT_USAGE
        )
    with changes_lock(repo):
        ensure_unclaimed(repo, source)
        target = paths["trash"] / f"{stamp()}-{source.name}"
        move_directory(repo, source, target)
        clear_mark(repo, target)
        write_dashboard(repo, paths)
    return [f"abandoned {shown(repo, target)}"]


def _owners(repo: Repo, source: Path) -> tuple[tuple[str, CrEntry] | None, list[str]]:
    """The open batch's CR that owned this folder (batch id, CR), and the slugs of its other CRs."""
    known, batch_crs = None, []
    for batch_dir in repo.batch_folders():
        record = read_batch_json(repo.store, batch_dir / "batch.json")
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


def _check_free(repo: Repo, name: str, batch_crs: list[str]) -> None:
    clash = folder_taken(repo, name, batch_crs)
    if clash:
        raise ChantierError(
            f"restore: the name {name} is already used by {clash}; "
            f"restore again with --slug <other>",
            EXIT_PRECONDITION,
        )


def _remember(repo: Repo, target: Path, known: tuple[str, CrEntry]) -> None:
    """Note on the folder what it was, and never give its number again."""
    remember_cr(repo, target, known[1].id, known[0])


def restore(args: argparse.Namespace) -> list[str]:
    """The reverse of `abandon`: a folder of `6-trash` comes back to `1-inbox`, whole, without its
    date (and without its number when an open batch's record says it was that batch's CR). Only on
    the user's word. A cancelled CR of an open batch stays cancelled there; its branch, worktree and
    PR are not touched."""
    repo = Repo.find()
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
        _check_free(repo, name, batch_crs)
        target = paths["inbox"] / name
        if known:
            repo.check_publish(
                [
                    repo.changes / RESTORED_NUMBER_FILE,
                    target / "01-intent.md",
                    target / "notes.md",
                ]
            )
        move_directory(repo, source, target)
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
