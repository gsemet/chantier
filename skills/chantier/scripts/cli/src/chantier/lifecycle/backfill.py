"""The batch records of the batches that ran before the records existed.

Once per planning folder, the first command after the update (as `convert_old_tree` does for the
tree), `5-archives/batches/` is written from what this machine still holds: the archived and
trashed CRs' `STATUS.json` (each names its batch), `.batch-number` and the live batch. Nothing in
an archive moves or changes: past retros are linked from the Markdown, never moved.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from chantier.core.batch_records import (
    Rec,
    blank_record,
    name_of,
    number_of,
    open_record,
    write_record,
)
from chantier.core.clock import now
from chantier.core.files import read_text, retry, write_file
from chantier.core.records import BatchRecord, read_batch_json
from chantier.core.repo import RECORDS, Repo
from chantier.history import table_lines
from chantier.lifecycle.stages import changes_lock
from chantier.status.views import when_of

STAGES = (("5-archives", "merged"), ("6-trash", "dropped"))
OLD_RETRO_FOLDER = re.compile(r"\d{6}-\d{4}-batch-(\d+)")


@dataclass
class Found:
    """What the archives still say of one batch number."""

    crs: list[Rec] = field(default_factory=list)
    former_id: str | None = None
    steps: list[str] = field(default_factory=list)
    merges: list[str] = field(default_factory=list)
    retros: list[str] = field(default_factory=list)


def _status(folder: Path) -> Rec | None:
    try:
        data = json.loads(read_text(folder / "STATUS.json"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _batch_of(status: Rec | None) -> tuple[int, str] | None:
    """The number and id a CR's `STATUS.json` names: `batch-07`, or an older `01-eval-real`."""
    batch = (status or {}).get("batch")
    match = re.match(r"(?:batch-)?(\d+)", batch) if isinstance(batch, str) else None
    return (int(match[1]), batch) if match and isinstance(batch, str) else None


def _folders(stage: Path) -> list[Path]:
    return sorted(p for p in stage.iterdir() if p.is_dir()) if stage.is_dir() else []


def _batch_number_file(repo: Repo) -> int:
    try:
        return int(read_text(repo.changes / ".batch-number"))
    except (OSError, ValueError):
        return 0


def _has_trace(repo: Repo) -> bool:
    if (repo.changes / ".batch-number").is_file() or (repo.batches / "batch.json").is_file():
        return True
    return any(_batch_of(_status(f)) for name, _ in STAGES for f in _folders(repo.changes / name))


def _entry(repo: Repo, folder: Path, status: Rec, result: str) -> Rec:
    pr = status.get("pr")
    return {
        "cr": status.get("cr") or folder.name,
        "title": status.get("title") or folder.name,
        "result": result,
        "archive": repo.rel(folder),
        "pr": pr.get("url") if isinstance(pr, dict) else pr,
        "rounds": status.get("round"),
        "cost_usd": status.get("cost_usd"),
        "cost_unpriced": status.get("cost_unpriced") or {},
    }


def _add_cr(repo: Repo, found: dict[int, Found], folder: Path, result: str) -> None:
    status = _status(folder)
    named = _batch_of(status)
    if status is None or named is None:
        return
    number, batch_id = named
    one = found.setdefault(number, Found())
    one.crs.append(_entry(repo, folder, status, result))
    if not re.fullmatch(r"batch-\d+", batch_id):
        one.former_id = batch_id
    one.steps += [s["at"] for s in status.get("steps") or [] if isinstance(s, dict) and s.get("at")]
    if result == "merged" and (when := when_of(folder.name)):
        one.merges.append(when)
    one.retros += [
        repo.rel(folder / r) for r in ("retro.md", "work/retro.md") if (folder / r).is_file()
    ]


def _scan(repo: Repo) -> dict[int, Found]:
    found: dict[int, Found] = {}
    for name, result in STAGES:
        for folder in _folders(repo.changes / name):
            old = OLD_RETRO_FOLDER.fullmatch(folder.name)
            if old and (folder / "retro.md").is_file():
                found.setdefault(int(old[1]), Found()).retros.append(repo.rel(folder / "retro.md"))
            elif not old:
                _add_cr(repo, found, folder, result)
    return found


def _cr_order(c: Rec) -> int:
    match = re.search(r"\d+", str(c["cr"]))
    return int(match.group()) if match else 0


def _record(number: int, one: Found | None, written: str) -> Rec:
    record = blank_record(number)
    if one is None:
        return {
            **record,
            "backfill": {
                "written": written,
                "former_id": None,
                "first_step": None,
                "last_merge": None,
                "retros": [],
            },
        }
    return {
        **record,
        "state": "closed",
        "report": f"{name_of(number)}.md",
        "crs": sorted(one.crs, key=_cr_order),
        "backfill": {
            "written": written,
            "former_id": one.former_id,
            "first_step": min(one.steps, default=None),
            "last_merge": max(one.merges, default=None),
            "retros": one.retros,
        },
    }


def _markdown(record: Rec) -> str:
    back = record["backfill"]
    note = (
        (
            "Backfilled on {} from the archived STATUS.json files on this machine: no open or "
            "close date, shape, steering, budget or final cost was kept."
        ).format(back["written"])
        if record["state"] == "closed"
        else "No trace of this batch was left on the machine that wrote this record."
    )
    lines = [f"# {record['batch']}", "", note, ""]
    if record["crs"]:
        lines += ["## Completion", "", *table_lines(record["crs"]), ""]
    links = [f"- [{r}](../../{r})" for r in back["retros"]]
    lines += ["## Retro", "", *(links or ["No retro found."])]
    return "\n".join(lines) + "\n"


def _write_all(repo: Repo, found: dict[int, Found], live: BatchRecord | None, highest: int) -> None:
    final = repo.changes / RECORDS
    tmp = repo.changes / "5-archives" / ".batches.tmp"
    if tmp.exists():
        shutil.rmtree(tmp)  # a killed run's leftover
    written = now()
    for n in range(1, highest + 1):
        if live and number_of(live.id) == n:
            write_record(tmp / f"{name_of(n)}.json", open_record(live))
            continue
        record = _record(n, found.get(n), written)
        write_record(tmp / f"{name_of(n)}.json", record)
        write_file(tmp / f"{name_of(n)}.md", _markdown(record))
    retry(tmp.rename, final)


def backfill_history(repo: Repo) -> None:
    """Write `5-archives/batches/` once, all or nothing, when it does not exist and a trace of an
    earlier batch does. With no trace (a new project) nothing is written, no folder made."""
    if (repo.changes / RECORDS).exists() or not _has_trace(repo):
        return
    with changes_lock(repo):
        if (repo.changes / RECORDS).exists():  # another command did it while this one waited
            return
        found = _scan(repo)
        live = (
            read_batch_json(repo.batches / "batch.json")
            if (repo.batches / "batch.json").is_file()
            else None
        )
        top = [_batch_number_file(repo), *found, *([number_of(live.id)] if live else [])]
        highest = max(top)
        if highest < 1:
            return
        _write_all(repo, found, live, highest)
    known = {*found, *([number_of(live.id)] if live else [])}
    bare = sum(1 for n in range(1, highest + 1) if n not in known)
    print(
        f"backfilled 5-archives/batches: {name_of(1)} to {name_of(highest)} ({bare} with no trace)",
        file=sys.stderr,
    )
