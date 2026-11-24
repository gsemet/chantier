"""A CR taken out of a batch (`order drop <cr> --note P2`) comes back under its number, with its
branch and PR while its branch exists: `formerly.json` is read at the join, then deleted."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from batch_helpers import FROM_AGENTS_MD, changes, host, open_bare, prepared, record
from conftest import SKILL, Chantier, sh
from test_batch_end import cr, patch, started
from test_order_drop_to import PR, one

from chantier.core.records import read_batch_json
from chantier.core.repo import Repo

COST = 1.5
NEAR = 400  # characters between the held-CR line and the parked one
CARDS = ("foreman.md", "chief-of-staff.md", "driver.md", "routing.md")
# where each card's moved rules now live, read with it
PIECES = {
    "foreman.md": ("foreman-hold.md", "foreman-refused.md", "foreman-stack.md"),
    "chief-of-staff.md": ("chief-of-staff-merge.md", "chief-of-staff-steering.md"),
    "driver.md": ("driver-retake.md", "driver-refused.md", "driver-session.md"),
    "routing.md": (),
}


def _read(name: str) -> str:
    """A card and its pieces, whitespace folded."""
    names = (name, *PIECES.get(name, ()))
    return " ".join(" ".join((SKILL / "references" / n).read_text("utf-8").split()) for n in names)


def dropped(
    repo: Path, cr_id: str, chantier: Chantier, branch: bool = True, note: str = "P2"
) -> Path:
    """The CR, ready with a PR, dropped to the backlog or `ready` by the real order: its folder."""
    c = cr(repo, cr_id)
    patch(repo, cr_id, status="ready", pr=PR, pr_draft=True, notes=["kept"], cost_usd=COST)
    if branch and not sh("git", "branch", "--list", c["branch"], cwd=repo):
        sh("git", "branch", c["branch"], cwd=repo)
    assert chantier("order", "drop", cr_id, "--note", note)[0] == 0
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


@pytest.mark.parametrize(("branch", "note"), [(True, "P2"), (False, "P2"), (True, "ready")])
def test_a_cr_comes_back_to_its_own_batch_as_the_same_entry(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, branch: bool, note: str
) -> None:
    cr_id, other = started(repo, chantier, monkeypatch, 2, 1)
    before = cr(repo, cr_id)
    folder = dropped(repo, cr_id, chantier, branch, note)
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


def test_order_add_of_a_moved_out_cr_from_3_ready_gives_it_its_number_back(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_bare(repo, chantier, monkeypatch, str(prepared(repo, chantier, "Back")))
    cr_id = record(repo)["crs"][0]["id"]
    folder = dropped(repo, cr_id, chantier)
    before = record(repo)["crs"]
    code, out, err = chantier("triage", str(folder), "--ready")
    assert code == 0 and len(out) == 1 and out[0].startswith("triaged "), err
    assert record(repo)["crs"] == before  # `triage --ready` joins nothing
    code, out, err = chantier("order", "add", "--note", f"3-ready/{folder.name}")
    assert code == 0, err
    assert [c["id"] for c in record(repo)["crs"]] == [cr_id]
    assert any(x.startswith(f"{cr_id} joins with its branch ") for x in out)
    assert (
        read_batch_json(Repo.find().store, changes(repo) / "4-batch" / "batch.json").crs[0].status
        == "queued"
    )
    assert not list(changes(repo).rglob("formerly.json"))
    assert json.loads((changes(repo) / "restored.json").read_text("utf-8"))


def test_the_cards_name_the_way_back_of_a_moved_out_cr() -> None:
    driver = _read("driver.md")
    chief = _read("chief-of-staff.md")
    for words in ("gh pr reopen", "glab mr reopen", "never open a second PR"):
        assert words in " ".join(driver.split()), words
    assert "`order add --note <folder>`" in chief and "then `order merged <cr>`" in chief
    foreman = _read("foreman.md")
    for card, words in (
        (chief, "`ready`, `3-ready`"),
        (foreman, "`6-trash`, `3-ready` or"),
        (driver + " " + _read("stack-driver-changes.md"), "`6-trash`, `3-ready` or"),
    ):
        assert words in card, words
    assert "inbox is not one of them" in chief and "`6-trash`, `1-inbox`" not in foreman


def test_the_cards_name_the_park_and_its_way_back() -> None:
    text = {n: _read(n) for n in CARDS}
    assert "`park <cr> --wait ... --epoch <n>`" in text["foreman.md"]
    assert 'take <cr> --note "wait cleared: <what>" --epoch <n>' in text["foreman.md"]
    assert (
        "rebase: <cr> dropped" in text["foreman.md"] and "rebase: <cr> dropped" in text["driver.md"]
    )
    assert "`[foreman→chief-of-staff] parked <cr>: ...`" in text["foreman.md"]
    assert (
        "Ask nothing" in text["chief-of-staff.md"] and "parked <cr>: <waits>" in text["routing.md"]
    )
    assert "the batch stays open" in text["chief-of-staff.md"]
    chief = _read("chief-of-staff-merge.md")
    held = chief.index("Name each held CR in the batch reports")
    assert 0 < chief.index("Name each parked CR in the batch reports too") - held < NEAR
    assert chief.index("Holding a CR") < held
    chief = _read("chief-of-staff-steering.md")
    typed = chief[chief.index("For a parked CR: `wait <cr> clear <id> --epoch <n>`") :][:500]
    assert 'order note <cr> --note "wait cleared: <what>"' in typed


@pytest.mark.parametrize(
    ("card", "words"),
    [
        ("foreman.md", ("stop hold:", "unhold:", "rebase: <cr> dropped")),
        ("driver.md", ("stop hold:", "stopped: held", "rebase: <cr> dropped")),
        ("routing.md", ("stop hold:",)),
    ],
)
def test_the_cards_name_the_hold_of_a_live_cr(card: str, words: tuple[str, ...]) -> None:
    text = _read(card)
    for w in words:
        assert w in text, w


def test_the_claim_lost_causes_and_the_holding_section_name_the_live_hold() -> None:
    driver = _read("driver-session.md")
    cause = driver[driver.index("- `claim lost`:") :][:400]
    assert "order hold" in cause
    chief = _read("chief-of-staff-merge.md")
    section = chief[chief.index("**Holding a CR:**") :][:600]
    assert "live CR" in section


def test_the_cards_name_the_push_ladder() -> None:
    cards = SKILL / "references"
    raw = (cards / "foreman-refused.md").read_text(encoding="utf-8")
    assert "## A Driver's refused force push" in raw.splitlines()
    text = {n: _read(n) for n in CARDS}
    text["concepts.md"] = " ".join((cards / "concepts.md").read_text(encoding="utf-8").split())
    route = (
        "git push --force-with-lease=<branch>:<expected> <remote> <local sha>:refs/heads/<branch>"
    )
    refused = _read("foreman-refused.md")
    section = refused[refused.index("## A Driver's refused force push") :]
    for words in (
        route,
        "push judged legitimate at",
        "push not tried: route rule missing",
        "[foreman→chief-of-staff] pushed <branch>",
    ):
        assert words in section, words
    for card in ("chief-of-staff.md", "driver.md", "routing.md"):
        assert "foreman-refused.md#a-drivers-refused-force-push" in text[card], card
    chief = text["chief-of-staff.md"]
    assert "the local head holds the remote head's work rebased onto the CR's base" not in chief
    for words in (
        "push judged legitimate",
        "both judgements",
        "on the user's yes",
        "push on the user's go at",
    ):
        assert words in chief, words
    assert "the steering session does not send it" in text["driver.md"]
    assert "the Chief of Staff does not send it" not in text["driver.md"]
    rows = (cards / "routing.md").read_text(encoding="utf-8").splitlines()
    row = next(r for r in rows if r.startswith("| Foreman → Chief of Staff |"))
    assert "`pushed <branch>`" in row and "`push failed <branch> <text>`" in row
    assert f"{route}` (or the same with `git -C <checkout>`)" in text["concepts.md"]
