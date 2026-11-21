"""The views of the record: a CR, a batch and the dashboard, as data."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from chantier.core.clock import age_minutes, now
from chantier.core.files import rel_in, subject, title_source
from chantier.core.records import (
    LIVE,
    SUMMARY_FILE,
    BatchRecord,
    CrEntry,
    EventRecord,
    read_batch_json,
    read_events,
    round_limit,
)
from chantier.core.repo import Repo
from chantier.rails import held
from chantier.stack_words import ready_word
from chantier.status.gate import gate_view
from chantier.status.steps import steps
from chantier.status.words import (
    ENDED,
    forge_word,
    no_start,
    notify,
    phase_text,
    severity,
    state_label,
    step,
    waits,
    waits_on,
)

if TYPE_CHECKING:
    from chantier.store.base import PlanStore

SCHEMA = 3
PAST_LIMIT = 50  # merged and trashed CRs listed in the index; the totals count them all
IN_PROGRESS = ("draft:",)  # shown in `Documents`, not in `Decisions`
SPEC_LINK = re.compile(r"[\w./-]+\.md\b")


def _now_next(repo: Repo, d: BatchRecord, c: CrEntry, waiting: list[str]) -> tuple[str, str]:
    pr = c.pr or f"its {forge_word([])}"
    if waits_on(c):
        reason = c.blocked_reason or ""
        what = reason.split(":", 1)[1].strip() or "something on its way"
        return (
            reason,
            f"Waits for {what}; the Foreman takes it back when that lands.",
        )
    if c.status == "blocked":
        return (
            c.blocked_reason or "Blocked.",
            "The user's answer, through the Chief of Staff.",
        )
    if c.status == "ready":
        return notify(repo, d, c, pr)
    return {
        "Queued": (
            f"Waits for {', '.join(waiting)}." if waiting else no_start(d),
            "A Driver starts it.",
        ),
        "Round": ("A coder and its reviews are working.", "The long gate, then the ship."),
        "CI": (
            f"{pr} is open: CI, then the verifier at the pushed head (it records `verdict`).",
            "The hand-back.",
        ),
        "Release": ("The Release driver follows the project's procedure.", "The next step of it."),
        "Merged": (f"Merged: {pr}.", "Nothing."),
        "Dropped": ("Dropped on the user's word.", "Nothing."),
    }[step(c)]


def _link(path: Path, start: Path) -> str:
    return Path(os.path.relpath(path, start)).as_posix()


def _documents(repo: Repo, c: CrEntry, folder: Path) -> list[dict[str, Any]]:
    """The CR's documents that exist, then the project's that its specification cites."""
    spec = folder / c.specification
    named = [
        ("request", folder / "intake" / "request.md"),
        ("intent", folder / "01-intent.md"),
        ("answers", folder / "02-answers.md"),
        ("specification", spec),
    ]
    store = repo.store
    work = folder / "work"
    named += [(Path(n).stem, work / n) for n in store.glob(rel_in(store.root, work), "*.md")]
    gates = store.glob(rel_in(store.root, work / "gates"), "*.log")
    named += [("long gate log", work / "gates" / gates[-1])] if gates else []
    named.append(("evidence", folder / "evidence"))
    docs = [
        {"kind": kind, "path": _link(p, folder)}
        for kind, p in named
        if store.exists(rel_in(store.root, p))
    ]
    if store.is_file(rel_in(store.root, spec)):
        text = store.read_text(rel_in(store.root, spec), "replace")
        for name in sorted(set(SPEC_LINK.findall(text))):
            target = repo.root / name
            # a URL's tail reads as a network path on Windows: this must never leave the disk
            if (
                not name.startswith("/") and ".." not in name and target.is_file()
            ):  # direct: a project file, outside the planning folder
                docs.append({"kind": "project", "path": _link(target, folder), "name": name})
    return docs


def cr_view(
    repo: Repo, d: BatchRecord, c: CrEntry, where: tuple[Path, list[EventRecord], bool]
) -> dict[str, Any]:
    """The CR's page; `where`: its folder, its events, and whether the folder is in the batch."""
    folder, events, in_batch = where
    waiting = waits(d, c)
    now_line, next_line = _now_next(repo, d, c, waiting)
    silent = age_minutes(c.updated) if c.status in LIVE else None
    pr = c.shown_pr()
    number = re.search(r"(\d+)/?$", pr or "")
    return {
        "schema": SCHEMA,
        "updated": now(),
        "cr": c.id,
        "title": shown_title(repo.store, c.title, folder),
        "batch": d.id,
        "in_batch": in_batch,
        "state": c.status,
        "severity": severity(c),
        "step": step(c),
        "phase": phase_text(c),
        "phase_at": c.phase_at if c.status == "working" else None,
        "label": state_label(repo, d, c, waiting),
        "readiness": ready_word(d, c, repo),
        "waits": waiting,
        "round": c.round,
        "max_rounds": round_limit(d, c),
        "now": now_line,
        "next": next_line,
        "pr": {"url": pr, "number": int(number[1]) if number else None} if pr else None,
        "gate": gate_view(repo, d, c, events),
        "steps": steps(d, c, events),
        "documents": _documents(repo, c, folder),
        "branch": c.branch,
        "worktree": c.worktree,
        "agent": c.agent,
        "notes": [n for n in c.notes if not n.startswith(IN_PROGRESS)],
        "blocked": c.blocked_reason if c.status == "blocked" else None,
        "cost_usd": c.cost_usd,
        "cost_unpriced": c.cost_unpriced,
        "final_cost": d.closing,
        "silent_minutes": round(silent) if silent is not None else None,
    }


