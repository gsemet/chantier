"""What "All projects" shows beyond the project lines: each project's open PRs and the newest events
of every project. It reads the record and the forge hub's journal only; it never reads the forge,
and what it returns carries no cost and no round (the public read-only key reads the `board`
topic)."""

from __future__ import annotations

from typing import Any

from chantier.board import history_page, reads
from chantier.board.context import Context
from chantier.board.projects import Project

FEED_ROWS = 20
CLOSED = ("merged", "cancelled")


def _red(ctx: Context, project: Project, batch: str, rows: list[dict[str, Any]]) -> set[str]:
    """The CRs ready to merge that the hub journaled `checks-red@1` for, after their last
    hand-back (a stamp is `YYYY-MM-DDTHH:MM:SSZ`, so strings compare as times)."""
    since = {r["cr"]: r.get("handed_back_at") or "" for r in rows if r["to_review"]}
    seen = reads.journal_entries(ctx, project.repo.store, project.repo.changes)
    return {
        str(e.get("cr"))
        for e in seen
        if e.get("type") == "checks-red@1"
        and e.get("batch") == batch
        and str(e.get("cr")) in since
        and str(e.get("t") or "") > since[str(e.get("cr"))]
    }


def open_prs(ctx: Context, project: Project, state: dict[str, Any]) -> list[dict[str, Any]]:
    """The batch's open PRs, as the record holds them (a PR recorded, not merged, on a CR that is
    not merged or cancelled): the CRs ready to merge first, in the merge order, then the others.
    `state` is `ready` (ready to merge), `red` (ready to merge and a red CI journaled) or
    `working`."""
    batch = state["batch"]
    if not batch:
        return []
    rows = [
        r for r in batch["crs"] if r["pr"] and not r.get("pr_merged") and r["state"] not in CLOSED
    ]
    review = [r for r in rows if r["to_review"]]
    red = _red(ctx, project, batch["id"], batch["crs"]) if review else set()
    order = {cr: n for n, cr in enumerate(batch["merge_order"])}
    review.sort(key=lambda r: order.get(r["cr"], len(order)))
    out = [
        {
            "cr": r["cr"],
            "title": r["title"],
            "pr": r["pr"],
            "state": "red" if r["cr"] in red else "ready",
        }
        for r in review
    ]
    out += [
        {"cr": r["cr"], "title": r["title"], "pr": r["pr"], "state": "working"}
        for r in rows
        if not r["to_review"]
    ]
    return out


def board_data(ctx: Context) -> dict[str, Any]:
    """The board's data, with each project line's `open_prs` and the `activity` of every project."""
    data = reads.board_data(ctx)
    projects = ctx.projects.all()
    by_id = {p.id: p for p in projects}
    for line in data["projects"]:
        p = by_id[line["id"]]
        line["open_prs"] = open_prs(ctx, p, reads.state_of(ctx, p, ask=False)[0])
    data["activity"] = history_page.feed(ctx, projects, FEED_ROWS)
    return data
