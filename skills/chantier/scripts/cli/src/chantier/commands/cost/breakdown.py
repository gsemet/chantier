"""The breakdown of the cost by role or by CR."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from chantier.commands.cost.pricing import add_unpriced, hints, sum_unpriced, unpriced_of
from chantier.core.batch import read_batch
from chantier.core.records import BatchRecord, read_events
from chantier.core.repo import Repo
from chantier.rails import not_priced, usd_text

MAX_HOPS = 5  # parent links followed from a worker to its Driver
CR_IN_NAME = re.compile(r"\bCR-\d+\b")


def _driver_root(r: dict[str, Any], by_agent: dict[str, dict[str, Any]]) -> dict[str, Any]:
    root = r
    for _ in range(5):
        parent = by_agent.get(root.get("parent") or "")
        if root["agent"] == "main" or parent is None or parent["agent"] == "main":
            break
        root = parent
    return root


def _cr_agents(repo: Repo, batch: str) -> dict[str, str]:
    """Every Driver a CR ever had, from the log: a replaced one keeps its CR."""
    qa_folder = {
        o.id: o.cr for o in read_batch(repo, batch).orders if o.kind == "qa"
    }  # a QA driver counts under its QA folder
    found: dict[str, str] = {}
    for e in read_events(repo.batch_dir(batch)):
        if e.kind == "agent" and e.cr and e.cr != "stack" and e.agent:
            found[e.agent] = qa_folder.get(e.cr, e.cr)
    return found


def cost_groups(
    repo: Repo, batch: str, rows: list[dict[str, Any]], by: str
) -> dict[str, list[Any]]:
    """Calls and dollars, by CR (`cr`) or by the Driver type a chain of parents leads back to."""
    agent_cr = _cr_agents(repo, batch)
    parents = {r["agent"]: r.get("parent") for r in rows}
    by_agent = {r["agent"]: r for r in rows if r["agent"] != "main"}

    def cr_of(agent: str | None, hops: int = 0) -> str | None:
        """A worker counts for the CR of the Driver that started it."""
        if agent is None or hops > MAX_HOPS:
            return None
        return agent_cr.get(agent) or cr_of(parents.get(agent), hops + 1)

    # calls, dollars, not priced, the Drivers' peak context, the Drivers' compactions
    groups: dict[str, list[Any]] = defaultdict(lambda: [0, 0.0, {}, 0, 0])
    for r in rows:
        if by == "cr":
            named = CR_IN_NAME.search(r.get("description") or "")
            key = (
                "foreman"
                if r["agent"] == "main" or r.get("own")
                else cr_of(r["agent"]) or (named.group(0) if named else "other")
            )
        else:  # "driver": the type of the agent a chain of parents leads back to
            root = _driver_root(r, by_agent)
            # the steering session's main row, a Foreman's or a Chief of Staff's, is never a Driver
            key = "foreman" if root.get("own") or root["agent"] == "main" else root["type"]
        groups[key][0] += r["calls"]
        groups[key][1] += r["usd"]
        add_unpriced(groups[key][2], unpriced_of(r))
        if by == "cr" and cost_kind(r) == "Driver":
            groups[key][3] = max(groups[key][3], r.get("peak_context", 0))
            groups[key][4] += r.get("compactions", 0)
    return groups


def apportion(parts: list[float], whole: int) -> list[int]:
    """Whole units for each part, summing to `whole` exactly (largest remainder)."""
    sizes = sum(parts)
    exact = [whole * p / sizes if sizes else 0.0 for p in parts]
    out = [int(x) for x in exact]
    order = sorted(range(len(parts)), key=lambda i: out[i] - exact[i])
    for i in order[: whole - sum(out)] if sizes else []:
        out[i] += 1
    return out


COMPACTION_USD = 0.12  # what a compaction call costs, about: it leaves no record to price


def cost_kind(r: dict[str, Any]) -> str:
    """Who an agent is, from the record alone: the Foreman is the main agent, a Driver an agent
    with no parent, a worker one with a parent. No role name: the type is the host's own string.
    Where the host gives no parent link (Copilot), the agent is only an agent."""
    if r["agent"] == "main" or r.get("own"):
        return "Foreman"  # the steering session, and its own subagents; `_label` says whose
    if "parent" not in r:
        return "Agent"
    return "Worker" if r["parent"] else "Driver"


STEERING = "Chief of Staff, steering the batch"


UNSPLIT = "Chief of Staff, steering the batch, grill included (not split on this host)"


def cost_label(r: dict[str, Any]) -> str:
    """The steering row of a direct batch is the Chief of Staff's, a Foreman's is the Foreman's;
    their own subagents have a line of their own."""
    if r.get("own"):
        return str(r["own"])
    if r["agent"] == "main" and r.get("type") == "chief-of-staff":
        return STEERING if "grill" in r else UNSPLIT  # Copilot rows are not split
    return cost_kind(r)


def _steers(mains: list[dict[str, Any]]) -> str:
    names = list(dict.fromkeys(cost_label(r) for r in mains))
    return " and ".join(names) or "Foreman"


def breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One entry for the Foreman, then one per Driver type, per worker type (and per agent type
    where the parent link is not measured), each with its own calls and dollars only."""
    entries: dict[tuple[str, str], dict[str, Any]] = {}
    for r in rows:
        kind = cost_kind(r)
        e = entries.setdefault(
            (kind, cost_label(r) if kind == "Foreman" else r["type"]),
            {
                "kind": kind,
                "label": cost_label(r) if kind == "Foreman" else f"{kind} {r['type']}",
                "rows": [],
                "calls": 0,
                "usd": 0.0,
                "unpriced": {},
            },
        )
        e["rows"].append(r)
        e["calls"] += r["calls"]
        e["usd"] += r["usd"]
        add_unpriced(e["unpriced"], unpriced_of(r))
    order = ("Foreman", "Driver", "Worker", "Agent")
    return sorted(
        (e for e in entries.values() if e["calls"] or e["unpriced"]),
        key=lambda e: (order.index(e["kind"]), -e["usd"]),
    )


