"""`order after`: --note replaces, --add and --remove change one entry; a ref is an id, a slug or a
path. On a prepared record of three queued CRs A, B, C, with B after A."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from batch_helpers import open_batch, record, write_record
from conftest import Chantier

from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE

World = tuple[str, str, str, str, str]  # A, B, C, the slug of C, the path of C


@pytest.fixture
def world(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch) -> World:
    a, b, c = open_batch(repo, chantier, monkeypatch, "Alpha", "Beta", "Gamma")
    code, _, err = chantier("order", "after", b, "--note", a)
    assert code == 0, err
    path = next(x["path"] for x in record(repo)["crs"] if x["id"] == c)
    return a, b, c, path.rsplit("/", 1)[1].split("-", 1)[1], path


def after_of(repo: Path, cr: str) -> list[str]:
    after: list[str] = next(x for x in record(repo)["crs"] if x["id"] == cr).get("after", [])
    return after


def last_note(repo: Path) -> str:
    return str(record(repo)["orders"][-1]["note"])


Case = tuple[str, Callable[[World], tuple[str, ...]], list[int], str]
# (name, args after `order after`, indexes of A, B, C kept in the list, the printed line)
CASES: list[Case] = [
    ("add-id", lambda w: (w[1], "--add", w[2]), [0, 2], "now waits for {0}, {2}"),
    ("add-known", lambda w: (w[1], "--add", w[0]), [0], "now waits for {0} (unchanged)"),
    ("remove", lambda w: (w[1], "--remove", w[0]), [], "{1} waits for nothing"),
    ("remove-absent", lambda w: (w[1], "--remove", w[2]), [0], "now waits for {0} (unchanged)"),
    ("add-slug", lambda w: (w[1], "--add", w[3]), [0, 2], "now waits for {0}, {2}"),
    ("add-ready-path", lambda w: (w[1], "--add", f"3-ready/{w[3]}"), [0, 2], "{2}"),
    ("add-batch-path", lambda w: (w[1], "--add", w[4]), [0, 2], "{2}"),
    ("add-number", lambda w: (w[1], "--add", w[2].removeprefix("CR-")), [0, 2], "{2}"),
    ("target-slug", lambda w: (w[3], "--add", w[0]), [], ""),
    ("note-slug", lambda w: (w[1], "--note", w[3]), [2], "now waits for {2}"),
    ("note-none", lambda w: (w[1], "--note", "-"), [], "waits for nothing"),
]


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_each_form_leaves_the_list_and_the_order_it_should(
    repo: Path, chantier: Chantier, world: World, case: Case
) -> None:
    name, args, kept, line = case
    a, b, c = world[:3]
    target = args(world)[0]
    code, out, err = chantier("order", "after", *args(world))
    assert code == 0, err
    if name == "target-slug":  # the target is C itself: the slug of C waits for A
        target_id, kept = c, [0]
    else:
        target_id = b
    ids = [a, b, c]
    assert after_of(repo, target_id) == [ids[i] for i in kept], target
    note = ", ".join(ids[i] for i in kept) or "-"
    assert last_note(repo) == note
    assert out[0].startswith(f"[chief-of-staff→foreman] order O-2: after {target_id} {note}")
    assert line.format(*ids) in "\n".join(out)


@pytest.mark.parametrize("ref", ["CR-999", "no-such-slug"])
def test_an_unknown_ref_is_refused_naming_the_forms(
    repo: Path, chantier: Chantier, world: World, ref: str
) -> None:
    code, _, err = chantier("order", "after", world[1], "--add", ref)
    assert code == EXIT_PRECONDITION and ref in err
    assert "its id" in err and "folder slug" in err and "path" in err
    assert after_of(repo, world[1]) == [world[0]]


def test_a_cycle_is_refused_and_the_list_is_untouched(
    repo: Path, chantier: Chantier, world: World
) -> None:
    code, _, err = chantier("order", "after", world[0], "--add", world[1])
    assert code == EXIT_PRECONDITION and "cycle" in err
    assert after_of(repo, world[0]) == []


@pytest.mark.parametrize(
    "args",
    [
        ("B", "--note", "x", "--add", "y"),
        ("B",),
        ("B", "--add", ""),
        ("B", "--note", "-", "--remove", "y"),
    ],
)
def test_the_three_forms_are_exclusive(
    chantier: Chantier, world: World, args: tuple[str, ...]
) -> None:
    given = tuple(world[1] if x == "B" else x for x in args)
    code, _, err = chantier("order", "after", *given)
    assert code == EXIT_USAGE and "--add" in err and "--remove" in err and "--note" in err


@pytest.mark.parametrize("flag", ["--add", "--remove"])
def test_add_and_remove_belong_to_after_alone(chantier: Chantier, world: World, flag: str) -> None:
    code, _, err = chantier("order", "note", world[1], flag, world[0])
    assert code == EXIT_USAGE and "order after" in err


def test_two_crs_sharing_a_slug_are_refused_with_both_ids(
    repo: Path, chantier: Chantier, world: World
) -> None:
    data = record(repo)
    by_id = {x["id"]: x for x in data["crs"]}
    by_id[world[2]]["path"] = (
        "4-batch/1-pending/9-" + by_id[world[0]]["path"].rsplit("/", 1)[1].split("-", 1)[1]
    )
    write_record(repo, data)
    slug = by_id[world[0]]["path"].rsplit("/", 1)[1].split("-", 1)[1]
    code, _, err = chantier("order", "after", world[1], "--add", slug)
    assert code == EXIT_PRECONDITION and world[0] in err and world[2] in err
