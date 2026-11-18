"""The sessions a cost line belongs to."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from chantier.commands.cost.breakdown import COMPACTION_USD
from chantier.commands.cost.pricing import (
    add_unpriced,
    hints,
    minus,
    price_table,
    spend,
    steering_windows,
    sum_unpriced,
    unpriced_of,
)
from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION, ChantierError
from chantier.core.records import BatchRecord, chief_sessions, read_events
from chantier.core.repo import Repo
from chantier.costs.copilot import copilot_session_costs
from chantier.costs.sessions import (
    Scope,
    is_spec_critic,
    is_specification_agent,
    session_costs,
    without_specification_agents,
)
from chantier.costs.transcripts import transcript_path
from chantier.rails import not_priced


def claimed_transcripts(d: BatchRecord) -> list[str]:
    return [c.transcript for c in d.foreman_claims]


def foreman_uuid(d: BatchRecord) -> list[str]:
    uuids = d.foreman_transcripts or ([d.foreman_transcript] if d.foreman_transcript else [])
    if not uuids or not uuids[0]:
        who = "steering" if d.steering == "direct" else "Foreman"
        raise ChantierError(f"no {who} transcript recorded", EXIT_PRECONDITION)
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


@dataclass
class _Part:
    """Calls, dollars and calls not priced of one part of the Chief of Staff's session."""

    calls: int = 0
    usd: float = 0.0
    unpriced: dict[str, Any] = field(default_factory=dict[str, Any])

    def add(self, r: dict[str, Any]) -> None:
        self.calls += r["calls"]
        self.usd += r["usd"]
        add_unpriced(self.unpriced, unpriced_of(r))

    def held(self) -> int:
        return int(self.calls + sum(self.unpriced.values()))


@dataclass
class _Chief:
    steer: _Part = field(default_factory=_Part)
    grill: _Part = field(default_factory=_Part)
    writers: int = 0
    critics: int = 0
    untimed: int = 0
    compactions: int = 0
    whole_usd: float = 0.0
    inside_usd: float = 0.0
    inside_un: dict[str, Any] = field(default_factory=dict[str, Any])
    context: int = 0
    inside_calls: int = 0
    whole_un: dict[str, Any] = field(default_factory=dict[str, Any])


def _chief_session(
    repo: Repo, d: BatchRecord, uuid: str, prices: dict[str, Any] | None
) -> tuple[list[Any], list[Any], list[Any]]:
    """The session whole, since the batch opened, and the steering row inside the window."""
    path = transcript_path(repo.session_root, uuid)
    windows = steering_windows(d, uuid) if uuid in claimed_transcripts(d) else None
    whole = session_costs(path, scope=Scope("chief-of-staff", prices=prices))
    scope = Scope("chief-of-staff", True, True, prices, windows)
    since = session_costs(path, d.created or "", scope=scope)
    steered = (
        without_specification_agents(
            session_costs(path, scope=Scope("chief-of-staff", True, True, prices, windows, windows))
        )
        if windows
        else []
    )
    return whole, since, steered


def _absorb(c: _Chief, whole: list[Any], since: list[Any], steered: list[Any]) -> None:
    main = since[0]
    for r in since:
        if is_specification_agent(r):
            if is_spec_critic(r):
                c.critics += 1
            else:
                c.writers += 1
            c.grill.add(r)
        else:
            c.steer.add(r)
    c.grill.add(main["grill"])
    c.compactions += main["compactions"]
    c.untimed += main["untimed"]
    inside = sum(r["usd"] for r in steered)  # the steering row: counted in the spend
    inside_un = sum_unpriced(steered)
    inside_n = sum(r["calls"] for r in steered)
    c.steer.calls -= inside_n
    c.steer.usd -= inside
    c.steer.unpriced = minus(c.steer.unpriced, inside_un)
    c.inside_calls += inside_n + sum(inside_un.values())
    # the whole session, the steering window included; `inside` is the part in the batch's spend
    c.whole_usd += sum(r["usd"] for r in whole)
    c.inside_usd += inside
    add_unpriced(c.inside_un, inside_un)
    add_unpriced(c.whole_un, sum_unpriced(whole))
    c.context = whole[0]["last_context"]  # the current session's, the last


def _why(n: int, un: dict[str, Any]) -> str:
    return f"{n} calls" + (f"; {not_priced(un)}" if un else "")


