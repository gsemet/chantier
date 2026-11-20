"""The base a head sits on (a restack's window) and the carry `ship` records, in-process on a
prepared repository."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import changes, open_batch, record, write_record
from conftest import Chantier, sh
from test_gate_carry import commit, git_at

from chantier.commands import delivery
from chantier.commands.carry import head_base
from chantier.core.batch import read_batch
from chantier.core.errors import EXIT_PRECONDITION
from chantier.core.repo import Repo

GATE = "python -c pass"
PR = "https://github.com/acme/demo/pull/7"


def events(repo: Path, kind: str) -> list[dict[str, Any]]:
    log = changes(repo) / "4-batch" / "events.jsonl"
    found = [json.loads(ln) for ln in log.read_text(encoding="utf-8").splitlines()]
    return [e for e in found if e["kind"] == kind]


def remote(repo: Path, name: str, sha: str) -> None:
    sh("git", "update-ref", f"refs/remotes/origin/{name}", sha, cwd=repo)


@pytest.fixture
def stack(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Chantier, list[dict[str, Any]]]:
    """A stack batch of two CRs, both started on main, each in its worktree; A has a commit."""
    ids = open_batch(repo, chantier, monkeypatch, "Cr a", "Cr b", args=("--mode", "stack"))
    for cr in ids:
        assert chantier("take", cr, "--epoch", 1)[0] == 0
    crs = record(repo)["crs"]
    for cr in crs:
        sh("git", "worktree", "add", "-q", "-b", cr["branch"], cr["worktree"], "HEAD", cwd=repo)
    monkeypatch.setattr(delivery, "read_state", lambda link: ("main", False, ""))
    return repo, chantier, crs


def test_the_gate_records_the_branch_the_head_sits_on_in_a_restacks_window_and_ship_carries(
    stack: tuple[Path, Chantier, list[dict[str, Any]]],
) -> None:
    repo, chantier, (a, b) = stack
    main = sh("git", "rev-parse", "HEAD", cwd=repo)
    wa, wb = Path(a["worktree"]), Path(b["worktree"])
    a_tip = commit(wa, "a.txt", "a\n", "A")
    remote(repo, a["branch"], a_tip)
    remote(repo, "main", main)
    commit(wb, "b.txt", "b\n", "B")
    assert chantier("gate", b["id"], GATE)[0] == 0
    first = events(repo, "gate")
    assert [e["base"] for e in first] == [main]  # B sits on main: its start base
    # the stack driver places B above A, rebases it, ships it: the PR still shows main
    assert chantier("stack", a["id"], b["id"])[0] == 0
    git_at(wb, "rebase", "-q", a_tip)
    code, out, err = chantier("ship", b["id"], PR)
    assert code == 0, err
    carry = events(repo, "carry")
    assert len(carry) == 1 and carry[0]["base"] == a_tip and carry[0]["gate_from"]
    assert carry[0]["head"] == sh("git", "rev-parse", "HEAD", cwd=wb)
    assert any(ln.startswith("carried: long gate from ") and "onto " in ln for ln in out), out
    assert not any("no long gate passed" in ln for ln in out), out
    assert read_batch(Repo.find(), record(repo)["id"]).crs[1].pr_base == "main"  # still the old
    # a gate re-run before `forge-stack rebuild`: the nearest tip, A's, not the old branch's
    assert chantier("gate", b["id"], GATE)[0] == 0
    assert events(repo, "gate")[-1]["base"] == a_tip
    # a later clean move, onto A rewritten, carries that pass again
    git_at(wa, "commit", "--amend", "-qm", "A, reworded")
    a_new = sh("git", "rev-parse", "HEAD", cwd=wa)
    remote(repo, a["branch"], a_new)
    git_at(wb, "rebase", "-q", "--onto", a_new, a_tip)
    assert chantier("ship", b["id"], PR)[0] == 0
    last = events(repo, "carry")[-1]
    assert last["base"] == a_new and last["gate_from"] == carry[0]["head"]


def test_shipping_a_head_again_logs_no_second_carry_and_no_stale_off_line(
    stack: tuple[Path, Chantier, list[dict[str, Any]]],
) -> None:
    repo, chantier, (a, b) = stack
    wa, wb = Path(a["worktree"]), Path(b["worktree"])
    a_tip = commit(wa, "a.txt", "a\n", "A")
    remote(repo, a["branch"], a_tip)
    remote(repo, "main", sh("git", "rev-parse", "HEAD", cwd=repo))
    commit(wb, "b.txt", "b\n", "B")
    assert chantier("gate", b["id"], GATE)[0] == 0
    assert chantier("stack", a["id"], b["id"])[0] == 0
    git_at(wb, "rebase", "-q", a_tip)
    assert chantier("ship", b["id"], PR)[0] == 0
    again = ("carried:", "off: the pass", "off: no long")
    for _ in range(2):  # the same head shipped again, twice
        code, out, err = chantier("ship", b["id"], PR)
        assert code == 0, err
        assert not any(ln.startswith(again) for ln in out)
    assert len(events(repo, "carry")) == 1


def test_a_head_on_none_of_the_candidate_branches_records_no_base(
    stack: tuple[Path, Chantier, list[dict[str, Any]]],
) -> None:
    repo, chantier, (_, b) = stack
    wb = Path(b["worktree"])
    remote(repo, "main", sh("git", "rev-parse", "HEAD", cwd=repo))
    sh("git", "checkout", "-q", "--orphan", "lone", cwd=wb)
    sh("git", "rm", "-rfq", ".", cwd=wb)
    lone = commit(wb, "l.txt", "l\n", "lone")
    d = read_batch(Repo.find(), record(repo)["id"])
    assert head_base(Repo.find(), d, d.crs[1], wb, lone) is None
    sh("git", "checkout", "-q", "-f", b["branch"], cwd=wb)
    assert chantier("gate", b["id"], GATE)[0] == 0
    assert "base" in events(repo, "gate")[-1]
    sh("git", "checkout", "-q", "-f", "--orphan", "lone2", cwd=wb)
    sh("git", "rm", "-rfq", ".", cwd=wb)
    commit(wb, "m.txt", "m\n", "lone 2")
    assert chantier("gate", b["id"], GATE)[0] == 0
    assert "base" not in events(repo, "gate")[-1]


def test_ship_with_a_base_git_cannot_read_records_the_pr_and_no_carry(
    stack: tuple[Path, Chantier, list[dict[str, Any]]],
) -> None:
    repo, chantier, (_, b) = stack
    wb = Path(b["worktree"])
    remote(repo, "main", sh("git", "rev-parse", "HEAD", cwd=repo))
    head = commit(wb, "b.txt", "b\n", "B")
    log = changes(repo) / "4-batch" / "events.jsonl"
    bad = {"t": "t", "actor": "driver", "kind": "gate", "cr": b["id"], "result": "pass"}
    bad |= {"head": head, "run": "1", "base": "f" * 40}
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(bad) + "\n")
    new = commit(wb, "c.txt", "c\n", "C")
    code, out, err = chantier("ship", b["id"], PR)
    assert code == 0, err
    assert any("does not carry: " in ln and "cannot be read" in ln for ln in out), out
    assert not events(repo, "carry")
    assert record(repo)["crs"][1]["head"] == new and record(repo)["crs"][1]["pr"] == PR


CASES = ["out of draft on main", "draft on main", "on A's branch", "A merged"]


@pytest.mark.parametrize("case", CASES)
def test_ship_refuses_an_out_of_draft_main_pr_that_carries_another_crs_commits(
    stack: tuple[Path, Chantier, list[dict[str, Any]]],
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    repo, chantier, (a, b) = stack
    wa, wb = Path(a["worktree"]), Path(b["worktree"])
    a_tip = commit(wa, "a.txt", "a\n", "A")
    remote(repo, a["branch"], a_tip)
    remote(repo, "main", sh("git", "rev-parse", "HEAD", cwd=repo))
    pr_a = "https://github.com/acme/demo/pull/6"
    assert chantier("ship", a["id"], pr_a)[0] == 0
    commit(wb, "b.txt", "b\n", "B")
    git_at(wb, "rebase", "-q", a_tip)
    state = {
        "out of draft on main": ("main", False, ""),
        "draft on main": ("main", True, ""),
        "on A's branch": (a["branch"], False, ""),
        "A merged": ("main", False, ""),
    }[case]
    monkeypatch.setattr(delivery, "read_state", lambda link: state)
    if case == "A merged":
        data = record(repo)
        data["crs"][0]["status"] = "merged"
        write_record(repo, data)
    before = len(events(repo, "ship"))
    code, _, err = chantier("ship", b["id"], PR)
    if case == "out of draft on main":
        assert code == EXIT_PRECONDITION
        assert a["id"] in err and pr_a in err, err
        assert len(events(repo, "ship")) == before
        assert "pr" not in record(repo)["crs"][1] or not record(repo)["crs"][1]["pr"]
        assert not record(repo)["crs"][1].get("head")
    else:
        assert code == 0, err
        assert len(events(repo, "ship")) == before + 1
        assert record(repo)["crs"][1]["pr"] == PR
        assert record(repo)["crs"][1]["head"] == sh("git", "rev-parse", "HEAD", cwd=wb)


@pytest.fixture
def stack3(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Chantier, list[dict[str, Any]]]:
    """A stack batch of three CRs, all started on main, each in its worktree."""
    ids = open_batch(repo, chantier, monkeypatch, "Cr a", "Cr b", "Cr c", args=("--mode", "stack"))
    for cr in ids:
        assert chantier("take", cr, "--epoch", 1)[0] == 0
    crs = record(repo)["crs"]
    for cr in crs:
        sh("git", "worktree", "add", "-q", "-b", cr["branch"], cr["worktree"], "HEAD", cwd=repo)
    monkeypatch.setattr(delivery, "read_state", lambda link: ("main", False, ""))
    remote(repo, "main", sh("git", "rev-parse", "HEAD", cwd=repo))
    return repo, chantier, crs


def judge(repo: Path, cr: dict[str, Any], head: str, base: str) -> None:
    """A gate pass and a verdict VERIFIED at `head`, judged on `base`."""
    log = changes(repo) / "4-batch" / "events.jsonl"
    one = {"t": "t", "actor": "driver", "cr": cr["id"], "head": head, "base": base}
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(one | {"kind": "gate", "result": "pass", "run": "1"}) + "\n")
        f.write(json.dumps(one | {"kind": "verdict", "result": "VERIFIED"}) + "\n")


def ship_off(chantier: Chantier, cr: dict[str, Any]) -> tuple[list[str], list[str]]:
    code, out, err = chantier("ship", cr["id"], PR)
    assert code == 0, err
    return [ln for ln in out if ln.startswith("carried:")], [
        ln for ln in out if "does not carry" in ln
    ]


@pytest.mark.parametrize("case", ["pushed", "local only", "three CRs"])
def test_a_clean_rebase_onto_the_crs_below_carries_with_no_stack_mark_and_the_pr_on_main(
    stack3: tuple[Path, Chantier, list[dict[str, Any]]], case: str
) -> None:
    repo, chantier, (a, b, c) = stack3
    wa, wb, wc = Path(a["worktree"]), Path(b["worktree"]), Path(c["worktree"])
    main = sh("git", "rev-parse", "HEAD", cwd=repo)
    a_tip = commit(wa, "a.txt", "a\n", "A")
    remote(repo, a["branch"], a_tip)
    upper, wu, below = (c, wc, b) if case == "three CRs" else (b, wb, a)
    if case == "three CRs":
        git_at(wb, "rebase", "-q", a_tip)
        below_tip = commit(wb, "b.txt", "b\n", "B")
        remote(repo, b["branch"], below_tip)
    else:
        below_tip = a_tip
    judged = commit(wu, "u.txt", "u\n", "U")
    judge(repo, upper, judged, main)
    if case == "local only":
        git_at(wa, "commit", "--amend", "-qm", "A, reworded")
        below_tip = sh("git", "rev-parse", "HEAD", cwd=wa)  # the remote ref keeps the old tip
    git_at(wu, "rebase", "-q", below_tip)
    carried, off = ship_off(chantier, upper)
    new = sh("git", "rev-parse", "HEAD", cwd=wu)
    (carry,) = events(repo, "carry")
    assert carry["gate_from"] == carry["verdict_from"] == judged and carry["base"] == below_tip
    assert carry["head"] == new and not off
    want = f"carried: long gate and verdict from {judged[:7]} (clean rebase onto {below['branch']})"
    assert carried == [want]


def test_the_gate_records_the_nearest_branch_of_the_batch_as_the_base(
    stack3: tuple[Path, Chantier, list[dict[str, Any]]],
) -> None:
    repo, chantier, (a, b, c) = stack3
    a_tip = commit(Path(a["worktree"]), "a.txt", "a\n", "A")
    git_at(Path(b["worktree"]), "rebase", "-q", a_tip)
    b_tip = commit(Path(b["worktree"]), "b.txt", "b\n", "B")
    git_at(Path(c["worktree"]), "rebase", "-q", b_tip)
    commit(Path(c["worktree"]), "c.txt", "c\n", "C")
    assert chantier("gate", c["id"], GATE)[0] == 0
    assert events(repo, "gate")[-1]["base"] == b_tip


def _added(repo: Path, wb: Path, wa: Path) -> tuple[str, str]:
    commit(wb, "x.txt", "x\n", "after")
    return "(own commits: 1 at ", ", 2 at "


def _edited(repo: Path, wb: Path, wa: Path) -> tuple[str, str]:
    (wb / "b.txt").write_text("edited\n", encoding="utf-8", newline="\n")
    git_at(wb, "commit", "-aqm", "B, edited", "--amend")
    return "(commit 1 of 1 differs)", ""


def _cancelled(repo: Path, wb: Path, wa: Path) -> tuple[str, str]:
    data = record(repo)
    data["crs"][0]["status"] = "cancelled"
    write_record(repo, data)
    return "(own commits: 1 at ", ", 2 at "


@pytest.mark.parametrize("change", [_added, _edited, _cancelled])
def test_a_real_change_is_refused_and_off_says_by_how_much(
    stack3: tuple[Path, Chantier, list[dict[str, Any]]], change: Any
) -> None:
    repo, chantier, (a, b, _) = stack3
    wa, wb = Path(a["worktree"]), Path(b["worktree"])
    main = sh("git", "rev-parse", "HEAD", cwd=repo)
    a_tip = commit(wa, "a.txt", "a\n", "A")
    remote(repo, a["branch"], a_tip)
    judge(repo, b, commit(wb, "b.txt", "b\n", "B"), main)
    git_at(wb, "rebase", "-q", a_tip)
    first, second = change(repo, wb, wa)
    carried, off = ship_off(chantier, b)
    assert not carried and not events(repo, "carry")
    assert off and all("the rebase changed the patch " in ln for ln in off), off
    assert all(first in ln and second in ln for ln in off), off
