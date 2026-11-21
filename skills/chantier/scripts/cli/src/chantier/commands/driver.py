"""The Driver's commands: `take`, `round`, `handback`, `note` and `log`."""

from __future__ import annotations

import argparse
from pathlib import Path

from chantier.commands.carry import head_base
from chantier.commands.crs import (
    batch_cr,
    cr_events,
    cr_worktree,
    short_head,
    work,
)
from chantier.commands.driver_checks import (
    GateBasis,
    handback_args,
    handback_blocked,
    handback_refusals,
    live_cr,
    wait_specs,
)
from chantier.commands.endpause import end_of_batch
from chantier.commands.facts import cr_facts, stack_lines
from chantier.commands.take_checks import check_take_all
from chantier.commands.waits import add_to_cr
from chantier.core import leases
from chantier.core.batch import Batch, check_epoch, find_cr_batch, require_epoch, resolve_batch
from chantier.core.clock import now, stamp
from chantier.core.errors import ChantierError
from chantier.core.records import LIVE, BatchRecord, CrEntry
from chantier.core.repo import Repo
from chantier.driver_prompt import DriverBlock, driver_prompt_lines, driver_row
from chantier.hub import journal
from chantier.hub.autostart import not_running_line
from chantier.lifecycle.session import RenderedBatch
from chantier.lifecycle.stages import changes_lock, cr_directory, done_cr, start_cr
from chantier.playbook.lines import team_lines, timing_lines
from chantier.plugin_files import archive_path, cli_command, recorded_timing
from chantier.rails import (
    all_merged,
    check_budget,
    check_round,
    check_stray_round,
    held,
    worktree_print,
)
from chantier.stack_words import PR_IN_DRAFT, READY_TO_MERGE, draft_clause, ready_word
from chantier.stacks import stack_base, start_on_for
from chantier.status.views import shown_title


def _reopen(b: Batch) -> list[str]:
    """A take on a paused batch sets it running again: its pause and cost to date are void."""
    if b.record.status != "paused":
        return []
    b.record.status = "running"
    b.record.unset("paused")
    b.record.unset("summary")
    b.log("reopen", None)
    return [f"{b.id} was paused: running again; `pause --epoch <n>` runs again at the end"]


def _take_stack(
    repo: Repo, b: RenderedBatch, batch: str, args: argparse.Namespace, fresh: list[str]
) -> list[str]:
    """The stack's driver is taken: the batch must be a stack with no driver recorded."""
    d, note, reclaim = b.record, args.note, bool(args.reclaim)
    if d.mode != "stack":
        raise ChantierError(f"batch {batch} is not a stack")
    if d.stack_agent:
        raise ChantierError(
            f"a stack driver is recorded ({d.stack_agent}); one "
            "that ended: `agents set stack - --epoch <n>` first (a stack driver "
            "reads the stack with `stack`, which changes nothing)"
        )
    row = driver_row(d.host, "take stack")  # before any state changes
    check_budget(d)
    old = leases.check_free(repo, d, "stack", reclaim)
    reopened = _reopen(b)
    leases.reclaim(b, "stack", old)
    lease = leases.start(d, "stack")
    b.log("take", None, note=note, lease=lease.n)
    head, *rows = stack_lines(repo, batch, d)
    rows += timing_lines(recorded_timing(d), d.host)  # after the CR rows, as `take <cr>` prints
    block = DriverBlock(
        {"<batch>": batch, "<root>": repo.root.as_posix()},
        f"{cli_command(repo)} <command> --batch {batch}",
        [head, *rows],
        team=team_lines(d.playbook),
        note=note,
        lease=(
            f"lease: stack {lease.n} (pass --lease {lease.n} on stack <crs>, --out-of-draft, "
            f"--draft and forge-stack create|rebuild|unstack; renew at each wake: lease stack "
            f"renew --lease {lease.n}; run a long gate under lease stack hold --lease {lease.n} "
            "-- <command>)"
        ),
    )
    watch = not_running_line(repo) if reopened else []
    return [head, *reopened, *rows, *driver_prompt_lines(row, d, block), *fresh, *watch]