def _priced(d: BatchRecord) -> bool:
    unknown = any(line.startswith("Spent: unknown") for line in d.summary)
    return d.spent_usd is not None and not unknown


def _row(
    repo: Repo, d: BatchRecord, c: CrEntry, start: Path, events: list[EventRecord]
) -> dict[str, Any]:
    folder = repo.planning_path(c.path) if c.path else None
    silent = age_minutes(c.updated) if c.status in LIVE else None
    waiting = waits(d, c)
    return {
        "cr": c.id,
        "title": shown_title(repo.store, c.title, folder),
        "state": c.status,
        "severity": severity(c),
        "step": step(c),
        "phase": phase_text(c),
        "label": state_label(repo, d, c, waiting),
        "readiness": ready_word(d, c, repo),
        "waits": waiting,
        "round": c.round,
        "branch": c.branch,
        "pr": c.shown_pr(),
        "gate": gate_view(repo, d, c, events),
        "cost_usd": c.cost_usd,
        "cost_unpriced": c.cost_unpriced,
        "blocked": c.blocked_reason if c.status == "blocked" else None,
        "silent_minutes": round(silent) if silent is not None else None,
        # always relative to `.agents/changes/`, whatever `start` is: the board resolves it there
        "folder": _link(folder, repo.changes) if folder else None,
        "status": _link(folder / "STATUS.md", start) if folder else None,
        "specification": _link(folder / c.specification, start) if folder else None,
    }


def batch_view(repo: Repo, d: BatchRecord, folder: Path) -> dict[str, Any]:
    events = read_events(repo.store, folder)
    return {
        "schema": SCHEMA,
        "updated": now(),
        "batch": d.id,
        "folder": folder.name,
        "state": d.status,
        "mode": d.mode,
        "steering": d.steering,
        "spent_usd": d.spent_usd,
        "spent_at": d.spent_at,
        "budget_usd": d.budget_usd,
        "unpriced": d.unpriced,  # model -> calls left out of spent_usd (a floor)
        "priced": _priced(d),
        "asks_unread": sum(1 for a in d.asks if not a.read),
        "orders_pending": sum(1 for o in d.orders if not o.done),
        "heartbeat": d.heartbeat,
        "heartbeat_stopped": d.heartbeat_stopped,  # the loop ended on purpose, when
        "paused": d.paused,
        "summary": d.summary,
        "crs": [_row(repo, d, c, folder, events) for c in sorted(d.crs, key=lambda x: x.order)],
        "crs_total": len(d.crs),  # every CR the batch ever held; `crs` lists its active ones
    }


def folder_title(store: PlanStore, folder: Path) -> str:
    """The title of a CR folder, as the board shows it when no summary or record gives one: the
    first heading of its specification, intent or request, else its first line, else its name."""
    return title_source(store, folder)[0]


def shown_title(store: PlanStore, recorded: str, folder: Path | None) -> str:
    """A CR's recorded title, unless it is empty or a front matter's fence (`---`, recorded by an
    older `open`): then the folder's own title, when the folder is known."""
    if recorded and recorded.strip() != "---":
        return subject(recorded)
    if folder is not None and store.is_dir(rel_in(store.root, folder)):
        return folder_title(store, folder)
    return recorded


def spec_state(store: PlanStore, folder: Path) -> str | None:
    """The spec-writer's state, read from the folder: `specifying` while the Chief of Staff's
    `work/specifying` marker exists, `specified` once the specification exists without it."""
    rel = rel_in(store.root, folder)
    if store.exists(f"{rel}/work/specifying"):
        return "specifying"
    return "specified" if store.is_file(f"{rel}/03-change-spec.md") else None


def _backlog(store: PlanStore, paths: dict[str, Path], start: Path) -> list[dict[str, Any]]:
    root = store.root
    found = [("3-ready", paths["ready"])]
    found += [
        ("P" + n[1:], paths["backlog"] / n)
        for n in store.glob(rel_in(root, paths["backlog"]), "P[1-4]")
    ]
    found.append(("inbox", paths["inbox"]))
    rows = []
    for priority, stage in found:
        stage_rel = rel_in(root, stage)
        for name in store.listdir(stage_rel) if store.is_dir(stage_rel) else []:
            item = stage / name
            if store.is_dir(f"{stage_rel}/{name}"):
                rows.append(
                    {
                        "priority": priority,
                        "item": item.name,
                        "title": folder_title(store, item),
                        "path": _link(item, start),
                        "spec": spec_state(store, item),
                        "files": sum(
                            1
                            for _, _, names in store.walk(f"{stage_rel}/{name}")
                            for n in names
                            if n != SUMMARY_FILE
                        ),  # the summary is no document of the CR: the index reads the same
                    }
                )
    return rows


