"""The sessions a cost line belongs to."""

from __future__ import annotations

from chantier.commands.cost.breakdown import COMPACTION_USD
from chantier.commands.cost.pricing import (
    add_unpriced,
    hints,
    minus,
    price_table,
    spend,
    steering_window,
    sum_unpriced,
    unpriced_of,
)
from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError
from chantier.core.records import chief_sessions, read_events
from chantier.core.repo import Repo
from chantier.costs.copilot import copilot_session_costs
from chantier.costs.sessions import is_spec_writer, session_costs, without_spec_writers
from chantier.costs.transcripts import transcript_path
from chantier.rails import not_priced


def claimed_transcripts(d: dict) -> list[str]:
    return [c["transcript"] for c in d.get("foreman_claims") or []]


def foreman_uuid(d: dict) -> list[str]:
    uuids = d.get("foreman_transcripts") or [d.get("foreman_transcript")]
    if not uuids[0]:
        raise ChantierError("no Foreman transcript recorded", EXIT_PRECONDITION)
    return uuids


OWN_CHIEF = "Chief of Staff's own subagents"


OWN_FOREMAN = "Foreman's own subagents"


STEER_OUT = "Chief of Staff, steering the batch (outside the budget)"


GRILL_OUT = "Chief of Staff, grill and specifications with the user (outside the budget)"


WHOLE = "Chief of Staff, whole session"


def _chief_unknown(cause: str) -> list[str]:
    """The Chief of Staff's lines when nothing can be measured: unknown, never $0.00."""
    why = f"unknown: {cause}" if cause.startswith("not measured") else f"unknown ({cause})"
    return [
        f"{STEER_OUT}: {why}",
        f"{GRILL_OUT}: {why}",
        f"{WHOLE}: {why}"
        + ("; compactions: not measured on this host" if "this host" in cause else ""),
    ]


