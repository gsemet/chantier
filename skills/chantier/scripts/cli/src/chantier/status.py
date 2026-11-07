"""What a person reads, and what a dashboard parses: `STATUS.md` and `STATUS.json`.

Three levels, linked both ways: `3-requests/` (the open batches and the backlog), the batch, the
CR. Everything comes from the state already written, never from the forge: this runs at each
change, so it must stay fast and cannot fail on the network. The JSON says what the Markdown says,
with more indicators; `schema` moves when a field changes meaning.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from types import SimpleNamespace

from .rails import held, over_budget, slot_free, waits_all
from .state import LIVE, Repo, _read_json, age_minutes, now, read_events, round_limit, write_file

SCHEMA = 2
PAST_LIMIT = 50  # landed and trashed CRs listed in the index; the totals count them all
ASKING = {"question", "approval", "merge", "fix", "infra", "budget", "refused", "rounds", "waits"}
ENDED = {"merged", "cancelled"}
AHEAD = ("Shipped", "Handed back")
IN_PROGRESS = ("draft:",)  # shown in `Documents`, not in `Decisions`
SPEC_LINK = re.compile(r"[\w./-]+\.md\b")
TITLE_FILES = ("03-change-spec.md", "01-intent.md", "intake/request.md")


def step(c: dict) -> str:
    status = c["status"]
    if status == "queued":
        return "Queued"
    if status == "ready":
        return "Notify"
    if status == "blocked":
        word = (c.get("blocked_reason") or "").split(":")[0].split(" ")[0].lower()
        return word.capitalize() if word in ASKING else "Blocked"
    if status in ENDED:
        return "Merged" if status != "cancelled" else "Dropped"
    if c.get("kind") == "release":
        return "Release"
    return "CI" if c.get("pr") else "Round"


def forge_word(links) -> str:
    """"MR" for a GitLab merge request link, "PR" for any other, "PR/MR" with no link yet."""
    links = [x for x in links if x]
    if not links:
        return "PR/MR"
    return "MR" if any("/merge_requests/" in x for x in links) else "PR"


def severity(c: dict) -> str:
    if c["status"] == "blocked":
        return "red"
    if c["status"] in {"ready", "merged"}:
        return "green"
    return "grey" if c["status"] == "cancelled" else "yellow"


def _round(c: dict) -> int:
    """The round under way, or the last one done: `chantier round` counts it."""
    return max(c.get("round", 0), 1)


def waits(d: dict, c: dict) -> list[str]:
    """What a queued CR waits for: the rule of `take`, read from the batch's record."""
    return waits_all(d["crs"], c) if c["status"] == "queued" else []


def _waits_on(c: dict) -> bool:
    """A blocked CR that waits for a thing already on its way: nobody has to decide."""
    return c["status"] == "blocked" and (c.get("blocked_reason") or "").lower().startswith("waits:")


def can_start(d: dict) -> bool:
    """A queued CR could start now: `take` refuses on no free slot and on a spent budget."""
    b = SimpleNamespace(data=d)
    return slot_free(b) and not over_budget(b)


def icon(c: dict, waiting: list[str], free: bool) -> str:
    """The icon of a state, the one the report copies; `severity` is another reading."""
    status = c["status"]
    if status == "queued":
        return "🟠" if waiting or not free else "⚪"
    if status == "blocked":
        return "🟠" if _waits_on(c) else "🔴"
    return {"working": "🟡", "ready": "🔵", "merged": "✅", "cancelled": "⚪"}[status]


def label(c: dict, max_rounds: int, waiting: list[str] | None = None, free: bool = True) -> str:
    """`🔴 blocked CI 1/3`: how a CR's state reads in every table."""
    state = "dropped" if c["status"] == "cancelled" else c["status"]
    mark = icon(c, waiting or [], free)
    if waiting:
        return f"{mark} {state}, waits for {', '.join(waiting)}"
    if c["status"] in ENDED | {"queued"}:
        return f"{mark} {state}"
    return f"{mark} {state} {step(c)} {_round(c)}/{max_rounds}"


def _no_start(d: dict) -> str:
    """Why a queued CR with nothing to wait for does not start: the budget, else the slots."""
    spent = over_budget(SimpleNamespace(data=d))
    return "Waiting for the budget." if spent else "Waiting for a free slot."


