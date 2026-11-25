"""`push`: a CR's own recorded `chantier/*` branch, from its worktree, by a lease holder, with
`--force-with-lease` against a bare remote; every refusal runs no `git push` and records nothing."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from batch_helpers import events, record, write_record
from conftest import Chantier, sh
from stack_world import Batch, stack_of
from test_gate_carry import commit, git_at

from chantier.core import clock
from chantier.core.errors import EXIT_EXTERNAL

World = tuple[Path, Chantier, list[dict[str, Any]], Path]
Edit = Callable[[dict[str, Any]], None]


def _bare(chantier: Chantier) -> Callable[..., tuple[int, list[str], str]]:
    return cast(Any, chantier).bare  # type: ignore[no-any-return]


@pytest.fixture
def world(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> World:
    """A stack batch of two CRs taken, each in its worktree, and a bare remote as `origin`."""
    crs = stack_of(Batch("push2", ("Cr a", "Cr b")), repo, chantier, monkeypatch)
    remote = tmp_path / "remote.git"
    sh("git", "init", "-q", "--bare", "-b", "main", str(remote))
    sh("git", "remote", "set-url", "origin", str(remote), cwd=repo)
    return repo, chantier, crs, remote


def tip(remote: Path, branch: str) -> str:
    p = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=remote,
        capture_output=True,
        text=True,
        check=False,
    )
    return p.stdout.strip()


def pushes(repo: Path) -> list[dict[str, Any]]:
    return [e for e in events(repo) if e["kind"] == "push"]


def _edit(repo: Path, change: Edit) -> None:
    data = record(repo)
    change(data)
    write_record(repo, data)


def _qa_order(data: dict[str, Any]) -> None:
    lease = {"n": 1, "taken": "t", "renewed": "t", "expires": "2099-01-01T00:00:00Z"}
    data["orders"] = [{"id": "O-1", "kind": "qa", "cr": "CR-2", "lease": lease}]


def _dirty(wt: Path) -> None:
    (wt / "loose.txt").write_text("x", encoding="utf-8")


def _other_branch(wt: Path) -> None:
    git_at(wt, "switch", "-q", "-c", "elsewhere")


REFUSALS: list[tuple[str, Edit | None, Callable[[Path], None] | None, list[str], int, str]] = [
    ("no branch", lambda d: d["crs"][0].update(branch=""), None, [], 2, "take CR-1"),
    ("not chantier", lambda d: d["crs"][0].update(branch="feature/x"), None, [], 2, "chantier/*"),
    ("default branch", lambda d: d["crs"][0].update(branch="main"), None, [], 2, "chantier/*"),
    ("no lease", None, None, ["BARE"], 2, "needs --lease"),
    ("stale lease", None, None, ["--lease", "99"], 3, "claim lost"),
    ("dirty worktree", None, _dirty, [], 2, "commit first"),
    ("HEAD elsewhere", None, _other_branch, [], 2, "check out"),
    (
        "unit without a lease",
        lambda d: d["crs"][0].update(lease=None),
        None,
        [],
        2,
        "has none (`help lease`)",
    ),
    (
        "stack unit outside the chain",
        lambda d: d["crs"][0].update(status="cancelled"),
        None,
        ["--unit", "stack"],
        2,
        "not in the chain",
    ),
    ("an order of another CR", _qa_order, None, ["--unit", "O-1"], 2, "not a QA order of CR-1"),
]


@pytest.mark.parametrize(
    ("name", "edit", "prepare", "extra", "code", "text"),
    REFUSALS,
    ids=[r[0] for r in REFUSALS],
)
def test_each_refusal_pushes_nothing_and_records_nothing(  # noqa: PLR0913, PLR0917
    world: World,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    edit: Edit | None,
    prepare: Callable[[Path], None] | None,
    extra: list[str],
    code: int,
    text: str,
) -> None:
    repo, chantier, (one, _), remote = world
    if edit:
        _edit(repo, edit)
    if prepare:
        prepare(Path(one["worktree"]))
    spied: list[Any] = []
    real = subprocess.run

    def spy(cmd: Any, *a: Any, **k: Any) -> Any:
        if isinstance(cmd, list) and "push" in cmd:
            spied.append(cmd)
        return real(cmd, *a, **k)

    monkeypatch.setattr(subprocess, "run", spy)
    run = _bare(chantier) if extra[:1] == ["BARE"] else chantier
    got, _, err = run("push", one["id"], *[x for x in extra if x != "BARE"])
    assert got == code and text in err, err
    assert not spied and not pushes(repo)
    assert tip(remote, one["branch"]) == ""


def test_a_new_branch_then_an_update_after_a_rebase_push_and_record(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, chantier, (one, _), remote = world
    wt = Path(one["worktree"])
    branch = one["branch"]
    first = commit(wt, "a.txt", "a\n", "A")
    before = record(repo)["crs"][0]["lease"]["expires"]
    monkeypatch.setattr(clock, "_fixed", [])
    clock.fix(clock.after(-300, before))  # the lease has 5 minutes left: a renewal moves it
    code, out, err = chantier("push", one["id"])
    assert code == 0, err
    assert out == [f"pushed {branch} at {first[:7]} (new branch on origin)"]
    assert tip(remote, branch) == first
    (e,) = pushes(repo)
    assert (e["branch"], e["head"], e["expected"], e["unit"]) == (branch, first, "", one["id"])
    assert record(repo)["crs"][0]["lease"]["expires"] > before
    git_at(wt, "commit", "-q", "--amend", "-m", "A again", "--allow-empty")  # a rebased head
    second = sh("git", "rev-parse", "HEAD", cwd=wt)
    assert chantier("push", one["id"])[1] == [f"pushed {branch} at {second[:7]} (was {first[:7]})"]
    assert tip(remote, branch) == second
    assert [x["expected"] for x in pushes(repo)] == ["", first]


def test_the_stack_lease_pushes_a_chain_crs_branch(world: World) -> None:
    repo, chantier, (_, two), remote = world
    wt = Path(two["worktree"])
    head = commit(wt, "b.txt", "b\n", "B")
    assert chantier("take", "stack", "--epoch", 1)[0] == 0
    code, out, err = chantier("push", two["id"], "--unit", "stack")
    assert code == 0, err
    assert out[0].startswith(f"pushed {two['branch']} at {head[:7]}")
    assert tip(remote, two["branch"]) == head
    assert pushes(repo)[0]["unit"] == "stack"


def test_a_remote_that_moved_is_refused_by_git_and_nothing_is_recorded(
    world: World, tmp_path: Path
) -> None:
    repo, chantier, (one, _), remote = world
    wt = Path(one["worktree"])
    commit(wt, "a.txt", "a\n", "A")
    assert chantier("push", one["id"])[0] == 0
    other = tmp_path / "second"  # a second clone pushes to the branch
    sh("git", "clone", "-q", str(remote), str(other))
    sh("git", "switch", "-q", one["branch"], cwd=other)
    moved = commit(other, "z.txt", "z\n", "elsewhere")
    sh("git", "push", "-q", "origin", one["branch"], cwd=other)
    git_at(wt, "commit", "-q", "--amend", "-m", "A again", "--allow-empty")
    code, _, err = chantier("push", one["id"])
    assert code == EXIT_EXTERNAL and "git refused the push" in err, err
    assert "nothing recorded (`help refused-push`)" in err
    assert "stale info" in err or "rejected" in err, err
    assert tip(remote, one["branch"]) == moved
    assert len(pushes(repo)) == 1
