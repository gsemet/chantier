"""What still runs when `close` asks: the causes from the record, the Foreman's heartbeat, the
leases (Copilot) and the Claude transcripts' ends."""

from __future__ import annotations

from typing import TYPE_CHECKING

from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.records import BatchRecord, chief_sessions
from chantier.core.repo import Repo
from chantier.rails import ENDED

if TYPE_CHECKING:
    from chantier.costs.sessions import Ending

STOPPED_HINT = (
    "an agent stopped without its hand-back (an app restart, the user's stop) passes only on the "
    "user's word: `close --stopped <name>` for each"
)


def held_agents(d: BatchRecord) -> dict[str, str]:
    """The agents the batch's record holds: recorded id -> the owner's label (a CR's slug
    or an order's id), for each CR's and each QA order's `agent` that `agents set` wrote and no
    `agents set <x> -` cleared. The recorded stack agent is not here: it is a record cause."""
    held = {c.agent: c.id for c in d.crs if c.agent}
    held.update({o.agent: o.id for o in d.orders if o.agent})
    return held


def running(repo: Repo, d: BatchRecord) -> tuple[list[str], list[Ending], list[Ending]]:
    """What shows a batch still runs: (the causes no flag passes, the state of each held agent's
    Claude transcript, the state of every other transcript). The causes come from the record (a CR
    not merged or cancelled, an open order, a recorded stack agent) and, on Copilot, from the
    leases of the held agents and the Foreman's heartbeat. On Claude each transcript is
    read at its end, never by the file's age: an agent that handed back has ended, one that waits
    on a tool call or has a step under way runs, one whose file is missing or cut cannot be read.
    Only the agents the batch holds can block: the current Foreman (the last claim's session main
    transcript) and each id `agents set` recorded and did not clear, a held id with no transcript
    under the steering sessions being one that cannot be read. The other transcripts (other
    subagents, a held Driver's own, the replaced Foremans' main ones) are returned apart, never a
    cause. The Foreman's session tree is all the CLI knows: a Driver run from another session of
    the user's is not in it. The Chief of Staff's own session is not counted (its subagents are)."""
    causes = [
        f"{c.id} is {c.status}, not merged or cancelled" for c in d.crs if c.status not in ENDED
    ]
    causes += [f"order {o.id} ({o.kind}) is open" for o in d.orders if not o.done]
    if d.stack_agent:
        causes.append(f"stack agent {d.stack_agent} is recorded")
    from chantier.costs.endings import transcript_endings  # noqa: PLC0415 - slow

    sessions = d.foreman_transcripts or ([d.foreman_transcript] if d.foreman_transcript else [])
    if d.host == "copilot":
        causes += _copilot_causes(repo, d)
        return causes, [], []
    stack = {d.stack_agent} if d.stack_agent else set()
    sessions = sorted(sessions, key=lambda s: [s] == [c.transcript for c in d.foreman_claims[-1:]])
    mine, others = transcript_endings(
        repo.session_root, sessions, chief_sessions(d), held_agents(d), stack
    )
    return causes, mine, others


def _copilot_causes(repo: Repo, d: BatchRecord) -> list[str]:
    """On Copilot no transcript says an agent ended: a held agent (a CR's, a QA order's, the
    stack's) with a live lease runs; one with no lease is not measured; and the Foreman's
    heartbeat younger than the lease's life shows it is there. A direct batch has none of these."""
    if d.mode == "direct":
        return []
    from chantier.core import leases  # noqa: PLC0415 - imports the rails

    causes = []
    units = [(c.agent, c.id, c.lease) for c in d.crs if c.agent]
    units += [(o.agent, o.id, o.lease) for o in d.orders if o.agent]
    if d.stack_agent:
        units.append((d.stack_agent, "stack", d.stack_lease))
    for agent, unit, lease in units:
        if lease is None:
            causes.append(f"{agent} ({unit}): not measured (no lease)")
        elif leases.liveness(repo, unit, lease).state == leases.LIVE:
            causes.append(
                f"{agent} ({unit}) holds lease {lease.n} until {leases.hms(lease.expires)}"
            )
    if d.heartbeat and not d.heartbeat_stopped:
        minutes = leases.minutes_ago(d.heartbeat)
        if minutes * 60 < leases.ttl_seconds():
            causes.append(
                f"Foreman n°{d.foreman_epoch}: heartbeat {minutes} min ago "
                f"(under {leases.ttl_seconds() // 60} min)"
            )
    return causes