def _now_next(d: dict, c: dict, waiting: list[str]) -> tuple[str, str]:
    pr = c.get("pr") or f"its {forge_word([])}"
    if _waits_on(c):
        what = c["blocked_reason"].split(":", 1)[1].strip() or "something on its way"
        return (c["blocked_reason"],
                f"Waits for {what}; the Foreman takes it back when that lands.")
    if c["status"] == "blocked":
        return (c.get("blocked_reason") or "Blocked.",
                "The user's answer, through the Chief of Staff.")
    return {
        "Queued": (f"Waits for {', '.join(waiting)}." if waiting else _no_start(d),
                   "A Driver starts it."),
        "Round": ("A coder and its reviews are working.", "The long gate, then the ship."),
        "CI": (f"{pr} is open: CI, then the verifier at the pushed head.", "The hand-back."),
        "Release": ("The Release driver follows the project's procedure.", "The next step of it."),
        "Notify": (f"Ready: {pr} waits for the user's merge.", "The merge, then the archive."),
        "Merged": (f"Merged: {pr}.", "Nothing."),
        "Dropped": ("Dropped on the user's word.", "Nothing."),
    }[step(c)]


def _steps(c: dict, events: list[dict]) -> list[dict]:
    """What the CR went through, from its log, then what is still ahead of it."""
    out = []

    def add(name: str, at: str, verdict: str = "", note: str = "") -> None:
        out.append({"name": name, "done": True, "verdict": verdict, "note": note, "at": at})

    for e in events:
        kind, at, note = e.get("kind"), e.get("t", ""), e.get("note") or ""
        if kind == "round":
            add(f"Round {e.get('round')}", at, note=note)
        elif kind == "note":
            add("Note", at, note=note)
        elif kind == "gate":
            add("Long gate", at, e.get("result", ""), e.get("head", ""))
        elif kind == "ship":
            add("Shipped", at, note=e.get("pr", ""))
        elif kind == "handback" and e.get("result") == "ready":
            add("Handed back", at)
        elif kind == "handback":
            add("Blocked", at, note=note)
        elif kind == "order" and e.get("order_kind") == "merged":
            if not any(s["name"] == "Merged" for s in out):
                add("Merged", at, note=c.get("pr") or "")
    if c["status"] not in ENDED and c.get("kind") != "release":
        seen = {s["name"] for s in out}
        out += [{"name": name, "done": False, "verdict": "", "note": "", "at": ""}
                for name in AHEAD if name not in seen]
    return out


def _link(path: Path, start: Path) -> str:
    return Path(os.path.relpath(path, start)).as_posix()


def _documents(repo: Repo, c: dict, folder: Path) -> list[dict]:
    """The CR's documents that exist, then the project's that its specification cites."""
    named = [("request", folder / "intake" / "request.md"), ("intent", folder / "01-intent.md"),
             ("answers", folder / "02-answers.md"),
             ("specification", folder / c.get("specification", "03-change-spec.md"))]
    work = folder / "work"
    if work.is_dir():
        named += [(p.stem, p) for p in sorted(work.glob("*.md"))]
        gates = sorted((work / "gates").glob("*.log"))
        if gates:
            named.append(("long gate log", gates[-1]))
    if (folder / "evidence").is_dir():
        named.append(("evidence", folder / "evidence"))
    docs = [{"kind": kind, "path": _link(p, folder)} for kind, p in named if p.exists()]
    spec = folder / c.get("specification", "03-change-spec.md")
    if spec.is_file():
        text = spec.read_text(encoding="utf-8", errors="replace")
        for name in sorted(set(SPEC_LINK.findall(text))):
            target = repo.root / name
            # a URL's tail reads as a network path on Windows: this must never leave the disk
            if not name.startswith("/") and ".." not in name and target.is_file():
                docs.append({"kind": "project", "path": _link(target, folder), "name": name})
    return docs