def restarted_drivers(repo: Repo, batch: str) -> set[str]:
    """The Drivers that came after another on the same CR, from the log's `agent` events."""
    seen: dict[str, list[str]] = {}
    for e in read_events(repo.batch_dir(batch)):
        if e.kind == "agent" and e.cr and e.cr != "stack" and e.agent:
            ids = seen.setdefault(e.cr, [])
            if e.agent not in ids:
                ids.append(e.agent)
    return {a for ids in seen.values() for a in ids[1:]}


def explain_line(entry: dict[str, Any], restarted: set[str]) -> str:
    """What explains a line's figure, all measured; `not measured` where the host gives none."""
    rows = [r for r in entry["rows"] if r["calls"] or unpriced_of(r)]
    n = len(rows)
    parts = [f"{n} agent{'s' if n != 1 else ''}, {entry['calls']} calls"]
    if not all("models" in r for r in rows):  # Copilot: per-call records, no token detail
        parts.append("model, shares of cost and calls after the cache expired: not measured")
    else:
        models = sorted(set().union(*(r["models"] for r in rows)))
        unpriced = set(entry["unpriced"])
        parts.append(
            "model " + ", ".join(f"{m} (not priced)" if m in unpriced else m for m in models)
        )
        total = sum(r["usd"] for r in rows)
        kinds = [sum(r[k] for r in rows) for k in ("usd_read", "usd_write", "usd_out", "usd_in")]
        shares = apportion(kinds, 100) if total else [0] * 4
        parts.append(
            "cost"
            + (" of the priced calls" if entry["unpriced"] else "")
            + ": "
            + ", ".join(
                f"{name} {s}%"
                for name, s in zip(
                    ("cache reads", "cache writes", "output", "input"), shares, strict=False
                )
            )
        )
        timed, expired = sum(r["timed"] for r in rows), sum(r["expired"] for r in rows)
        parts.append(
            f"{expired} of {timed} timed calls after the cache expired"
            if timed
            else "calls after the cache expired: not measured (no timestamps)"
        )
    if entry["kind"] == "Driver":
        parts.append(
            f"{sum(r['agent'] in restarted for r in rows)} restarted on a CR that already had one"
        )
    elif entry["kind"] == "Agent":
        parts.append("restarts: not measured (no parent link)")
    return "  " + "; ".join(parts)


EXPIRY_NOTE = (
    "A cache has expired when the gap from the agent's previous call is over its "
    "lifetime: 5 min after a 5-minute cache write, 1 h after a 1-hour one"
)


