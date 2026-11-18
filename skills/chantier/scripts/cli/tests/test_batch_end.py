"""The end of a batch's last CR: the merged CRs' worktrees and branches are removed and the batch
is paused by the CLI (`order merged`, `handback released`, `cancel`, `order drop`)."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import open_batch, record, write_record
from conftest import Chantier, sh

from chantier.commands.closing import _to_remove
from chantier.core.records import read_batch_json
from chantier.core.repo import Repo

LEFTOVERS = 3


def cr(repo: Path, cr_id: str) -> dict[str, Any]:
    return next(c for c in record(repo)["crs"] if c["id"] == cr_id)


def exists(repo: Path, cr_id: str) -> tuple[bool, bool]:
    """Whether the CR's worktree folder and its branch exist."""
    c = cr(repo, cr_id)
    return Path(c["worktree"]).exists(), bool(sh("git", "branch", "--list", c["branch"], cwd=repo))


def started(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    count: int,
    took: int,
    *flags: object,
) -> list[str]:
    """A batch of `count` CRs, the first `took` of them taken, each with its real worktree."""
    ids = open_batch(repo, chantier, monkeypatch, *[f"End {i}" for i in range(count)], args=flags)
    for cr_id in ids[:took]:
        assert chantier("take", cr_id, "--epoch", 1)[0] == 0
        c = cr(repo, cr_id)
        sh("git", "worktree", "add", "-q", "-b", c["branch"], c["worktree"], cwd=repo)
    return ids


def merge(chantier: Chantier, cr_id: str, own: bool = True) -> tuple[int, list[str], str]:
    return chantier("order", "merged", cr_id, *(("--epoch", 1) if own else ()))


def patch(repo: Path, cr_id: str, **fields: Any) -> None:
    crs = [{**c, **fields} if c["id"] == cr_id else c for c in record(repo)["crs"]]
    write_record(repo, {**record(repo), "crs": crs})


@pytest.mark.parametrize("end", ["merged-chief", "merged-own", "released", "cancel", "drop"])
def test_the_end_of_the_last_cr_cleans_the_merged_crs_and_pauses_the_batch(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, end: str
) -> None:
    first, last = started(repo, chantier, monkeypatch, 2, 1 if end == "drop" else 2)
    if end == "released":
        patch(repo, last, kind="release")
    code, out, _ = merge(chantier, first)  # not the last: nothing is paused or removed
    assert code == 0 and record(repo)["status"] == "running"
    assert exists(repo, first) == (True, True) and not any("cleanup" in line for line in out)
    code, out, err = {
        "merged-chief": lambda: merge(chantier, last, own=False),
        "merged-own": lambda: merge(chantier, last),
        "released": lambda: chantier("handback", last, "ready", "v1.0.0"),
        "cancel": lambda: chantier("cancel", last, "--epoch", 1),
        "drop": lambda: chantier("order", "drop", last),
    }[end]()
    assert code == 0, err
    data = record(repo)
    assert data["status"] == "paused" and data["paused"] and data["summary"]
    assert data["heartbeat_stopped"] and all(o.get("done") for o in data["orders"])
    assert any(line.startswith(f"cleanup: {first} worktree") and "removed" in line for line in out)
    assert any(line.startswith("paused batch-") for line in out)
    assert not any("not paused" in line for line in out)
    assert any(line.startswith("next: the retro (with its critic)") for line in out)
    assert exists(repo, first) == (False, False)
    if end == "cancel":  # a cancelled CR's worktree and branch stay for the user's word
        assert exists(repo, last) == (True, True)
    if end in ("merged-chief", "merged-own", "released"):
        assert exists(repo, last) == (False, False)


