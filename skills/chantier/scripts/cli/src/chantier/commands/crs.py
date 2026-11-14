"""The facts of a CR that several commands share."""

from __future__ import annotations

import re
from pathlib import Path

from chantier.core.batch import Batch, find_cr_batch, read_batch
from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.git import git
from chantier.core.ids import normalize_cr
from chantier.core.records import (
    BatchRecord,
    CrEntry,
    EventRecord,
    ReleaseGrant,
    read_events,
)
from chantier.core.repo import Repo
from chantier.lifecycle.stages import cr_directory, stage_layout
from chantier.rails_release import MAX_GRANTED_FIXES


def shown(repo: Repo, path: Path) -> str:
    try:
        return path.relative_to(repo.session_root).as_posix()
    except ValueError:
        return path.as_posix()


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "cr"


def new_request(
    repo: Repo, slug: str, raw: bytes, hint: str = "file it again with --slug <other>"
) -> Path:
    """A new inbox folder, the request kept as received. The caller holds `changes_lock`."""
    folder = stage_layout(repo)["inbox"] / slug
    folder.parent.mkdir(parents=True, exist_ok=True)
    try:
        folder.mkdir()
    except FileExistsError as e:
        raise ChantierError(
            f"CR folder already exists: {shown(repo, folder)}; {hint}", EXIT_PRECONDITION
        ) from e
    try:
        (folder / "intake").mkdir()
        (folder / "intake" / "request.md").write_bytes(raw)
    except OSError as e:
        raise ChantierError(
            f"could not finish filing {folder}; preserve it for recovery: {e}", EXIT_EXTERNAL
        ) from e
    return folder


def batch_cr(repo: Repo, cr_id: str, batch: str | None) -> tuple[str, BatchRecord, CrEntry]:
    cr_id = normalize_cr(cr_id)
    batch = find_cr_batch(repo, cr_id, batch)
    data = read_batch(repo, batch)
    c = next((x for x in data.crs if x.id == cr_id), None)
    if c is None:
        raise ChantierError(f"unknown CR {cr_id} in batch {batch}", EXIT_USAGE)
    return batch, data, c


def work(repo: Repo, c: CrEntry) -> Path:
    """The CR's work folder, inside its own folder: notes, gate logs, the PR body."""
    return cr_directory(repo, c) / "work"


def cr_worktree(c: CrEntry) -> Path:
    """The CR's worktree, once its Driver has created it; the CLI never does."""
    if not Path(c.worktree).is_dir():
        raise ChantierError(
            f"{c.id}: no worktree at {c.worktree}; its Driver creates it "
            f"(`git worktree add -b {c.branch} {c.worktree} <base>`)",
            EXIT_PRECONDITION,
        )
    return Path(c.worktree)


def cr_events(repo: Repo, batch: str, cr_id: str) -> list[EventRecord]:
    return [e for e in read_events(repo.batch_dir(batch)) if e.cr == cr_id]


def same_head(recorded: str | None, head: str | None) -> bool:
    """Heads are recorded as the full SHA. One recorded short before (an open batch from an older
    version) matches the full SHA it is a prefix of."""
    if not recorded or not head:
        return False
    return recorded == head or head.startswith(recorded) or recorded.startswith(head)


def short_head(head: str | None) -> str:
    """A head for display only: 7 characters."""
    return (head or "")[:7]


def dirty_files(wt: Path) -> str:
    """The worktree's tracked changes and untracked files, as `git status --porcelain` says."""
    return git("status", "--porcelain", "--untracked-files=normal", cwd=wt)


def gate_passed(events: list[EventRecord], head: str | None) -> bool:
    """A long gate passed at a head: the last `gate` invocation at that head passed every command
    it was given. The events of one invocation share a `run`; it stops at its first failure, so
    its last event says. An event with no `run` (an older record) is an invocation by itself."""
    here = [e for e in events if e.kind == "gate" and same_head(e.head, head)]
    if not here:
        return False
    run = here[-1].run
    if run is None:
        return bool(here[-1].result == "pass")
    return all(e.result == "pass" for e in here if e.run == run)


def last_verdict(events: list[EventRecord], head: str | None) -> str | None:
    """The last verdict recorded at a head: it decides; a verdict at another head never counts."""
    seen = [e.result for e in events if e.kind == "verdict" and same_head(e.head, head)]
    return seen[-1] if seen else None


def grant_line(release: ReleaseGrant) -> str:
    """What the user allowed the release to do without asking, in one line."""
    n, done = release.autonomous, release.published
    return "; ".join(
        [
            f"up to {n} releases without asking ({done} published)"
            if n
            else "every irreversible action waits for the user's approval",
            f"the Foreman starts and merges up to {MAX_GRANTED_FIXES} fixes"
            if release.fixes
            else "the user starts and merges the fixes",
        ]
    )


def filed_fix(b: Batch, rel: CrEntry, item: str) -> str:
    """A release's fix file is the fix's specification: it becomes a prepared CR in the inbox.
    Anything else is already a prepared CR."""
    repo = b.repo
    source = repo.planning_path(item, "fix")
    if not source.is_file() or cr_directory(repo, rel) not in source.parents:
        return item
    folder = new_request(repo, f"{rel.id.lower()}-{slugify(source.stem)}", source.read_bytes())
    import shutil  # noqa: PLC0415 - slow import

    shutil.copyfile(source, folder / "03-change-spec.md")
    return str(folder)
