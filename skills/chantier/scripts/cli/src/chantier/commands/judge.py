"""`chantier judge <cr> --epoch N`: the steering session's ask to the user for a CR handed back,
worded from the record only (`status/judge_words.py`). With no `--record` it writes nothing; with
`--record` it records the ask as `asks` does, with the steering session's one sentence appended.
It decides no merge and no take-back, reads no forge and runs no git."""

from __future__ import annotations

import argparse

from chantier.commands.activity import stopped_agents
from chantier.commands.wait_view import wait_line
from chantier.core.batch import check_epoch, find_cr_batch, read_batch, require_epoch, stale_epoch
from chantier.core.errors import EXIT_PRECONDITION, ChantierError
from chantier.core.records import BatchRecord, CrEntry, EventRecord, read_events
from chantier.core.repo import Repo
from chantier.lifecycle.session import RenderedBatch
from chantier.rails_release import record_ask
from chantier.stacks import chain
from chantier.status.judge_words import (
    ask_text,
    local_gate_clause,
    stack_open,
    stack_pairs,
)
from chantier.status.ready_line import ready_line

DECIDE = (
    'decide: send it with `judge {cr} --record ["<one sentence>"] --epoch {n}`, or take it back '
    'with `take {cr} --note "…" --epoch {n}`; the merge is the user\'s'
)


def _cr(d: BatchRecord, cr: str) -> CrEntry:
    found = next((x for x in d.crs if x.id == cr), None)
    if found is None:
        raise ChantierError(
            f"judge {cr}: {cr} is not in {d.id}; `status` shows the batch", EXIT_PRECONDITION
        )
    return found


def _no_ask(
    repo: Repo, d: BatchRecord, c: CrEntry, events: list[EventRecord], local_gate: bool
) -> tuple[str, list[str]]:
    """(why, the facts) of a CR that gets no ask."""
    if c.status == "blocked":
        notes = [e for e in events if e.cr == c.id and e.kind == "handback" and e.result != "ready"]
        why = (
            f"{c.id} handed back blocked; taking it back or carrying it is yours (`take {c.id} "
            f'--note "…" --epoch {d.foreman_epoch}`, or `asks "blocked {c.id} <reason>"`)'
        )
        return "blocked", [f"no ask: {why}", *([f"blocked: {notes[-1].note}"] if notes else [])]
    ids = ", ".join(x.id for x in stack_open(d, c))
    why = (
        f"{c.id} is in {d.id}'s stack and not alone (open: {ids}); its readiness goes up with the "
        f'stack\'s: `forge-stack show`, then `asks "stack-ready-to-merge …"`'
    )
    out = [f"no ask: {why}", f"for the stack's ask: {stack_pairs(d, events)}"]
    if local_gate:
        out.append(local_gate_clause(chain(d)[-1], events))
    return "in the stack", out


def judge(args: argparse.Namespace) -> list[str]:
    repo = Repo.find()
    cr = args.cr
    require_epoch(args.epoch, f"judge {cr} --epoch <n>")
    try:
        batch = find_cr_batch(repo, cr, args.batch)
    except ChantierError as e:
        raise ChantierError(f"judge {cr}: {e}; `status` shows the batch", EXIT_PRECONDITION) from e
    d = read_batch(repo, batch)
    stale_epoch(d.id, d.foreman_epoch, args.epoch)
    c = _cr(d, cr)
    events = read_events(repo.store, repo.batch_dir(batch))
    if c.status not in ("ready", "blocked"):
        raise ChantierError(
            f"judge {cr}: {cr} is {c.status}, not handed back; nothing to word yet; `status` "
            "shows the batch",
            EXIT_PRECONDITION,
        )
    stopped = stopped_agents(repo, d, events)
    text = ask_text(repo, d, c, events, stopped, args.local_gate)
    out: list[str] = []
    why = ""
    if text is None:
        why, facts = _no_ask(repo, d, c, events, args.local_gate)
        out += facts
    else:
        out += [f"ask: {text}", ready_line(repo, d, c, events, stopped)]
    if (waits := wait_line(repo, d, c)) is not None:
        out.append(waits)
    if args.record is None:
        if text is not None:
            out.append(DECIDE.format(cr=cr, n=args.epoch))
        return out
    if text is None:
        raise ChantierError(
            f'judge {cr} --record: no ask to record ({why}); `asks "<text>"` records your own',
            EXIT_PRECONDITION,
        )
    return _record(repo, batch, args)  # the lines `asks` prints, in place of the ask and facts


def _record(repo: Repo, batch: str, args: argparse.Namespace) -> list[str]:
    with RenderedBatch(repo, batch, actor="foreman") as b:
        check_epoch(b, args.epoch)
        c = _cr(b.record, args.cr)
        events = read_events(repo.store, repo.batch_dir(batch))
        text = ask_text(
            repo, b.record, c, events, stopped_agents(repo, b.record, events), args.local_gate
        )
        if text is None:
            raise ChantierError(
                f"judge {args.cr} --record: no ask to record (the record changed); "
                '`asks "<text>"` records your own',
                EXIT_PRECONDITION,
            )
        note = " ".join(args.record.split())
        aid, old = record_ask(b, text + (f" | note: {args.record}" if note else ""))
        return [
            f"[foreman→chief-of-staff] ask {aid}: {b.record.asks[-1].text}",
            *[f"{o} superseded by {aid} (marked read)" for o in old],
        ]
