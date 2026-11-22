"""A CR the record places on another CR's branch holds that CR's recorded head: `ship` refuses one
that does not, `stack --out-of-draft` too, on real commits in the CRs' worktrees."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, NamedTuple

import pytest
from batch_helpers import changes, record, write_record
from conftest import Chantier, sh
from stack_world import Batch, stack_of
from test_carry_ship import remote
from test_gate_carry import commit, git_at

from chantier.commands import delivery
from chantier.core.errors import EXIT_PRECONDITION
from chantier.core.git import is_ancestor
from chantier.core.repo import Repo
from chantier.hub import journal

PR = "https://github.com/acme/demo/pull/{}"
NOT_BASED = "branch not based on"


class World(NamedTuple):
    repo: Path
    chantier: Chantier
    crs: list[dict[str, Any]]

    def wt(self, i: int) -> Path:
        return Path(self.crs[i]["worktree"])

    def cr(self, i: int) -> dict[str, Any]:
        return dict(record(self.repo)["crs"][i])

    def files(self) -> tuple[bytes, bytes]:
        folder = changes(self.repo) / "4-batch"
        return (folder / "batch.json").read_bytes(), (folder / "events.jsonl").read_bytes()

    def edit(self, i: int, **fields: Any) -> None:
        data = record(self.repo)
        data["crs"][i].update(fields)
        write_record(self.repo, data)

    def ship(self, i: int) -> tuple[int, list[str], str]:
        return self.chantier("ship", self.crs[i]["id"], PR.format(i + 1))


def build(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, batch: Batch) -> World:
    """The batch (CRs taken, each in its worktree), `main` on the remote. A PR is a draft on the
    branch below it, or on main for the first: no read of the forge."""

    def main_on_remote(work: Path) -> None:
        remote(work, "main", sh("git", "rev-parse", "HEAD", cwd=work))

    crs = stack_of(replace(batch, after=main_on_remote), repo, chantier, monkeypatch)
    base = {PR.format(i + 1): c["branch"] for i, c in enumerate(crs)}
    state = {PR.format(i + 1): (base[PR.format(i)] if i else "main", True, "") for i in range(3)}
    monkeypatch.setattr(delivery, "read_state", lambda link: state.get(link, ("main", True, "")))
    return World(repo, chantier, crs)


def push(w: World, i: int, name: str) -> str:
    """A commit in CR i's worktree, its branch pushed (the remote ref as the clone has it)."""
    tip = commit(w.wt(i), f"{name}.txt", f"{name}\n", name.upper())
    remote(w.repo, w.crs[i]["branch"], tip)
    return tip


@pytest.fixture
def stack3(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch) -> World:
    return build(repo, chantier, monkeypatch, Batch("chain3", ("Cr a", "Cr b", "Cr c")))


def a_shipped_b_from_main(w: World) -> str:
    """A shipped at its tip, A and B stacked, B's branch cut from main with one commit."""
    a_tip = push(w, 0, "a")
    assert w.ship(0)[0] == 0
    assert w.chantier("stack", w.crs[0]["id"], w.crs[1]["id"])[0] == 0
    push(w, 1, "b")
    return a_tip


def refused(w: World, i: int, *words: str) -> str:
    before = w.files()
    code, _, err = w.ship(i)
    assert code == EXIT_PRECONDITION, err
    assert "nothing recorded" in err and all(x in err for x in words), err
    assert w.files() == before  # no touch, no ship event, no carry event
    return err


def test_the_ancestry_read_has_three_outcomes(repo: Path) -> None:
    head = sh("git", "rev-parse", "HEAD", cwd=repo)
    git_at(repo, "commit", "-q", "--allow-empty", "-m", "next")
    new = sh("git", "rev-parse", "HEAD", cwd=repo)
    assert is_ancestor(head, new, cwd=repo) is True
    assert is_ancestor(new, head, cwd=repo) is False
    assert is_ancestor("f" * 40, new, cwd=repo) is None