def _owner(d: BatchRecord, name: str) -> str:
    """The CR or order id that holds the agent a `--stopped` name stands for; `<owner>` if none."""
    held = held_agents(d)
    keys = (name, f"agent-{name}", name.removeprefix("agent-"))
    return next((held[k] for k in keys if k in held), "<owner>")


def _declared(
    d: BatchRecord, endings: list[Ending], others: list[Ending], stopped: list[str]
) -> list[Ending]:
    """The held agents' transcripts the user's `--stopped` names, each one that reads as running;
    a name that matches none, an ended one or one that cannot be read is refused, as is a name of
    another transcript (a subagent the batch does not hold, a replaced Foreman) and of the
    recorded stack agent, which no flag passes (exit 2)."""
    chosen: list[Ending] = []
    for name in stopped:
        if d.stack_agent and d.stack_agent in {name, f"agent-{name}", name.removeprefix("agent-")}:
            raise ChantierError(
                f"close --stopped {name}: the stack agent is a record cause no flag passes; "
                "clear it: `agents set stack - --epoch <n>`. Nothing was deleted.",
                EXIT_PRECONDITION,
            )
        if any(name in {e.name, e.name.removeprefix("agent-")} for e in others) and not any(
            name in {e.name, e.name.removeprefix("agent-")} for e in endings
        ):
            raise ChantierError(
                f"close --stopped {name}: not an agent {d.id} holds; it does not block close, "
                f"drop the flag: `close` without `--stopped {name}`. Nothing was deleted.",
                EXIT_PRECONDITION,
            )
        match = next((e for e in endings if name in {e.name, e.name.removeprefix("agent-")}), None)
        if match is None:
            names = [e.name for e in endings if e.state == "running"]
            raise ChantierError(
                f"close --stopped {name}: no transcript of {d.id} by that name; still running: "
                f"{', '.join(names) or 'none'}. Nothing was deleted. "
                f"`close --stopped {name}` takes only a name listed as still running.",
                EXIT_PRECONDITION,
            )
        if match.state == "ended":
            raise ChantierError(
                f"close --stopped {name}: its transcript shows it ended; drop the flag: "
                f"`close` without `--stopped {name}`. Nothing was deleted.",
                EXIT_PRECONDITION,
            )
        if match.state == "unreadable":
            where = "no transcript found" if match.missing else str(match.path)
            raise ChantierError(
                f"close --stopped {name}: its transcript cannot be read ({where}), and the "
                "flag covers only an agent that reads as running. Nothing was deleted. "
                "If it is not "
                f"running, `agents set {_owner(d, name)} - --epoch <n>` clears it.",
                EXIT_PRECONDITION,
            )
        if match not in chosen:
            chosen.append(match)
    return chosen


def check_idle(
    repo: Repo, d: BatchRecord, stopped: list[str] | None = None
) -> tuple[list[Ending], list[Ending]]:
    """Refuse (exit 2) while anything the batch holds runs, with the causes and the files, and
    return (the agents the user declared stopped, the other transcripts that run or cannot be
    read, listed apart and never a cause). The rule: the transcript of a held agent (the current
    Foreman, each id `agents set` recorded and did not clear) that shows it still runs, or that
    cannot be read (a held id with no transcript included), refuses, whatever the file's age.
    `stopped` (`close --stopped`, on the user's word only): the names of held agents that read as
    running but ended with no hand-back; each drops out of the causes. Every other cause still
    refuses, and a name that is not a running held agent is refused."""
    causes, endings, others = running(repo, d)
    declared = _declared(d, endings, others, stopped or [])
    causes += [e.text() for e in endings if e.state != "ended" and e not in declared]
    if causes:
        hint = (
            f" {STOPPED_HINT}."
            if any(e.state == "running" and e not in declared for e in endings)
            else ""
        )
        raise ChantierError(
            f"cannot close {d.id}, something still runs: "
            + "; ".join(causes)
            + f". Nothing was deleted. Run `close` again once none of these runs.{hint}",
            EXIT_PRECONDITION,
        )
    return declared, [e for e in others if e.state != "ended"]
