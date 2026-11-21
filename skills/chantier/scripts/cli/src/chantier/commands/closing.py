"""`chantier pause` and `chantier close`."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import TYPE_CHECKING

from chantier.commands.batch_status import record_costs
from chantier.commands.close_archive import Closing, archive_and_delete, batch_files, final_rows
from chantier.commands.cost.breakdown import cost_groups, cost_summary
from chantier.commands.cost.pricing import TO_DATE
from chantier.commands.cost.receipt import cost_receipt
from chantier.commands.cost.sessions import chief_line, chief_read, cost_rows, foreman_uuid
from chantier.core import leases
from chantier.core.batch import check_epoch, require_epoch, resolve_batch
from chantier.core.batch_records import Rec, check_closable, number_of, read_retro
from chantier.core.clock import now
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.git import branch_exists
from chantier.core.ids import normalize_batch
from chantier.core.records import LIVE, BatchRecord, read_batch_json
from chantier.core.repo import Repo
from chantier.lifecycle.session import RenderedBatch
from chantier.lifecycle.stages import changes_lock, cr_directory, stage_layout
from chantier.rails_idle import check_idle
from chantier.status.write import write_dashboard

if TYPE_CHECKING:
    from chantier.costs.sessions import Ending


def record_pause(repo: Repo, b: RenderedBatch, trigger: str) -> list[str]:
    """The one place a pause is recorded, whoever pauses (`pause --epoch <n>`, or the end of the
    batch's last CR): the cost to date computed and recorded, the record set `paused`, a `pause`
    event naming its trigger. Returns the cost summary."""
    paused = now()
    try:
        rows = cost_rows(repo, b.record, b.record.host, foreman_uuid(b.record))
        record_costs(repo, b, rows)
        summary = [
            *cost_summary(
                b.record,
                rows,
                cost_groups(repo, b.id, rows, "cr"),
                cost_groups(repo, b.id, rows, "driver"),
                chief_line(repo, b.record),
            ),
            TO_DATE,
        ]
    except ChantierError as e:  # never a false $0.00
        summary = [f"Spent: unknown ({e})"]
    b.record.status = "paused"
    b.record.paused = paused
    b.record.summary = summary
    b.record.heartbeat_stopped = paused
    b.log("pause", None, trigger=trigger)
    return summary


def record_born_paused(b: RenderedBatch) -> None:
    """A batch opened with no CR is born paused: nothing to price, no steering transcript yet, so
    its spend stays unset (shown `none yet`, never $0.00)."""
    paused = now()
    b.record.status = "paused"
    b.record.paused = paused
    b.record.heartbeat_stopped = paused
    b.record.summary = ["Spent: none yet (no CR)"]
    b.log("pause", None, trigger="open, no CR")


def pause(args: argparse.Namespace) -> list[str]:
    """The batch's end of work: it is paused, and the cost to date is computed and printed;
    `close` prices the final one. A paused batch is not paused again: `order add` adds work,
    the first `take` sets it running, then `pause` runs again."""
    require_epoch(args.epoch, "pause --epoch <n>")
    repo = Repo.find()
    batch = resolve_batch(repo, args.batch)
    with RenderedBatch(repo, batch, actor="foreman") as b:
        check_epoch(b, args.epoch)
        if b.record.status == "paused":
            raise ChantierError(
                f"{batch} is already paused (at {b.record.paused}): "
                "`order add` adds work, the first `take` sets it running again, "
                "then `pause --epoch <n>` runs again"
            )
        live_ids = [c.id for c in b.record.crs if c.status in LIVE]
        pending = [o.id for o in b.record.orders if not o.done]
        queued = [c.id for c in b.record.crs if c.status == "queued"]
        open_ = [c.id for c in b.record.crs if c.status in {"ready", "blocked"}]
        if live_ids or pending or queued or open_ or b.record.stack_agent:
            raise ChantierError(
                f"cannot pause {batch}: live {', '.join(live_ids) or '-'}, "
                f"queued {', '.join(queued) or '-'}, "
                f"not merged {', '.join(open_) or '-'}, orders pending "
                f"{', '.join(pending) or '-'} (the Foreman ends each with "
                "`order done <O-k> --epoch <n>`), "
                f"stack driver {b.record.stack_agent or 'none'}"
            )
        summary = record_pause(repo, b, "pause --epoch")
    return [f"paused {batch}: cost to date below", f"report: {b.dir / 'STATUS.md'}", *summary]


def _close_target(
    repo: Repo, batch: str | None, stopped: list[str] | None = None
) -> tuple[str, Path, BatchRecord]:
    """The batch `close` acts on: the project's one batch, named or not. One that is not paused is
    refused with what runs in it (less the agents `--stopped` declares), or with "`pause` first"."""
    folders = repo.batch_folders()
    batch = normalize_batch(batch) if batch else batch
    datas = {d: read_batch_json(repo.store, d / "batch.json") for d in folders}
    pick = [d for d in folders if not batch or datas[d].id == batch]
    if len(pick) != 1:
        raise ChantierError(
            f"close names one batch; batches: {', '.join(d.id for d in datas.values()) or 'none'}",
            EXIT_USAGE,
        )
    d = datas[pick[0]]
    if d.status != "paused":
        check_idle(repo, d, stopped)
        raise ChantierError(
            f"cannot close {d.id}: it is {d.status}, not paused; "
            "`pause --epoch <n>` comes first. Nothing was deleted.",
            EXIT_PRECONDITION,
        )
    return d.id, pick[0], d


def _held(batch: str, folder: Path) -> None:
    held = [
        f"{stage}/{p.name}"
        for stage in ("1-pending", "2-actives")
        for p in sorted((folder / stage).iterdir() if (folder / stage).is_dir() else [])
        if p.is_dir()
    ]
    if held:
        raise ChantierError(
            f"{batch} still holds {', '.join(held)} in 4-batch: nothing was deleted"
        )


def _apart_lines(batch: str, apart: list[Ending]) -> list[str]:
    """The other transcripts that run or cannot be read: a heading and one line each, none when
    there are none."""
    if not apart:
        return []
    head = (
        f"not agents of {batch}, not judged (no word needed; their calls are counted only "
        f"up to now): {len(apart)}"
    )
    return [head, *[f"- {e.text()}" for e in apart]]


def _to_remove(repo: Repo, d: BatchRecord) -> list[str]:
    """The dropped CRs' worktrees and branches, and what still exists of the merged CRs'."""
    clone = repo.clone if repo.external else repo.root
    dropped = [
        f"{c.id} (dropped) worktree {c.worktree} branch {c.branch}"
        for c in d.crs
        if c.status == "cancelled" and not c.moved_to()
    ]
    for c in d.crs:  # a merged CR's leftovers: the worktree folder, the branch, what still exists
        if c.status != "merged":
            continue
        left = [
            *([f"worktree {c.worktree}"] if c.worktree and Path(c.worktree).exists() else []),
            *([f"branch {c.branch}"] if branch_exists(c.branch, clone) else []),
        ]
        if left:
            dropped.append(f"{c.id} (merged) {' '.join(left)}")
    return dropped


def _kept(repo: Repo, d: BatchRecord) -> list[str]:
    """The CRs `order drop` moved to the inbox or the backlog: they keep their work, nothing on
    their line is removed. A folder that has moved on since (triaged, added again) says so."""
    kept = []
    for c in d.crs:
        to = c.moved_to()
        if not to:
            continue
        here = bool(c.path) and repo.planning_path(str(c.path), "recorded CR path").is_dir()
        folder = f"{c.path}" if here else f"moved since from {to}"
        kept.append(
            f"{c.id} ({folder}) worktree {c.worktree} branch {c.branch} PR {c.shown_pr() or 'none'}"
        )
    return kept


def _live_lease_lines(repo: Repo, d: BatchRecord) -> list[str]:
    """On Claude Code the transcripts judge what runs; a live lease is shown beside them, never a
    cause."""
    if d.host == "copilot":
        return []
    units = [(c.id, c.lease) for c in d.crs] + [(o.id, o.lease) for o in d.orders]
    units.append(("stack", d.stack_lease))
    lines = [
        leases.line(repo, unit, lease)
        for unit, lease in units
        if lease is not None and leases.liveness(repo, unit, lease).state == leases.LIVE
    ]
    return [f"live leases, beside the transcripts: {'; '.join(lines)}"] if lines else []


def _closing(
    repo: Repo,
    batch: str,
    folder: Path,
    d: BatchRecord,
    idle: tuple[list[Rec], list[Ending]],
) -> tuple[Closing, list[str]]:
    """What `close` acts on, and the lines it prints after those of the `Closing`; `idle`: the
    agents declared stopped, and the other transcripts that run or cannot be read, listed apart
    and never judged."""
    stopped, apart = idle
    done = stage_layout(repo)["done"]
    archived = [
        (c, cr_directory(repo, c)) for c in d.crs if c.path and cr_directory(repo, c).parent == done
    ]
    dropped = _to_remove(repo, d)
    check_closable(repo, number_of(batch))
    rows = final_rows(repo, batch, d)
    by_driver = cost_groups(repo, batch, rows, "driver")
    chief = chief_read(repo, d)  # the Chief of Staff's transcripts, read once
    summary = cost_summary(
        d, rows, cost_groups(repo, batch, rows, "cr"), by_driver, chief_line(repo, d, chief)
    )
    k = Closing(
        repo,
        batch,
        folder,
        d,
        rows,
        archived,
        batch_files(folder),
        read_retro(repo.store, folder),
        summary,
        stopped,
        cost_receipt(d, rows, by_driver, chief),
    )
    tail = [
        "the trashed CRs and the merged CRs' leftovers, to remove on the same word where they "
        f"still exist (`git {'-C ' + repo.clone.as_posix() + ' ' if repo.external else ''}"
        "worktree remove --force`, `git branch -D`; for a folder git no longer knows, "
        f"`git worktree prune` once it is deleted): {'; '.join(dropped) or 'none'}",
        f"kept, moved out with their work: {'; '.join(_kept(repo, d)) or 'none'}",
        *_apart_lines(batch, apart),
        *_live_lease_lines(repo, d),
        "final cost, up to now (nothing runs):",
        *summary,
    ]
    return k, tail


def close(args: argparse.Namespace) -> tuple[list[str], int]:
    """The batch's own files go, its `retro.md` after it is kept in the batch's record
    (`5-archives/batches/batch-NN.md`, with the Completion table and the final cost, beside
    `batch-NN.json`), and its merged CRs move from `3-done` to `5-archives`: the Chief
    of Staff shows the user what would happen, with the dropped CRs' worktrees and branches it
    removes itself on the same word, and passes `--yes`. Without it, nothing is touched. It
    refuses while anything runs or `1-pending` or `2-actives` holds a CR, with or without `--yes`,
    and it prices the batch up to now: this is the final cost, printed either way. It refuses,
    with or without `--yes`, when nothing can be priced (no Foreman transcript recorded, no priced
    call in the whole batch). Calls of a model with no price do not refuse it: the final cost is a
    floor, printed with the calls not priced.

    Whether anything runs is read from the batch's record and from the end of the Claude
    transcripts of the agents the batch holds (the current Foreman, and each id `agents set`
    recorded and did not clear), never from a file's age: an agent that handed back has ended, one
    that waits on a tool call or has a step under way runs, and a transcript that cannot be read
    (a held id with no transcript included) refuses; each refusal names the agent and the file.
    The session's other subagents (grill, spec, critics, Drivers already replaced, a Driver's own
    subagents) and the replaced Foremans never block: those still running or unreadable are
    listed apart before the final cost, which counts their calls only up to now. An agent held
    that stopped without its hand-back (an app restart, the user's stop) reads as running:
    `--stopped NAME` (repeatable), on the user's word only, passes it. It is refused for a name
    that is not a running held agent. Nothing else is passed. With `--yes` the declaration is kept
    in the batch's record (`stopped_agents` in `batch-NN.json`, a line under Cost in
    `batch-NN.md`); the listed transcripts are never recorded."""
    repo = Repo.find()
    stopped = args.stopped or []
    with changes_lock(repo):
        batch, folder, d = _close_target(
            repo, args.batch or os.environ.get("CHANTIER_BATCH"), stopped
        )
        stopped_endings, apart = check_idle(repo, d, stopped)
        declared = [
            {"agent": e.name, "transcript": str(e.path), "cause": e.cause} for e in stopped_endings
        ]
        _held(batch, folder)
        k, tail = _closing(repo, batch, folder, d, (declared, apart))
        if not args.yes:
            return [*k.preview(), *tail, "ask the user, then `chantier close --yes`"], 0
        archive_and_delete(k)
        write_dashboard(repo, stage_layout(repo))
    return [
        f"closed {batch}: its files are deleted, {len(k.archived)} CRs archived",
        *k.done_lines()[1:],
        *tail,
    ], 0
