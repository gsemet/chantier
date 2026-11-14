"""`summary`: the CR's condensed JSON. `lint` lists what is missing or late, `set` stores what an
agent wrote and records the checksums, `label` and `group` link CRs. The CLI writes no title and no
summary of its own, and no other command refuses because of a gap."""

from __future__ import annotations

import argparse
from pathlib import Path

from chantier.core.clock import now
from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.records import (
    GROUP_MAX,
    SUMMARY_MAX,
    TITLE_MAX,
    CrSummary,
)
from chantier.core.repo import Repo
from chantier.lifecycle.convert import open_repo
from chantier.lifecycle.filing import shown
from chantier.lifecycle.stages import changes_lock, cr_folders, cr_stage, stage_layout
from chantier.summaries import store
from chantier.summaries.edit import change_group, change_labels, label_set, one_line
from chantier.summaries.gaps import Gap, gap_of
from chantier.summaries.origin import issue_url, origin_of
from chantier.summaries.sources import checksums, covered_files


def _cr_folder(repo: Repo, paths: dict[str, Path], item: str) -> Path:
    """A CR folder of a stage, from the path the command was given."""
    folder = repo.planning_path(item, "CR folder")
    stage = cr_stage(paths, folder) if folder.is_dir() else None
    if stage is None:
        raise ChantierError(f"not a CR folder: {shown(repo, folder)}", EXIT_USAGE)
    if stage == "trash":
        raise ChantierError("a dropped CR keeps its summary as it is: restore it first", EXIT_USAGE)
    return folder


def _gap_line(repo: Repo, gap: Gap) -> str:
    path = shown(repo, gap.folder)
    if gap.kind == "no summary":
        return (
            f"{path}: no summary → summary set {path} "
            '--title "<title>" --summary "<the CR\'s state now>"'
        )
    if gap.kind == "unreadable":
        return (
            f"{path}: summary.json unreadable ({gap.error}) → repair or remove it, "
            f"then summary set {path} …"
        )
    files = ", ".join(f"{c.path} {c.how}" for c in gap.changes)
    return (
        f'{path}: summary late ({files}) → read them, then summary set {path} --summary "<…>" '
        "or --unchanged"
    )


def lint(args: argparse.Namespace) -> tuple[list[str], int] | list[str]:
    """The gaps, one line each with the command that closes it; nothing is written."""
    repo = open_repo()
    paths = stage_layout(repo)
    folders = [_cr_folder(repo, paths, item) for item in args.folders] or cr_folders(paths)
    crs = [f for f in folders if covered_files(f)]
    gaps = [gap for f in crs if (gap := gap_of(f))]
    if not gaps:
        return [f"no gap ({len(crs)} CRs)"]
    return [f"{len(gaps)} gap(s) in {len(crs)} CRs", *(_gap_line(repo, g) for g in gaps)], 2


def _require_fields(current: CrSummary, title: str | None, text: str | None, same: bool) -> None:
    """What the file lacks, given what this call brings."""
    if not (title or current.title):
        raise ChantierError("--title is required: this CR has no title yet", EXIT_USAGE)
    if not (text or current.summary):
        what = "--unchanged needs a summary already set: give" if same else "give"
        raise ChantierError(f"{what} --summary: this CR has no summary yet", EXIT_USAGE)


def set_summary(args: argparse.Namespace) -> list[str]:
    """Store the title and summary an agent gives, refresh the origin from the `issue:` line, and
    record the covered files' checksums when the summary is set or confirmed."""
    repo = open_repo()
    folder = _cr_folder(repo, stage_layout(repo), args.folder)
    title = None if args.title is None else one_line(args.title, "title", TITLE_MAX)
    text = None if args.summary is None else one_line(args.summary, "summary", SUMMARY_MAX)
    if title is None and text is None and not args.unchanged:
        raise ChantierError("summary set takes --title, --summary or --unchanged", EXIT_USAGE)
    origin = origin_of(issue_url(folder), args.tracker)
    with changes_lock(repo):
        current = store.read_or_new(folder)
        _require_fields(current, title, text, args.unchanged)
        if title:
            current.title = title
        if text or args.unchanged:
            current.summary = text or current.summary
            current.sources = checksums(folder)
            current.summarized = now()
        current.origin = origin
        store.write(folder, current)
    kind = f"{origin.kind} {origin.ref}" if origin.ref else origin.kind
    return [f"summary set {shown(repo, folder)} (origin {kind}; {len(current.sources)} files)"]


def _folders(items: list[str]) -> tuple[Repo, list[Path]]:
    repo = open_repo()
    paths = stage_layout(repo)
    return repo, [_cr_folder(repo, paths, item) for item in items]


def label(args: argparse.Namespace) -> list[str]:
    """Add or remove labels on CRs; a label never makes a summary fresh or late."""
    add, remove = (label_set(raw) if raw else set() for raw in (args.add, args.remove))
    repo, folders = _folders(args.folders)
    return change_labels(repo, folders, add, remove)


def group(args: argparse.Namespace) -> list[str]:
    """Put CRs in one group, or take them out of theirs."""
    name = None if args.clear else one_line(args.name, "group", GROUP_MAX)
    repo, folders = _folders(args.folders)
    return change_group(repo, folders, name)


def needs_action(args: argparse.Namespace) -> list[str]:
    raise ChantierError("summary takes lint, set, label or group", EXIT_USAGE)
