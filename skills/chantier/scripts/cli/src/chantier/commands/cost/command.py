"""`chantier cost`."""

from __future__ import annotations

from chantier.commands.cost.breakdown import (
    COMPACTION_USD,
    EXPIRY_NOTE,
    apportion,
    breakdown,
    cost_groups,
    cost_summary,
    explain_line,
    orchestration,
    restarted_drivers,
)
from chantier.commands.cost.pricing import hints, spend, sum_unpriced
from chantier.commands.cost.sessions import chief_line, cost_rows, foreman_uuid
from chantier.commands.registry import BATCH, Subparsers, add_command
from chantier.core.batch import read_batch, resolve_batch
from chantier.core.errors import ChantierError
from chantier.lifecycle.convert import open_repo
from chantier.rails import not_priced


def cost(args) -> list[str]:
    """The batch's spend, read from the Foreman's transcript on the batch's host; `status
    --refresh` and `pause` record it."""
    repo = open_repo()
    batch = resolve_batch(repo, args.batch)
    d = read_batch(repo, batch)
    if not (d.get("foreman_transcripts") or d.get("foreman_transcript")):
        var = "$COPILOT_AGENT_SESSION_ID" if d["host"] == "copilot" else "$CLAUDE_CODE_SESSION_ID"
        raise ChantierError(
            f"no Foreman transcript recorded: the Foreman runs `chantier foreman transcript {var}`"
        )
    rows = cost_rows(repo, d, d["host"], foreman_uuid(d))
    total = sum(r["usd"] for r in rows)
    un = sum_unpriced(rows)
    chief = chief_line(repo, d)
    if args.summary:
        return cost_summary(
            d,
            rows,
            cost_groups(repo, batch, rows, "cr"),
            cost_groups(repo, batch, rows, "driver"),
            chief,
        )
    if args.explain and args.by == "cr":
        raise ChantierError("`--explain` explains the breakdown by role, not `--by cr`")
    driver_context: dict[str, str] = {}
    if args.by == "cr":  # a CR's Driver and its workers
        groups = cost_groups(repo, batch, rows, "cr")
        lines = [
            (k, v[0], v[1], None, v[2]) for k, v in sorted(groups.items(), key=lambda kv: -kv[1][1])
        ]
        driver_context = {
            k: f"Driver peak context {v[3]:,} tokens, {v[4]} compaction{'s' if v[4] != 1 else ''}"
            for k, v in groups.items()
            if v[3]
        }
    else:  # the Foreman, each Driver type, each worker type: their own calls and dollars
        restarted = restarted_drivers(repo, batch) if args.explain else set()
        lines = [
            (
                e["label"],
                e["calls"],
                e["usd"],
                explain_line(e, restarted) if args.explain else None,
                e["unpriced"],
            )
            for e in breakdown(rows)
        ]
    mills = (
        [round(usd * 1000) for _, _, usd, _, _ in lines]
        if args.by == "cr"  # each CR's own
        else apportion([usd for _, _, usd, _, _ in lines], round(total * 1000))
    )  # add up
    shares = None if args.by == "cr" else apportion([usd for _, _, usd, _, _ in lines], 100)
    estimated = sum(r.get("estimated", 0) for r in rows)
    calls_all = sum(r["calls"] for r in rows)
    out = [
        f"{batch}: at least ${total:.3f} over {calls_all} priced model calls; {not_priced(un)}"
        if un
        else f"{batch}: ${total:.3f} over {calls_all} model calls"
        + (f" ({estimated} estimated, not billed)" if estimated else "")
    ]
    for i, ((label, calls, _, why, lun), m) in enumerate(zip(lines, mills, strict=False)):
        share = None if shares is None else "share not measured" if un else f"{shares[i]}%"
        detail = (
            ([f"{calls} calls" + (f", {share}" if share else "")] if calls or not lun else [])
            + ([not_priced(lun)] if lun else [])
            + ([driver_context[label]] if label in driver_context else [])
        )
        out += [f"{label}: {spend(m / 1000, calls, lun, 3)} ({'; '.join(detail)})"] + (
            [why] if why else []
        )
    if shares is not None:
        out.append(orchestration(d, rows, shares, un))
    out += hints(sorted(un))
    out += chief
    if args.explain:
        n = sum(r.get("compactions", 0) for r in rows)
        out += [
            EXPIRY_NOTE
            if all("models" in r for r in rows)
            else "Cache expiry: not measured on this host",
            f"Not counted: {n} compaction calls, which leave no record (about "
            f"${COMPACTION_USD:.2f} each, ${n * COMPACTION_USD:.2f})"
            if all("compactions" in r for r in rows)
            else "Not counted: compaction calls are not measured on this host",
        ]
    return list(dict.fromkeys(out))  # a model the Chief of Staff shares gets one hint


def register(sub: Subparsers) -> None:
    """Declare this module's commands."""
    s = add_command(sub, "cost", cost, "price the Foreman's transcript and its subagents", BATCH)
    s.add_argument(
        "--by",
        choices=["role", "cr"],
        default="role",
        help="role: the Foreman, each Driver type, each worker type; cr: a CR's own",
    )
    s.add_argument(
        "--explain",
        action="store_true",
        help="under each line: agents, model, shares of cost, calls after the cache "
        "expired, restarted Drivers; ends with what the figures do not count",
    )
    s.add_argument(
        "--summary",
        action="store_true",
        help="total, budget, Foreman, Drivers and workers, the costliest CRs",
    )