def test_ship_refuses_a_stacked_cr_cut_from_main_then_records_it_once_rebased(
    stack3: World,
) -> None:
    w = stack3
    a_tip = a_shipped_b_from_main(w)
    a7 = a_tip[:7]
    refused(w, 1, f"{w.crs[1]['id']}: {NOT_BASED} {w.crs[0]['id']}'s head {a7}", w.crs[0]["branch"])
    git_at(w.wt(1), "rebase", "-q", a_tip)
    remote(w.repo, w.crs[1]["branch"], sh("git", "rev-parse", "HEAD", cwd=w.wt(1)))
    code, _, err = w.ship(1)
    assert code == 0, err
    assert w.cr(1)["head"] == sh("git", "rev-parse", "HEAD", cwd=w.wt(1))


def test_a_new_head_of_the_cr_below_refuses_the_first_message_again(stack3: World) -> None:
    w = stack3
    a_tip = a_shipped_b_from_main(w)
    git_at(w.wt(1), "rebase", "-q", a_tip)
    git_at(w.wt(0), "commit", "-q", "--amend", "-m", "A, reworded")
    a_new = sh("git", "rev-parse", "HEAD", cwd=w.wt(0))
    remote(w.repo, w.crs[0]["branch"], a_new)
    assert w.ship(0)[0] == 0  # A recorded at its new head
    refused(w, 1, f"{NOT_BASED} {w.crs[0]['id']}'s head {a_new[:7]}")


@pytest.mark.parametrize("remote_ref", ["present", "deleted", "recorded not pushed"])
def test_the_second_message_names_a_branch_moved_since_its_last_ship(
    stack3: World, remote_ref: str
) -> None:
    w = stack3
    a_tip = a_shipped_b_from_main(w)
    a_two = ""
    if remote_ref == "recorded not pushed":  # recorded at a new commit, never pushed
        commit(w.wt(0), "a2.txt", "a2\n", "A2")
        assert w.ship(0)[0] == 0
        git_at(w.wt(1), "rebase", "-q", a_tip)
    else:
        git_at(w.wt(0), "commit", "-q", "--amend", "-m", "A, reworded")  # A rewritten
        a_two = sh("git", "rev-parse", "HEAD", cwd=w.wt(0))
        remote(w.repo, w.crs[0]["branch"], a_two)  # pushed, not shipped
        git_at(w.wt(1), "rebase", "-q", a_two)
    if remote_ref == "deleted":
        sh("git", "update-ref", "-d", f"refs/remotes/origin/{w.crs[0]['branch']}", cwd=w.repo)
    if remote_ref == "present":
        refused(w, 1, f"{w.crs[0]['id']}'s branch moved since its last ship ({a_tip[:7]} ->")
        assert a_two[:7] in w.ship(1)[2]
    else:
        err = refused(w, 1, f"{NOT_BASED} {w.crs[0]['id']}'s head")
        assert "moved since" not in err


def test_a_cr_taken_onto_another_crs_branch_and_not_placed_is_checked_with_a_live_start_on(
    stack3: World,
) -> None:
    w = stack3
    a_tip = push(w, 0, "a")
    assert w.ship(0)[0] == 0
    push(w, 1, "b")
    w.edit(1, start_on=w.crs[0]["branch"])
    refused(w, 1, f"{NOT_BASED} {w.crs[0]['id']}'s head {a_tip[:7]}")


def series_world(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, merged: bool
) -> World:
    """A series of two: A taken (its worktree), then handed back or merged, then B taken in a
    worktree cut from main."""
    w = build(
        repo,
        chantier,
        monkeypatch,
        Batch("chain-series", ("Cr a", "Cr b"), args=("--mode", "series"), took=1),
    )
    a_tip = push(w, 0, "a")
    assert w.ship(0)[0] == 0
    w.edit(0, status="merged" if merged else "ready")
    assert chantier("take", w.crs[1]["id"], "--epoch", 1)[0] == 0
    b = w.crs[1]
    sh("git", "worktree", "add", "-q", "-b", b["branch"], b["worktree"], "main", cwd=repo)
    assert a_tip
    return w


