"""What `close --yes` does: the CRs archived, the batch's record completed, its files removed."""

from __future__ import annotations

import contextlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from chantier.commands.cost.breakdown import cost_groups
from chantier.commands.cost.pricing import sum_unpriced
from chantier.commands.cost.sessions import cost_rows, foreman_uuid
from chantier.commands.crs import shown
from chantier.core.batch import move_directory
from chantier.core.batch_records import (
    Rec,
    check_closable,
    number_of,
    record_path,
    report_path,
    undo_close,
    write_close,
)
from chantier.core.clock import now
from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError
from chantier.core.files import retry
from chantier.core.repo import Repo
from chantier.history import close_markdown, close_record, release_retro_line
from chantier.lifecycle.stages import STATE_FOLDERS, archive_name, stage_layout
from chantier.status.write import write_final_pages


@dataclass
class Closing:
    """What `close --yes` acts on: the batch, its priced rows, the CRs to archive, the files that
    go, the retro's text and the cost lines that `batch-NN.md` keeps."""

    repo: Repo
    batch: str
    folder: Path
    d: Rec
    rows: list[Rec]
    archived: list[tuple[Rec, Path]]
    own: list[Path]
    retro: str | None
    summary: list[str]

    def preview(self) -> list[str]:
        """The lines `close` prints about what it does: the files that go, the CRs archived,
        the retro and the record."""
        r, number = self.repo, number_of(self.batch)
        report, record = report_path(r, number), record_path(r, number)
        retro = (
            f"retro: {shown(r, self.folder / 'retro.md')} goes into {shown(r, report)}"
            if self.retro is not None
            else "retro: no retro"
        )
        return [
            f"close {self.batch} deletes its files in {shown(r, self.folder)}: "
            f"{', '.join(p.name for p in self.own) or 'none'}",
            f"{len(self.archived)} CRs move from 3-done to 5-archives: "
            f"{', '.join(c['id'] for c, _ in self.archived) or 'none'}",
            retro,
            f"record: {shown(r, record)} and {report.name}",
        ]

    def done_lines(self) -> list[str]:
        """The same lines once `--yes` has run: where the retro and the record are kept."""
        r, number = self.repo, number_of(self.batch)
        lines = self.preview()
        if self.retro is not None:
            lines[2] = f"retro: kept in {shown(r, report_path(r, number))}"
        lines[3] = f"record: {shown(r, record_path(r, number))} closed"
        return lines


def batch_files(folder: Path) -> list[Path]:
    """What `close` deletes: everything in `4-batch/` but the three state folders, `retro.md`
    included (its text goes into the batch's record first)."""
    return sorted(p for p in folder.iterdir() if p.name not in STATE_FOLDERS)


def final_rows(repo: Repo, batch: str, d: Rec) -> list[Rec]:
    """The batch priced to now, once, before anything is touched. Calls of a model with no price
    do not refuse the close: they are counted apart and the cost is a floor. It is refused (exit 2)
    with its cause when nothing can be priced (no Foreman transcript recorded, no priced call in
    the whole batch), never closed on a false $0.00."""
    try:
        return cost_rows(repo, d, d["host"], foreman_uuid(d))
    except ChantierError as e:
        raise ChantierError(
            f"cannot close {batch}: its final cost cannot be priced ({e}). Nothing was deleted.",
            EXIT_PRECONDITION,
        ) from e


def _final_pages(k: Closing, d: Rec) -> None:
    """The archived CR pages outlive the batch: priced to now, they alone say the cost is final."""
    by_cr = cost_groups(k.repo, k.batch, k.rows, "cr")
    crs = [
        {**c, "cost_usd": round(by_cr[c["id"]][1], 4), "cost_unpriced": by_cr[c["id"]][2]}
        if c["id"] in by_cr
        else c
        for c in d["crs"]
    ]
    write_final_pages(k.repo, {**d, "crs": crs}, k.folder)


def _close_files(k: Closing, record: Rec) -> tuple[Rec, str]:
    """`batch-NN.json` and `batch-NN.md` as `close` writes them, the CRs at their archives."""
    by_cr = cost_groups(k.repo, k.batch, k.rows, "cr")
    final = close_record(record, now(), sum(r["usd"] for r in k.rows), sum_unpriced(k.rows), by_cr)
    return final, close_markdown(final, k.summary, k.retro, release_retro_line(k.repo, record))


def _move_own_files(k: Closing, done: list[tuple[Path, Path]]) -> Path:
    """The batch's own files go by a rename first: a rename fails whole on a file in use, a delete
    would stop halfway."""
    going = k.repo.changes / f".closing-{k.batch}"
    going.mkdir()
    for p in k.own:
        try:
            retry(p.rename, going / p.name)
        except OSError as e:
            raise ChantierError(
                f"{p.name} of {shown(k.repo, k.folder)} is in use, close what holds "
                f"it and run this again: {e}",
                EXIT_EXTERNAL,
            ) from e
        done.append((p, going / p.name))
    return going


def _put_back(k: Closing, done: list[tuple[Path, Path]]) -> None:
    for source, target in reversed(done):
        if target.exists() and not source.exists():
            retry(target.rename, source)
    with contextlib.suppress(OSError):
        (k.repo.changes / f".closing-{k.batch}").rmdir()


def archive_and_delete(k: Closing) -> None:
    """All or nothing: each `3-done` CR is renamed into `5-archives` (named for its merge time),
    the batch's record is completed (`batch-NN.md`, then `batch-NN.json`, which holds the retro
    and the final cost), the final pages are written where the CRs are now, and the batch's own
    files go by a rename first. Any failure puts every rename back, removes the Markdown and
    puts the JSON as it was."""
    repo, number = k.repo, number_of(k.batch)
    archives = stage_layout(repo)["archives"]
    done: list[tuple[Path, Path]] = []
    path = record_path(repo, number)
    old = path.read_bytes() if path.is_file() else None
    wrote = False
    try:
        record = {**k.d, "crs": [dict(c) for c in k.d["crs"]]}
        for c, source in k.archived:
            target = archives / archive_name(c, source)
            move_directory(source, target)
            done.append((source, target))
            next(x for x in record["crs"] if x["id"] == c["id"])["path"] = repo.rel(target)
        check_closable(repo, number)
        wrote = True
        write_close(repo, *_close_files(k, record))
        _final_pages(k, record)
        going = _move_own_files(k, done)
    except BaseException:
        _put_back(k, done)
        if wrote:
            undo_close(repo, number, old)
        raise
    shutil.rmtree(going)
