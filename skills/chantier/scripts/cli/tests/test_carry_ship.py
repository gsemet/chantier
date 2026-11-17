"""The base a head sits on (a restack's window) and the carry `ship` records, in-process on a
prepared repository."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import changes, open_batch, record
from conftest import Chantier, sh
from test_gate_carry import commit, git_at

from chantier.commands import delivery
from chantier.commands.carry import head_base
from chantier.core.batch import read_batch
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
