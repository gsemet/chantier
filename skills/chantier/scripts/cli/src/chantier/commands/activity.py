"""The activity lines of `status --refresh`: how long each working CR has been quiet."""

from __future__ import annotations

from chantier.commands.cost.sessions import foreman_uuid
from chantier.commands.gate_lock import gate_state
from chantier.core.clock import age_minutes
from chantier.core.errors import ChantierError
from chantier.core.records import LIVE, BatchRecord, EventRecord, read_events
from chantier.core.repo import Repo
from chantier.costs.sessions import agent_records, idle_seconds

MAX_HOPS = 5  # parent links followed from a worker to its Driver


def _event_ages(events: list[EventRecord]) -> tuple[dict[str, float], dict[str, str]]:
    """Per key (a CR, `stack`, an order), the minutes since its last event; and, from the `agent`
    events, agent id -> key."""
    last: dict[str, float] = {}
    owner: dict[str, str] = {}
    for e in events:
        age = age_minutes(e.t)
        if e.cr and age is not None:
            last[e.cr] = min(age, last.get(e.cr, age))
        if e.kind == "agent" and e.cr and e.agent:
            owner[e.agent] = e.cr
    return last, owner


def _targets(d: BatchRecord) -> list[tuple[str, str]]:
    """(key, label) of what works: each live CR, the stack driver, each open QA order with an
    agent."""
    targets = [(c.id, c.id) for c in d.crs if c.status in LIVE]
    if d.stack_agent:
        targets.append(("stack", "stack"))
    targets += [(o.id, f"{o.id} qa") for o in d.orders if o.kind == "qa" and not o.done and o.agent]
    return targets


def _mine(
    records: dict[str, tuple[str | None, float | None]], owner: dict[str, str], key: str
) -> list[str]:
    """The agent ids whose parent links, followed up to a Driver, reach this key."""

    def key_of(agent: str | None, hops: int = 0) -> str | None:
        if agent is None or hops > MAX_HOPS:
            return None
        return owner.get(agent) or key_of(records.get(agent, (None, None))[0], hops + 1)

    return [i for i in records if key_of(i) == key]


def _record_line(
    word: str,
    key: str,
    ages: list[float],
    records: dict[str, tuple[str | None, float | None]],
    owner: dict[str, str],
) -> str:
    mine = _mine(records, owner, key)
    readable = [v for i in mine if (v := records[i][1]) is not None]
    if any(v == key for v in owner.values()) and not readable:
        return f"{word} not measured"  # a Driver is recorded, its record cannot be read
    ages = [*ages, *(a / 60 for a in readable)]
    return f"{word} {min(ages):.0f} min" if ages else f"{word} not measured"


def activity(repo: Repo, d: BatchRecord) -> list[str]:
    """One line per working CR (and the stack driver, and each open QA order with an agent id):
    the age of its last activity, the most recent of its last event in the log and the last write
    of the session records that are its own. The CLI states the age and never judges it.
    A host with no per-agent record (Copilot) gives the session's age, said so. A record that
    cannot be read is `not measured`. A long gate is `gate running` when the lock names the CR
    and its command or suite is still the process the lock recorded (a dead or reused pid is a
    stale lock), and `gate queued behind <cr>` (bare `gate queued` when it is next) when a live
    ticket of the queue names it. This only reads: it deletes no ticket."""
    last, owner = _event_ages(read_events(repo.batch_dir(d.id)))
    targets = _targets(d)
    if not targets:
        return []
    try:
        sessions = foreman_uuid(d)
    except ChantierError:
        sessions = []
    copilot = d.host == "copilot"
    session_min: float | None = None
    records: dict[str, tuple[str | None, float | None]] = {}
    if copilot:
        ages = [a for _, a in idle_seconds(repo.session_root, "copilot", sessions) if a is not None]
        session_min = min(ages) / 60 if ages else None
    else:
        records = agent_records(repo.session_root, sessions)
    out = []
    for key, label in targets:
        word = f"activity {label}"
        mine = [last[key]] if key in last else []
        if state := gate_state(repo, key):
            out.append(f"{word} {state}")
        elif not copilot:
            out.append(_record_line(word, key, mine, records, owner))
        elif session_min is None:
            out.append(f"{word} not measured")
        else:
            out.append(f"{word} {min([*mine, session_min]):.0f} min (session-level)")
    return out
