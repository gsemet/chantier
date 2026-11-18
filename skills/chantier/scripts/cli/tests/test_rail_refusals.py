"""The rails a batch refuses by: rounds, the round limit, slots, the budget, `take`, QA."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import FROM_AGENTS_MD, changes, open_batch, prepared, record, write_record
from conftest import Chantier

from chantier.core.batch import resolve_batch
from chantier.core.errors import (
    EXIT_BUDGET,
    EXIT_CONFLICT,
    EXIT_PRECONDITION,
    EXIT_USAGE,
    ChantierError,
)
from chantier.core.repo import Repo

ROUNDS = 3
SPENT = 2  # against a budget of 1


def order_id(line: str) -> str:
    found = re.search(r"order (O-\d+):", line)
    assert found
    return found[1]


def cr_of(repo: Path, cr: str) -> dict[str, Any]:
    return next(c for c in record(repo)["crs"] if c["id"] == cr)


def rounds_logged(repo: Path, cr: str) -> int:
    events = (changes(repo) / "4-batch" / "events.jsonl").read_text(encoding="utf-8")
    return sum(
        1
        for ln in events.splitlines()
        if (e := json.loads(ln))["kind"] == "round" and e["cr"] == cr
    )


def spend(repo: Path, usd: float | None, budget: int | None = 1) -> None:
    write_record(repo, {**record(repo), "spent_usd": usd, "budget_usd": budget})


@pytest.fixture
def rails(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Chantier, list[str]]:
    ids = open_batch(
        repo, chantier, monkeypatch, "Rail one", "Rail two", args=("--slots", 1, "--budget", 1)
    )
    assert chantier("take", ids[0], "--epoch", 1)[0] == 0
    return repo, chantier, ids


def test_a_round_with_nothing_since_and_the_round_limit_are_refused_and_more_can_be_granted(
    rails: tuple[Path, Chantier, list[str]],
) -> None:
    repo, chantier, (one, _) = rails
    assert chantier("round", one, "--note", "round 1")[0] == 0
    code, _, err = chantier("round", one)
    assert code == EXIT_PRECONDITION and "nothing happened since" in err and "handoff" in err
    assert cr_of(repo, one)["round"] == 1 and rounds_logged(repo, one) == 1
    for i in range(2):
        chantier("note", one, f"round {i + 1} done")
        assert chantier("round", one)[0] == 0
    assert cr_of(repo, one)["round"] == ROUNDS and rounds_logged(repo, one) == ROUNDS
    code, _, err = chantier("round", one)
    assert code == EXIT_BUDGET and "round limit" in err and cr_of(repo, one)["round"] == ROUNDS
    assert any(ln.startswith(f"{one} working r3/3") for ln in chantier("status")[1])
    chantier("order", "rounds", one, "--note", "4")
    chantier("note", one, "the limit was raised")
    assert chantier("round", one)[0] == 0
    assert (cr_of(repo, one)["round"], cr_of(repo, one)["rounds"]) == (ROUNDS + 1, ROUNDS + 1)


def test_phase_refuses_a_queued_cr_a_review_with_no_detail_and_a_long_detail(
    rails: tuple[Path, Chantier, list[str]],
) -> None:
    repo, chantier, (one, two) = rails
    before = record(repo)
    for args in (
        (two, "inspector"),
        (one, "review"),
        (one, "gate", "x" * 41),
    ):
        assert chantier("phase", *args)[0] == EXIT_PRECONDITION, args
    assert record(repo) == before and "phase" not in cr_of(repo, two)
    assert chantier("phase", one, "review", "security")[0] == 0


def test_slots_zero_holds_and_a_spent_budget_stops_the_next_driver_until_it_is_raised(
    rails: tuple[Path, Chantier, list[str]],
) -> None:
    repo, chantier, (_, two) = rails
    chantier("order", "slots", "--note", "0")
    code, _, err = chantier("take", two, "--epoch", 1)
    assert code == EXIT_PRECONDITION and "no free slot" in err
    code, _, err = chantier("order", "slots", "--note", "none")
    assert code == EXIT_USAGE and "0 holds" in err
    with pytest.raises(SystemExit) as stopped:  # `land` is no longer a command
        chantier("land", "--epoch", 1)
    assert stopped.value.code == EXIT_PRECONDITION
    assert record(repo)["status"] == "running"
    chantier("order", "slots", "--note", "2")
    spend(repo, SPENT)
    code, _, err = chantier("take", two, "--epoch", 1)
    assert code == EXIT_BUDGET and "budget" in err and cr_of(repo, two)["status"] == "queued"
    chantier("order", "budget", "--note", "10")
    assert chantier("take", two, "--epoch", 1)[0] == 0


def test_a_ready_cr_goes_back_to_a_driver_only_with_a_note_and_cancel_needs_the_epoch(
    rails: tuple[Path, Chantier, list[str]],
) -> None:
    repo, chantier, (one, _) = rails
    data = record(repo)
    for c in data["crs"]:
        if c["id"] == one:
            c.update(status="ready", pr="https://example.invalid/pr/1", agent=None)
    write_record(repo, data)
    code, _, err = chantier("take", one, "--epoch", 1)
    assert code == EXIT_PRECONDITION and "only with `--note`" in err
    code, _, _ = chantier(
        "take", one, "--note", "rebase: main moved; the PR no longer merges", "--epoch", 1
    )
    assert code == 0 and cr_of(repo, one)["status"] == "working"
    assert cr_of(repo, one)["notes"][-1].startswith("back to a Driver: rebase:")
    before = (cr_of(repo, one)["status"], cr_of(repo, one)["path"])
    code, _, err = chantier("cancel", one)
    assert code == EXIT_PRECONDITION and f"gate {one} --stop" in err
    assert (cr_of(repo, one)["status"], cr_of(repo, one)["path"]) == before


STEERING = (
    (("foreman", "set", "local_x"), "foreman set <session-id> --epoch <n>"),
    (("foreman", "transcript", "uuid-x"), "foreman transcript <uuid> --epoch <n>"),
    (("status", "--stop-heartbeat"), "status --stop-heartbeat --epoch <n>"),
    (("take", "CR-102"), "take CR-102 --epoch <n>"),
    (("take", "stack"), "take stack --epoch <n>"),
    (("agents", "set", "CR-101", "-"), "agents set CR-101 <id>|- --epoch <n>"),
    (("order", "done", "O-1"), "order done O-1 --epoch <n>"),
    (("pause",), "pause --epoch <n>"),
)


@pytest.mark.parametrize(("argv", "usage"), STEERING)
def test_a_steering_command_without_its_number_is_refused_and_writes_nothing(
    rails: tuple[Path, Chantier, list[str]], argv: tuple[str, ...], usage: str
) -> None:
    repo, chantier, _ = rails
    files = (changes(repo) / "4-batch" / "batch.json", changes(repo) / "4-batch" / "events.jsonl")
    before = [f.read_bytes() for f in files]
    code, _, err = chantier(*argv)
    assert code == EXIT_PRECONDITION and usage in err and "Foreman n°" in err
    assert "epoch" not in err.replace("--epoch", "")
    assert [f.read_bytes() for f in files] == before


def test_the_budget_bounds_the_rounds_and_leaves_the_round_limit_its_own_message(
    rails: tuple[Path, Chantier, list[str]],
) -> None:
    repo, chantier, (one, two) = rails
    chantier("order", "slots", "--note", "2")
    assert chantier("take", two, "--epoch", 1)[0] == 0
    chantier("order", "rounds", one, "--note", "9")
    for i in range(ROUNDS):
        chantier("note", one, f"round {i}")
        assert chantier("round", one)[0] == 0
    spend(repo, SPENT)
    code, _, err = chantier("round", two)
    assert code == EXIT_BUDGET and "budget" in err and "round limit" not in err
    assert cr_of(repo, two)["round"] == 0 and not rounds_logged(repo, two)
    data = record(repo)
    data["crs"][0]["rounds"] = ROUNDS  # the limit reached too: the budget message wins
    write_record(repo, data)
    code, _, err = chantier("round", one)
    assert code == EXIT_BUDGET and "budget" in err and "round limit" not in err
    spend(repo, 0)
    chantier("note", one, "again")
    code, _, err = chantier("round", one)
    assert code == EXIT_BUDGET and "round limit" in err and "budget" not in err
    spend(repo, SPENT, budget=None)
    assert chantier("round", two, "--note", "unbounded")[0] == 0
    assert cr_of(repo, two)["round"] == 1


def test_order_qa_needs_a_request_and_a_budget_and_its_folder_is_not_opened(
    rails: tuple[Path, Chantier, list[str]],
) -> None:
    repo, chantier, _ = rails
    chantier("order", "slots", "--note", "2")
    code, _, err = chantier("order", "qa")
    assert code == EXIT_USAGE and "what to test" in err
    inbox = changes(repo) / "1-inbox"
    before = (sorted(p.name for p in inbox.glob("qa-*")), len(record(repo)["orders"]))
    spend(repo, SPENT)
    code, _, err = chantier("order", "qa", "--note", "try the export on a phone")
    assert code == EXIT_BUDGET and "budget" in err
    assert (sorted(p.name for p in inbox.glob("qa-*")), len(record(repo)["orders"])) == before
    chantier("order", "budget", "--note", "10")
    code, out, err = chantier("order", "qa", "--note", "try the export on a phone")
    assert code == 0, err
    assert len(record(repo)["orders"]) == before[1] + 2 and len(list(inbox.glob("qa-*"))) == 1
    folder = repo / out[1].removeprefix("QA folder: ").split(";")[0]
    assert "phone" in (folder / "intake" / "request.md").read_text(encoding="utf-8")
    code, _, err = chantier("open", str(folder), *FROM_AGENTS_MD)
    assert code == EXIT_PRECONDITION and "QA report" in err and "triage" in err
    assert chantier("agents", "set", order_id(out[0]), "agent-qa", "--epoch", 1)[0] == 0
    assert chantier("agents", "set", "O-1", "agent-x", "--epoch", 1)[0] == EXIT_USAGE


@pytest.mark.usefixtures("repo")
@pytest.mark.parametrize(
    ("running", "paused", "reading", "expected"),
    [
        ([], [], True, "no running batch: run `chantier open` first"),
        ([], ["batch-18"], True, "batch-18"),
        ([], ["batch-18"], False, "no running batch; paused: batch-18: pass `--batch batch-18`"),
        ([], ["batch-17", "batch-18"], True, "paused: batch-17, batch-18: pass `--batch <name>`"),
        (["batch-19"], ["batch-18"], True, "batch-19"),
    ],
)
def test_a_paused_batch_is_read_when_alone_and_named_otherwise(
    monkeypatch: pytest.MonkeyPatch,
    running: list[str],
    paused: list[str],
    reading: bool,
    expected: str,
) -> None:
    repo_ = Repo.find()
    monkeypatch.setattr(Repo, "open_batches", lambda _self: running)
    monkeypatch.setattr(Repo, "paused_batches", lambda _self: paused)
    if expected.startswith("batch-"):
        assert resolve_batch(repo_, None, paused=reading) == expected
        return
    with pytest.raises(ChantierError) as refused:
        resolve_batch(repo_, None, paused=reading)
    assert expected in str(refused.value)
    assert ("chantier open" in str(refused.value)) == (not paused)


def test_a_command_that_writes_refuses_a_paused_batch_by_name_and_status_reads_it(
    rails: tuple[Path, Chantier, list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, chantier, _ = rails
    write_record(repo, {**record(repo), "status": "paused"})
    monkeypatch.delenv("CHANTIER_BATCH")
    batch = record(repo)["id"]
    assert chantier("status")[0] == 0
    code, _, err = chantier("asks")
    assert code != 0 and f"--batch {batch}" in err and "chantier open" not in err


@pytest.mark.parametrize(
    "host_cell",
    [
        ("claude", "CLAUDE_CODE_SESSION_ID", True),
        ("copilot", "COPILOT_AGENT_SESSION_ID", True),
        ("claude", "CLAUDE_CODE_SESSION_ID", False),  # no Chief of Staff transcript recorded
    ],
)
def test_the_chief_of_staff_claiming_a_foreman_batch_makes_it_direct(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    host_cell: tuple[str, str, bool],
) -> None:
    host, variable, recorded = host_cell
    monkeypatch.setenv("CHANTIER_HOST", host)
    if recorded:
        monkeypatch.setenv(variable, "uuid-chief")
    assert chantier("open", str(prepared(repo, chantier, "Fix login")), *FROM_AGENTS_MD)[0] == 0
    folder = repo / ".agents" / "changes" / "4-batch"
    assert chantier("foreman", "set", "s-foreman", "--epoch", 1)[0] == 0
    assert chantier("foreman", "transcript", "uuid-foreman", "--epoch", 1)[1] == [
        "transcript uuid-foreman"
    ]
    assert chantier("foreman", "set", "uuid-chief", "--epoch", 2)[0] == 0
    code, out, err = chantier("foreman", "transcript", "uuid-chief", "--epoch", 2)
    assert code == 0, err
    events = [json.loads(ln) for ln in (folder / "events.jsonl").read_text("utf-8").splitlines()]
    steering = [e for e in events if e["kind"] == "steering"]
    state = json.loads((folder / "batch.json").read_text(encoding="utf-8"))["steering"]
    if not recorded:  # nothing could tell the claim from a Foreman's: no flip, no line, no event
        assert (state, out, steering) == ("foreman", ["transcript uuid-chief"], [])
        return
    assert (
        state == "direct"
        and len(out) == len(["transcript", "steering"])
        and out[0] == "transcript uuid-chief"
    )
    assert out[1].startswith("steering direct:") and "epoch" not in out[1]
    assert [(e["steering"], e["transcript"]) for e in steering] == [("direct", "uuid-chief")]
    assert " steering direct (the Chief of Staff) " in chantier("status")[1][0]
    assert chantier("status", "--refresh", "--epoch", 1)[0] == EXIT_CONFLICT  # the old number
    code, out, err = chantier("take", "CR-101", "--epoch", 2)
    assert code == 0, err
    assert any(ln.startswith("  Steering: the Chief of Staff") for ln in out)
