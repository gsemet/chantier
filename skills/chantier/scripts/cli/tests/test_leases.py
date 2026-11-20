"""Driver leases: what `take` gives, what each command asks of it, and when it stops holding."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Protocol, cast

import pytest
from batch_helpers import DEAD, changes, events, open_batch, record, write_record
from conftest import Chantier

from chantier.commands.closing import _live_lease_lines
from chantier.core import clock, leases
from chantier.core.errors import EXIT_CONFLICT, EXIT_PRECONDITION
from chantier.core.records import read_batch_json
from chantier.core.repo import Repo
from chantier.rails_idle import running

T0 = "2030-01-01T00:00:00Z"  # a lease taken at T0 expires at 00:10:00
SECOND, THIRD, LATE_MINUTES, CHILD_EXIT = 2, 3, 5, 7


class Cli(Protocol):
    """The `chantier` fixture: `bare` runs a command as typed, with no lease added."""

    def __call__(self, *args: object) -> tuple[int, list[str], str]: ...

    def bare(self, *args: object) -> tuple[int, list[str], str]: ...


Led = tuple[Path, Cli, list[str]]


@pytest.fixture
def leased(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch) -> Led:
    """A batch of two CRs, the clock frozen at T0, CR one taken: its lease 1 is live."""
    monkeypatch.setattr(clock, "_fixed", [])
    clock.fix(T0)
    ids = open_batch(repo, chantier, monkeypatch, "Lease one", "Lease two", args=("--slots", 2))
    cli = cast(Cli, chantier)
    code, out, err = cli.bare("take", ids[0], "--epoch", 1)
    assert code == 0, err
    assert out[0].endswith(", lease 1 until 00:10:00"), out[0]
    return repo, cli, ids


def at(minutes: float) -> None:
    clock.fix(clock.after(int(minutes * 60), T0))


def cr_of(repo: Path, cr: str) -> dict[str, Any]:
    return next(c for c in record(repo)["crs"] if c["id"] == cr)


def test_take_refuses_a_live_or_not_confirmed_lease_and_reclaim_starts_the_next(
    leased: Led,
) -> None:
    repo, chantier, (one, _) = leased
    resume = ("take", one, "--note", "resume: stuck", "--epoch", 1)
    at(5)
    before = record(repo)
    code, _, err = chantier.bare(*resume)
    assert code == EXIT_CONFLICT and "is held: lease 1 live until 00:10:00" in err
    assert "--reclaim only on the user's word" in err and record(repo) == before
    at(11)
    code, _, err = chantier.bare(*resume)
    assert code == EXIT_CONFLICT and "lease 1 not confirmed since 00:10 (1 min ago)" in err
    assert "check with the host that its Driver ended, then take it with --reclaim" in err
    code, out, err = chantier.bare(*resume, "--reclaim")
    assert code == 0, err
    assert out[0].endswith(", lease 2 until 00:21:00") and "lease: 2 (" in "\n".join(out)
    lease = cr_of(repo, one)["lease"]
    assert lease["n"] == SECOND and lease["ended"] is None
    assert next(e for e in events(repo) if e["kind"] == "reclaim")["lease"] == 1


GUARDED = [
    ("round", "{cr}"),
    ("ship", "{cr} https://example.invalid/pr/1"),  # no worktree: only the missing number
    ("handback", "{cr} ready https://example.invalid/pr/1 --no-gate x"),
    ("handback", "{cr} blocked why"),
]


@pytest.mark.parametrize(("command", "rest"), GUARDED)
def test_a_guarded_command_needs_the_lease_and_a_stale_one_is_lost(
    leased: Led, command: str, rest: str
) -> None:
    repo, chantier, (one, _) = leased
    argv = [command, *rest.format(cr=one).split()]
    code, _, err = chantier.bare(*argv)
    assert code == EXIT_PRECONDITION and f"{command} " in err and "needs --lease <n>" in err
    if command == "ship":
        return
    at(11)
    assert chantier.bare("take", one, "--note", "resume: x", "--reclaim", "--epoch", 1)[0] == 0
    before = record(repo)
    code, _, err = chantier.bare(*argv, "--lease", 1)
    assert code == EXIT_CONFLICT and "claim lost" in err and "was taken again (lease 2)" in err
    assert "stop now: nothing recorded" in err and record(repo) == before


def test_a_not_confirmed_current_lease_is_accepted_late_and_a_handback_ends_it(
    leased: Led,
) -> None:
    repo, chantier, (one, _) = leased
    at(15)
    assert chantier.bare("round", one, "--lease", 1)[0] == 0
    late = [e for e in events(repo) if e["kind"] == "lease-late"]
    assert late and late[0]["lease"] == 1 and late[0]["minutes"] == LATE_MINUTES
    assert cr_of(repo, one)["lease"]["expires"] == "2030-01-01T00:25:00Z"  # renewed
    code, _, err = chantier.bare("handback", one, "blocked", "stop", "--lease", 1)
    assert code == 0, err
    assert cr_of(repo, one)["lease"]["ended"] == "2030-01-01T00:15:00Z"
    code, _, err = chantier.bare("note", one, "more", "--lease", 1)
    assert code == EXIT_CONFLICT and "ended at 00:15" in err


def test_a_ship_of_a_cr_whose_lease_ended_needs_no_number(
    leased: Led,
) -> None:
    """The stack driver restacks a CR handed back: it holds the stack's lease, not the CR's."""
    _, chantier, (one, _) = leased
    argv = ["ship", one, "https://example.invalid/pr/1"]
    assert chantier.bare("handback", one, "blocked", "stop", "--lease", 1)[0] == 0
    _, _, err = chantier.bare(*argv)
    assert "needs --lease" not in err, err  # past the lease check: it stops at the worktree


def test_a_batch_with_no_lease_needs_no_lease_and_take_gives_the_next_its_own(
    leased: Led,
) -> None:
    repo, chantier, (one, two) = leased
    data = record(repo)
    data["crs"] = [{k: v for k, v in c.items() if k != "lease"} for c in data["crs"]]
    write_record(repo, data)
    assert chantier.bare("round", one)[0] == 0  # opened before leases
    assert chantier.bare("take", two, "--epoch", 1)[0] == 0
    assert cr_of(repo, two)["lease"]["n"] == 1


def test_the_stack_drivers_writing_forms_need_its_lease_and_its_reading_forms_none(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(clock, "_fixed", [])
    clock.fix(T0)
    args = ("--mode", "stack")
    one, two = open_batch(repo, chantier, monkeypatch, "Stack a", "Stack b", args=args)
    cli = cast(Cli, chantier)
    code, out, err = cli.bare("take", "stack", "--epoch", 1)
    assert code == 0, err
    assert any(ln.strip().startswith("lease: stack 1 (") for ln in out), out
    assert record(repo)["stack_lease"]["n"] == 1
    assert cli.bare("stack", one, two)[0] == EXIT_PRECONDITION
    assert cli.bare("stack", "--out-of-draft", one)[0] == EXIT_PRECONDITION
    assert cli.bare("forge-stack", "create")[0] == EXIT_PRECONDITION
    assert cli.bare("forge-stack", "rebuild")[0] == EXIT_PRECONDITION
    assert cli.bare("stack")[0] == 0  # bare `stack` reads
    code, _, err = cli.bare("stack", one, two, "--lease", 1)
    assert code == 0, err
    assert cli.bare("agents", "set", "stack", "-", "--epoch", 1)[0] == 0
    assert record(repo)["stack_lease"]["ended"]
    code, _, err = cli.bare("stack", one, two, "--lease", 1)
    assert code == EXIT_CONFLICT and "claim lost" in err


def test_the_lease_command_shows_renews_and_runs_a_command_under_it(leased: Led) -> None:
    repo, chantier, (one, _) = leased
    code, out, _ = chantier.bare("lease", one)
    assert code == 0 and out == [f"lease 1 of {one}: live until 00:10:00 (renewed 00:00:00)"]
    at(4)
    code, out, _ = chantier.bare("lease", one, "renew", "--lease", 1)
    assert code == 0 and out == [f"lease 1 of {one}: live until 00:14:00 (renewed 00:04:00)"]
    assert chantier.bare("lease", one, "renew", "--lease", 9)[0] == EXIT_CONFLICT
    at(30)
    assert "not confirmed since 00:14 (16 min ago)" in chantier.bare("lease", one)[1][0]
    marker = repo / "ran.txt"
    write = f"import pathlib; pathlib.Path({str(marker)!r}).write_text('x')"
    child = f"import sys; {write}; sys.exit({CHILD_EXIT})"
    hold = ("lease", one, "hold", "--lease")
    code, _, err = chantier.bare(*hold, 9, "--", sys.executable, "-c", child)
    assert code == EXIT_CONFLICT and not marker.exists(), err  # a stale number runs nothing
    code, _, err = chantier.bare(*hold, 1, "--", sys.executable, "-c", child)
    assert code == CHILD_EXIT and marker.read_text() == "x"  # the child's own exit code
    assert not list(changes(repo).glob(".lease-hold.*.run"))
    assert cr_of(repo, one)["lease"]["expires"] == "2030-01-01T00:40:00Z"  # renewed at its end


def test_a_long_gate_a_queue_ticket_or_a_hold_keeps_an_expired_lease_live(
    leased: Led, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, chantier, (one, _) = leased
    at(30)
    assert "not confirmed" in chantier.bare("lease", one)[1][0]
    queue = changes(repo) / ".long-gate.queue"
    queue.mkdir()
    ticket = queue / "0001"
    ticket.write_text(f"{one} pid {DEAD}\n", encoding="utf-8")
    assert "not confirmed" in chantier.bare("lease", one)[1][0]  # a dead ticket holds nothing
    ticket.write_text(f"{one} pid {os.getpid()}\n", encoding="utf-8")
    assert chantier.bare("lease", one)[1][0].endswith("gate queued")
    ticket.unlink()
    slot = SimpleNamespace(holder=SimpleNamespace(cr=one), slot=SimpleNamespace(lock=None))
    with monkeypatch.context() as patch:
        patch.setattr("chantier.gate_slots.slot_of", lambda _repo, _cr: slot)
        patch.setattr("chantier.gate_slots.holder_alive", lambda *_: True)
        assert chantier.bare("lease", one)[1][0].endswith("gate running")
    clock.fix(clock.after(30 * 60, T0))
    dead = changes(repo) / f".lease-hold.{one}.1.run"
    dead.write_text(json.dumps({"unit": one, "lease": 1, "pid": DEAD}), encoding="utf-8")
    _, out, err = chantier.bare("lease", one)
    assert "not confirmed" in out[0] and not dead.exists(), err
    where = SimpleNamespace(changes=changes(repo))
    path = leases.write_hold(where, one, 1, ["x"])  # type: ignore[arg-type]
    assert "held by 1 background task(s)" in chantier.bare("lease", one)[1][0]
    path.unlink()


def test_a_qa_orders_lease_starts_with_the_order_and_a_restart_needs_it_free(
    leased: Led,
) -> None:
    repo, chantier, _ = leased
    code, out, err = chantier.bare("order", "qa", "--note", "check it")
    assert code == 0, err
    order = record(repo)["orders"][-1]
    oid = order["id"]
    assert order["lease"]["n"] == 1 and f"lease: 1 of {oid}" in "\n".join(out)
    code, out, err = chantier.bare("agents", "set", oid, "qa-agent", "--epoch", 1)
    assert code == 0 and not any("lease" in x for x in out), err  # the first keeps lease 1
    assert chantier.bare("agents", "set", oid, "-", "--epoch", 1)[0] == 0  # live: ended
    assert record(repo)["orders"][-1]["lease"]["ended"]
    code, out, _ = chantier.bare("agents", "set", oid, "qa-2", "--epoch", 1)
    assert code == 0 and out[1].startswith(f"lease 2 of {oid}: live until")
    at(11)
    code, _, err = chantier.bare("agents", "set", oid, "-", "--epoch", 1)
    assert code == 0 and record(repo)["orders"][-1]["lease"]["ended"] is None  # not confirmed
    code, _, err = chantier.bare("agents", "set", oid, "qa-3", "--epoch", 1)
    assert code == EXIT_CONFLICT and "not confirmed" in err
    assert chantier.bare("agents", "set", oid, "qa-3", "--reclaim", "--epoch", 1)[0] == 0
    assert record(repo)["orders"][-1]["lease"]["n"] == THIRD
    assert chantier.bare("order", "done", oid, "--epoch", 1)[0] == 0
    assert record(repo)["orders"][-1]["lease"]["ended"]


def test_a_clearance_before_any_agent_does_not_make_the_first_real_set_a_restart(
    leased: Led,
) -> None:
    repo, chantier, _ = leased
    chantier.bare("order", "qa", "--note", "check it")
    oid = record(repo)["orders"][-1]["id"]
    assert chantier.bare("agents", "set", oid, "-", "--epoch", 1)[0] == 0  # ends lease 1
    code, out, err = chantier.bare("agents", "set", oid, "qa-agent", "--epoch", 1)
    assert code == 0, err  # the first real set: no refusal; the ended lease is replaced
    assert out[1].startswith(f"lease 2 of {oid}: live until")
    code, _, err = chantier.bare("agents", "set", oid, "qa-2", "--epoch", 1)
    assert code == EXIT_CONFLICT, err  # now a restart: lease 2 is live


def test_agents_set_dash_and_a_cancel_end_a_lease_and_the_old_driver_is_told(
    leased: Led,
) -> None:
    repo, chantier, (one, two) = leased
    assert chantier.bare("agents", "set", one, "-", "--epoch", 1)[0] == 0
    assert cr_of(repo, one)["lease"]["ended"] == T0
    assert chantier.bare("round", one, "--lease", 1)[0] == EXIT_CONFLICT
    assert chantier.bare("take", two, "--epoch", 1)[0] == 0
    code, _, err = chantier.bare("order", "drop", two, "--note", "trash")
    assert code == 0, err
    assert cr_of(repo, two)["lease"]["ended"] == T0


def test_status_names_a_lease_that_is_not_confirmed_and_handoff_prints_its_line(
    leased: Led,
) -> None:
    _, chantier, (one, _) = leased
    assert "lease not confirmed" not in "\n".join(chantier.bare("status")[1])
    at(13)
    rows = "\n".join(chantier.bare("status")[1])
    assert "lease not confirmed since 00:10 (3 min ago)" in rows
    shown = "\n".join(chantier.bare("handoff", one)[1])
    assert f"lease 1 of {one}: not confirmed since 00:10" in shown


HOLDS = "{agent} ({cr}) holds lease 1 until 00:10:00"
NO_LEASE = "{agent} ({cr}): not measured (no lease)"
BEAT = "Foreman n°1: heartbeat 5 min ago (under 10 min)"
# (label, host, mode, minutes after the take, the CR's lease kept, heartbeat minutes ago, causes)
CLOSE_CASES = [
    ("live lease", "copilot", "parallel", 5, True, None, [HOLDS]),
    ("not confirmed", "copilot", "parallel", 15, True, None, []),
    ("no lease", "copilot", "parallel", 5, False, None, [NO_LEASE]),
    ("heartbeat under", "copilot", "parallel", 15, True, 5, [BEAT]),
    ("heartbeat over", "copilot", "parallel", 15, True, 15, []),
    ("direct batch", "copilot", "direct", 5, True, 5, []),
    ("claude, live lease", "claude", "parallel", 5, True, None, []),
]


@pytest.mark.parametrize("case", [c[1:] for c in CLOSE_CASES], ids=[c[0] for c in CLOSE_CASES])
def test_copilot_close_causes_come_from_leases_and_the_foremans_heartbeat(
    leased: Led, case: tuple[Any, ...]
) -> None:
    repo, _, (one, _) = leased
    host, mode, minutes, keep, beat, expected = case
    data = record(repo)
    taken = next(c for c in data["crs"] if c["id"] == one)
    taken["agent"] = "agent-a"
    if not keep:
        taken.pop("lease")
    data.update(host=host, mode=mode, heartbeat=None)
    at(minutes)
    if beat is not None:
        data["heartbeat"] = clock.after(-beat * 60)
    write_record(repo, data)
    causes, _, _ = running(Repo.find(), read_batch_json(changes(repo) / "4-batch" / "batch.json"))
    ours = [x for x in causes if "lease" in x or "heartbeat" in x or "not measured" in x]
    assert ours == [x.format(agent="agent-a", cr=one) for x in expected], causes


# (label, the unit's lease kept, minutes after the take, causes)
UNIT_CASES = [
    ("live", True, 5, ["{agent} ({unit}) holds lease 1 until 00:10:00"]),
    ("not confirmed", True, 15, []),
    ("no lease", False, 5, ["{agent} ({unit}): not measured (no lease)"]),
]


@pytest.mark.parametrize("unit", ["order", "stack"])
@pytest.mark.parametrize("case", [c[1:] for c in UNIT_CASES], ids=[c[0] for c in UNIT_CASES])
def test_copilot_close_reads_a_qa_orders_and_the_stack_agents_lease(
    leased: Led, unit: str, case: tuple[Any, ...]
) -> None:
    repo, chantier, _ = leased
    keep, minutes, expected = case
    if unit == "order":
        chantier.bare("order", "qa", "--note", "check it")
    data = record(repo)
    data.update(host="copilot", mode="parallel", heartbeat=None)
    if unit == "stack":  # the stack's lease: the CR's, taken at T0, as `take stack` writes it
        data["stack_lease"] = dict(data["crs"][0]["lease"])
    if unit == "order":
        target = data["orders"][-1]
        target["agent"], name = "agent-q", target["id"]
    else:
        data["stack_agent"], name, target = "agent-s", "stack", data
    target["lease" if unit == "order" else "stack_lease"] = (
        target["lease" if unit == "order" else "stack_lease"] if keep else None
    )
    write_record(repo, data)
    at(minutes)
    causes, _, _ = running(Repo.find(), read_batch_json(changes(repo) / "4-batch" / "batch.json"))
    agent = "agent-q" if unit == "order" else "agent-s"
    ours = [x for x in causes if "lease" in x or "not measured" in x]
    assert ours == [x.format(agent=agent, unit=name) for x in expected], causes


def test_claude_close_shows_a_live_lease_beside_the_transcripts_and_it_is_no_cause(
    leased: Led,
) -> None:
    repo, _, (one, _) = leased
    d = read_batch_json(changes(repo) / "4-batch" / "batch.json")
    shown = _live_lease_lines(Repo.find(), d)
    assert shown and f"lease 1 of {one}: live until 00:10:00" in shown[0]
    assert not any("lease" in x for x in running(Repo.find(), d)[0])
    at(15)
    assert _live_lease_lines(Repo.find(), d) == []
