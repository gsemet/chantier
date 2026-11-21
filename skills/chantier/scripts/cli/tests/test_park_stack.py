"""A CR parked in the middle of a stack: the stack's reads, the refusals of `stack`, `status`'s line
and the forge-stack rebuild, on a batch built by the CLI's own commands."""

from __future__ import annotations

from pathlib import Path

import pytest
from batch_helpers import batch_of, open_batch, record, write_record
from conftest import Chantier
from test_stack_hold import PR, REPO, FakeForge

from chantier.rails import apart_owner, out_of_order
from chantier.stack_words import ready_word
from chantier.stacks import chain, next_merge, stack_base, top_cr


def parked_stack(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """CR-1, CR-2 (parked), CR-3 started on CR-2's branch, CR-4 `after` CR-2: all ready with a PR
    but CR-2, which was working when `park` ran."""
    ids = open_batch(repo, chantier, monkeypatch, "A", "B", "C", "D", args=("--mode", "stack"))
    data = record(repo)
    for i, c in enumerate(data["crs"], 1):
        c.update(
            status="ready",
            pr=f"{PR}{i}",
            pr_draft=False,
            pr_base="main" if i == 1 else f"b/{i - 1}",
            branch=f"b/{i}",
            stacked=i < len(data["crs"]),
            order=i,
        )
    data["crs"][2]["start_on"] = "b/2"
    data["crs"][3].update(after=[ids[1]], pr_base="b/2", stacked=False)
    data["crs"][1]["status"] = "working"
    write_record(repo, data)
    assert chantier("park", ids[1], "--wait", "answer=which API?", "--epoch", 1)[0] == 0
    return ids


def test_a_parked_cr_and_its_dependent_leave_the_stacks_reads_and_status_names_them(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b, c, e = parked_stack(repo, chantier, monkeypatch)
    crs = record(repo)["crs"]
    assert "start_on" not in crs[1] and "start_on" not in crs[2]  # the other one that started on it
    d = batch_of(repo)
    assert [x.id for x in chain(d)] == [a, c]
    top, nxt = top_cr(d), next_merge(d)
    assert top is not None and top.id == c and nxt is not None and nxt.id == a
    dep = d.crs[3]
    assert out_of_order(d.crs, dep, "stack") and apart_owner(d.crs, dep, "stack").id == b
    assert stack_base(d, d.crs[1], REPO) == "main" and stack_base(d, dep, REPO) == "b/2"
    assert ready_word(d, dep, REPO) == "PR in draft"
    _, out, _ = chantier("status")
    line = next(x for x in out if x.startswith(f"parked: {b} since "))
    assert f"waiting with it: {e}" in line and "out of the slots and the stack" in line
    assert chantier("stack")[0] == 0


@pytest.mark.parametrize(
    ("which", "words"),
    [
        ("park", "is parked out of the stack (since "),
        ("dep", "waits with parked {b}: it stays out of the stack until {b} is back"),
    ],
)
def test_stack_refuses_a_parked_cr_and_its_dependent(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, which: str, words: str
) -> None:
    ids = parked_stack(repo, chantier, monkeypatch)
    target = ids[1] if which == "park" else ids[3]
    for argv in (("stack", target, ids[0]), ("stack", "--out-of-draft", target)):
        code, _, err = chantier(*argv)
        assert code != 0 and target in err and words.format(b=ids[1]) in err, err


def test_forge_stack_rebuild_leaves_the_dependents_pr_where_it_is_and_names_it_apart(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    forge = FakeForge({1: "main", 2: "b/1", 3: "b/2", 4: "b/2"}, [1, 2, 3, 4])
    monkeypatch.setattr("chantier.commands.forge_stack.gh", forge)
    monkeypatch.setattr("chantier.commands.forge_stack_gh.gh", forge)
    _, b, _, e = parked_stack(repo, chantier, monkeypatch)
    code, out, err = chantier("forge-stack", "rebuild")
    assert code == 0, err
    text = "\n".join(out)
    assert f"#4 of {e}, waits with parked {b}: left out" in text
    assert "#2 base b/1 -> main (parked out of the stack)" in text
    assert forge.bases[4] == "b/2" and forge.stacks[-1]["prs"] == [1, 3]
    forge.stacks[-1]["prs"] = [1, 3, 4]  # the dependent put into the native stack by hand
    code, out, _ = chantier("forge-stack", "show")
    assert code != 0 and f"#4 of {e}" in "\n".join(out) and "foreign" not in "\n".join(out)
