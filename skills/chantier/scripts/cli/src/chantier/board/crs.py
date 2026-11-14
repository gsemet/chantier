"""The batch's CRs as the board draws them: every CR, with the meanings chantier gives
"ready", "to review", the stack and a PR's base, derived here so no view computes them."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from chantier.board.backlog import count_files, description, subject
from chantier.commands.facts import chain, stack_base
from chantier.core.records import BatchRecord, CrEntry, EventRecord, round_limit
from chantier.core.repo import Repo
from chantier.rails import ENDED, series_predecessor
from chantier.status.words import can_start, label, severity, waits


def link_of(url: str | None) -> str | None:
    """A link only for an http(s) URL; anything else is not one."""
    return url if url and re.match(r"https?://", url) else None


def handed_back_at(events: list[EventRecord], cr: str) -> str | None:
    """The `t` of the CR's last `handback` with `result: ready`."""
    found = [e.t for e in events if e.kind == "handback" and e.cr == cr and e.result == "ready"]
    return found[-1] if found else None


def _open_after(d: BatchRecord, c: CrEntry) -> list[CrEntry]:
    found = {x.id: x for x in d.crs}
    return [found[i] for i in c.after if i in found and found[i].status not in ENDED]


def _on(d: BatchRecord, repo: Repo, branch: str) -> str:
    """The CR whose branch this is, else the branch (the default one)."""
    by_branch = {x.branch: x.id for x in d.crs if x.branch}
    return by_branch.get(branch, branch)


def base_of(d: BatchRecord, c: CrEntry, repo: Repo) -> dict[str, str]:
    """The base of the CR's PR: its place in the stack once stacked (else where `stack` will put
    it), the previous CR of a series, else its last open dependency, else the default branch."""
    default: str = repo.config["default_branch"] or "main"
    if c.kind != "fix" and d.mode == "stack" and c.id in [x.id for x in chain(d)]:
        branch = stack_base(d, c, repo, planned=not _open_after(d, c))
        why = "stack" if c.stacked else "dependency" if _open_after(d, c) else "planned"
        return {"on": _on(d, repo, branch), "why": why}
    if d.mode == "series":
        pred = series_predecessor(d.crs, c)
        if pred and pred.status != "merged":
            return {"on": pred.id, "why": "series"}
    elif c.kind != "fix" and (open_ := _open_after(d, c)):
        return {"on": open_[-1].id, "why": "dependency"}
    return {"on": default, "why": "default"}


def _folder_of(repo: Repo, c: CrEntry) -> Path | None:
    try:
        folder = repo.planning_path(c.path) if c.path else None
    except OSError:
        return None
    return folder if folder and folder.is_dir() else None


def _row(repo: Repo, d: BatchRecord, c: CrEntry, events: list[EventRecord]) -> dict[str, Any]:
    folder = _folder_of(repo, c)
    waiting = waits(d, c)
    place = [x.id for x in chain(d)]
    base = base_of(d, c, repo)
    default: str = repo.config["default_branch"] or "main"
    return {
        "cr": c.id,
        "title": subject(c.title),
        "folder": repo.rel(folder) if folder else None,
        "state": c.status,
        "label": label(c, round_limit(d, c), waiting, can_start(d)),
        "severity": severity(c),
        "round": c.round,
        "round_limit": round_limit(d, c),
        "cost_usd": c.cost_usd,
        "cost_unpriced": c.cost_unpriced,
        "pr": link_of(c.pr),
        "blocked": c.blocked_reason if c.status == "blocked" else None,
        "waits": waiting,
        "kind": c.kind if c.kind in {"fix", "release"} else None,
        "order": c.order,
        "stacked": c.stacked,
        "after": list(c.after),
        "merged_at": c.merged_at,
        "handed_back_at": handed_back_at(events, c.id),
        "files": count_files(folder) if folder else 0,
        "description": description(folder) if folder else "",
        "chain_place": place.index(c.id) + 1 if c.id in place else None,
        "base": base,
        "to_review": c.status == "ready" and base["on"] == default,
    }


def merge_order(d: BatchRecord, rows: list[dict[str, Any]]) -> list[str]:
    """The CRs to review, in the order their PRs are merged: a stack from its top, a series in
    its order, parallel ones by hand-back."""
    review = {r["cr"]: r for r in rows if r["to_review"]}
    if d.mode == "stack":
        return [x.id for x in reversed(chain(d)) if x.id in review]
    if d.mode == "series":
        return sorted(review, key=lambda i: review[i]["order"])
    return sorted(review, key=lambda i: review[i]["handed_back_at"] or "")


def cr_rows(repo: Repo, d: BatchRecord, events: list[EventRecord]) -> list[dict[str, Any]]:
    """Every CR of the batch, merged and cancelled included, in order."""
    return [_row(repo, d, c, events) for c in sorted(d.crs, key=lambda x: x.order)]
