"""The facts of a CR that several commands share."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import NamedTuple

from chantier.core.batch import Batch, find_cr_batch, read_batch
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.files import read_text
from chantier.core.git import git
from chantier.core.heads import gate_passed, same_head
from chantier.core.ids import normalize_cr
from chantier.core.records import (
    TITLE_MAX,
    BatchRecord,
    CrEntry,
    EventRecord,
    ReleaseGrant,
    read_events,
)
from chantier.core.repo import Repo
from chantier.lifecycle.filing import new_request, slugify
from chantier.lifecycle.stages import cr_directory, stage_layout
from chantier.rails_release import MAX_GRANTED_FIXES
from chantier.summaries.title import short_heading


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
    return [e for e in read_events(repo.store, repo.batch_dir(batch)) if e.cr == cr_id]


def short_head(head: str | None) -> str:
    """A head for display only: 7 characters."""
    return (head or "")[:7]


def dirty_files(wt: Path) -> str:
    """The worktree's tracked changes and untracked files, as `git status --porcelain` says."""
    return git("status", "--porcelain", "--untracked-files=normal", cwd=wt)


PATCH_ID_GIT = (2, 39)  # `git patch-id --verbatim` needs it


class Judged(NamedTuple):
    """A head a long gate pass or a verdict stands at, for a carry: the head, the base it was
    judged on (None when the event recorded none), and the original judged head it chains from."""

    head: str
    base: str | None
    origin: str


def conflict_cut(events: list[EventRecord]) -> int:
    """The index of the CR's last `ship` that resolved a conflict, else -1. What was judged or
    carried before it never carries again."""
    cut = -1
    for i, e in enumerate(events):
        if e.kind == "ship" and e.conflict:
            cut = i
    return cut


def carry_at(
    events: list[EventRecord], head: str | None, key: str | None = None
) -> EventRecord | None:
    """The last `carry` event recorded at a head (with `key`, when given), or None; None as well
    when a `ship --conflict` is at or after it."""
    cut = conflict_cut(events)
    found = None
    for i, e in enumerate(events):
        if e.kind == "carry" and same_head(e.head, head) and (key is None or getattr(e, key)):
            found = e if i > cut else None
    return found


def judged_gate(events: list[EventRecord]) -> Judged | None:
    """The head of the CR's latest passed long gate, or the latest head a pass was carried to,
    with the base it was judged on; None before the last `ship --conflict`."""
    events = events[conflict_cut(events) + 1 :]
    seen: list[str] = []
    for e in reversed(events):
        if e.kind == "carry" and e.head and e.gate_from:
            return Judged(str(e.head), e.base, str(e.gate_from))
        if e.kind == "gate" and e.head and e.head not in seen:
            seen.append(e.head)
            if gate_passed(events, e.head):
                return Judged(str(e.head), e.base, str(e.head))
    return None


def judged_verdict(events: list[EventRecord]) -> Judged | None:
    """The head of the CR's latest verdict when the last verdict there is VERIFIED, or the
    latest head a verdict was carried to; None when a later NOT VERIFIED, at a later head or at
    the same one, blocks it, and before the last `ship --conflict`."""
    events = events[conflict_cut(events) + 1 :]
    for e in reversed(events):
        if e.kind == "carry" and e.head and e.verdict_from:
            return Judged(str(e.head), e.base, str(e.verdict_from))
        if e.kind == "verdict" and e.head:
            ok = last_verdict(events, e.head) == "VERIFIED"
            return Judged(str(e.head), e.base, str(e.head)) if ok else None
    return None


def last_gate_pass(events: list[EventRecord]) -> str | None:
    """The head of the CR's latest passed long gate (or carried pass), or None."""
    j = judged_gate(events)
    return j.head if j else None


def git_version() -> tuple[int, ...]:
    """The installed git's version, as numbers (`git version 2.43.0.windows.1` is (2, 43, 0))."""
    m = re.search(r"(\d+(?:\.\d+)+)", git("version", check=False))
    return tuple(int(x) for x in m[1].split(".")) if m else ()


def _readable(wt: Path, ref: str) -> None:
    if not git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", cwd=wt, check=False):
        raise ChantierError(
            f"{short_head(ref) if re.fullmatch('[0-9a-f]{40}', ref) else ref} cannot be read"
        )


def _patch_ids(wt: Path, base: str, head: str) -> list[str]:
    """The exact patch-ids (`git patch-id --verbatim`) of `base..head`'s commits, oldest first.
    Git computes them; the diff text is never compared here. A failing git call raises a
    ChantierError naming it, never an empty list."""
    log = subprocess.run(
        ["git", "log", "--reverse", "-p", "--no-merges", "--format=commit %H", f"{base}..{head}"],
        cwd=wt,
        capture_output=True,
        check=False,
    )
    ids = log if log.returncode else None
    if ids is None:
        ids = subprocess.run(
            ["git", "patch-id", "--verbatim"],
            cwd=wt,
            input=log.stdout,
            capture_output=True,
            check=False,
        )
    if ids.returncode:
        first = (ids.stderr.decode("utf-8", "replace").strip().splitlines() or ["no message"])[0]
        raise ChantierError(
            f"git could not read the patch-ids of {short_head(base)}..{short_head(head)}: {first}"
        )
    return [
        ln.split()[0] for ln in ids.stdout.decode("utf-8", "replace").splitlines() if ln.strip()
    ]


