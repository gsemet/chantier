"""The views of the record: a CR, a batch and the dashboard, as data."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from chantier.core.clock import age_minutes, now
from chantier.core.files import read_text
from chantier.core.records import LIVE, read_batch_json, round_limit
from chantier.core.repo import Repo
from chantier.rails import held
from chantier.status.words import (
    ENDED,
    can_start,
    forge_word,
    label,
    no_start,
    severity,
    step,
    waits,
    waits_on,
)

SCHEMA = 3


PAST_LIMIT = 50  # merged and trashed CRs listed in the index; the totals count them all


AHEAD = ("Shipped", "Handed back")


IN_PROGRESS = ("draft:",)  # shown in `Documents`, not in `Decisions`


SPEC_LINK = re.compile(r"[\w./-]+\.md\b")


TITLE_FILES = ("03-change-spec.md", "01-intent.md", "intake/request.md")


def _now_next(d: dict[str, Any], c: dict[str, Any], waiting: list[str]) -> tuple[str, str]:
    pr = c.get("pr") or f"its {forge_word([])}"
    if waits_on(c):
        what = c["blocked_reason"].split(":", 1)[1].strip() or "something on its way"
        return (
            c["blocked_reason"],
            f"Waits for {what}; the Foreman takes it back when that lands.",
        )
    if c["status"] == "blocked":
        return (
            c.get("blocked_reason") or "Blocked.",
            "The user's answer, through the Chief of Staff.",
        )
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
        "Notify": (f"Ready: {pr} waits for the user's merge.", "The merge, then the archive."),
        "Merged": (f"Merged: {pr}.", "Nothing."),
        "Dropped": ("Dropped on the user's word.", "Nothing."),
    }[step(c)]


def _step_entries(
    e: dict[str, Any], c: dict[str, Any], out: list[dict[str, Any]]
) -> list[tuple[str, str, str]]:
    """The steps (name, verdict, note) one event of the log makes."""
    kind, note = e.get("kind"), e.get("note") or ""
    head = (e.get("head") or "")[:7]  # display only
    result = e.get("result", "")
    plain = {
        "round": (f"Round {e.get('round')}", "", note),
        "note": ("Note", "", note),
        "gate": ("Long gate", result, head),
        "verdict": ("Verdict", result, head),
        "ship": ("Shipped", "", e.get("pr", "")),
    }
    if kind in plain:
        return [plain[kind]]
    if kind == "handback":
        if result != "ready":
            return [("Blocked", "", note)]
        # handed back with no long gate: the reason is shown
        waived = [("Long gate", f"waived: {e['no_gate']}", "")] if e.get("no_gate") else []
        return [*waived, ("Handed back", "", "")]
    merged = kind == "order" and e.get("order_kind") == "merged"
    if merged and not any(s["name"] == "Merged" for s in out):
        return [("Merged", "", c.get("pr") or "")]
    return []


def _steps(c: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What the CR went through, from its log, then what is still ahead of it."""
    out: list[dict[str, Any]] = []
    for e in events:
        for name, verdict, note in _step_entries(e, c, out):
            out.append(
                {"name": name, "done": True, "verdict": verdict, "note": note, "at": e.get("t", "")}
            )
    if c["status"] not in ENDED and c.get("kind") != "release":
        seen = {s["name"] for s in out}
        out += [
            {"name": name, "done": False, "verdict": "", "note": "", "at": ""}
            for name in AHEAD
            if name not in seen
        ]
    return out


def _link(path: Path, start: Path) -> str:
    return Path(os.path.relpath(path, start)).as_posix()


def _documents(repo: Repo, c: dict[str, Any], folder: Path) -> list[dict[str, Any]]:
    """The CR's documents that exist, then the project's that its specification cites."""
    spec = folder / c.get("specification", "03-change-spec.md")
    named = [
        ("request", folder / "intake" / "request.md"),
        ("intent", folder / "01-intent.md"),
        ("answers", folder / "02-answers.md"),
        ("specification", spec),
    ]
    work = folder / "work"
    named += [(p.stem, p) for p in sorted(work.glob("*.md"))]
    gates = sorted((work / "gates").glob("*.log"))
    named += [("long gate log", gates[-1])] if gates else []
    named.append(("evidence", folder / "evidence"))
    docs = [{"kind": kind, "path": _link(p, folder)} for kind, p in named if p.exists()]
    if spec.is_file():
        text = read_text(spec, "replace")
        for name in sorted(set(SPEC_LINK.findall(text))):
            target = repo.root / name
            # a URL's tail reads as a network path on Windows: this must never leave the disk
            if not name.startswith("/") and ".." not in name and target.is_file():
                docs.append({"kind": "project", "path": _link(target, folder), "name": name})
    return docs


