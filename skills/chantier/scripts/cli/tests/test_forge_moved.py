"""`forge-stack`: a CR moved out to the inbox or the backlog keeps its PR, left out on main."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from batch_helpers import open_batch, record, write_record
from conftest import Chantier
from test_stack_hold import PR, FakeForge

from chantier.commands import forge_stack_gitlab as gl

TWO = 2
BASES = {1: "main", 2: "b/1", 3: "b/2", 4: "b/3"}


def moved_batch(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, forge: FakeForge
) -> list[str]:
    """Four CRs with a PR in a stack: CR-2 moved to the backlog, CR-4 sent to the trash."""
    ids = open_batch(repo, chantier, monkeypatch, "A", "B", "C", "D", args=("--mode", "stack"))
    data = record(repo)
    for i, c in enumerate(data["crs"], 1):
        c.update(status="ready", pr=f"{PR}{i}", pr_draft=False, branch=f"b/{i}", stacked=True)
        c.update(order=i, pr_base=BASES[i])
    data["crs"][1].update(status="cancelled", left_to="2-backlog/P2")
    data["crs"][3].update(status="cancelled", left_to="6-trash")
    write_record(repo, data)
    monkeypatch.setattr("chantier.commands.forge_stack.gh", forge)
    monkeypatch.setattr("chantier.commands.forge_stack_gh.gh", forge)
    return ids


def test_forge_stack_rebuild_names_a_moved_pr_apart_and_leaves_it_on_main(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = FakeForge(BASES, [1, 2, 3, 4])
    _, two, _, four = moved_batch(repo, chantier, monkeypatch, forge)
    code, out, err = chantier("forge-stack", "rebuild")
    assert code == 0, err
    text = "\n".join(out)
    assert f"#2 of {two}, moved to 2-backlog/P2: left out, on main" in text
    assert f"#4 of {four}" in text and f"#4 of {four}, moved" not in text
    assert "#2 base b/1 -> main (moved to 2-backlog/P2)" in text
    assert "foreign" not in text
    assert forge.bases[TWO] == "main" and TWO not in forge.stacks[-1]["prs"]
    forge.stacks[-1]["prs"] = [1, 2, 3]  # a moved PR back in the stack as it stands
    code, out, _ = chantier("forge-stack", "show")
    assert code != 0
    assert f"check 2: #2 of {two}, moved to 2-backlog/P2, is left out of the stack" in "\n".join(
        out
    )


def test_a_gitlab_chain_retargets_a_moved_mr_to_the_default_branch_with_its_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    targets = {1: "main", 2: "b/1"}

    def fake(
        path: str, host: str, method: str = "GET", fields: dict[str, str] | None = None
    ) -> Any:
        if method == "PUT" and fields:
            targets[int(path.rsplit("/", 1)[1])] = fields["target_branch"]
        if path.endswith("merge_requests"):
            return []
        n = int(path.rsplit("/", 1)[1])
        return {"iid": n, "state": "opened", "target_branch": targets[n], "source_branch": f"b/{n}"}

    monkeypatch.setattr(gl, "glab", fake)
    link = "https://gitlab.com/o/r/-/merge_requests/1"
    rows = [
        {
            "number": 1,
            "base": "main",
            "branch": "b/1",
            "release": False,
            "link": link,
            "cr": "CR-1",
            "head": "-",
            "status": "ready",
            "word": "ready",
            "recorded": False,
            "default": "main",
        }
    ]
    moved = [{"number": 2, "base": "main", "why": " (moved to 2-backlog/P2)"}]
    out, _ = gl.make(rows, [], ("gitlab.com", "o/r", ""), moved)
    assert "!2 target b/1 -> main (moved to 2-backlog/P2)" in out and targets[TWO] == "main"