def cost_summary(
    d: BatchRecord,
    rows: list[dict[str, Any]],
    by_cr: dict[str, list[Any]],
    by_driver: dict[str, list[Any]],
    chief: list[str],
) -> list[str]:
    """What the user reads at the end of a batch; the detail is in `cost`. The split is the
    breakdown of `cost` summed by kind: the Foreman, the Drivers alone, the workers alone. The
    per-Driver figures say "with its workers". Amounts and shares add up as printed."""
    total = sum(r["usd"] for r in rows)
    un = sum_unpriced(rows)  # calls of a model with no price: every figure is then a floor
    budget = d.budget_usd
    mains = [r for r in rows if r["agent"] == "main"]  # one per steering session of the batch
    steer = _steers(mains)
    measured = all("parent" in r for r in rows if r["agent"] != "main")
    top = sorted(
        ((k, v[1], v[2]) for k, v in by_cr.items() if k != "foreman"), key=lambda kv: -kv[1]
    )
    lines = [
        f"Total: {usd_text(total, un)}"
        + (f" of a ${budget:g} budget" if budget else ", no budget")
        + (f"; {not_priced(un)}" if un else ""),
        _split(rows, steer, total, un),
        "Most: " + (", ".join(f"{k} {usd_text(usd, kun)}" for k, usd, kun in top[:3]) or "-"),
        *_wakes(steer, mains),
        *(
            _driver_line(k, v)
            for k, v in sorted(by_driver.items(), key=lambda kv: -kv[1][1])
            if k != "foreman" and measured
        ),
        *hints(sorted(un)),
        *chief,
        f"Not counted: compaction calls, which leave no record (about ${COMPACTION_USD:.2f} each)",
    ]
    return list(dict.fromkeys(lines))  # a model the Chief of Staff shares gets one hint


def _driver_line(k: str, v: list[Any]) -> str:
    return (
        f"Driver {k} with its workers: {usd_text(v[1], v[2])} ({v[0]} calls"
        + (f"; {not_priced(v[2])}" if v[2] else "")
        + ")"
    )


def _wakes(steer: str, mains: list[dict[str, Any]]) -> list[str]:
    n = sum(r.get("wakes", 0) for r in mains)
    if not n:
        return []
    return [
        f"{steer}: {n} wakes, context "
        f"{sum(r.get('wake_context', 0) for r in mains) // n:,} tokens on average, "
        f"{max(r.get('peak_context', 0) for r in mains):,} at its peak"
    ]


def _split(rows: list[dict[str, Any]], steer: str, total: float, un: dict[str, Any]) -> str:
    """The spend by kind: the steering session, the Drivers, the workers, as printed."""
    entries = breakdown(rows)
    kinds = [
        (
            name,
            sum(e["usd"] for e in entries if e["kind"] == kind),
            sum_unpriced([r for e in entries if e["kind"] == kind for r in e["rows"]]),
        )
        for name, kind in (
            (steer, "Foreman"),
            ("Drivers", "Driver"),
            ("workers", "Worker"),
            ("agents, Driver or worker not measured", "Agent"),
        )
    ]
    kinds = [k for k in kinds if k[1] or k[2] or k[0] in (steer, "Drivers", "workers")]
    parts = [usd for _, usd, _ in kinds]
    cents = apportion(parts, round(total * 100))
    shares = apportion(parts, 100) if total else [0] * len(parts)
    return ", ".join(
        f"{name} {usd_text(c / 100, kun)} ({'not measured' if un else f'{s}%'})"
        for (name, _, kun), c, s in zip(kinds, cents, shares, strict=False)
    )


def orchestration(
    d: BatchRecord, rows: list[dict[str, Any]], shares: list[int], un: dict[str, Any]
) -> str:
    """The ratio of orchestration: the steering session (its own subagents with it) and the
    Drivers, from the shares printed on the lines, so the figures add up as printed."""
    head = "Orchestration (steering + Drivers):"
    if d.host == "copilot":  # a Driver cannot be told from a worker there
        return f"{head} not measured (no parent link on this host)"
    if un:
        return f"{head} not measured (calls not priced)"
    kinds = [e["kind"] for e in breakdown(rows)]
    steering = sum(s for k, s in zip(kinds, shares, strict=False) if k in ("Foreman", "Driver"))
    return f"{head} {steering}% of the batch's spend"