def chief_line(repo: Repo, d: dict) -> list[str]:
    """The Chief of Staff's session, priced apart from the spend and the budget, in the lines
    that add up: what it spent since the batch opened, steering and grilling apart, and the whole
    session. What a direct batch's steering row holds is that row's, never counted twice."""
    chiefs = chief_sessions(d)
    if d.get("host") == "copilot":
        return _chief_unknown("not measured on this host")
    if not chiefs:
        return _chief_unknown("no Chief of Staff transcript recorded")
    prices = price_table(repo, d["host"])
    steer = [0, 0.0, {}]  # calls, dollars, calls not priced, since the batch opened, the steering
    grill = [0, 0.0, {}]  # row's own left out
    writers = untimed = compactions = 0
    whole_usd, context, inside_calls, whole_un = 0.0, 0, 0, {}
    for uuid in chiefs:  # every Chief of Staff session of the batch, summed
        path = transcript_path(repo.session_root, uuid)
        try:
            window = (
                steering_window(d, uuid) if uuid in claimed_transcripts(d) else None
            )  # strict rule inside it
            whole = session_costs(path, kind="chief-of-staff", prices=prices)
            since = session_costs(
                path,
                d.get("created", ""),
                kind="chief-of-staff",
                allow_empty=True,
                split=True,
                prices=prices,
                steering=window,
            )
            steered = (
                without_spec_writers(
                    session_costs(
                        path,
                        *window,
                        kind="chief-of-staff",
                        allow_empty=True,
                        split=True,
                        prices=prices,
                        steering=window,
                    )
                )
                if window
                else []
            )
        except ChantierError as e:
            return _chief_unknown(str(e))
        main = since[0]
        for r in since:
            if is_spec_writer(r):
                writers += 1
                grill[0] += r["calls"]
                grill[1] += r["usd"]
                add_unpriced(grill[2], unpriced_of(r))
            else:
                steer[0] += r["calls"]
                steer[1] += r["usd"]
                add_unpriced(steer[2], unpriced_of(r))
        grill[0] += main["grill"]["calls"]
        grill[1] += main["grill"]["usd"]
        add_unpriced(grill[2], unpriced_of(main["grill"]))
        compactions += main["compactions"]
        untimed += main["untimed"]
        inside = sum(r["usd"] for r in steered)  # the steering row: counted in the spend
        inside_un = sum_unpriced(steered)
        steer[0] -= sum(r["calls"] for r in steered)
        steer[1] -= inside
        steer[2] = minus(steer[2], inside_un)
        inside_calls += sum(r["calls"] for r in steered) + sum(inside_un.values())
        whole_usd += sum(r["usd"] for r in whole) - inside
        add_unpriced(whole_un, minus(sum_unpriced(whole), inside_un))
        context = whole[0]["last_context"]  # the current session's, the last
    lines = []
    steer_held = steer[0] + sum(steer[2].values())

    def why(n, un):
        return f"{n} calls" + (f"; {not_priced(un)}" if un else "")

    if (
        not steer_held and untimed
    ):  # the only calls of this part cannot be placed: unknown, not $0.00
        lines.append(f"{STEER_OUT}: unknown ({untimed} calls without a time, not placed)")
    elif steer_held or not inside_calls:  # a direct batch's steering is its row, not a line
        lines.append(
            f"{STEER_OUT}: {spend(steer[1], steer[0], steer[2])} since the batch "
            f"opened ({why(steer[0], steer[2])})"
        )
    lines += [
        f"{GRILL_OUT}: {spend(grill[1], grill[0], grill[2])} since the batch opened "
        f"({why(grill[0], grill[2])}, {writers} spec-writers)",
        f"{WHOLE}: {spend(whole_usd, 1, whole_un)}, context {context:,} tokens; not "
        f"counted: {compactions} compactions since the batch opened, which leave no record "
        f"(about ${COMPACTION_USD:.2f} each)" + (f"; {not_priced(whole_un)}" if whole_un else ""),
    ]
    if untimed and steer_held:
        lines.append(f"Chief of Staff: {untimed} calls without a time, not placed")
    return lines + hints(sorted(add_unpriced(add_unpriced(dict(steer[2]), grill[2]), whole_un)))


def cost_rows(repo: Repo, d: dict, host: str, uuids: list[str]) -> list[dict]:
    """Every Foreman of the batch, summed, from its opening to now: `pause` ends no window, a
    call made after it is spend. A call of a model with no price is counted in the row's
    `unpriced`, not refused."""
    prices = price_table(repo, host)
    rows: list[dict] = []
    chiefs = chief_sessions(d)
    # a Driver is an agent the log ties to a CR, the stack or a QA order; any other agent with no
    # parent is the steering session's own subagent
    drivers = {
        e["agent"]
        for e in read_events(repo.batch_dir(d["id"]))
        if e.get("kind") == "agent" and e.get("agent")
    }
    for uuid in uuids:
        steering = uuid in chiefs  # a Chief of Staff's own steering window
        if host == "copilot":
            got = copilot_session_costs(uuid)  # no timestamps: the whole session
        else:
            since, until = steering_window(d, uuid)
            got = session_costs(
                transcript_path(repo.session_root, uuid),
                since,
                until,
                kind="chief-of-staff" if steering else "foreman",
                allow_empty=len(uuids) > 1,
                split=steering,
                prices=prices,
                steering=(since, until) if steering and uuid in claimed_transcripts(d) else None,
            )
        if steering:
            got[0]["type"] = "chief-of-staff"
            got = without_spec_writers(got)  # grill and specifications: their own line
        for r in got:
            if (
                r["agent"] != "main"
                and "parent" in r
                and not r["parent"]
                and r["agent"] not in drivers
            ):
                r["own"] = OWN_CHIEF if steering else OWN_FOREMAN
        rows += got
    if not any(r["calls"] for r in rows):
        raise ChantierError("no priced calls in the Foreman transcripts", EXIT_EXTERNAL)
    return rows