def test_a_merged_cr_whose_driver_is_still_held_is_kept_and_the_batch_is_paused(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, last = started(repo, chantier, monkeypatch, 2, 2)
    patch(repo, last, kind="release")
    for cr_id in (first, last):
        assert chantier("agents", "set", cr_id, f"agent-{cr_id}", "--epoch", 1)[0] == 0
    assert merge(chantier, first)[0] == 0
    code, out, _ = chantier("handback", last, "ready", "v1.0.0")
    assert code == 0 and record(repo)["status"] == "paused"
    assert f"cleanup: {first} kept: agent agent-{first} still held" in out
    assert f"cleanup: {last} kept: agent agent-{last} still held" in out
    assert exists(repo, first) == (True, True) and exists(repo, last) == (True, True)
    assert any(line.startswith("kept: remove them") for line in out)


@pytest.mark.parametrize("blocker", ["note", "stack"])
def test_a_blocked_pause_leaves_the_end_recorded_and_cleans_nothing(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, blocker: str
) -> None:
    first, last = started(repo, chantier, monkeypatch, 2, 2)
    assert merge(chantier, first)[0] == 0
    if blocker == "note":
        assert chantier("order", "note", "--note", "think about it")[0] == 0
    else:
        write_record(repo, {**record(repo), "stack_agent": "stack-1"})
    code, out, _ = merge(chantier, last)
    assert code == 0 and record(repo)["status"] == "running"
    assert cr(repo, last)["status"] == "merged"
    assert any("every CR is merged or cancelled, not paused: " in line for line in out)
    assert exists(repo, first) == (True, True) and exists(repo, last) == (True, True)
    status = chantier("status")[1]
    cause = "orders pending" if blocker == "note" else "stack driver stack-1"
    assert any(
        "every CR is merged or cancelled, not paused: " in line and cause in line for line in status
    )


def test_a_release_crs_order_merged_and_the_drop_of_a_live_cr_pause_nothing(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, last = started(repo, chantier, monkeypatch, 2, 2)
    assert merge(chantier, first)[0] == 0
    patch(repo, last, kind="release", status="ready", pr="https://example.com/pr/1")
    code, out, _ = merge(chantier, last)  # the release PR merged: the procedure goes on
    assert code == 0 and record(repo)["status"] == "running"
    assert cr(repo, last)["status"] == "queued"
    assert not any(line.startswith(("cleanup", "paused")) for line in out)
    patch(repo, last, status="working")
    code, out, _ = chantier("order", "drop", last)  # a live CR: the Foreman stops its Driver
    assert code == 0 and record(repo)["status"] == "running"
    assert not any(line.startswith(("cleanup", "paused")) for line in out)


@pytest.mark.parametrize("pr", ["https://example.com/pr/1", None])
def test_a_merged_release_crs_pr_stays_in_its_record(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    pr: str | None,
) -> None:
    first, last = started(repo, chantier, monkeypatch, 2, 2)
    assert merge(chantier, first)[0] == 0
    patch(repo, last, kind="release", status="ready", pr=pr)
    assert merge(chantier, last)[0] == 0
    c = cr(repo, last)
    assert c["pr"] is None and c["merged_pr"] == (pr or "the release PR")
    assert (f"PR: {pr} (merged);" if pr else "PR: none;") in " ".join(chantier("handoff", last)[1])
    row = next(x for x in chantier("status")[1] if x.startswith(f"{last} "))
    assert (f" {pr} " in row) if pr else (" - " in row)
    status = json.loads(
        (repo / ".agents" / "changes" / c["path"] / "STATUS.json").read_text(encoding="utf-8")
    )
    assert (status["pr"] or {}).get("url") == pr
    code, out, _ = chantier("release", "go", last, "--note", "merged")
    assert code == 0 and any("go" in x and "was merged" in x for x in out)


def test_a_stack_line_marks_a_merged_release_pr_and_not_an_open_one(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, last = open_batch(
        repo, chantier, monkeypatch, "Stack a", "Stack b", args=("--mode", "stack")
    )
    patch(repo, first, status="ready", pr="https://example.com/pr/2")
    patch(repo, last, kind="release", status="queued", merged_pr="https://example.com/pr/1")
    lines = chantier("stack")[1]
    assert any(
        x.startswith(f"{first} ") and " PR https://example.com/pr/2 head" in x for x in lines
    )
    assert any(
        x.startswith(f"{last} ") and " PR https://example.com/pr/1 (merged) head" in x
        for x in lines
    )


def test_a_worktree_git_refuses_to_remove_is_kept_with_its_branch(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, last = started(repo, chantier, monkeypatch, 2, 2)
    (Path(cr(repo, first)["worktree"]) / "wip.txt").write_text("uncommitted\n")
    assert merge(chantier, first)[0] == 0
    code, out, _ = merge(chantier, last)
    assert code == 0 and record(repo)["status"] == "paused"
    assert any(
        line.startswith(f"cleanup: {first} worktree") and "not removed:" in line for line in out
    )
    assert exists(repo, first) == (True, True) and exists(repo, last) == (False, False)


@pytest.mark.skipif(sys.platform != "win32", reason="an open handle blocks a delete on Windows")
def test_a_worktree_with_a_file_held_open_is_kept_and_the_batch_is_paused(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, last = started(repo, chantier, monkeypatch, 2, 2)
    assert merge(chantier, first)[0] == 0
    with open(Path(cr(repo, last)["worktree"]) / "README.md", "rb"):
        code, out, _ = merge(chantier, last)
    assert code == 0 and record(repo)["status"] == "paused"
    assert any(
        line.startswith(f"cleanup: {last} worktree") and "not removed:" in line for line in out
    )
    assert exists(repo, last)[1]


def test_close_names_the_merged_crs_leftovers_beside_the_dropped_ones(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    kept, folderless, removed, dropped = started(repo, chantier, monkeypatch, 4, 4)
    (Path(cr(repo, kept)["worktree"]) / "wip.txt").write_text("uncommitted\n")
    assert chantier("agents", "set", folderless, "agent-x", "--epoch", 1)[0] == 0
    for cr_id in (kept, folderless):
        assert merge(chantier, cr_id)[0] == 0
    shutil.rmtree(cr(repo, folderless)["worktree"])
    assert chantier("cancel", dropped, "--epoch", 1)[0] == 0
    assert merge(chantier, removed, own=False)[0] == 0
    assert record(repo)["status"] == "paused"
    batch = read_batch_json(repo / ".agents" / "changes" / "4-batch" / "batch.json")
    line = _to_remove(Repo.find(), batch)
    assert any(x.startswith(f"{kept} (merged) worktree") and " branch " in x for x in line)
    assert f"{folderless} (merged) branch {cr(repo, folderless)['branch']}" in line
    assert (
        any(x.startswith(f"{dropped} (dropped) worktree") for x in line) and len(line) == LEFTOVERS
    )
    assert not any(x.startswith(removed) for x in line)


def test_the_end_of_the_last_cr_of_a_factory_batch_waits_for_the_next_ready_cr(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, last = started(repo, chantier, monkeypatch, 2, 2, "--factory")
    assert record(repo)["factory"] is True and merge(chantier, first)[0] == 0
    code, out, err = merge(chantier, last)
    assert code == 0, err
    assert record(repo)["status"] == "paused" and exists(repo, last) == (False, False)
    assert any(line.startswith("cleanup: ") for line in out)  # cleaned as in any batch
    text = " ".join(out)
    assert "waits for its next ready CR" in text and "order factory off" in text
    assert "offer the close" not in text and "the retro (with its critic)" not in text
