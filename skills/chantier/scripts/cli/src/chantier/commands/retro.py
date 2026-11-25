"""`chantier retro draft`: the retro's draft points from the batch's events, printed, or appended
to `4-batch/retro.md` with `--write` when it has no draft section. It files no point, logs no
event, reads no forge and runs no git; the author judges and fills each point."""

from __future__ import annotations

import argparse

from chantier.commands.cost.breakdown import cost_groups
from chantier.commands.cost.command import batch_rows
from chantier.commands.cost.pricing import sum_unpriced
from chantier.commands.retro_draft import (
    OPEN_MARK,
    Numbered,
    Point,
    draft_block,
    draft_points,
    window_crs,
)
from chantier.core import clock
from chantier.core.batch import (
    Batch,
    check_epoch,
    read_batch,
    require_epoch,
    resolve_batch,
    stale_epoch,
)
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.records import BatchRecord, numbered_events
from chantier.core.repo import Repo
from chantier.rails import not_priced

RETRO = "4-batch/retro.md"


def _start(since: int | None, d: BatchRecord, numbered: Numbered, last: int) -> int:
    """The sequence the window starts after: `--since`, else the current pause's."""
    if since is not None:
        if since < 0 or since > last:
            why = "a sequence is 0 or more" if since < 0 else f"{d.id}'s events stop at {last}"
            raise ChantierError(
                f"retro draft --since {since}: {why}; `retro draft --since 0` drafts from every "
                "event",
                EXIT_USAGE,
            )
        return since
    pauses = [n for n, e in numbered if e.kind == "pause"]
    if d.status == "paused":
        return pauses[-2] if len(pauses) >= 2 else 0  # noqa: PLR2004 - the pause before this one
    return pauses[-1] if pauses else 0


def _costs(repo: Repo, d: BatchRecord) -> tuple[dict[str, float] | None, list[str]]:
    """Each CR's dollars, or None and the `cost:` line that says why no outlier is judged."""
    try:
        rows = batch_rows(repo, d)
    except ChantierError as e:
        return None, [f"cost: not read ({e})"]
    un = sum_unpriced(rows)
    if un:
        return None, [f"cost: not all priced ({not_priced(un)}); no outlier judged"]
    groups = cost_groups(repo, d.id, rows, "cr")
    return {k: v[1] for k, v in groups.items() if k not in {"foreman", "other"}}, []


def _has_draft(data: bytes) -> bool:
    return any(line.startswith(OPEN_MARK) for line in data.decode("utf-8", "replace").splitlines())


def _separator(data: bytes) -> bytes:
    """What goes before the block so it starts after one blank line."""
    if not data or data.endswith((b"\n\n", b"\n\r\n")):
        return b""
    return b"\n" if data.endswith(b"\n") else b"\n\n"


def _write(repo: Repo, batch: str, epoch: int, block: str, points: list[Point]) -> str:
    """Append the block under the batch's lock; refused when the file has a draft section."""
    with Batch(repo, batch, actor="foreman") as b:
        check_epoch(b, epoch)
        rel = repo.rel(repo.batch_dir(batch) / "retro.md")
        data = repo.store.read_bytes(rel) if repo.store.is_file(rel) else b""
        if _has_draft(data):
            raise ChantierError(
                f"retro draft --write: {RETRO} already has a draft section; `retro draft --epoch "
                f"{epoch}` prints this one",
                EXIT_PRECONDITION,
            )
        repo.store.write_bytes(rel, data + _separator(data) + block.encode("utf-8"))
    return f"written: {RETRO} ({len(points)} points appended after {len(data)} bytes of your text)"


def retro(args: argparse.Namespace) -> list[str]:
    """`retro draft`: the window's points; `--write` appends them to `retro.md` when it has no
    draft section."""
    repo = Repo.find()
    batch = resolve_batch(repo, args.batch, paused=True)
    require_epoch(args.epoch, "retro draft --epoch <n>")
    d = read_batch(repo, batch)
    stale_epoch(batch, d.foreman_epoch, args.epoch)
    numbered, last = numbered_events(repo.store, repo.batch_dir(batch))
    start = _start(args.since, d, numbered, last)
    window = [(n, e) for n, e in numbered if n > start]
    crs = window_crs(window)
    costs, cost_line = _costs(repo, d)
    points = draft_points(window, costs)
    head = [
        f"retro draft: {batch}, events {start + 1}..{last}, CRs {', '.join(crs) or 'none'} "
        f"({len(points)} points)",
        *cost_line,
    ]
    block = draft_block(points, clock.now()[:10], crs, start + 1, last)
    if args.write:
        return [*head, _write(repo, batch, args.epoch, block, points)]
    return [
        *head,
        *block.splitlines(),
        f"next: judge each point, then the Retro critic; `retro draft --write --epoch "
        f"{args.epoch}` appends this block to {RETRO} when it has none",
    ]