def cr_view(
    repo: Repo, d: dict[str, Any], c: dict[str, Any], where: tuple[Path, list[dict[str, Any]], bool]
) -> dict[str, Any]:
    """The CR's page; `where`: its folder, its events, and whether the folder is in the batch."""
    folder, events, in_batch = where
    waiting = waits(d, c)
    now_line, next_line = _now_next(d, c, waiting)
    silent = age_minutes(c.get("updated")) if c["status"] in LIVE else None
    pr = c.get("pr")
    number = re.search(r"(\d+)/?$", pr or "")
    return {
        "schema": SCHEMA,
        "updated": now(),
        "cr": c["id"],
        "title": c["title"],
        "batch": d["id"],
        "in_batch": in_batch,
        "state": c["status"],
        "severity": severity(c),
        "step": step(c),
        "label": label(c, round_limit(d, c), waiting, can_start(d)),
        "waits": waiting,
        "round": c.get("round", 0),
        "max_rounds": round_limit(d, c),
        "now": now_line,
        "next": next_line,
        "pr": {"url": pr, "number": int(number[1]) if number else None} if pr else None,
        "steps": _steps(c, events),
        "documents": _documents(repo, c, folder),
        "branch": c.get("branch"),
        "worktree": c.get("worktree"),
        "agent": c.get("agent"),
        "notes": [n for n in c.get("notes", []) if not n.startswith(IN_PROGRESS)],
        "blocked": c.get("blocked_reason") if c["status"] == "blocked" else None,
        "cost_usd": c.get("cost_usd"),
        "cost_unpriced": c.get("cost_unpriced") or {},
        "final_cost": bool(d.get("closing")),
        "silent_minutes": round(silent) if silent is not None else None,
    }


def _priced(d: dict[str, Any]) -> bool:
    unknown = any(line.startswith("Spent: unknown") for line in d.get("summary", []))
    return d.get("spent_usd") is not None and not unknown


def _row(repo: Repo, d: dict[str, Any], c: dict[str, Any], start: Path) -> dict[str, Any]:
    folder = repo.planning_path(c["path"]) if c.get("path") else None
    silent = age_minutes(c.get("updated")) if c["status"] in LIVE else None
    waiting = waits(d, c)
    return {
        "cr": c["id"],
        "title": c["title"],
        "state": c["status"],
        "severity": severity(c),
        "step": step(c),
        "label": label(c, round_limit(d, c), waiting, can_start(d)),
        "waits": waiting,
        "round": c.get("round", 0),
        "branch": c.get("branch"),
        "pr": c.get("pr"),
        "cost_usd": c.get("cost_usd"),
        "cost_unpriced": c.get("cost_unpriced") or {},
        "blocked": c.get("blocked_reason") if c["status"] == "blocked" else None,
        "silent_minutes": round(silent) if silent is not None else None,
        # always relative to `.agents/changes/`, whatever `start` is: the board resolves it there
        "folder": _link(folder, repo.changes) if folder else None,
        "status": _link(folder / "STATUS.md", start) if folder else None,
        "specification": _link(folder / c.get("specification", "03-change-spec.md"), start)
        if folder
        else None,
    }


def batch_view(repo: Repo, d: dict[str, Any], folder: Path) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "updated": now(),
        "batch": d["id"],
        "folder": folder.name,
        "state": d["status"],
        "mode": d.get("mode"),
        "steering": d.get("steering"),
        "spent_usd": d.get("spent_usd"),
        "budget_usd": d.get("budget_usd"),
        "unpriced": d.get("unpriced") or {},  # model -> calls left out of spent_usd (a floor)
        "priced": _priced(d),
        "asks_unread": sum(1 for a in d.get("asks", []) if not a["read"]),
        "orders_pending": sum(1 for o in d.get("orders", []) if not o["done"]),
        "heartbeat": d.get("heartbeat"),
        "heartbeat_stopped": d.get("heartbeat_stopped"),  # the loop ended on purpose, when
        "paused": d.get("paused"),
        "summary": d.get("summary", []),
        "crs": [_row(repo, d, c, folder) for c in sorted(d["crs"], key=lambda x: x["order"])],
    }


def _title(folder: Path) -> str:
    for name in TITLE_FILES:
        path = folder / name
        if path.is_file():
            text = read_text(path, "replace")
            line = next((ln for ln in text.splitlines() if ln.strip()), "")
            if line:
                return line.lstrip("# ").strip()
    return folder.name


