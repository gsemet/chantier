"""The forge journal: `forge-journal.jsonl` at the planning folder's root, one JSON line per forge
event of a project's batch. It is local (ignored by git) and append-only; chantier never
truncates it. The forge hub (`by: "hub"`) and the board's PRs page (`by: "board"`) are its
writers; `chantier status` and `chantier watch` its readers. Nothing here records anything in a
batch: a line is a signal the Chief of Staff reads.

Every line carries `seq` (1 for the first line, then the highest readable `seq` plus one), `t`,
`by` and `kind`:

- `merged`: `batch`, `cr`, `pr`, `into`, `into_cr`, `merged_at`, and once the base landed
  `landed_with` and `landed_at`. Written once per batch, CR and landed-or-not: a PR merged into
  another CR's branch is first read not landed, and one second line follows, once, when a later
  read finds it landed with its base.
- `checks-red`: `batch`, `cr`, `pr`, `head` (the PR head's commit SHA). Written once per batch,
  CR and head: a new red head after a fix gives a new line, the same head read again none.

Every append runs under the project's lifecycle lock, reads the file, assigns `seq` and skips a
line already there, whoever wrote the first. An unreadable line is skipped, never rewritten."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from chantier.core import clock
from chantier.core.files import read_text
from chantier.core.repo import Repo
from chantier.lifecycle.stages import changes_lock

FILE = "forge-journal.jsonl"
SHA_SHOWN = 7


def read(changes: Path) -> tuple[list[dict[str, Any]], list[int]]:
    """The lines that are JSON objects, and the numbers (from 1) of the lines that are not."""
    path = changes / FILE
    if not path.is_file():
        return [], []
    found: list[dict[str, Any]] = []
    bad: list[int] = []
    for n, line in enumerate(read_text(path, "replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            entry = None
        if isinstance(entry, dict):
            found.append(entry)
        else:
            bad.append(n)
    return found, bad


def last_seq(entries: list[dict[str, Any]]) -> int:
    """The highest readable `seq`, 0 for none."""
    return max((e["seq"] for e in entries if type(e.get("seq")) is int), default=0)


def _key(e: dict[str, Any]) -> tuple[Any, ...]:
    """What makes two lines the same event."""
    if e.get("kind") == "checks-red":
        return ("checks-red", e.get("batch"), e.get("cr"), e.get("head"))
    return ("merged", e.get("batch"), e.get("cr"), bool(e.get("landed_with")))


def merged_events(batch: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The `merged` events of the rows the forge shows merged and the record does not."""
    out: list[dict[str, Any]] = []
    for r in rows:
        if r.get("why") != "merged":
            continue
        landed = r.get("landed_with") or {}
        into = r["merged_into"] or {}
        entry: dict[str, Any] = {
            "kind": "merged",
            "batch": batch,
            "cr": r["cr"],
            "pr": r["pr"],
            "into": into.get("branch"),
            "into_cr": into.get("cr"),
            "merged_at": r["merged_at"],
        }
        if landed:
            entry["landed_with"], entry["landed_at"] = landed["cr"], landed["at"]
        out.append(entry)
    return out


def red_event(batch: str, cr: str, pr: str, head: str) -> dict[str, Any]:
    return {"kind": "checks-red", "batch": batch, "cr": cr, "pr": pr, "head": head}


def append(repo: Repo, events: list[dict[str, Any]], by: str) -> list[dict[str, Any]]:
    """Append each event not yet in the journal, under the lifecycle lock; the lines written."""
    if not events:
        return []
    with changes_lock(repo):
        entries = read(repo.changes)[0]
        seen = {_key(e) for e in entries}
        seq = last_seq(entries)
        written: list[dict[str, Any]] = []
        for event in events:
            if _key(event) in seen:
                continue
            seen.add(_key(event))
            seq += 1
            written.append({"seq": seq, "t": clock.now(), "by": by, **event})
        if written:
            text = "".join(
                json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n" for e in written
            )
            with (repo.changes / FILE).open("ab") as f:
                f.write(text.encode("utf-8", errors="replace"))
        return written


def merged_text(e: dict[str, Any]) -> str:
    """The line a `merged` event is told by, in `status` and at a watcher's end."""
    head = f"forge saw merged: {e.get('cr')} {e.get('pr')}"
    at, cr = e.get("merged_at"), e.get("cr")
    if e.get("into_cr") and e.get("landed_with"):
        return (
            f"{head} into {e['into_cr']}'s branch at {at}, landed with {e['landed_with']} "
            f"at {e.get('landed_at')}; for the Chief of Staff: order merged {cr}"
        )
    if e.get("into_cr"):
        return (
            f"{head} into {e['into_cr']}'s branch at {at}; for the Chief of Staff: not "
            f"landed, tell the user, record nothing until {e['into_cr']} lands"
        )
    return f"{head} into {e.get('into')} at {at}; for the Chief of Staff: order merged {cr}"


def red_text(e: dict[str, Any]) -> str:
    return (
        f"forge saw checks red: {e.get('cr')} {e.get('pr')} at {str(e.get('head'))[:SHA_SHOWN]}, "
        "ready to merge in the record; for the Chief of Staff: tell the user, record nothing"
    )


def event_text(e: dict[str, Any]) -> str:
    return red_text(e) if e.get("kind") == "checks-red" else merged_text(e)


def lines(entries: list[dict[str, Any]], batch: str, open_crs: set[str]) -> list[str]:
    """The `status` lines for the Chief of Staff, one per open CR of `batch`: the `merged` entry
    that says the PR landed wins, else the first. A `checks-red` entry is never listed."""
    chosen: dict[str, dict[str, Any]] = {}
    for e in entries:
        cr = e.get("cr")
        if e.get("kind") != "merged" or e.get("batch") != batch or cr not in open_crs:
            continue
        if cr not in chosen or (e.get("landed_with") and not chosen[cr].get("landed_with")):
            chosen[cr] = e
    return [merged_text(e) for e in chosen.values()]