def when_of(name: str) -> str | None:
    """`261105-1059-...` read as a UTC timestamp, or None for a name without the prefix."""
    m = re.match(r"(\d\d)(\d\d)(\d\d)-(\d\d)(\d\d)", name)
    return f"20{m[1]}-{m[2]}-{m[3]}T{m[4]}:{m[5]}:00Z" if m else None


def _past(store: PlanStore, stage: Path, start: Path) -> tuple[list[dict[str, Any]], int]:
    """The last `PAST_LIMIT` CRs of an archive or trash stage, newest first, and the stage's count.

    At most `PAST_LIMIT` STATUS.json files are read; a folder without one gives its title only.
    """
    # `batches` (the batches' records) and a retro-only folder (`<YYMMDD-HHMM>-<batch id>`, from
    # before the records) hold no CR: not listed, not counted
    stage_rel = rel_in(store.root, stage)
    folders = (
        sorted(
            (
                stage / n
                for n in store.listdir(stage_rel)
                if store.is_dir(f"{stage_rel}/{n}")
                and n != "batches"
                and not re.fullmatch(r"\d{6}-\d{4}-batch-\d+", n)
            ),
            reverse=True,
        )
        if store.is_dir(stage_rel)
        else []
    )
    out = []
    for folder in folders[:PAST_LIMIT]:
        try:
            s = json.loads(store.read_text(rel_in(store.root, folder / "STATUS.json")))
        except (OSError, ValueError):
            s = {}
        pr = s.get("pr")
        out.append(
            {
                "cr": s.get("cr"),
                "title": shown_title(store, s.get("title") or "", folder),
                "state": s.get("state"),
                "batch": s.get("batch"),
                "pr": pr.get("url") if isinstance(pr, dict) else pr,
                "cost_usd": s.get("cost_usd"),
                "when": when_of(folder.name),
                "path": _link(folder, start),
            }
        )
    return out, len(folders)


def _done_rows(repo: Repo, start: Path) -> list[dict[str, Any]]:
    """The batch's CRs waiting in `3-done`, newest merge first: they head the merged list."""
    out = []
    for folder in repo.batch_folders():
        d = read_batch_json(repo.store, folder / "batch.json")
        for c in d.crs:
            where = repo.planning_path(c.path) if c.path else None
            if where is None or where.parent != folder / "3-done":
                continue
            out.append(
                {
                    "cr": c.id,
                    "title": shown_title(repo.store, c.title, where),
                    "state": c.status,
                    "batch": d.id,
                    "pr": c.shown_pr(),
                    "cost_usd": c.cost_usd,
                    "when": c.merged_at,
                    "path": _link(where, start),
                }
            )
    return sorted(out, key=lambda r: r["when"] or "", reverse=True)


def dashboard_view(repo: Repo, paths: dict[str, Path]) -> dict[str, Any]:
    start = repo.changes
    batches = []
    for folder in repo.batch_folders():
        d = read_batch_json(repo.store, folder / "batch.json")
        v = batch_view(repo, d, folder)
        events = read_events(repo.store, folder)
        active = [c for c in sorted(d.crs, key=lambda x: x.order) if c.status not in ENDED]
        batches.append(
            {
                "batch": v["batch"],
                "folder": folder.name,
                "state": v["state"],
                "spent_usd": v["spent_usd"],
                "spent_at": v["spent_at"],
                "budget_usd": v["budget_usd"],
                "unpriced": v["unpriced"],
                "asks_unread": v["asks_unread"],
                "heartbeat": v["heartbeat"],
                "heartbeat_stopped": v["heartbeat_stopped"],
                "orders_pending": v["orders_pending"],
                "slots": {"taken": len(held(d)), "total": d.slots},
                "mode": v["mode"],
                "crs_total": v["crs_total"],
                "crs": [_row(repo, d, c, start, events) for c in active],
            }
        )
    merged, merged_total = _past(repo.store, paths["archives"], start)
    done = _done_rows(repo, start)
    merged, merged_total = (done + merged)[:PAST_LIMIT], merged_total + len(done)
    trashed, trashed_total = _past(repo.store, paths["trash"], start)
    return {
        "schema": SCHEMA,
        "updated": now(),
        "batches": batches,
        "active_crs": sum(len(b["crs"]) for b in batches),
        "backlog": _backlog(repo.store, paths, start),
        "merged": merged,
        "merged_total": merged_total,
        "trashed": trashed,
        "trashed_total": trashed_total,
    }
