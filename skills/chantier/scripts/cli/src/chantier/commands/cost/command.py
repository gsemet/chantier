"""`chantier cost`."""

from __future__ import annotations

import argparse
from typing import Any

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
from chantier.core.batch import read_batch, resolve_batch
from chantier.core.errors import ChantierError
from chantier.core.records import BatchRecord
from chantier.core.repo import Repo
from chantier.plugin_files import read_playbook
from chantier.rails import not_priced

Line = tuple[
    str, int, float, str | None, dict[str, Any]
]  # label, calls, dollars, explanation, unpriced


def _by_cr(repo: Repo, batch: str, rows: list[dict[str, Any]]) -> tuple[list[Line], dict[str, str]]:
    """A CR's Driver and its workers, and the Drivers' context notes."""
    groups = cost_groups(repo, batch, rows, "cr")
    mains = [r.get("type") == "chief-of-staff" for r in rows if r["agent"] == "main"]
    # the group key stays "foreman"; only its printed label names who steered
    label = {
        "foreman": "foreman"
        if not any(mains)
        else "Chief of Staff, steering the batch, and its own subagents"
        if all(mains)
        else "Chief of Staff, steering the batch, and the Foreman, with their own subagents"
    }
    lines: list[Line] = [
        (label.get(k, k), v[0], v[1], None, v[2])
        for k, v in sorted(groups.items(), key=lambda kv: -kv[1][1])
    ]
    context = {
        k: f"Driver peak context {v[3]:,} tokens, {v[4]} compaction{'s' if v[4] != 1 else ''}"
        for k, v in groups.items()
        if v[3]
    }
    return lines, context


def _by_role(repo: Repo, batch: str, rows: list[dict[str, Any]], explain: bool) -> list[Line]:
    """The Foreman, each Driver type, each worker type: their own calls and dollars."""
    restarted = restarted_drivers(repo, batch) if explain else set()
    return [
        (
            e["label"],
            e["calls"],
            e["usd"],
            explain_line(e, restarted) if explain else None,
            e["unpriced"],
        )
        for e in breakdown(rows)
    ]


def _headline(batch: str, rows: list[dict[str, Any]], un: dict[str, Any]) -> str:
    total = sum(r["usd"] for r in rows)
    estimated = sum(r.get("estimated", 0) for r in rows)
    calls_all = sum(r["calls"] for r in rows)
    if un:
        return (
            f"{batch}: at least ${total:.3f} over {calls_all} priced model calls; {not_priced(un)}"
        )
    return f"{batch}: ${total:.3f} over {calls_all} model calls" + (
        f" ({estimated} estimated, not billed)" if estimated else ""
    )


def _line_text(line: Line, mills: int, share: str | None, context: dict[str, str]) -> list[str]:
    label, calls, _, why, lun = line
    detail = (
        ([f"{calls} calls" + (f", {share}" if share else "")] if calls or not lun else [])
        + ([not_priced(lun)] if lun else [])
        + ([context[label]] if label in context else [])
    )
    return [f"{label}: {spend(mills / 1000, calls, lun, 3)} ({'; '.join(detail)})"] + (
        [why] if why else []
    )


GRILL_ROLES = ("spec-writer", "spec-critic")


def _grill_notes(repo: Repo, host: str) -> list[str]:
    """A Spec-writer or Spec critic the configuration read now starts as a generic agent, or as
    the user's own agent, is not found by its agent type: say its spend is not on the grill line.
    An invalid configuration gives no note (`playbook` and `preflight` report it)."""
    made, problems = read_playbook(repo, host)
    roles = {} if problems or not made else made.get("roles", {})
    out = []
    for role in GRILL_ROLES:
        rec = roles.get(role, {})
        if rec.get("start") == "generic" or (rec.get("start") == "named" and rec.get("agent")):
            who = (
                "a generic agent" if rec.get("start") == "generic" else f"your agent {rec['agent']}"
            )
            out.append(
                f"Grill line: {role} starts as {who}, so its spend is counted with the Chief of "
                "Staff's steering, not on the grill line"
            )
    return out


def _explain_notes(rows: list[dict[str, Any]], repo: Repo, host: str) -> list[str]:
    n = sum(r.get("compactions", 0) for r in rows)
    return [
        *_grill_notes(repo, host),
        EXPIRY_NOTE
        if all("models" in r for r in rows)
        else "Cache expiry: not measured on this host",
        f"Not counted: {n} compaction calls, which leave no record (about "
        f"${COMPACTION_USD:.2f} each, ${n * COMPACTION_USD:.2f})"
        if all("compactions" in r for r in rows)
        else "Not counted: compaction calls are not measured on this host",
    ]


def batch_rows(repo: Repo, d: BatchRecord) -> list[dict[str, Any]]:
    """The batch's spend rows, read from the steering session's transcripts on the batch's host;
    refused when no steering transcript is recorded (`cost` and `retro draft` read them)."""
    if not (d.foreman_transcripts or d.foreman_transcript):
        var = "$COPILOT_AGENT_SESSION_ID" if d.host == "copilot" else "$CLAUDE_CODE_SESSION_ID"
        who = "Chief of Staff" if d.steering == "direct" else "Foreman"
        what = "steering" if d.steering == "direct" else "Foreman"
        raise ChantierError(
            f"no {what} transcript recorded: the {who} runs "
            f"`chantier foreman transcript {var} --epoch <n>`"
        )
    return cost_rows(repo, d, d.host, foreman_uuid(d))


def cost(args: argparse.Namespace) -> list[str]:
    """The batch's spend, read from the Foreman's transcript on the batch's host; `status
    --refresh`, `pause` and the budget checks record it."""
    repo = Repo.find()
    batch = resolve_batch(repo, args.batch, paused=True)
    d = read_batch(repo, batch)
    rows = batch_rows(repo, d)
    total = sum(r["usd"] for r in rows)
    un = sum_unpriced(rows)
    chief = chief_line(repo, d)
    if args.summary:
        by_cr = cost_groups(repo, batch, rows, "cr")
        return cost_summary(d, rows, by_cr, cost_groups(repo, batch, rows, "driver"), chief)
    if args.explain and args.by == "cr":
        raise ChantierError("`--explain` explains the breakdown by role, not `--by cr`")
    context: dict[str, str] = {}
    if args.by == "cr":
        lines, context = _by_cr(repo, batch, rows)
        mills = [round(usd * 1000) for _, _, usd, _, _ in lines]  # each CR's own
        shares = None
    else:
        lines = _by_role(repo, batch, rows, args.explain)
        usds = [usd for _, _, usd, _, _ in lines]
        mills = apportion(usds, round(total * 1000))  # add up
        shares = apportion(usds, 100)
    out = [_headline(batch, rows, un)]
    for i, (line, m) in enumerate(zip(lines, mills, strict=False)):
        share = None if shares is None else "share not measured" if un else f"{shares[i]}%"
        out += _line_text(line, m, share, context)
    if shares is not None:
        out.append(orchestration(d, rows, shares, un))
    out += hints(sorted(un))
    out += chief
    if args.explain:
        out += _explain_notes(rows, repo, d.host)
    return list(dict.fromkeys(out))  # a model the Chief of Staff shares gets one hint
