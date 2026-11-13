"""`chantier pause` and `chantier close`."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from chantier.commands.batch_status import record_costs
from chantier.commands.close_archive import Closing, archive_and_delete, batch_files, final_rows
from chantier.commands.cost.breakdown import cost_groups, cost_summary
from chantier.commands.cost.pricing import TO_DATE
from chantier.commands.cost.sessions import chief_line, cost_rows, foreman_uuid
from chantier.commands.registry import BATCH, BATCH_EPOCH, Subparsers, add_command
from chantier.core.batch import check_epoch, resolve_batch
from chantier.core.batch_records import check_closable, number_of, read_retro
from chantier.core.clock import now
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.records import LIVE, normalize_batch, read_batch_json
from chantier.core.repo import Repo
from chantier.lifecycle.convert import open_repo
from chantier.lifecycle.session import RenderedBatch
from chantier.lifecycle.stages import changes_lock, cr_directory, stage_layout
from chantier.rails import check_idle
from chantier.status.write import write_dashboard


def pause(args) -> list[str]:
    """The batch's end of work: it is paused, and the cost to date is computed and printed;
    `close` prices the final one. A paused batch is not paused again: `order add` adds work,
    the first `take` sets it running, then `pause` runs again."""
    repo = open_repo()
    batch = resolve_batch(repo, args.batch)
    with RenderedBatch(repo, batch, actor="foreman") as b:
        check_epoch(b, args.epoch)
        if b.data["status"] == "paused":
            raise ChantierError(
                f"{batch} is already paused (at {b.data.get('paused')}): "
                "`order add` adds work, the first `take` sets it running again, "
                "then `pause` runs again"
            )
        paused = now()
        live_ids = [c["id"] for c in b.data["crs"] if c["status"] in LIVE]
        pending = [o["id"] for o in b.data["orders"] if not o["done"]]
        queued = [c["id"] for c in b.data["crs"] if c["status"] == "queued"]
        open_ = [c["id"] for c in b.data["crs"] if c["status"] in {"ready", "blocked"}]
        if live_ids or pending or queued or open_ or b.data.get("stack_agent"):
            raise ChantierError(
                f"cannot pause {batch}: live {', '.join(live_ids) or '-'}, "
                f"queued {', '.join(queued) or '-'}, "
                f"not merged {', '.join(open_) or '-'}, orders pending "
                f"{', '.join(pending) or '-'} (the Foreman ends each with "
                "`order done <O-k>`), "
                f"stack driver {b.data.get('stack_agent') or 'none'}"
            )
        try:
            rows = cost_rows(repo, b.data, b.data["host"], foreman_uuid(b.data))
            record_costs(repo, b, rows)
            summary = [
                *cost_summary(
                    b.data,
                    rows,
                    cost_groups(repo, batch, rows, "cr"),
                    cost_groups(repo, batch, rows, "driver"),
                    chief_line(repo, b.data),
                ),
                TO_DATE,
            ]
        except ChantierError as e:  # never a false $0.00
            summary = [f"Spent: unknown ({e})"]
        b.data.update(status="paused", paused=paused, summary=summary, heartbeat_stopped=paused)
        b.log("pause", None)
    return [f"paused {batch}: cost to date below", f"report: {b.dir / 'STATUS.md'}", *summary]


def _close_target(repo: Repo, batch: str | None) -> tuple[str, Path, dict[str, Any]]:
    """The batch `close` acts on: the project's one batch, named or not. One that is not paused is
    refused with what runs in it, or with "`pause` first"."""
    folders = repo.batch_folders()
    batch = normalize_batch(batch) if batch else batch
    datas = {d: read_batch_json(d / "batch.json") for d in folders}
    pick = [d for d in folders if not batch or datas[d]["id"] == batch]
    if len(pick) != 1:
        raise ChantierError(
            f"close names one batch; batches: "
            f"{', '.join(d['id'] for d in datas.values()) or 'none'}",
            EXIT_USAGE,
        )
    d = datas[pick[0]]
    if d.get("status") != "paused":
        check_idle(repo, d)
        raise ChantierError(
            f"cannot close {d['id']}: it is {d.get('status')}, not paused; "
            "`pause` comes first. Nothing was deleted.",
            EXIT_PRECONDITION,
        )
    return d["id"], pick[0], d


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


def _closing(repo: Repo, batch: str, folder: Path, d: dict[str, Any]) -> tuple[Closing, list[str]]:
    """What `close` acts on, and the lines it prints after those of the `Closing`."""
    done = stage_layout(repo)["done"]
    archived = [
        (c, cr_directory(repo, c))
        for c in d["crs"]
        if c.get("path") and cr_directory(repo, c).parent == done
    ]
    dropped = [
        f"{c['id']} worktree {c['worktree']} branch {c['branch']}"
        for c in d["crs"]
        if c["status"] == "cancelled"
    ]
    check_closable(repo, number_of(batch))
    rows = final_rows(repo, batch, d)
    summary = cost_summary(
        d,
        rows,
        cost_groups(repo, batch, rows, "cr"),
        cost_groups(repo, batch, rows, "driver"),
        chief_line(repo, d),
    )
    k = Closing(
        repo, batch, folder, d, rows, archived, batch_files(folder), read_retro(folder), summary
    )
    tail = [
        "the dropped CRs, to remove on the same word where they still exist "
        f"(`git {'-C ' + repo.clone_dir.as_posix() + ' ' if repo.external else ''}"
        f"worktree remove --force`, `git branch -D`): {'; '.join(dropped) or 'none'}",
        "final cost, up to now (nothing runs):",
        *summary,
    ]
    return k, tail


def close(args) -> tuple[list[str], int]:
    """The batch's own files go, its `retro.md` after it is kept in the batch's record
    (`5-archives/batches/batch-NN.md`, with the Completion table and the final cost, beside
    `batch-NN.json`), and its merged CRs move from `3-done` to `5-archives`: the Chief
    of Staff shows the user what would happen, with the dropped CRs' worktrees and branches it
    removes itself on the same word, and passes `--yes`. Without it, nothing is touched. It
    refuses while anything runs or `1-pending` or `2-actives` holds a CR, with or without `--yes`,
    and it prices the batch up to now: this is the final cost, printed either way. It refuses,
    with or without `--yes`, when nothing can be priced (no Foreman transcript recorded, no priced
    call in the whole batch). Calls of a model with no price do not refuse it: the final cost is a
    floor, printed with the calls not priced."""
    repo = open_repo()
    with changes_lock(repo):
        batch, folder, d = _close_target(repo, args.batch or os.environ.get("CHANTIER_BATCH"))
        check_idle(repo, d)
        _held(batch, folder)
        k, tail = _closing(repo, batch, folder, d)
        if not args.yes:
            return [*k.preview(), *tail, "ask the user, then `chantier close --yes`"], 0
        archive_and_delete(k)
        write_dashboard(repo, stage_layout(repo))
    return [
        f"closed {batch}: its files are deleted, {len(k.archived)} CRs archived",
        *k.done_lines()[1:],
        *tail,
    ], 0


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    add_command(
        sub,
        "pause",
        pause,
        "pause the batch once its work is done: refused while anything is live or already "
        "paused; prints the cost to date",
        BATCH_EPOCH,
    )

    s = add_command(
        sub,
        "close",
        close,
        "refused while anything runs; prints the final cost and what deleting a paused batch "
        "would remove; --yes deletes it",
        BATCH,
    )
    s.add_argument("--yes", action="store_true", help="on the user's word")