def cr_view(repo: Repo, d: dict, c: dict, folder: Path, events: list[dict],
            in_batch: bool) -> dict:
    waiting = waits(d, c)
    now_line, next_line = _now_next(d, c, waiting)
    silent = age_minutes(c.get("updated")) if c["status"] in LIVE else None
    pr = c.get("pr")
    number = re.search(r"(\d+)/?$", pr) if pr else None
    return {"schema": SCHEMA, "updated": now(), "cr": c["id"], "title": c["title"],
            "batch": d["folder"], "in_batch": in_batch, "state": c["status"],
            "severity": severity(c), "step": step(c), "label": label(c, round_limit(d, c), waiting, can_start(d)),
            "waits": waiting, "round": c.get("round", 0), "max_rounds": round_limit(d, c),
            "now": now_line, "next": next_line,
            "pr": {"url": pr, "number": int(number[1]) if number else None} if pr else None,
            "steps": _steps(c, events), "documents": _documents(repo, c, folder),
            "branch": c.get("branch"), "worktree": c.get("worktree"), "agent": c.get("agent"),
            "notes": [n for n in c.get("notes", []) if not n.startswith(IN_PROGRESS)],
            "blocked": c.get("blocked_reason") if c["status"] == "blocked" else None,
            "cost_usd": c.get("cost_usd"), "final_cost": bool(d.get("closing")),
            "silent_minutes": round(silent) if silent is not None else None}


def _step_line(s: dict) -> str:
    text = s["name"] + (f" {s['verdict']}" if s["verdict"] else "")
    return f"- [{'x' if s['done'] else ' '}] {text}{': ' + s['note'] if s['note'] else ''}"


def cr_markdown(v: dict) -> str:
    batch = f"[{v['batch']}](../STATUS.md)" if v["in_batch"] else f"{v['batch']}"
    pr = v["pr"]
    head = f"{v['label']} · {batch}" + (f" · [{forge_word([pr['url']])}]({pr['url']})" if pr else "")
    docs = [f"- [{d.get('name') or d['kind']}]({d['path']})" for d in v["documents"]]
    lines = [f"# {v['cr']} {v['title']}", "", head, "", f"**Now:** {v['now']}",
             f"**Next:** {v['next']}", "", "## Progress", "",
             *(_step_line(s) for s in v["steps"]), "", "## Documents", "", *(docs or ["- none"]),
             "", "## Where", "", f"- Branch: `{v['branch'] or '-'}`",
             f"- Worktree: `{v['worktree'] or '-'}`", f"- Driver: `{v['agent'] or '-'}`", "",
             "## Decisions and open questions", "",
             *(f"- {n}" for n in v["notes"][-10:]),
             *([f"- Open: {v['blocked']}"] if v["blocked"] else []),
             *(["- None."] if not v["notes"] and not v["blocked"] else []), "", "## Cost", ""]
    usd = v["cost_usd"]
    lines.append("No figure yet." if usd is None else
                 f"${usd:.2f}{'' if v['final_cost'] else ' so far (at the last heartbeat)'}.")
    return "\n".join(lines) + "\n"


def _priced(d: dict) -> bool:
    return not any(line.startswith("Spent: unknown") for line in d.get("summary", []))


def _row(repo: Repo, d: dict, c: dict, start: Path) -> dict:
    folder = repo.root / c["path"] if c.get("path") else None
    silent = age_minutes(c.get("updated")) if c["status"] in LIVE else None
    waiting = waits(d, c)
    return {"cr": c["id"], "title": c["title"], "state": c["status"], "severity": severity(c),
            "step": step(c), "label": label(c, round_limit(d, c), waiting, can_start(d)), "waits": waiting,
            "round": c.get("round", 0), "branch": c.get("branch"), "pr": c.get("pr"), "cost_usd": c.get("cost_usd"),
            "blocked": c.get("blocked_reason") if c["status"] == "blocked" else None,
            "silent_minutes": round(silent) if silent is not None else None,
            # always relative to `3-requests/`, whatever `start` is: the board resolves it there
            "folder": _link(folder, repo.batches) if folder else None,
            "status": _link(folder / "STATUS.md", start) if folder else None,
            "specification": _link(folder / c.get("specification", "03-change-spec.md"), start)
            if folder else None}


