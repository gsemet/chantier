"""A CR taken out of a batch (`order drop <cr> --note P2`) comes back under its number, with its
branch and PR while its branch exists: `formerly.json` is read at the join, then deleted."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from batch_helpers import FROM_AGENTS_MD, changes, host, open_factory, prepared, record
from conftest import SKILL, Chantier, sh
from test_batch_end import cr, patch, started
from test_order_drop_to import PR, one

from chantier.core.records import read_batch_json
from chantier.core.repo import Repo

COST = 1.5


def dropped(repo: Path, cr_id: str, chantier: Chantier, branch: bool = True) -> Path:
    """The CR, ready with a PR, dropped to the backlog by the real order: its folder."""
    c = cr(repo, cr_id)
    patch(repo, cr_id, status="ready", pr=PR, pr_draft=True, notes=["kept"], cost_usd=COST)
    if branch and not sh("git", "branch", "--list", c["branch"], cwd=repo):
        sh("git", "branch", c["branch"], cwd=repo)
    assert chantier("order", "drop", cr_id, "--note", "P2")[0] == 0
    return Path(changes(repo) / cr(repo, cr_id)["path"])


def number(cr_id: str) -> int:
    return int(cr_id.removeprefix("CR-"))


def test_a_cr_comes_back_to_another_batch_under_its_number_with_its_branch_and_pr(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    cr_id = one(repo, chantier, monkeypatch)
    before = cr(repo, cr_id)
    folder = dropped(repo, cr_id, chantier)
    assert (folder / "formerly.json").is_file()
    shutil.rmtree(changes(repo) / "4-batch")  # the first batch is over
    host(monkeypatch)
    code, out, err = chantier("open", str(folder), *FROM_AGENTS_MD)
    assert code == 0, err
    (entry,) = record(repo)["crs"]
    assert entry["id"] == cr_id and entry["path"].startswith("4-batch/1-pending/")
    assert Path(entry["path"]).name == folder.name
    assert (entry["branch"], entry["worktree"]) == (before["branch"], before["worktree"])
    assert entry["pr"] == PR and entry["pr_draft"] is True
    joins = f"{cr_id} joins with its branch {before['branch']} and PR {PR}"
    assert out[out.index(joins) - 1].startswith(f"{cr_id} ")
    assert not (changes(repo) / entry["path"] / "formerly.json").exists()
    monkeypatch.setenv("CHANTIER_BATCH", record(repo)["id"])
    assert chantier("order", "add", "--note", str(prepared(repo, chantier, "Later")))[0] == 0
    assert number(record(repo)["crs"][-1]["id"]) > number(cr_id)


@pytest.mark.parametrize("branch", [True, False])
def test_a_cr_comes_back_to_its_own_batch_as_the_same_entry(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, branch: bool
) -> None:
    cr_id, other = started(repo, chantier, monkeypatch, 2, 1)
    before = cr(repo, cr_id)
    folder = dropped(repo, cr_id, chantier, branch)
    if not branch:
        sh("git", "worktree", "remove", "--force", before["worktree"], cwd=repo)
        sh("git", "branch", "-D", before["branch"], cwd=repo)
    patch(repo, cr_id, round=2, attempts=1, agent="a1", head="abc", stacked=True, phase="coding")
    rel = folder.relative_to(changes(repo)).as_posix()
    code, out, err = chantier("order", "add", "--note", rel)
    assert code == 0, err
    crs = record(repo)["crs"]
    assert [c["id"] for c in crs].count(cr_id) == 1
    c = cr(repo, cr_id)
    assert c["status"] == "queued" and c["notes"] == ["kept"] and c["cost_usd"] == COST
    assert (c["round"], c["attempts"], c["stacked"]) == (0, 0, False)
    assert not {"agent", "left_to", "head", "phase"} & set(c)
    assert c["order"] == max(x["order"] for x in crs) > cr(repo, other)["order"]
    at = next(i for i, x in enumerate(out) if x.startswith(f"added {cr_id}, queued"))
    assert not (folder / "formerly.json").exists()
    assert not folder.exists() and (changes(repo) / c["path"] / "03-change-spec.md").exists()
    if branch:
        assert c["pr"] == PR and c["pr_draft"] is True and c["branch"] == before["branch"]
        assert out[at + 1] == f"{cr_id} joins with its branch {before['branch']} and PR {PR}"
    else:
        assert "pr" not in c and c["branch"].startswith(f"chantier/{record(repo)['id']}/cr-")
        assert out[at + 1] == (
            f"{cr_id} joins fresh: its branch {before['branch']} is gone; "
            f"its former PR {PR} is left as it is"
        )


def test_triage_ready_of_a_moved_out_cr_joins_a_factory_batch_under_its_number(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_factory(repo, chantier, monkeypatch, "--factory", str(prepared(repo, chantier, "Fac")))
    cr_id = record(repo)["crs"][0]["id"]
    folder = dropped(repo, cr_id, chantier)
    code, out, err = chantier("triage", str(folder), "--ready")
    assert code == 0, err
    assert [c["id"] for c in record(repo)["crs"]] == [cr_id]
    assert any(x.startswith(f"{cr_id} joins with its branch ") for x in out)
    assert out[-1].startswith(f"factory {record(repo)['id']}: {cr_id} joined on its own")
    assert (
        read_batch_json(Repo.find().store, changes(repo) / "4-batch" / "batch.json").crs[0].status
        == "queued"
    )
    assert not list(changes(repo).rglob("formerly.json"))
    assert json.loads((changes(repo) / "restored.json").read_text("utf-8"))


def test_the_cards_name_the_way_back_of_a_moved_out_cr() -> None:
    cards = SKILL / "references"
    driver = (cards / "driver.md").read_text(encoding="utf-8")
    chief = " ".join((cards / "chief-of-staff.md").read_text(encoding="utf-8").split())
    for words in ("gh pr reopen", "glab mr reopen", "never open a second PR"):
        assert words in " ".join(driver.split()), words
    assert "`order add --note <folder>`" in chief and "then `order merged <cr>`" in chief