def _cr_driver_block(repo: Repo, batch: str, c: CrEntry, facts: list[str]) -> DriverBlock:
    """The CR Driver's block: the facts after the `cli:` line, and `writes:` the CR folder then,
    when `take` prints an archive path, the archive in the CR's worktree, both absolute."""
    writes = cr_directory(repo, c).as_posix()
    if archive := archive_path(repo, c):
        writes += f"; {Path(c.worktree, archive).as_posix()}/"
    title = shown_title(repo.store, c.title, cr_directory(repo, c))
    fill = {"<cr>": c.id, "<title>": title, "<batch>": batch, "<root>": repo.root.as_posix()}
    return DriverBlock(fill, facts[1].removeprefix("cli: "), facts[2:], writes)


def _start_work(repo: Repo, b: Batch, c: CrEntry) -> None:
    """`1-pending` to `2-actives`, before the Driver gets its facts; the archive's name, kept
    from the first take; the work folder."""
    start_cr(b, c)
    if repo.external:
        c.archive_stamp = c.archive_stamp or stamp()
    repo.store.make_folder(repo.rel(work(repo, c)), True)


def take(args: argparse.Namespace) -> list[str]:
    """The Foreman gives a CR to a Driver (or the stack to its driver): the rails refuse what the
    batch does not allow (a slot, the budget, a CR that has nothing to do), the state records
    it, and the CR's facts are printed for the prompt. The Foreman chooses the agent."""
    require_epoch(args.epoch, f"take {args.cr} --epoch <n>")
    repo = Repo.find()
    if args.cr == "stack":
        batch = resolve_batch(repo, args.batch)
    else:
        batch = find_cr_batch(repo, args.cr, args.batch)
    from chantier.commands.batch_status import refresh_for_check  # noqa: PLC0415 - slow import

    fresh = refresh_for_check(repo, batch, "foreman")  # the budget is checked on the real spend
    with changes_lock(repo), RenderedBatch(repo, batch, actor="foreman") as b:
        check_epoch(b, args.epoch)
        d = b.record
        if args.cr == "stack":
            return _take_stack(repo, b, batch, args, fresh)
        c = b.cr(args.cr)
        old = check_take_all(repo, d, c, note=args.note, reclaim=bool(args.reclaim))
        row = driver_row(d.host, "take <cr>", c.kind)  # before any state changes
        reopened = _reopen(b)
        leases.reclaim(b, c.id, old)
        lease = leases.start(d, c.id)
        restart = c.status == "working"  # a new Driver on a CR already working
        if c.status in {"ready", "blocked", "working"}:
            c.append("notes", f"back to a Driver: {args.note}")
        landed = journal.seen_merged(journal.read(repo.changes)[0], d)
        if c.status == "queued" and (start_on := start_on_for(d, c, landed)):
            c.start_on = start_on  # the start base is fixed at the first take
        b.touch(c, status="working", blocked_reason=None)
        c.clear_phase()
        b.log("take", c.id, note=args.note, lease=lease.n, **({"restart": True} if restart else {}))
        _start_work(repo, b, c)
        facts = cr_facts(repo, batch, d, c, landed)
        block = _cr_driver_block(repo, batch, c, facts)
        block.team, block.note = team_lines(d.playbook), args.note
        block.lease = leases.driver_line(c.id, lease)
        skeleton = driver_prompt_lines(row, d, block)
    return [
        f"took {c.id} ({len(held(d))} of {d.slots} slots held), lease {lease.n} until "
        f"{leases.hms(lease.expires)}",
        *reopened,
        *facts,
        *skeleton,
        *fresh,
        *(not_running_line(repo) if reopened else []),
    ]