def _chief_lines(c: _Chief) -> list[str]:
    lines = []
    steer = c.steer
    if not steer.held() and c.untimed:  # the only calls of this part cannot be placed
        lines.append(f"{STEER_OUT}: unknown ({c.untimed} calls without a time, not placed)")
    elif steer.held() or not c.inside_calls:  # a direct batch's steering is its row, not a line
        lines.append(
            f"{STEER_OUT}: {spend(steer.usd, steer.calls, steer.unpriced)} since the batch "
            f"opened ({_why(steer.calls, steer.unpriced)})"
        )
    grill = c.grill
    part = (
        f" ({spend(c.inside_usd, c.inside_calls, c.inside_un)} of it in the batch's spend)"
        if c.inside_calls
        else ""
    )
    lines += [
        f"{GRILL_OUT}: {spend(grill.usd, grill.calls, grill.unpriced)} since the batch opened "
        f"({_why(grill.calls, grill.unpriced)}, {c.writers} spec-writers, "
        f"{c.critics} spec critics)",
        f"{WHOLE}: {spend(c.whole_usd, 1, c.whole_un)}{part}, context {c.context:,} tokens; not "
        f"counted: {c.compactions} compactions since the batch opened, which leave no record "
        f"(about ${COMPACTION_USD:.2f} each)"
        + (f"; {not_priced(c.whole_un)}" if c.whole_un else ""),
    ]
    if c.untimed and steer.held():
        lines.append(f"Chief of Staff: {c.untimed} calls without a time, not placed")
    return lines


def chief_read(repo: Repo, d: BatchRecord) -> _Chief | str:
    """The Chief of Staff's sessions of the batch, summed, read once; the cause (a string) when
    nothing can be measured."""
    chiefs = chief_sessions(d)
    if d.host == "copilot":
        return "not measured on this host"
    if not chiefs:
        return "no Chief of Staff transcript recorded"
    prices = price_table(repo, d.host)
    c = _Chief()
    for uuid in chiefs:  # every Chief of Staff session of the batch, summed
        try:
            parts = _chief_session(repo, d, uuid, prices)
        except ChantierError as e:
            return str(e)
        _absorb(c, *parts)
    return c


def chief_line(repo: Repo, d: BatchRecord, read: _Chief | str | None = None) -> list[str]:
    """The Chief of Staff's session, priced apart from the spend and the budget, in the lines
    that add up: what it spent since the batch opened, steering and grilling apart, and the whole
    session, steering window included, with the part of it in the batch's spend named in a
    parenthesis. What a direct batch's steering row holds is that row's, never counted twice in
    the steering line. `read` is `chief_read`'s, when the caller already has it."""
    c = chief_read(repo, d) if read is None else read
    if isinstance(c, str):
        return _chief_unknown(c)
    unpriced = add_unpriced(add_unpriced(dict(c.steer.unpriced), c.grill.unpriced), c.whole_un)
    return _chief_lines(c) + hints(sorted(unpriced))


def _outside_part(p: _Part) -> dict[str, Any]:
    return {"usd": round(p.usd, 4), "calls": p.calls, "unpriced": dict(p.unpriced)}


def chief_outside(d: BatchRecord, read: _Chief | str) -> dict[str, Any]:
    """The parts of the Chief of Staff's session outside the budget, as data: `outside` (the
    grill, and the steering in a Foreman batch; `None` when nothing can be measured) and, then,
    `outside_unknown` with the cause. Never a $0.00 for what is not measured."""
    if isinstance(read, str):
        return {"outside": None, "outside_unknown": read}
    steer = read.steer
    steering: dict[str, Any] | None
    if d.steering == "direct" or (not steer.held() and read.inside_calls):
        steering = None  # a direct batch's steering is its Steering line, inside the budget
    elif not steer.held() and read.untimed:
        steering = {"usd": None, "calls": 0, "unpriced": {}, "unknown": "calls without a time"}
    else:
        steering = _outside_part(steer)
    return {"outside": {"grill": _outside_part(read.grill), "steering": steering}}


def _transcripts(d: BatchRecord) -> str:
    if d.steering == "direct":
        return "steering transcripts (the Chief of Staff's)"
    return "Foreman transcripts"


def cost_rows(repo: Repo, d: BatchRecord, host: str, uuids: list[str]) -> list[dict[str, Any]]:
    """Every Foreman of the batch, summed, from its opening to now: `pause` ends no window, a
    call made after it is spend. A call of a model with no price is counted in the row's
    `unpriced`, not refused."""
    prices = price_table(repo, host)
    rows: list[dict[str, Any]] = []
    chiefs = chief_sessions(d)
    # a Driver is an agent the log ties to a CR, the stack or a QA order; any other agent with no
    # parent is the steering session's own subagent
    drivers = {e.agent for e in read_events(repo.batch_dir(d.id)) if e.kind == "agent" and e.agent}
    for uuid in uuids:
        steering = uuid in chiefs  # a Chief of Staff's own steering window
        if host == "copilot":
            got = copilot_session_costs(uuid)  # no timestamps: the whole session
        else:
            windows = steering_windows(d, uuid)
            got = session_costs(
                transcript_path(repo.session_root, uuid),
                scope=Scope(
                    "chief-of-staff" if steering else "foreman",
                    allow_empty=len(uuids) > 1,
                    split=steering,
                    prices=prices,
                    steering=windows if steering and uuid in claimed_transcripts(d) else None,
                    windows=windows,
                ),
            )
        if steering:
            got[0]["type"] = "chief-of-staff"
            got = without_specification_agents(got)  # grill and specifications: their own line
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
        raise ChantierError(f"no priced calls in the {_transcripts(d)}", EXIT_EXTERNAL)
    return rows
