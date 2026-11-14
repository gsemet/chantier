"""`summary`: the CR's condensed JSON. `lint` lists what is missing or late, `set` stores what an
agent wrote and records the checksums, `label` and `group` link CRs. The CLI writes no title and no
summary of its own, and no other command refuses because of a gap."""

from __future__ import annotations

import argparse
import re
import unicodedata
from collections.abc import Callable
from pathlib import Path

from chantier.commands.crs import shown
from chantier.core.clock import now
from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.records import (
    GROUP_MAX,
    LABEL_PATTERN,
    SUMMARY_MAX,
    TITLE_MAX,
    CrSummary,
)
from chantier.core.repo import Repo
from chantier.lifecycle.convert import open_repo
from chantier.lifecycle.stages import changes_lock, cr_folders, cr_stage, stage_layout
from chantier.summaries import store
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


def _one_line(value: str, field: str, limit: int) -> str:
    """A value of one line of plain text, not empty, within its limit."""
    if any(unicodedata.category(c) == "Cc" for c in value):
        raise ChantierError(
            f"{field} is one line of plain text: no newline or other control character",
            EXIT_USAGE,
        )
    text = value.strip()
    if not text:
        raise ChantierError(f"{field} must not be empty", EXIT_USAGE)
    if len(text) > limit:
        raise ChantierError(f"{field} is {len(text)} characters: the limit is {limit}", EXIT_USAGE)
    return text


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
    title = None if args.title is None else _one_line(args.title, "title", TITLE_MAX)
    text = None if args.summary is None else _one_line(args.summary, "summary", SUMMARY_MAX)
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


def _edit_all(
    items: list[str], edit: Callable[[CrSummary], None], show: Callable[[str, CrSummary], str]
) -> list[str]:
    """Apply one edit to several CRs' summaries under one lock: all are read before any is
    written, and none changes `sources`."""
    repo = open_repo()
    paths = stage_layout(repo)
    folders = list(dict.fromkeys(_cr_folder(repo, paths, item) for item in items))
    with changes_lock(repo):
        loaded = [(folder, store.read_or_new(folder)) for folder in folders]
        for folder, summary in loaded:
            edit(summary)
            store.write(folder, summary)
    return [show(shown(repo, folder), summary) for folder, summary in loaded]


def _labels(raw: str) -> set[str]:
    """Comma-separated labels, lowercased and checked."""
    labels = {part.strip().lower() for part in raw.split(",") if part.strip()}
    bad = sorted(x for x in labels if not re.fullmatch(LABEL_PATTERN, x))
    if bad or not labels:
        raise ChantierError(
            f"a label is lowercase letters, digits and hyphens, 24 characters at most, "
            f"starting with a letter or digit: {', '.join(bad) or 'none given'}",
            EXIT_USAGE,
        )
    return labels


def label(args: argparse.Namespace) -> list[str]:
    """Add or remove labels on CRs; a label never makes a summary fresh or late."""
    add, remove = (_labels(raw) if raw else set() for raw in (args.add, args.remove))

    def edit(summary: CrSummary) -> None:
        summary.labels = sorted((set(summary.labels) | add) - remove)

    return _edit_all(
        args.folders, edit, lambda path, s: f"labels {path}: {', '.join(s.labels) or 'none'}"
    )


def group(args: argparse.Namespace) -> list[str]:
    """Put CRs in one group, or take them out of theirs."""
    name = None if args.clear else _one_line(args.name, "group", GROUP_MAX)

    def edit(summary: CrSummary) -> None:
        if name is None:
            summary.unset("group")
        else:
            summary.group = name

    return _edit_all(args.folders, edit, lambda path, s: f"group {path}: {s.group or 'none'}")


def needs_action(args: argparse.Namespace) -> list[str]:
    raise ChantierError("summary takes lint, set, label or group", EXIT_USAGE)