def _rows_markdown(rows: list[dict]) -> list[str]:
    def number(r: dict) -> str:
        return r["cr"].removeprefix("CR-")

    word = forge_word(r["pr"] for r in rows)
    return [f"| CR | Subject | Status | Branch | {word} | Cost |", "| --- | --- | --- | --- | --- | ---: |",
            *(f"| [{number(r)}]({r['specification']}) | {r['title']} | "
              f"[{r['label']}]({r['status']}) | `{r['branch'] or '-'}` | "
              f"{'[' + word + '](' + r['pr'] + ')' if r['pr'] else '-'} | "
              f"{'-' if r['cost_usd'] is None else '$%.2f' % r['cost_usd']} |" for r in rows)]


def batch_view(repo: Repo, d: dict, folder: Path) -> dict:
    return {"schema": SCHEMA, "updated": now(), "batch": d["id"], "folder": folder.name,
            "state": d["status"], "mode": d.get("mode"), "steering": d.get("steering", "foreman"),
            "spent_usd": d.get("spent_usd", 0), "budget_usd": d.get("budget_usd"),
            "priced": _priced(d), "asks_unread": sum(1 for a in d.get("asks", []) if not a["read"]),
            "orders_pending": sum(1 for o in d.get("orders", []) if not o["done"]),
            "heartbeat": d.get("heartbeat"), "landed": d.get("landed"),
            "summary": d.get("summary", []),
            "crs": [_row(repo, d, c, folder)
                    for c in sorted(d["crs"], key=lambda x: x["order"])]}


def _budget(v: dict) -> str:
    spent, budget = v["spent_usd"], v["budget_usd"]
    return f"${spent:.2f}" + (f" of ${budget:g}" if budget else "")


def batch_markdown(v: dict) -> str:
    lines = [f"# {v['folder']}: {v['state']}", "",
             f"Updated {v['updated']} · steering {v.get('steering', 'foreman')} · spent {_budget(v) if v['priced'] else 'unknown'}"
             f"{' (not final)' if v['landed'] and v['priced'] else ''} · "
             f"{v['asks_unread']} asks unread · "
             f"{v['orders_pending']} orders pending", "",
             "[All change requests](../STATUS.md)", "", *_rows_markdown(v["crs"])]
    if v["landed"]:
        lines += ["", "## Landed", "", f"- Landed: {v['landed']}"]
    if v["summary"]:
        lines += ["", "## Cost", "", *(f"- {ln}" for ln in v["summary"])]
    return "\n".join(lines) + "\n"


def _title(folder: Path) -> str:
    for name in TITLE_FILES:
        path = folder / name
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
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


def _backlog(paths: dict[str, Path], start: Path) -> list[dict]:
    found = [("P" + p.name[1:], p) for p in sorted(paths["backlog"].glob("P[1-4]"))]
    found.append(("inbox", paths["inbox"]))
    rows = []
    for priority, stage in found:
        for item in sorted(stage.iterdir()) if stage.is_dir() else []:
            if item.is_dir():
                rows.append({"priority": priority, "item": item.name, "title": _title(item),
                             "path": _link(item, start), "spec": spec_state(item),
                             "files": sum(1 for p in item.rglob("*") if p.is_file())})
    return rows


def _when(name: str) -> str | None:
    """`261105-1059-...` read as a UTC timestamp, or None for a name without the prefix."""
    m = re.match(r"(\d\d)(\d\d)(\d\d)-(\d\d)(\d\d)", name)
    return f"20{m[1]}-{m[2]}-{m[3]}T{m[4]}:{m[5]}:00Z" if m else None