def test_a_series_cr_is_checked_against_its_open_predecessor(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    w = series_world(repo, chantier, monkeypatch, merged=False)
    a_tip = w.cr(0)["head"]
    push(w, 1, "b")
    refused(w, 1, f"{NOT_BASED} {w.crs[0]['id']}'s head {a_tip[:7]}")


@pytest.mark.parametrize("case", ["cut from main", "top at a new head"])
def test_the_release_cr_is_checked_against_the_top_cr(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    w = build(repo, chantier, monkeypatch, Batch("chain-release", ("Cr a", "Cr rel")))
    w.edit(1, kind="release")
    a_tip = push(w, 0, "a")
    assert w.ship(0)[0] == 0
    push(w, 1, "r")
    if case == "top at a new head":
        git_at(w.wt(1), "rebase", "-q", a_tip)
        a_tip = commit(w.wt(0), "a2.txt", "a2\n", "A2")
        remote(w.repo, w.crs[0]["branch"], a_tip)
        assert w.ship(0)[0] == 0
    refused(w, 1, f"{NOT_BASED} {w.crs[0]['id']}'s head {a_tip[:7]}")
    git_at(w.wt(1), "rebase", "-q", a_tip)
    assert w.ship(1)[0] == 0


@pytest.mark.parametrize("journal_line", [True, False])
def test_a_cr_below_seen_merged_is_never_the_cr_below(stack3: World, journal_line: bool) -> None:
    w = stack3
    a_shipped_b_from_main(w)
    if journal_line:
        event = {
            "type": "merged@1",
            "batch": record(w.repo)["id"],
            "cr": w.crs[0]["id"],
            "pr": PR.format(1),
            "into": "main",
            "into_cr": None,
            "merged_at": "2026-11-18T10:01:40Z",
        }
        journal.append(Repo.find(), [event], "hub")
        code, _, err = w.ship(1)
        assert code == 0, err
    else:
        refused(w, 1, f"{NOT_BASED} {w.crs[0]['id']}'s head")  # no forge read: the refusal stands


@pytest.mark.parametrize(
    "case",
    [
        "no start_on and not placed",
        "start_on owner merged",
        "start_on owner held",
        "first CR of the stack",
        "release with no CR under it",
        "fix CR",
        "held CR",
    ],
)
def test_a_cr_the_record_does_not_place_on_another_is_not_checked(stack3: World, case: str) -> None:
    w = stack3
    a_tip = push(w, 0, "a")
    assert w.ship(0)[0] == 0
    push(w, 1, "b")
    me, branch = 1, w.crs[0]["branch"]
    if case == "start_on owner merged":
        w.edit(0, status="merged")
        w.edit(1, start_on=branch)
    if case == "start_on owner held":
        w.edit(0, held="O-1")
        w.edit(1, start_on=branch)
    if case == "first CR of the stack":
        me = 0
        assert w.chantier("stack", w.crs[0]["id"], w.crs[1]["id"])[0] == 0
    if case == "release with no CR under it":
        w.edit(0, status="merged")
        w.edit(1, kind="release")
    if case == "fix CR":
        w.edit(1, kind="fix")
    if case == "held CR":
        w.edit(1, held="O-1", stacked=True)
    code, _, err = w.ship(me)
    assert code == 0, err
    assert a_tip


def test_a_series_cr_whose_predecessor_merged_is_not_checked(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    w = series_world(repo, chantier, monkeypatch, merged=True)
    push(w, 1, "b")
    assert w.ship(1)[0] == 0


def test_a_head_of_the_cr_below_git_cannot_read_refuses_and_records_nothing(
    stack3: World,
) -> None:
    w = stack3
    a_shipped_b_from_main(w)
    w.edit(0, head="f" * 40)
    refused(w, 1, f"{w.crs[1]['id']}: git cannot read {w.crs[0]['id']}'s head fffffff: fetch")


def tree_commit(w: World, parent: str, text: str) -> str:
    tree = sh("git", "rev-parse", f"{parent}^{{tree}}", cwd=w.repo)
    return sh(
        "git",
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@e.com",
        "commit-tree",
        tree,
        "-p",
        parent,
        "-m",
        text,
        cwd=w.repo,
    )


def ready_stack(w: World, broken: bool, release: bool = False) -> list[str]:
    """CR-101..103 (and a release) stacked, handed back ready with a draft PR each; the recorded
    heads form a chain, but B's (the second) is cut from main when `broken`."""
    main = sh("git", "rev-parse", "main", cwd=w.repo)
    a = tree_commit(w, main, "A")
    b = tree_commit(w, main if broken else a, "B")
    c = tree_commit(w, b, "C")
    heads = [a, b, c]
    if release:
        heads.append(tree_commit(w, main, "R"))  # the release, off the top CR's head
        w.edit(3, kind="release")
    for i, head in enumerate(heads):
        w.edit(i, status="ready", pr=PR.format(i + 1), pr_draft=True, stacked=True, head=head)
        w.edit(i, order=i + 1)
    return heads


def out_of_draft(w: World, *names: int) -> tuple[int, list[str], str]:
    return w.chantier("stack", "--out-of-draft", *(w.crs[i]["id"] for i in names))


@pytest.mark.parametrize(
    ("named", "pr_words"),
    [
        ((0, 1, 2), "put CR-102, CR-103' PRs back to draft"),
        ((0, 1), "put CR-102' PRs back to draft"),
    ],
)
def test_out_of_draft_refuses_a_cr_whose_recorded_head_is_off_the_cr_below_and_writes_nothing(
    stack3: World, named: tuple[int, ...], pr_words: str
) -> None:
    w = stack3
    heads = ready_stack(w, broken=True)
    before = w.files()
    code, _, err = out_of_draft(w, *named)
    assert code == EXIT_PRECONDITION, err
    assert f"CR-102: {NOT_BASED} CR-101's head {heads[0][:7]}" in err
    assert pr_words in err and "put CR-101" not in err
    assert "then stack --out-of-draft again; nothing recorded" in err
    assert w.files() == before


def test_out_of_draft_accepts_a_chain_that_holds(stack3: World) -> None:
    w = stack3
    ready_stack(w, broken=False)
    code, _, err = out_of_draft(w, 0, 1, 2)
    assert code == 0, err


def test_out_of_draft_reads_a_cr_below_seen_merged_as_ended(stack3: World) -> None:
    w = stack3
    ready_stack(w, broken=True)
    w.edit(0, pr_draft=False)
    event = {
        "type": "merged@1",
        "batch": record(w.repo)["id"],
        "cr": "CR-101",
        "pr": PR.format(1),
        "into": "main",
        "into_cr": None,
        "merged_at": "2026-11-18T10:01:40Z",
    }
    assert out_of_draft(w, 1, 2)[0] == EXIT_PRECONDITION  # the merge is not in the journal yet
    journal.append(Repo.find(), [event], "hub")
    code, _, err = out_of_draft(w, 1, 2)
    assert code == 0, err


def test_out_of_draft_checks_the_release_against_the_top_cr(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    w = build(repo, chantier, monkeypatch, Batch("chain4", ("Cr a", "Cr b", "Cr c", "Cr rel")))
    heads = ready_stack(w, broken=False, release=True)
    code, _, err = out_of_draft(w, 0, 1, 2, 3)
    assert code == EXIT_PRECONDITION, err
    assert f"CR-104: {NOT_BASED} CR-103's head {heads[2][:7]}" in err
    assert "put CR-104' PRs back to draft" in err and "nothing recorded" in err


def test_out_of_draft_refuses_a_recorded_head_git_cannot_read(stack3: World) -> None:
    w = stack3
    ready_stack(w, broken=False)
    w.edit(0, head="f" * 40)
    before = w.files()
    code, _, err = out_of_draft(w, 0, 1, 2)
    assert code == EXIT_PRECONDITION, err
    assert (
        "CR-102: git cannot read CR-101's head fffffff: fetch, then stack --out-of-draft again"
        in err
    )
    assert "nothing recorded" in err and w.files() == before
