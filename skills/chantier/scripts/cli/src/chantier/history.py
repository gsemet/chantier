"""The batch records: each batch leaves `batch-NN.json` (read by a UI) and `batch-NN.md` (read by
a person) in `5-archives/batches/`, published with the planning folder.

`open` reserves the number by writing the JSON as `running`; `close` completes it and writes the
Markdown, which also holds the batch's retro; the next number is read from these records. Each
batch writes only its own two files, so two users of a surface never edit the same file.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .rails import usd_text
from .state import EXIT_CONFLICT, RECORDS, ChantierError, Repo, read_text, write_file
from .status import forge_word, shape_word, steering_word

Rec = dict[str, Any]  # a record, as its JSON reads
SCHEMA = 1
NO_RETRO = "No retro was written."


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


def write_record(path: Path, record: Rec) -> None:
    write_file(path, json.dumps(record, indent=2, ensure_ascii=False) + "\n")


def read_record(path: Path) -> Rec | None:
    try:
        data = json.loads(read_text(path))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def blank_record(number: int) -> Rec:
    """Every field, each `null` (or empty) until it is known."""
    return {"schema": SCHEMA, "batch": name_of(number), "number": number, "state": "unknown",
            "opened": None, "closed": None, "mode": None, "steering": None, "host": None,
            "budget_usd": None, "cost_usd": None, "cost_unpriced": {}, "crs": [], "report": None,
            "backfill": None}


def open_record(data: Rec) -> Rec:
    """The record of a running batch, from its `batch.json`: no CR is listed before `close`."""
    return {**blank_record(number_of(data["id"])), "state": "running",
            "opened": data.get("created"), "mode": data.get("mode"),
            "steering": data.get("steering"), "host": data.get("host"),
            "budget_usd": data.get("budget_usd")}


def reserve_record(repo: Repo, data: Rec) -> Path:
    """`open` writes the record before the batch's state; one that exists is another machine's
    batch, whose planning folder was not pulled: refused, nothing written."""
    number = number_of(data["id"])
    path = record_path(repo, number)
    if path.exists():
        raise ChantierError(f"{data['id']} is already recorded in {repo.rel(path)}; pull the "
                            "planning folder and open again", EXIT_CONFLICT)
    write_record(path, open_record(data))
    return path


# ---- the last closed batch --------------------------------------------------------------------

def last_closed(repo: Repo) -> Rec | None:
    """The record with the highest number whose state is `closed`."""
    found = []
    for path in records_dir(repo).glob("batch-*.json"):
        if (m := re.fullmatch(r"batch-(\d+)\.json", path.name)):
            found.append((int(m[1]), path))
    for _, path in sorted(found, reverse=True):
        record = read_record(path)
        if record and record.get("state") == "closed":
            return record
    return None


def last_closed_text(record: Rec | None) -> str:
    """The line `status` prints under its head line."""
    if record is None:
        return "last closed: none"
    crs = record.get("crs") or []
    counts = f"{sum(c['result'] == 'merged' for c in crs)} merged, " \
             f"{sum(c['result'] == 'dropped' for c in crs)} dropped"
    when = f", closed {record['closed'][:10]}" if record.get("closed") \
        else " (backfilled, no close date)"
    cost = record.get("cost_usd")
    price = "" if cost is None else ", " + usd_text(cost, record.get("cost_unpriced"))
    return f"last closed: {record['batch']}{when}, {counts}{price}"


def last_closed_note(repo: Repo) -> str:
    """The end of the refusal when no batch runs: which batch was the last."""
    record = last_closed(repo)
    return f"; last closed: {record['batch']}" if record else "; no batch closed yet"


# ---- close ------------------------------------------------------------------------------------

def read_retro(folder: Path) -> str | None:
    """`4-batch/retro.md`'s text; None when there is no retro: missing, or no bytes but
    whitespace."""
    retro = folder / "retro.md"
    try:
        if not retro.is_file() or not retro.read_bytes().strip():
            return None
        return read_text(retro, "replace")
    except OSError:
        return None


def check_closable(repo: Repo, number: int) -> None:
    """Refuses (exit 3) a batch whose `batch-NN.md` exists or whose record says `closed`."""
    existing = read_record(record_path(repo, number))
    if report_path(repo, number).exists() or (existing and existing.get("state") == "closed"):
        raise ChantierError(f"refusing to overwrite {repo.rel(report_path(repo, number))}: "
                            f"{name_of(number)} is already closed, nothing was closed",
                            EXIT_CONFLICT)


def archive_of(c: Rec) -> str | None:
    """A CR's folder after `close`, relative to the planning folder, in `/` form."""
    path = c.get("path")
    return str(path).replace("\\", "/").removeprefix(".agents/changes/") if path else None


