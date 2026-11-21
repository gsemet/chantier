"""The batch records on disk: each batch leaves `batch-NN.json` (read by a UI) and `batch-NN.md`
(read by a person) in `5-archives/batches/`, published with the planning folder.

`open` reserves the number by writing the JSON as `running`; `close` completes it and writes the
Markdown, which also holds the batch's retro; the next number is read from these records. Each
batch writes only its own two files, so two users of a surface never edit the same file. What
the Markdown says is made in `chantier.history`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from chantier.core.errors import EXIT_CONFLICT, ChantierError
from chantier.core.files import rel_in
from chantier.core.records import BatchRecord
from chantier.core.repo import RECORDS, Repo

if TYPE_CHECKING:
    from chantier.store import PlanStore

Rec = dict[str, Any]  # a record, as its JSON reads
SCHEMA = 1


def name_of(number: int) -> str:
    return f"batch-{number:02d}"


def number_of(batch_id: str) -> int:
    match = re.search(r"\d+", batch_id)
    if not match:
        raise ChantierError(f"{batch_id} carries no batch number")
    return int(match.group())


def records_dir(repo: Repo) -> Path:
    return repo.changes / RECORDS


def record_path(repo: Repo, number: int) -> Path:
    return records_dir(repo) / f"{name_of(number)}.json"


def report_path(repo: Repo, number: int) -> Path:
    return records_dir(repo) / f"{name_of(number)}.md"


def write_record(repo: Repo, path: Path, record: Rec) -> None:
    repo.store.write_json(repo.rel(path), record, ensure_ascii=False)


def read_record(store: PlanStore, path: Path) -> Rec | None:
    try:
        data = json.loads(store.read_text(rel_in(store.root, path)))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def blank_record(number: int) -> Rec:
    """Every field, each `null` (or empty) until it is known."""
    return {
        "schema": SCHEMA,
        "batch": name_of(number),
        "number": number,
        "state": "unknown",
        "opened": None,
        "closed": None,
        "mode": None,
        "steering": None,
        "host": None,
        "budget_usd": None,
        "cost_usd": None,
        "cost_unpriced": {},
        "crs": [],
        "cost_receipt": None,
        "report": None,
    }


def open_record(data: BatchRecord) -> Rec:
    """The record of a running batch, from its `batch.json`: no CR is listed before `close`."""
    return {
        **blank_record(number_of(data.id)),
        "state": "running",
        "opened": data.created,
        "mode": data.mode,
        "steering": data.steering,
        "host": data.host,
        "budget_usd": data.budget_usd,
    }


def reserve_record(repo: Repo, data: BatchRecord) -> Path:
    """`open` writes the record before the batch's state; one that exists is another machine's
    batch, whose planning folder was not pulled: refused, nothing written."""
    number = number_of(data.id)
    path = record_path(repo, number)
    if repo.store.exists(rel_in(repo.store.root, path)):
        raise ChantierError(
            f"{data.id} is already recorded in {repo.rel(path)}; pull the "
            "planning folder and open again",
            EXIT_CONFLICT,
        )
    write_record(repo, path, open_record(data))
    return path


def last_closed(repo: Repo) -> Rec | None:
    """The record with the highest number whose state is `closed`."""
    store = repo.store
    found = []
    for name in store.glob(rel_in(store.root, records_dir(repo)), "batch-*.json"):
        if m := re.fullmatch(r"batch-(\d+)\.json", name):
            found.append((int(m[1]), records_dir(repo) / name))
    for _, path in sorted(found, reverse=True):
        record = read_record(store, path)
        if record and record.get("state") == "closed":
            return record
    return None


def last_closed_note(repo: Repo) -> str:
    """The end of the refusal when no batch runs: which batch was the last."""
    record = last_closed(repo)
    return f"; last closed: {record['batch']}" if record else "; no batch closed yet"


def read_retro(store: PlanStore, folder: Path) -> str | None:
    """`4-batch/retro.md`'s text; None when there is no retro: missing, or no bytes but
    whitespace."""
    rel = rel_in(store.root, folder / "retro.md")
    try:
        if not store.is_file(rel) or not store.read_bytes(rel).strip():
            return None
        return store.read_text(rel, "replace")
    except OSError:
        return None


def check_closable(repo: Repo, number: int) -> None:
    """Refuses (exit 3) a batch whose `batch-NN.md` exists or whose record says `closed`."""
    store = repo.store
    existing = read_record(store, record_path(repo, number))
    if store.exists(rel_in(store.root, report_path(repo, number))) or (
        existing and existing.get("state") == "closed"
    ):
        raise ChantierError(
            f"refusing to overwrite {repo.rel(report_path(repo, number))}: "
            f"{name_of(number)} is already closed, nothing was closed",
            EXIT_CONFLICT,
        )


def write_close(repo: Repo, record: Rec, markdown: str) -> None:
    """The Markdown first, then the JSON. The caller has checked that no Markdown exists
    (`check_closable`), and undoes with `undo_close` from here on."""
    repo.store.write_text(repo.rel(report_path(repo, record["number"])), markdown)
    write_record(repo, record_path(repo, record["number"]), record)


def undo_close(repo: Repo, number: int, old: bytes | None) -> None:
    """Put the JSON's old bytes back (none: remove it) and remove the Markdown this close wrote."""
    for path in (report_path(repo, number), *([record_path(repo, number)] if old is None else [])):
        if repo.store.exists(rel_in(repo.store.root, path)):
            repo.store.remove(repo.rel(path))
    if old is not None:
        repo.store.write_bytes(repo.rel(record_path(repo, number)), old)