def round_(args: argparse.Namespace) -> list[str]:
    """A Driver counts a round before it starts the round's Coder; once the budget is spent, or
    past the batch's limit or the one the user granted the CR, it is refused (exit 5), the
    budget first (its own message), the round count unchanged and nothing logged. A round on
    which nothing happened since the last one is refused too (exit 2). Prints the Driver's
    context size. The round event keeps the worktree's head and a fingerprint of its content."""
    repo = Repo.find()
    batch = find_cr_batch(repo, args.cr, args.batch)
    from chantier.commands.batch_status import refresh_for_check  # noqa: PLC0415 - slow import

    fresh = refresh_for_check(repo, batch, "driver")  # the budget is checked on the real spend
    with changes_lock(repo), RenderedBatch(repo, batch, actor="driver") as b:
        c = b.cr(args.cr)
        if c.status not in LIVE:
            raise ChantierError(f"{args.cr} is {c.status}: no Driver to run a round")
        leases.claim(b, c.id, args.lease, what=f"round {c.id}", required=True)
        limit = check_round(b.record, c)  # the budget first, then the limit
        wt = Path(c.worktree) if c.worktree else None
        seen = worktree_print(wt)
        check_stray_round(cr_events(repo, batch, c.id), c, seen)  # then a stray round
        repo.check_publish([work(repo, c)])
        b.touch(c, round=c.round + 1, phase="coder", phase_at=now())
        c.unset("phase_detail")
        b.log("round", c.id, round=c.round, note=args.note, **seen)
        repo.store.make_folder(repo.rel(work(repo, c)), True)
        facts = cr_facts(repo, batch, b.record, c)
        context = context_line(repo, b.record, c.agent)
    return [f"round {c.round} of {limit} for {c.id}", *facts, context, *fresh]


def context_line(repo: Repo, d: BatchRecord, agent: str | None) -> str:
    """The context size of an agent (a CR's Driver, or the stack driver): the last call's prompt,
    read from the end of its transcript. Not an error when it cannot be measured."""
    from chantier.commands.cost.sessions import foreman_uuid  # noqa: PLC0415 - slow import
    from chantier.costs.sessions import agent_context  # noqa: PLC0415 - slow import

    if not agent:
        return "context: not measured (no agent recorded)"
    if d.host == "copilot":
        return "context: not measured (Copilot gives no per-agent record)"
    try:
        sessions = foreman_uuid(d)
    except ChantierError:
        return "context: not measured (no steering transcript recorded)"
    n = agent_context(repo.session_root, sessions, agent)
    if n is None:
        return f"context: not measured (no transcript found for agent {agent})"
    return f"context: {n} tokens (agent {agent})"


def handback(args: argparse.Namespace) -> list[str]:
    """A Driver's end, in the state first: `ready <link>` or `blocked <reason>`. Prints the line
    to send the Foreman, and what the state did with it; a release that ends the batch's last CR
    cleans and pauses the batch, once the locks are released."""
    repo = Repo.find()
    note = " ".join(args.note).strip()
    no_gate = handback_args(args, note)
    wait_specs(args)  # a refusal before anything is written
    ended: list[str] = []
    lines = _handback_locked(repo, args, (note, no_gate), ended)
    return [*lines, *(end_of_batch(repo, ended[0], f"handback {args.cr}") if ended else [])]