def _past(stage: Path, start: Path) -> tuple[list[dict], int]:
    """The last `PAST_LIMIT` CRs of an archive or trash stage, newest first, and the stage's count.

    At most `PAST_LIMIT` STATUS.json files are read; a folder without one gives its title only.
    """
    folders = sorted((p for p in stage.iterdir() if p.is_dir()), reverse=True) \
        if stage.is_dir() else []
    out = []
    for folder in folders[:PAST_LIMIT]:
        try:
            s = json.loads((folder / "STATUS.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            s = {}
        pr = s.get("pr")
        out.append({"cr": s.get("cr"), "title": s.get("title") or _title(folder),
                    "state": s.get("state"), "batch": s.get("batch"),
                    "pr": pr.get("url") if isinstance(pr, dict) else pr,
                    "cost_usd": s.get("cost_usd"), "when": _when(folder.name),
                    "path": _link(folder, start)})
    return out, len(folders)


def dashboard_view(repo: Repo, paths: dict[str, Path]) -> dict:
    start = repo.batches
    batches = []
    for folder in repo.batch_folders():
        d = _read_json(folder / "batch.json")
        v = batch_view(repo, d, folder)
        active = [c for c in sorted(d["crs"], key=lambda x: x["order"]) if c["status"] not in ENDED]
        batches.append({"batch": v["batch"], "folder": folder.name, "state": v["state"],
                        "spent_usd": v["spent_usd"], "budget_usd": v["budget_usd"],
                        "asks_unread": v["asks_unread"], "heartbeat": v["heartbeat"],
                        "orders_pending": v["orders_pending"],
                        "slots": {"taken": len(held(SimpleNamespace(data=d))), "total": d["slots"]},
                        "crs": [_row(repo, d, c, start) for c in active]})
    landed, landed_total = _past(paths["archives"], start)
    trashed, trashed_total = _past(paths["trash"], start)
    return {"schema": SCHEMA, "updated": now(), "batches": batches,
            "active_crs": sum(len(b["crs"]) for b in batches),
            "backlog": _backlog(paths, start),
            "landed": landed, "landed_total": landed_total,
            "trashed": trashed, "trashed_total": trashed_total}


def dashboard_markdown(v: dict) -> str:
    lines = ["# Change requests", "",
             f"> Updated {v['updated']}: {v['active_crs']} active CRs in {len(v['batches'])} "
             "batches.", "", "## Active"]
    for b in v["batches"]:
        lines += ["", f"### [{b['folder']}]({b['folder']}/STATUS.md): {b['state']}, "
                  f"{_budget(b)}", ""]
        lines += _rows_markdown(b["crs"]) if b["crs"] else ["No active CR."]
    if not v["batches"]:
        lines += ["", "No open batch."]
    lines += ["", "## Backlog", "", "| Priority | Item | Title | Spec | Files |",
              "| --- | --- | --- | --- | ---: |",
              *(f"| {r['priority']} | [{r['item']}]({r['path']}) | {r['title']} | "
                f"{r.get('spec') or '-'} | {r['files']} |"
                for r in v["backlog"])]
    return "\n".join(lines) + "\n"


def _write(folder: Path, markdown: str, view: dict) -> None:
    write_file(folder / "STATUS.md", markdown)
    write_file(folder / "STATUS.json", json.dumps(view, indent=2, ensure_ascii=False) + "\n")


def write_batch(repo: Repo, d: dict, folder: Path) -> None:
    """Rewrite the batch's file and each of its CRs', wherever they are."""
    d = {**d, "folder": folder.name}
    events: dict[str, list[dict]] = {}
    for e in read_events(folder):
        if e.get("cr"):
            events.setdefault(e["cr"], []).append(e)
    for c in d["crs"]:
        cr_folder = repo.root / c["path"] if c.get("path") else None
        if cr_folder and cr_folder.is_dir():
            v = cr_view(repo, d, c, cr_folder, events.get(c["id"], []),
                        cr_folder.parent == folder)
            _write(cr_folder, cr_markdown(v), v)
    v = batch_view(repo, d, folder)
    _write(folder, batch_markdown(v), v)


def write_final_pages(repo: Repo, d: dict, folder: Path) -> None:
    """At `close` only, once the cost is priced: the CR pages that outlive the batch's folder
    (the archived ones) say their cost is final. Nothing before `close` may say so."""
    d = {**d, "folder": folder.name, "closing": True}
    events: dict[str, list[dict]] = {}
    for e in read_events(folder):
        if e.get("cr"):
            events.setdefault(e["cr"], []).append(e)
    for c in d["crs"]:
        cr_folder = repo.root / c["path"] if c.get("path") else None
        if cr_folder and cr_folder.is_dir() and cr_folder.parent != folder:
            v = cr_view(repo, d, c, cr_folder, events.get(c["id"], []), False)
            _write(cr_folder, cr_markdown(v), v)


def write_dashboard(repo: Repo, paths: dict[str, Path]) -> None:
    v = dashboard_view(repo, paths)
    repo.batches.mkdir(parents=True, exist_ok=True)
    _write(repo.batches, dashboard_markdown(v), v)
