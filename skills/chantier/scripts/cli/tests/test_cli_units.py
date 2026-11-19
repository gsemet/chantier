"""Units of the CLI: the spelling of a CR, a gate and a verdict at a head, the cost breakdown and
the sandbox checks.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import PLUGIN_ROOT, load_script

from chantier.commands.cost.breakdown import breakdown, cost_kind, cost_label
from chantier.commands.cost.sessions import OWN_CHIEF
from chantier.commands.crs import carry_at, last_gate_pass, last_verdict, last_verdict_head
from chantier.commands.driver import _ready_lines
from chantier.commands.forge_stack_gh import Unreadable, gh
from chantier.core.errors import EXIT_EXTERNAL, ChantierError
from chantier.core.git import git
from chantier.core.heads import gate_passed
from chantier.core.ids import normalize_cr
from chantier.core.records import BatchRecord, CrEntry, EventRecord
from chantier.status.steps import step_entries
from chantier.status.words import next_to_start, notify, phase_text

FULL_ROWS = 13


def test_a_cr_has_one_spelling_and_a_passed_gate_and_a_verdict_are_read_at_a_head() -> None:
    assert [normalize_cr(x) for x in ("165", "CR-165", "cr-165", "stack", "O-2", "-")] == [
        "CR-165",
        "CR-165",
        "CR-165",
        "stack",
        "O-2",
        "-",
    ]

    def g(result: str, run: str, head: str = "abc1234") -> EventRecord:
        return EventRecord(t="t", actor="driver", kind="gate", result=result, head=head, run=run)

    assert gate_passed([g("pass", "1"), g("pass", "1")], "abc1234")
    assert not gate_passed([g("pass", "1"), g("fail", "1")], "abc1234")  # the second command failed
    assert not gate_passed(
        [g("fail", "1"), g("pass", "2"), g("fail", "3")], "abc1234"
    )  # the last run
    assert gate_passed([g("fail", "1"), g("pass", "2")], "abc1234")
    assert not gate_passed([g("pass", "1")], "other")

    def v(result: str, head: str = "abc1234") -> EventRecord:
        return EventRecord(t="t", actor="driver", kind="verdict", result=result, head=head)

    assert last_verdict([v("VERIFIED"), v("NOT VERIFIED")], "abc1234") == "NOT VERIFIED"
    assert last_verdict([v("NOT VERIFIED"), v("VERIFIED")], "abc1234") == "VERIFIED"
    assert last_verdict([v("VERIFIED", "old")], "abc1234") is None
    assert last_verdict_head([v("VERIFIED", "a")]) == "a"
    assert last_verdict_head([v("VERIFIED", "a"), v("NOT VERIFIED", "b")]) is None
    assert last_verdict_head([v("VERIFIED", "a"), v("NOT VERIFIED", "a")]) is None
    assert last_verdict_head([v("NOT VERIFIED", "a"), v("VERIFIED", "b")]) == "b"
    assert last_verdict_head([]) is None


def test_cost_puts_the_steering_sessions_own_subagents_on_their_own_line_and_qa_on_a_driver() -> (
    None
):
    def row(agent: str, parent: str | None, **more: Any) -> dict[str, Any]:
        return {
            "agent": agent,
            "type": "Explore",
            "parent": parent,
            "calls": 1,
            "usd": 1.0,
            **more,
        }

    assert cost_kind(row("a", None)) == "Driver"  # tied to a CR, the stack or a QA order by the log
    own = row("b", None, own=OWN_CHIEF)  # `_cost_rows` marks the others
    assert (cost_kind(own), cost_label(own)) == ("Foreman", OWN_CHIEF)
    labels = [e["label"] for e in breakdown([row("a", None), own, row("c", "a")])]
    assert labels == [OWN_CHIEF, "Driver Explore", "Worker Explore"]


def test_the_eval_sandbox_builds_its_recorded_base() -> None:
    script = PLUGIN_ROOT / "evals" / "kit" / "sandbox.py"
    done = subprocess.run(
        [sys.executable, str(script), "build"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    found = re.search(r"^base ([0-9a-f]+)$", done.stdout, re.MULTILINE)
    assert found, done.stdout + done.stderr
    built = found.group(1)
    recorded = json.loads(
        (PLUGIN_ROOT / "evals" / "kit" / "sandbox.json").read_text(encoding="utf-8")
    )["base"]
    assert built == recorded
    assert re.fullmatch(r"[0-9a-f]{40}", recorded)


def test_the_sandbox_campaigns_name_only_frozen_crs_with_hidden_tests() -> None:
    kit = Path(__file__).resolve().parents[5] / "evals" / "kit"
    if not (kit / "setup.py").is_file():
        pytest.skip("the eval kit is not part of this install")
    setup = load_script("eval_setup", kit / "setup.py")
    sandbox = {name: c for name, c in setup.CAMPAIGNS.items() if "batches" in c}
    assert set(sandbox) == {"full", "real-foreman", "real-direct", "copilot", "ticket-summary"}
    summary = sandbox["ticket-summary"]
    assert setup.sandbox_crs(summary) == []
    for part in ("body", "chat"):
        assert (kit / summary["issue"][part]).is_file(), f"ticket-summary lacks {part}"
    for name, campaign in sandbox.items():
        for slug in setup.sandbox_crs(campaign):
            folder = kit / "sandbox-crs" / slug
            for part in ("intake/request.md", "01-intent.md", "02-answers.md", "03-change-spec.md"):
                assert (folder / part).is_file(), f"{name}: {slug} lacks {part}"
            if not slug.startswith("release-"):
                assert list((kit / "sandbox-judge" / slug).glob("test_judge_*.py")), (
                    f"{name}: {slug} has no hidden test"
                )
            else:  # a release bumps the version: its lock moves with it (the judge checks it)
                spec_text = (folder / "03-change-spec.md").read_text(encoding="utf-8")
                files = spec_text.split("## Files", 1)[-1].split("\n## ", 1)[0]
                assert "uv.lock" in files, f"{name}: {slug} does not name uv.lock in its Files"
    assert not list((kit / "sandbox-crs").rglob("test_*.py")), "a hidden test sits in a frozen CR"
    full = setup.sandbox_crs(sandbox["full"])
    assert len(full) == FULL_ROWS
    for quick in ("real-foreman", "real-direct"):
        assert setup.sandbox_crs(sandbox[quick]) == setup.QUICK and set(setup.QUICK) <= set(full)


def test_phase_text_reads_the_step_of_a_working_cr_and_waits_for_the_user_on_a_blocked_one() -> (
    None
):
    def c(status: str = "working", **more: Any) -> CrEntry:
        return CrEntry(id="CR-1", status=status, round=3, **more)

    assert phase_text(c(phase="investigator")) == "investigator"
    assert phase_text(c(phase="coder")) == "coder r3"
    assert phase_text(c(phase="inspector")) == "inspector r3"
    assert phase_text(c(phase="review", phase_detail="security")) == "security r3"
    assert phase_text(c(phase="conflict-resolver")) == "conflict resolver"
    assert phase_text(c(phase="gate", phase_detail="scenario")) == "gate scenario"
    assert phase_text(c(phase="gate")) == "gate"
    assert [phase_text(c(phase=p)) for p in ("pr", "ci", "rebase", "verifier", "debugger")] == [
        "PR",
        "CI",
        "rebase",
        "verifier",
        "debugger",
    ]
    assert phase_text(c(phase="release", phase_detail="tag")) == "release tag"
    assert phase_text(c()) is None  # working, no step recorded
    assert phase_text(c("blocked", blocked_reason="question: which?")) == "waits for the user"
    assert phase_text(c("blocked", blocked_reason="waits: CR-2")) is None
    assert all(phase_text(c(s, phase="ci")) is None for s in ("queued", "ready", "merged"))


def test_next_to_start_is_the_queued_cr_of_the_lowest_order_with_nothing_to_wait_for() -> None:
    def batch(mode: str = "parallel", **more: Any) -> BatchRecord:
        crs = [
            CrEntry(id="CR-1", status="working", order=1),
            CrEntry(id="CR-2", status="queued", order=2, after=["CR-1"]),
            CrEntry(id="CR-4", status="queued", order=4),
            CrEntry(id="CR-3", status="queued", order=3),
        ]
        return BatchRecord(mode=mode, crs=crs, **more)

    assert next_to_start(batch()) == "CR-3"  # CR-2 waits for CR-1
    assert next_to_start(batch("series")) is None  # a series waits for its predecessor
    assert next_to_start(batch(budget_usd=1, spent_usd=2)) is None  # the budget is spent
    d = batch()
    d.crs[0].status = "merged"
    assert next_to_start(d) == "CR-2"


@pytest.mark.parametrize(
    ("empty_ok", "ran", "expected"),
    [
        (True, SimpleNamespace(returncode=0, stdout="", stderr=""), None),
        (True, SimpleNamespace(returncode=0, stdout="\n  ", stderr=""), None),
        (True, SimpleNamespace(returncode=0, stdout='{"number": 1}', stderr=""), {"number": 1}),
        (True, SimpleNamespace(returncode=0, stdout="<html>", stderr=""), "not JSON"),
        (False, SimpleNamespace(returncode=0, stdout="", stderr=""), "not JSON"),
        (True, SimpleNamespace(returncode=1, stdout="", stderr="HTTP 404"), "HTTP 404"),
    ],
)
def test_gh_reads_an_empty_reply_only_when_asked(
    monkeypatch: pytest.MonkeyPatch, empty_ok: bool, ran: Any, expected: Any
) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/bin/gh")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: ran)
    if not isinstance(expected, str):
        assert gh(["-X", "POST", "x"], "github.com", empty_ok=empty_ok) == expected
        return
    with pytest.raises(ChantierError) as raised:
        gh(["-X", "POST", "x"], "github.com", empty_ok=empty_ok)
    assert expected in str(raised.value) and raised.value.code == EXIT_EXTERNAL
    assert isinstance(raised.value, Unreadable) == (ran.returncode == 0)


def _ev(kind: str, **keys: Any) -> EventRecord:
    return EventRecord(t="t", actor="driver", kind=kind, **keys)


def test_a_carry_is_a_judged_head_and_a_later_not_verified_blocks_it() -> None:
    gate = _ev("gate", result="pass", head="a", run="1", base="m")
    ok = _ev("verdict", result="VERIFIED", head="a", base="m")
    carry = _ev("carry", head="b", base="n", gate_from="a", verdict_from="a")
    other = _ev("carry", head="b", base="n", gate_from="a")
    assert carry_at([gate, carry], "b") is carry
    assert carry_at([gate, carry, other], "b") is other  # the last one
    assert carry_at([gate, carry, other], "b", "verdict_from") is carry
    assert carry_at([gate, carry], "c") is None
    assert last_gate_pass([gate, ok, carry]) == "b"
    assert last_verdict_head([gate, ok, carry]) == "b"
    assert last_verdict_head([ok, carry, _ev("verdict", result="NOT VERIFIED", head="b")]) is None
    assert last_verdict_head([ok, carry, _ev("verdict", result="NOT VERIFIED", head="a")]) is None
    # a carry is not a pass or a verdict of the head's own
    assert not gate_passed([gate, carry], "b") and last_verdict([ok, carry], "b") is None


def test_a_ship_with_a_conflict_voids_every_judged_head_and_carry_before_it() -> None:
    gate = _ev("gate", result="pass", head="a", run="1", base="m")
    ok = _ev("verdict", result="VERIFIED", head="a", base="m")
    carry = _ev("carry", head="b", base="n", gate_from="a", verdict_from="a")
    ship = _ev("ship", head="c", conflict=True)
    log = [gate, ok, carry, ship]
    assert last_gate_pass(log) is None and last_verdict_head(log) is None
    assert carry_at(log, "b") is None and carry_at(log, "c") is None
    later = _ev("carry", head="d", base="n", gate_from="c")
    assert carry_at([*log, later], "d") is later  # a judgment after the conflict can carry
    fresh = _ev("gate", result="pass", head="c", run="2", base="n")
    assert last_gate_pass([*log, fresh]) == "c"


@pytest.mark.parametrize(
    ("gate_from", "verdict_from", "steps"),
    [
        (
            "a" * 40,
            "a" * 40,
            [("Long gate", "carried from aaaaaaa"), ("Verdict", "carried from aaaaaaa")],
        ),
        (None, "a" * 40, [("Verdict", "carried from aaaaaaa")]),
        (None, None, []),
    ],
)
def test_a_ready_handback_shows_its_carried_verdict_as_a_step(
    gate_from: str | None, verdict_from: str | None, steps: list[tuple[str, str]]
) -> None:
    e = EventRecord(
        t="t",
        actor="driver",
        kind="handback",
        result="ready",
        gate_from=gate_from,
        verdict_from=verdict_from,
    )
    got = step_entries(e, BatchRecord(id="b"), CrEntry(id="CR-1"), [])
    assert [(n, v) for n, v, _ in got] == [*steps, ("Handed back", "")]


@pytest.mark.parametrize("draft", [True, False, None])
@pytest.mark.parametrize("wait", ["cr-pr", "cr-no-pr", "branch", "none"])
def test_the_now_line_of_a_pr_in_draft_takes_the_ready_lines_clause(
    draft: bool | None, wait: str
) -> None:
    if wait == "none" and draft is False:
        pytest.skip("a PR out of draft on the default branch reads ready to merge")
    below = CrEntry(
        id="CR-1",
        order=1,
        status="ready",
        branch="b/cr-1",
        pr="https://h/o/r/pull/1" if wait == "cr-pr" else None,
        pr_draft=True,
    )
    base = {"cr-pr": below.branch, "cr-no-pr": below.branch, "branch": "feature/x", "none": "main"}[
        wait
    ]
    c = CrEntry(
        id="CR-2",
        order=2,
        status="ready",
        branch="b/cr-2",
        pr="https://h/o/r/pull/2",
        pr_draft=draft,
        pr_base=base,
    )
    crs = [below, c] if wait in {"cr-pr", "cr-no-pr"} else [c]
    d = BatchRecord(id="b", mode="parallel", crs=crs)
    repo: Any = SimpleNamespace(config={"default_branch": "main"})
    ready = _ready_lines(repo, d, c, False, "")[1]
    now, nxt = notify(repo, d, c, str(c.pr))
    assert ready.startswith("CR-2 PR in draft: ")
    assert now == f"PR in draft: {ready.removeprefix('CR-2 PR in draft: ')}."
    assert f"on {base}," not in now
    out = "" if draft is False else " and the PR is out of draft"
    assert nxt == f"Ready to merge once what is under it is{out}."


def test_git_in_a_missing_folder_is_a_refusal_naming_it(tmp_path: Path) -> None:
    with pytest.raises(ChantierError, match=r"no folder .*missing"):
        git("status", cwd=tmp_path / "missing", check=False)