def _handback_locked(
    repo: Repo, args: argparse.Namespace, said_args: tuple[str, str | None], ended: list[str]
) -> list[str]:
    note, no_gate = said_args
    with (
        changes_lock(repo),
        RenderedBatch(repo, find_cr_batch(repo, args.cr, args.batch), actor="driver") as b,
    ):
        c = live_cr(b, args.cr, args.result)
        was_blocked = c.status == "blocked"  # a ready hand-back from the Driver that blocked
        if not was_blocked:  # a blocked hand-back ended the lease already
            leases.claim(b, c.id, args.lease, what=f"handback {c.id}", required=True)
        leases.end(c.lease)  # a hand-back, ready or blocked, ends it; a refusal below saves nothing
        reason = c.blocked_reason or ""
        line = f"[driver {args.cr}→foreman] hand-back {args.result} {note}"
        if args.result == "blocked":
            specs = wait_specs(args)
            applied = add_to_cr(repo, b.record, c, specs, note) if specs else ([], [])
            return handback_blocked(b, c, note, line, applied)
        # a release with an unmerged PR recorded: the release PR is prepared and waits for
        # its merge (the checks of a CR, no verdict); with none, it is released
        prepared = c.kind == "release" and bool(c.pr)
        if c.kind == "release" and not prepared:  # released: nothing is left to merge
            c.released = note.split()[0]
            b.log("handback", args.cr, result=args.result, note=note)
            done_cr(b, c)
            b.touch(c, status="merged")
            if all_merged(b.record):
                ended.append(b.id)
            return [line, f"{args.cr} released, in 3-done"]
        if not c.pr:
            raise ChantierError(f"{args.cr}: ready means a PR recorded (`chantier ship`)")
        basis = handback_refusals(repo, b, c, no_gate, prepared)
        said = (note, no_gate, prepared)
        return _record_ready(repo, b, c, said, (basis, reason if was_blocked else ""))


def _record_ready(
    repo: Repo,
    b: RenderedBatch,
    c: CrEntry,
    said: tuple[str, str | None, bool],
    basis_reason: tuple[GateBasis, str],
) -> list[str]:
    """The ready hand-back in the record; `reason` is the block it ends, when the CR was blocked,
    and `basis` the long gate's basis: a carried head, or a waiver."""
    note, no_gate, prepared = said
    basis, reason = basis_reason
    carried = basis.carried
    keys = {"no_gate": no_gate} if no_gate is not None else {}
    b.log(
        "handback",
        c.id,
        result="ready",
        note=note,
        **keys,
        **basis.event_keys(),
        **({"from_blocked": reason} if reason else {}),
    )
    if reason:
        c.append("notes", f"ready after blocked: {reason}")
    b.touch(c, status="ready", **({"blocked_reason": None} if reason else {}))
    c.clear_phase()
    gate = f", no long gate: {no_gate}" if no_gate is not None else ""
    if basis.waiver:
        gate = f", {basis.words()}"
    vcarried = basis.verdict_carried
    onto = head_base(repo, b.record, c, cr_worktree(c), str(c.head))
    how = f"(clean rebase onto {onto.branch if onto else stack_base(b.record, c, repo)})"
    if carried and carried == vcarried:
        gate = f", long gate and verdict carried from {short_head(carried)} {how}"
    else:
        if carried:
            gate = f", long gate carried from {short_head(carried)} {how}"
        if vcarried:
            gate += f", verdict carried from {short_head(vcarried)} {how}"
    lines = _ready_lines(repo, b.record, c, prepared, f"{gate} {note}")
    if reason:
        lines[-1] += f"; it was blocked: {reason}"
    return lines


def _ready_lines(repo: Repo, d: BatchRecord, c: CrEntry, prepared: bool, tail: str) -> list[str]:
    """The line to send the Foreman and the CR's state, in the word the record derives: ready to
    merge, or PR in draft with what its PR waits on."""
    word = ready_word(d, c, repo) or PR_IN_DRAFT
    line = f"[driver {c.id}→foreman] hand-back {word}{tail}"
    if word == READY_TO_MERGE:
        wait = f": the release PR {c.pr} waits for its merge" if prepared else ""
        return [line, f"{c.id} {word}{wait}"]
    return [line, f"{c.id} {word}: {draft_clause(d, c, repo, prepared)}"]


def log(args: argparse.Namespace) -> list[str]:
    """The CR's events, readable: what happened and when."""
    repo = Repo.find()
    batch, _, c = batch_cr(repo, args.cr, args.batch)
    lines = []
    for e in cr_events(repo, batch, c.id):
        rest = {
            k: v
            for k, v in e.to_data().items()
            if k not in {"t", "actor", "kind", "cr"} and v not in (None, "", [])
        }
        lines.append(
            f"{e.t} {e.actor} {e.kind}"
            + (" " + " ".join(f"{k}={v}" for k, v in rest.items()) if rest else "")
        )
    return lines or [f"no event for {c.id}"]