def _merges(wt: Path, base: str, head: str) -> bool:
    return bool(git("rev-list", "--merges", f"{base}..{head}", cwd=wt, check=False))


def _unproved(g: Judged, head: str, head_base: str | None, what: str) -> str | None:
    """The reason nothing can be proved before git is asked: an old git, a base not recorded."""
    have = git_version()
    if have < PATCH_ID_GIT:
        need = ".".join(map(str, PATCH_ID_GIT))
        got = ".".join(map(str, have)) or "?"
        return f"git {got} is older than {need}: no patch-id --verbatim to prove it"
    if not g.base and what == "verdict":
        return f"the verdict VERIFIED at {short_head(g.head)} recorded no base: verify again"
    if not g.base:
        return f"the pass at {short_head(g.head)} recorded no base: run the long gate again"
    if not head_base:
        return f"{short_head(head)} sits on none of its base branches: no base to prove it"
    return None


def _changed(wt: Path, g: Judged, head: str, head_base: str) -> str | None:
    """Why the CR's own commits at `head` (above `head_base`) are not the judged ones (above
    `g.base`), or None when their exact patch-ids are the same, in order."""
    try:
        judged = _patch_ids(wt, str(g.base), g.head)
        now = _patch_ids(wt, head_base, head)
    except ChantierError as e:
        return str(e)
    if judged == now:
        return None
    if len(judged) != len(now):
        return (
            f"the rebase changed the patch (own commits: {len(judged)} at {short_head(g.head)} "
            f"above {short_head(str(g.base))}, {len(now)} at {short_head(head)} "
            f"above {short_head(head_base)})"
        )
    i = next(k for k, (x, y) in enumerate(zip(judged, now, strict=True), 1) if x != y)
    return f"the rebase changed the patch (commit {i} of {len(now)} differs)"


def carry_check(
    wt: Path, g: Judged, head: str, head_base: str | None, what: str = "pass"
) -> str | None:
    """Why the long gate pass (or the verdict, `what`) judged at `g` does not carry to `head` on
    `head_base`, or None when it carries: the CR's own commits (above its base) have the same
    exact patch-ids, in order. Git does the proof, not the Driver's word; no other method. A ref
    git cannot read raises a ChantierError."""
    why = _unproved(g, head, head_base, what)
    if why or not (g.base and head_base):
        return why
    for ref in (g.base, g.head, head_base, head):
        _readable(wt, ref)
    if _merges(wt, g.base, g.head):
        return f"a merge commit in {short_head(g.head)}'s commits"
    if _merges(wt, head_base, head):
        return f"a merge commit in {short_head(head)}'s commits"
    return _changed(wt, g, head, head_base)


def last_verdict(events: list[EventRecord], head: str | None) -> str | None:
    """The last verdict recorded at a head: it decides; a verdict at another head never counts."""
    seen = [e.result for e in events if e.kind == "verdict" and same_head(e.head, head)]
    return seen[-1] if seen else None


def last_verdict_head(events: list[EventRecord]) -> str | None:
    """The head of the CR's latest verdict (or carried verdict), when the last verdict there is
    VERIFIED, else None: a later NOT VERIFIED, at a later head or at the same one, blocks any
    carry from an older one."""
    j = judged_verdict(events)
    return j.head if j else None


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


def fix_folder(b: Batch, rel: CrEntry, item: str) -> Path | None:
    """The new inbox folder a release's fix file will be filed in; None for an item that is
    already a prepared CR."""
    repo = b.repo
    source = repo.planning_path(item, "fix")
    if not source.is_file() or cr_directory(repo, rel) not in source.parents:
        return None
    return stage_layout(repo)["inbox"] / f"{rel.id.lower()}-{slugify(source.stem)}"


def filed_fix(b: Batch, rel: CrEntry, item: str) -> str:
    """A release's fix file is the fix's specification: it becomes a prepared CR in the inbox.
    Anything else is already a prepared CR."""
    repo = b.repo
    target = fix_folder(b, rel, item)
    if target is None:
        return item
    source = repo.planning_path(item, "fix")
    if short_heading(read_text(source, "replace")) is None:  # never an inbox CR validate refuses
        raise ChantierError(
            f'the fix {item} has no short "# Title" heading (at most {TITLE_MAX} characters) '
            "→ write one at its top",
            EXIT_USAGE,
        )
    repo.check_publish([target, target / "intake" / "request.md", target / "03-change-spec.md"])
    folder = new_request(repo, target.name, source.read_bytes())
    repo.store.write_bytes(repo.rel(folder / "03-change-spec.md"), source.read_bytes())
    return str(folder)
