"""`order hold` / `order unhold`: a ready CR held out of a stack, on a prepared record."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from batch_helpers import changes, events, open_batch, record, write_record
from conftest import Chantier

from chantier.commands.orders_merged import check_merged
from chantier.core.batch import Batch, read_batch, resolve_batch
from chantier.core.errors import ChantierError
from chantier.core.records import BatchRecord, CrEntry
from chantier.core.repo import Repo
from chantier.stack_words import draft_clause, draft_waited, draft_waits
from chantier.stacks import (
    chain,
    held_lines,
    next_merge,
    stack_base,
    stack_top,
    start_base,
    start_on_for,
    top_cr,
)
from chantier.status.words import state_label

PR = "https://github.com/o/r/pull/"
REPO = cast(Repo, SimpleNamespace(config={"default_branch": "main"}))
UNHOLD = "`order unhold CR-2`"
WAIT = f"held out of the stack (order O-1): {UNHOLD}"


def cr(n: int, **kw: Any) -> CrEntry:
    fields: dict[str, Any] = {
        "status": "ready",
        "pr": f"{PR}{n}",
        "order": n,
        "branch": f"b/cr-{n}",
        "pr_draft": False,
    }
    return CrEntry(id=f"CR-{n}", **{**fields, **kw})


def stack_of(*crs: CrEntry) -> BatchRecord:
    return BatchRecord(id="batch-01", mode="stack", crs=list(crs))


def held_stack() -> BatchRecord:
    """CR-1 bottom, CR-2 held (it started on CR-1), CR-3 on top (it started on CR-2), release."""
    return stack_of(
        cr(1, stacked=True),
        cr(2, held="O-1", stacked=False, pr_base="main"),
        cr(3, stacked=True, start_on="b/cr-2", pr_base="b/cr-2"),
        cr(4, kind="release", pr=None, status="queued"),
    )


def test_a_held_cr_is_outside_the_stack_in_every_read_of_the_record() -> None:
    d = held_stack()
    assert [c.id for c in chain(d)] == ["CR-1", "CR-3", "CR-4"]
    top, merge, tip = top_cr(d), next_merge(d), stack_top(d)
    assert top is not None and top.id == "CR-3"
    assert merge is not None and merge.id == "CR-1"
    assert tip is not None and tip.id == "CR-3"
    assert stack_base(d, d.crs[2], REPO, planned=True) == "b/cr-1"  # on the CR below the held one
    new = cr(9, status="queued", pr=None)
    d.crs.append(new)
    assert start_on_for(d, new) == "b/cr-3"  # never on the held one
    d.crs.remove(new)
    d.crs[0].status = "merged"  # a stale `held` on an ended CR reads as not held
    d.crs[1].status = "merged"
    assert [c.id for c in chain(d)] == ["CR-3", "CR-4"] and held_lines(d, REPO) == []


def test_a_held_crs_base_is_the_default_branch_even_when_it_started_on_another_cr() -> None:
    d = held_stack()
    held, above = d.crs[1], d.crs[2]
    held.start_on = "b/cr-1"
    assert start_base(d, held, REPO) == "main"
    assert stack_base(d, held, REPO) == "main"
    assert stack_base(d, held, REPO, planned=True) == "main"
    assert start_base(d, above, REPO) == "main"  # its owner is held: the default branch
    assert start_base(d, cr(5, start_on="b/cr-1"), REPO) == "b/cr-1"


def test_a_placed_crs_start_on_owner_ended_falls_back_below_and_held_goes_to_default() -> None:
    d = held_stack()
    above = d.crs[2]
    assert start_base(d, above, REPO) == "main"  # owner held
    d.crs[1].held = None
    d.crs[1].status = "cancelled"  # owner ended: the nearest CR below with a PR
    assert start_base(d, above, REPO) == "b/cr-1"


def test_a_held_crs_waits_text_names_the_hold_and_the_way_back() -> None:
    d = held_stack()
    held = d.crs[1]
    assert draft_waited(d, held, REPO) == f"held out of the stack (order O-1): {UNHOLD}"
    assert draft_waits(d, held, REPO) == WAIT
    held.pr_draft = True
    assert draft_clause(d, held, REPO, False) == (
        f"its PR {held.pr} is a draft on the forge; it waits: {WAIT}"
    )
    assert WAIT in state_label(REPO, d, held, [])


def shown(repo: Path) -> list[str]:
    r = Repo.find()
    d = read_batch(r, resolve_batch(r, None))
    return held_lines(d, r)


def stacked_batch(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, mode: str = "stack"
) -> list[str]:
    """Three CRs ready with a PR, CR-2 started on CR-1's branch, CR-3 on CR-2's."""
    ids = open_batch(repo, chantier, monkeypatch, "A", "B", "C", args=("--mode", mode))
    data = record(repo)
    for i, c in enumerate(data["crs"], 1):
        c.update(
            status="ready",
            pr=f"{PR}{i}",
            pr_draft=False,
            pr_base="main" if i == 1 else f"b/{i - 1}",
            branch=f"b/{i}",
            stacked=True,
            order=i,
        )
        if i > 1:
            c["start_on"] = f"b/{i - 1}"
    write_record(repo, data)
    return ids


def make_release(c: dict[str, Any]) -> None:
    c["kind"] = "release"


def make_fix(c: dict[str, Any]) -> None:
    c["kind"] = "fix"


def make_blocked(c: dict[str, Any]) -> None:
    c["status"] = "blocked"


def make_queued(c: dict[str, Any]) -> None:
    c["status"] = "queued"


def make_held(c: dict[str, Any]) -> None:
    c["held"] = "O-1"


@pytest.mark.parametrize(
    ("case", "words"),
    [
        (("parallel", None), "is ready in a parallel batch: a ready CR holds no slot"),
        (("series", None), "is ready in a series batch: a ready CR holds no slot"),
        (("stack", make_release), "the release CR"),
        (("stack", make_fix), "a fix CR"),
        (("stack", make_blocked), "is blocked; only a live CR, or a ready CR of a stack, is held"),
        (("stack", make_queued), "is queued; only a live CR, or a ready CR of a stack, is held"),
        (("stack", make_held), "is already held (order O-1)"),
        (("stack", "after"), "depends on"),
    ],
)
def test_order_hold_refuses_and_writes_nothing(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    case: tuple[str, Callable[[dict[str, Any]], None] | str | None],
    words: str,
) -> None:
    mode, mutate = case
    ids = stacked_batch(repo, chantier, monkeypatch, mode)
    data = record(repo)
    if callable(mutate):
        mutate(data["crs"][0])
    elif mutate == "after":
        data["crs"][1]["after"] = [ids[0]]
    write_record(repo, data)
    path = changes(repo) / "4-batch" / "batch.json"
    log = changes(repo) / "4-batch" / "events.jsonl"
    before = (path.read_bytes(), log.read_bytes())
    code, _, err = chantier("order", "hold", ids[0])
    assert code != 0 and words in err
    code, _, err = chantier("order", "unhold", ids[2])
    assert code != 0 and "is not held" in err
    assert (path.read_bytes(), log.read_bytes()) == before


def test_hold_leaves_the_cr_apart_and_unhold_puts_it_back_on_top(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b, c = stacked_batch(repo, chantier, monkeypatch)
    code, out, err = chantier("order", "hold", b)
    assert code == 0, err
    assert any(x.startswith(f"{b} held out of the stack (order O-1): ") for x in out)
    data = record(repo)
    held, above = data["crs"][1], data["crs"][2]
    assert held["held"] == "O-1" and held["stacked"] is False and "start_on" not in held
    assert "start_on" not in above and above["stacked"] is True
    order = data["orders"][-1]
    assert (order["kind"], order["cr"], order["applied"]) == ("hold", b, True)
    assert [e["kind"] for e in events(repo)[-2:]] == ["hold", "order"] or any(
        e["kind"] == "hold" and e["cr"] == b for e in events(repo)
    )
    r = Repo.find()
    d = read_batch(r, resolve_batch(r, None))
    assert [x.id for x in chain(d)] == [a, c]
    assert stack_base(d, d.crs[2], r, planned=True) == d.crs[0].branch
    code, out, _ = chantier("stack")
    assert code == 0 and not any(x.startswith(f"{b} ") for x in out)
    assert any(
        x.startswith(f"held: {b} (order O-1) out of the stack, PR {PR}2 on main") for x in out
    )
    code, out, _ = chantier("status")
    assert any(x.startswith(f"held: {b} ") and f"`order unhold {b}`" in x for x in out)
    top = max(x["order"] for x in data["crs"])
    code, out, err = chantier("order", "unhold", b)
    assert code == 0 and any("back in the stack, on top" in x for x in out), err
    back = record(repo)["crs"][1]
    assert "held" not in back and back["order"] == top + 1
    d = read_batch(r, resolve_batch(r, None))
    assert [x.id for x in chain(d)] == [a, c, b]


def test_a_held_cr_is_refused_by_stack_out_of_draft_and_take_but_its_draft_is_recorded(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    a, b, c = stacked_batch(repo, chantier, monkeypatch)
    assert chantier("order", "hold", b)[0] == 0
    path = changes(repo) / "4-batch" / "batch.json"
    log = changes(repo) / "4-batch" / "events.jsonl"
    before = (path.read_bytes(), log.read_bytes())
    for args, words in [
        (("stack", b, a, c), "is held out of the stack (order O-1)"),
        (("stack", "--out-of-draft", b), "unhold it first"),
        (
            ("take", b, "--note", "again", "--epoch", "1"),
            f"only the user's `order unhold {b}` releases it",
        ),
    ]:
        code, _, err = chantier(*args)
        assert code != 0 and words in err
    assert (path.read_bytes(), log.read_bytes()) == before
    code, out, err = chantier("stack", "--draft", b)
    assert code == 0 and out == [f"{b} PR in draft"], err
    assert record(repo)["crs"][1]["pr_draft"] is True


@pytest.mark.parametrize("to", ["series", "parallel"])
def test_leaving_a_stack_lets_a_held_cr_go_with_a_unique_order(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, to: str
) -> None:
    _, b, _ = stacked_batch(repo, chantier, monkeypatch)
    assert chantier("order", "hold", b)[0] == 0
    data = record(repo)
    data["crs"][1]["order"] = 3  # `stack` renumbered the chain only: the held CR's order is stale
    data["crs"][2]["order"] = 3
    write_record(repo, data)
    code, out, err = chantier("order", "mode", "--note", to)
    assert code == 0, err
    assert f"{b}: no longer held (the batch leaves the stack)" in out
    crs = record(repo)["crs"]
    assert all("held" not in x for x in crs)
    open_ = [x["order"] for x in crs if x["status"] not in {"merged", "cancelled"}]
    assert len(set(open_)) == len(open_)


def test_a_held_cr_merged_on_the_default_branch_is_recorded_merged_and_the_release_waits() -> None:
    d = held_stack()
    batch = cast(Batch, SimpleNamespace(record=d))
    with pytest.raises(ChantierError, match="CR-1, CR-2, CR-3 not merged or cancelled"):
        check_merged(batch, d.crs[3])
    assert check_merged(batch, d.crs[1]) is False


def test_order_merged_of_a_held_cr_is_accepted_and_unsets_the_hold(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, b, _ = stacked_batch(repo, chantier, monkeypatch)
    assert chantier("order", "hold", b)[0] == 0
    code, _, err = chantier("order", "merged", b)
    assert code == 0, err
    crs = record(repo)["crs"]
    assert crs[1]["status"] == "merged" and "held" not in crs[1]


class FakeForge:
    """The forge's REST calls the stack commands make, on a few PRs: each has a base and a draft
    flag, and the stacks are lists of PR numbers."""

    def __init__(self, bases: dict[int, str], stack: list[int]) -> None:
        self.bases = dict(bases)
        self.stacks: list[dict[str, Any]] = [{"number": 7, "open": True, "prs": list(stack)}]
        self.calls: list[str] = []

    def __call__(self, args: list[str], host: str, *, empty_ok: bool = False) -> Any:
        method, path = args[1], args[2].split("/", 3)[3]
        numbers = [int(x.split("=")[1]) for x in args if x.startswith("pull_requests[]=")]
        self.calls.append(f"{method} {path}")
        if path.startswith("pulls/"):
            n = int(path.split("/")[1])
            if method == "PATCH":
                self.bases[n] = args[args.index("-f") + 1].removeprefix("base=")
            return {"base": {"ref": self.bases[n]}}
        if path == "stacks" and method == "GET":
            return [self.shape(s) for s in self.stacks]
        if path == "stacks":
            self.stacks.append({"number": 355, "open": True, "prs": numbers})
            return {"number": 355}
        number = int(path.split("/")[1])
        stack = next(s for s in self.stacks if s["number"] == number)
        if path.endswith("/unstack"):
            stack["open"] = False
            return None
        return self.shape(stack)

    def shape(self, stack: dict[str, Any]) -> dict[str, Any]:
        prs = [{"number": n, "draft": False} for n in stack["prs"]]
        return {"number": stack["number"], "open": stack["open"], "pull_requests": prs}


def forge_batch(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, forge: FakeForge
) -> list[str]:
    """Five CRs ready: CR-2 held in the middle, CR-5 held at the top, the rest stacked."""
    ids = open_batch(repo, chantier, monkeypatch, "A", "B", "C", "D", "E", args=("--mode", "stack"))
    data = record(repo)
    for i, c in enumerate(data["crs"], 1):
        c.update(
            status="ready",
            pr=f"{PR}{i}",
            pr_draft=False,
            pr_base="main" if i == 1 else f"b/{i - 1}",
            branch=f"b/{i}",
            stacked=True,
            order=i,
        )
    write_record(repo, data)
    for i in (2, 5):
        assert chantier("order", "hold", ids[i - 1])[0] == 0
    monkeypatch.setattr("chantier.commands.forge_stack.gh", forge)
    monkeypatch.setattr("chantier.commands.forge_stack_gh.gh", forge)
    return ids


def test_forge_stack_rebuild_leaves_the_held_prs_out_on_the_default_branch(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    bases = {1: "main", 2: "b/1", 3: "b/2", 4: "b/3", 5: "b/4"}
    forge = FakeForge(bases, [1, 2, 3, 4, 5])
    _, b, _, _, e = forge_batch(repo, chantier, monkeypatch, forge)
    code, out, err = chantier("forge-stack", "rebuild")
    assert code == 0, err
    text = "\n".join(out)
    assert f"#2 of {b} #5 of {e}, held out of the stack: left out" in text
    assert "#2 base b/1 -> main (held out of the stack)" in text
    assert "#5 base b/4 -> main (held out of the stack)" in text
    assert forge.bases == {1: "main", 2: "main", 3: "b/1", 4: "b/3", 5: "main"}
    assert forge.stacks[-1]["prs"] == [1, 3, 4]
    forge.stacks[-1]["prs"] = [1, 2, 3, 4]  # a held PR back in the stack as it stands
    code, out, _ = chantier("forge-stack", "show")
    assert (
        code != 0
        and f"check 2: #2 of {b} is held out of the stack and still in stack #355" in "\n".join(out)
    )
