"""The Markdown of the STATUS files."""

from __future__ import annotations

from typing import Any

from chantier.rails import not_priced as _not_priced
from chantier.rails import usd_text as _usd
from chantier.status.words import forge_word


def _step_line(s: dict[str, Any]) -> str:
    text = s["name"] + (f" {s['verdict']}" if s["verdict"] else "")
    return f"- [{'x' if s['done'] else ' '}] {text}{': ' + s['note'] if s['note'] else ''}"


def cr_markdown(v: dict[str, Any]) -> str:
    batch = f"[{v['batch']}](../../STATUS.md)" if v["in_batch"] else f"{v['batch']}"
    pr = v["pr"]
    head = f"{v['label']} · {batch}" + (
        f" · [{forge_word([pr['url']])}]({pr['url']})" if pr else ""
    )
    docs = [f"- [{d.get('name') or d['kind']}]({d['path']})" for d in v["documents"]]
    lines = [
        f"# {v['cr']} {v['title']}",
        "",
        head,
        "",
        f"**Now:** {v['now']}",
        f"**Next:** {v['next']}",
        *([f"**Step:** {v['phase']}"] if v.get("phase") else []),
        "",
        "## Progress",
        "",
        *(_step_line(s) for s in v["steps"]),
        "",
        "## Documents",
        "",
        *(docs or ["- none"]),
        "",
        "## Where",
        "",
        f"- Branch: `{v['branch'] or '-'}`",
        f"- Worktree: `{v['worktree'] or '-'}`",
        f"- Driver: `{v['agent'] or '-'}`",
        "",
        "## Decisions and open questions",
        "",
        *(f"- {n}" for n in v["notes"][-10:]),
        *([f"- Open: {v['blocked']}"] if v["blocked"] else []),
        *(["- None."] if not v["notes"] and not v["blocked"] else []),
        "",
        "## Cost",
        "",
    ]
    usd = v["cost_usd"]
    floor = "at least " if v["cost_unpriced"] else ""
    lines.append(
        "No figure yet."
        if usd is None
        else f"{floor}${usd:.2f}{'' if v['final_cost'] else ' so far (at the last heartbeat)'}."
        + (f" {_not_priced(v['cost_unpriced'])}." if floor else "")
    )
    return "\n".join(lines) + "\n"


def _rows_markdown(rows: list[dict[str, Any]]) -> list[str]:
    def number(r: dict[str, Any]) -> str:
        return str(r["cr"].removeprefix("CR-"))

    word = forge_word([r["pr"] for r in rows])
    return [
        f"| CR | Subject | Status | Step | Branch | {word} | Long gate | Cost |",
        "| --- | --- | --- | --- | --- | --- | --- | ---: |",
        *(
            f"| [{number(r)}]({r['specification']}) | {r['title']} | "
            f"[{r['label']}]({r['status']}) | {r.get('phase') or '-'} | `{r['branch'] or '-'}` | "
            f"{'[' + word + '](' + r['pr'] + ')' if r['pr'] else '-'} | "
            f"{r['gate']['text'].replace('|', '/')} | "
            f"{'-' if r['cost_usd'] is None else _usd(r['cost_usd'], r['cost_unpriced'])} |"
            for r in rows
        ),
    ]


def _budget(v: dict[str, Any], dated: bool = False) -> str:
    spent, budget = v["spent_usd"], v["budget_usd"]
    at = v.get("spent_at") if dated else None
    return (
        "unknown"
        if spent is None
        else _usd(spent, v.get("unpriced")) + (f" as of {at}" if at else "")
    ) + (f" of ${budget:g}" if budget else "")


def _no_cr(v: dict[str, Any]) -> bool:
    """A batch that never held a CR and has no spend yet."""
    return v.get("crs_total") == 0 and v["spent_usd"] is None


def batch_markdown(v: dict[str, Any]) -> str:
    who = {
        "direct": "steered by the Chief of Staff (direct mode)",
        "foreman": "steered by a Foreman",
    }.get(v.get("steering") or "", "steering unknown")
    shape = {
        "stack": "a stack of PRs",
        "series": "a series of PRs, one after the other",
        "parallel": "independent PRs (parallel)",
    }.get(v.get("mode") or "", "shape unknown")
    lines = [
        f"# {v['batch']}: {v['state']}",
        "",
        f"Updated {v['updated']} · {who} · {shape}{' · factory: on' if v.get('factory') else ''} · "
        f"spent {_budget(v, True) if v['priced'] else ('none yet' if _no_cr(v) else 'unknown')}"
        f"{' (to date)' if v['paused'] and v['priced'] else ''} · "
        f"{v['asks_unread']} asks unread · "
        f"{v['orders_pending']} orders pending",
        "",
        "[All change requests](../STATUS.md)",
        "",
        *_rows_markdown(v["crs"]),
    ]
    if v["paused"]:
        lines += ["", "## Paused", "", f"- Paused: {v['paused']}"]
        if v.get("crs_total") == 0:
            lines.append("- No CR yet.")
    if v["summary"]:
        lines += ["", "## Cost", "", *(f"- {ln}" for ln in v["summary"])]
    return "\n".join(lines) + "\n"


def dashboard_markdown(v: dict[str, Any]) -> str:
    lines = [
        "# Change requests",
        "",
        f"> Updated {v['updated']}: {v['active_crs']} active CRs in {len(v['batches'])} batches.",
        "",
        "## Active",
    ]
    for b in v["batches"]:
        lines += ["", f"### [{b['batch']}](4-batch/STATUS.md): {b['state']}, {_budget(b)}", ""]
        lines += _rows_markdown(b["crs"]) if b["crs"] else ["No active CR."]
    if not v["batches"]:
        lines += ["", "No batch."]
    lines += [
        "",
        "## Backlog",
        "",
        "| Priority | Item | Title | Spec | Files |",
        "| --- | --- | --- | --- | ---: |",
        *(
            f"| {r['priority']} | [{r['item']}]({r['path']}) | {r['title']} | "
            f"{r.get('spec') or '-'} | {r['files']} |"
            for r in v["backlog"]
        ),
    ]
    return "\n".join(lines) + "\n"