def spec_state(folder: Path) -> str | None:
    """The spec-writer's state, read from the folder: `specifying` while the Chief of Staff's
    `work/specifying` marker exists, `specified` once the specification exists without it."""
    if (folder / "work" / "specifying").exists():
        return "specifying"
    return "specified" if (folder / "03-change-spec.md").is_file() else None


def _backlog(paths: dict[str, Path], start: Path) -> list[dict[str, Any]]:
    found = [("3-ready", paths["ready"])]
    found += [("P" + p.name[1:], p) for p in sorted(paths["backlog"].glob("P[1-4]"))]
    found.append(("inbox", paths["inbox"]))
    rows = []
    for priority, stage in found:
        for item in sorted(stage.iterdir()) if stage.is_dir() else []:
            if item.is_dir():
                rows.append(
                    {
                        "priority": priority,
                        "item": item.name,
                        "title": _title(item),
                        "path": _link(item, start),
                        "spec": spec_state(item),
                        "files": sum(1 for p in item.rglob("*") if p.is_file()),
                    }
                )
    return rows


def when_of(name: str) -> str | None:
    """`261105-1059-...` read as a UTC timestamp, or None for a name without the prefix."""
    m = re.match(r"(\d\d)(\d\d)(\d\d)-(\d\d)(\d\d)", name)
    return f"20{m[1]}-{m[2]}-{m[3]}T{m[4]}:{m[5]}:00Z" if m else None


def _past(stage: Path, start: Path) -> tuple[list[dict[str, Any]], int]:
    """The last `PAST_LIMIT` CRs of an archive or trash stage, newest first, and the stage's count.

    At most `PAST_LIMIT` STATUS.json files are read; a folder without one gives its title only.
    """
    # `batches` (the batches' records) and a retro-only folder (`<YYMMDD-HHMM>-<batch id>`, from
    # before the records) hold no CR: not listed, not counted
    folders = (
        sorted(
            (
                p
                for p in stage.iterdir()
                if p.is_dir()
                and p.name != "batches"
                and not re.fullmatch(r"\d{6}-\d{4}-batch-\d+", p.name)
            ),
            reverse=True,
        )
        if stage.is_dir()
        else []
    )
    out = []
    for folder in folders[:PAST_LIMIT]:
        try:
            s = json.loads(read_text(folder / "STATUS.json"))
        except (OSError, ValueError):
            s = {}
        pr = s.get("pr")
        out.append(
            {
                "cr": s.get("cr"),
                "title": s.get("title") or _title(folder),
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
        d = read_batch_json(folder / "batch.json")
        for c in d["crs"]:
            where = repo.planning_path(c["path"]) if c.get("path") else None
            if where is None or where.parent != folder / "3-done":
                continue
            out.append(
                {
                    "cr": c["id"],
                    "title": c["title"],
                    "state": c["status"],
                    "batch": d["id"],
                    "pr": c.get("pr"),
                    "cost_usd": c.get("cost_usd"),
                    "when": c.get("merged_at"),
                    "path": _link(where, start),
                }
            )
    return sorted(out, key=lambda r: r["when"] or "", reverse=True)


def dashboard_view(repo: Repo, paths: dict[str, Path]) -> dict[str, Any]:
    start = repo.changes
    batches = []
    for folder in repo.batch_folders():
        d = read_batch_json(folder / "batch.json")
        v = batch_view(repo, d, folder)
        active = [c for c in sorted(d["crs"], key=lambda x: x["order"]) if c["status"] not in ENDED]
        batches.append(
            {
                "batch": v["batch"],
                "folder": folder.name,
                "state": v["state"],
                "spent_usd": v["spent_usd"],
                "budget_usd": v["budget_usd"],
                "unpriced": v["unpriced"],
                "asks_unread": v["asks_unread"],
                "heartbeat": v["heartbeat"],
                "heartbeat_stopped": v["heartbeat_stopped"],
                "orders_pending": v["orders_pending"],
                "slots": {"taken": len(held(SimpleNamespace(data=d))), "total": d["slots"]},
                "crs": [_row(repo, d, c, start) for c in active],
            }
        )
    merged, merged_total = _past(paths["archives"], start)
    done = _done_rows(repo, start)
    merged, merged_total = (done + merged)[:PAST_LIMIT], merged_total + len(done)
    trashed, trashed_total = _past(paths["trash"], start)
    return {
        "schema": SCHEMA,
        "updated": now(),
        "batches": batches,
        "active_crs": sum(len(b["crs"]) for b in batches),
        "backlog": _backlog(paths, start),
        "merged": merged,
        "merged_total": merged_total,
        "trashed": trashed,
        "trashed_total": trashed_total,
    }