def cr_entry(c: Rec, by_cr: Rec) -> Rec:
    cost = by_cr.get(c["id"])
    return {"cr": c["id"], "title": c.get("title"),
            "result": "merged" if c["status"] == "merged" else "dropped",
            "archive": archive_of(c), "pr": c.get("pr"), "rounds": c.get("round"),
            "cost_usd": round(cost[1], 4) if cost else None,
            "cost_unpriced": cost[2] if cost else {}}


def close_record(d: Rec, closed: str, total: float, unpriced: Rec, by_cr: Rec) -> Rec:
    """`d` is the batch as it is at `close`, its CRs' `path` already the archives'."""
    crs = sorted(d["crs"], key=lambda c: c.get("order", 0))
    return {**open_record(d), "state": "closed", "closed": closed, "cost_usd": round(total, 4),
            "cost_unpriced": unpriced, "crs": [cr_entry(c, by_cr) for c in crs],
            "report": f"{d['id']}.md"}


def link_to(archive: str | None) -> str:
    """A folder of the planning folder, as a link from `5-archives/batches/`."""
    if not archive:
        return ""
    return f"../{archive.removeprefix('5-archives/')}/" if archive.startswith("5-archives/") \
        else f"../../{archive}/"


def table_lines(crs: list[Rec]) -> list[str]:
    """The Completion report's table: CR, subject, result, PR, rounds, cost."""
    forge = forge_word([c.get("pr") for c in crs])
    lines = [f"| CR | Subject | Result | {forge} | Rounds | Cost |",
             "| --- | --- | --- | --- | ---: | ---: |"]
    for c in crs:
        cr = f"[{c['cr']}]({link_to(c.get('archive'))})" if c.get("archive") else c["cr"]
        cost = c.get("cost_usd")
        price = "-" if cost is None else usd_text(cost, c.get("cost_unpriced"))
        lines.append(f"| {cr} | {str(c.get('title') or '-').replace('|', '/')} | {c['result']} | "
                     f"{c.get('pr') or '-'} | {'-' if c.get('rounds') is None else c['rounds']} "
                     f"| {price} |")
    return lines


def head_line(record: Rec) -> str:
    budget = record.get("budget_usd")
    cost = record.get("cost_usd")
    price = "no cost recorded" if cost is None else usd_text(cost, record.get("cost_unpriced"))
    return (f"Opened {record['opened']}, closed {record['closed']}, "
            f"{shape_word(record['mode'])}, steered by {steering_word(record['steering'])}, "
            f"{f'budget ${budget:g}' if budget else 'no budget'}, final cost {price}. "
            f"[{record['batch']}.json]({record['batch']}.json)")


def release_retro_line(repo: Repo, d: Rec) -> str | None:
    """A release CR's own `work/retro.md`, linked where it is archived, never copied."""
    for c in d["crs"]:
        archive = archive_of(c)
        if c.get("kind") == "release" and archive \
                and (repo.changes / archive / "work" / "retro.md").is_file():
            return f"Release retro: {link_to(archive)}work/retro.md"
    return None


def close_markdown(record: Rec, summary: list[str], retro: str | None,
                   release: str | None) -> str:
    """`batch-NN.md`: the title, the head line, the Completion table, the cost, the retro."""
    head = [f"# {record['batch']}", "", head_line(record), "", "## Completion", "",
            *table_lines(record["crs"]), "", "## Cost", "", *(f"- {s.strip()}" for s in summary),
            "", "## Retro", ""]
    body = retro if retro else NO_RETRO  # the retro's own bytes, whole
    return "\n".join(head) + "\n" + body + ("" if body.endswith("\n") else "\n") \
        + (f"\n{release}\n" if release else "")


def write_close(repo: Repo, record: Rec, markdown: str) -> None:
    """The Markdown first, then the JSON. The caller has checked that no Markdown exists
    (`check_closable`), and undoes with `undo_close` from here on."""
    write_file(report_path(repo, record["number"]), markdown)
    write_record(record_path(repo, record["number"]), record)


def undo_close(repo: Repo, number: int, old: bytes | None) -> None:
    """Put the JSON's old bytes back (none: remove it) and remove the Markdown this close wrote."""
    report_path(repo, number).unlink(missing_ok=True)
    if old is None:
        record_path(repo, number).unlink(missing_ok=True)
    else:
        record_path(repo, number).write_bytes(old)
