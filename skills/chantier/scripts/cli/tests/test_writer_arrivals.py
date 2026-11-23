"""The surface's writer tells each CR that an integration of the upstream brought into a project's
inbox or backlog (`arrived@1`, `via: pull`), over a real surface and a real bare origin."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from typing import Any

import pytest
from conftest import sh
from writer_rig import QUIET, Rig

from chantier.hub.schemas import PUBLISHED

CH = "projects/demo/changes/"
FETCH = 70.0  # past the 60 s between two fetches


def arrived(r: Rig) -> list[dict[str, Any]]:
    return [x for x in r.lines() if x["type"] == "arrived@1"]


def other_commit(r: Rig, message: str, *moves: tuple[str | None, str | None]) -> str:
    """The other machine's commit: each (source, target) a move, a write (no source) or a removal
    (no target) of a CR's intent, relative to the changes folder; pushed. The origin's head."""
    sh("git", "pull", "-q", "--rebase", cwd=r.other)
    for source, target in moves:
        if source and target and source != target:
            (r.other / CH / target).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(r.other / CH / source), str(r.other / CH / target))
        elif target:
            r.write(CH + target + "/01-intent.md", message, where=r.other)
        elif source:
            shutil.rmtree(r.other / CH / source)
    sh("git", "add", "-A", cwd=r.other)
    sh("git", "commit", "-qm", message, cwd=r.other)
    sh("git", "push", "-q", "origin", "main", cwd=r.other)
    return r.pushed()


@pytest.mark.parametrize(
    ("first", "then", "told"),
    [
        (None, "1-inbox/s", ("new in 1-inbox", None)),
        (None, "2-backlog/P2/s", ("new in 2-backlog/P2", None)),
        ("1-inbox/s", "2-backlog/P1/s", ("moved from 1-inbox/s", "1-inbox/s")),
        ("2-backlog/P2/s", "2-backlog/P1/s", ("moved from 2-backlog/P2/s", "2-backlog/P2/s")),
        ("3-ready/s", "2-backlog/P3/s", ("back from 3-ready", "3-ready/s")),
        ("6-trash/261101-1000-s", "1-inbox/s", None),
        ("5-archives/261101-1000-s", "1-inbox/s", None),
        ("1-inbox/s", "3-ready/s", None),
        ("1-inbox/s", "4-batch/1-pending/s", None),
        ("1-inbox/s", "1-inbox/s", None),
    ],
)
def test_a_cr_another_machine_brings_into_the_inbox_or_the_backlog_is_told_once(
    rig: Callable[[], Rig], first: str | None, then: str, told: tuple[str, str | None] | None
) -> None:
    r = rig()
    if first:
        other_commit(r, "first", (None, first))
        r.tick()
        r.tick(QUIET)
    base = len(arrived(r))
    head = other_commit(r, "then", (first, then))
    r.tick(FETCH)
    r.tick(FETCH)
    lines = arrived(r)[base:]
    if told is None:
        assert not lines
        return
    (line,) = lines
    assert (line["folder"], line["stage"], line["before"]) == (
        then,
        then.rsplit("/", 1)[0],
        told[1],
    )
    assert (line["via"], line["upstream"], line["source"], line["project"]) == (
        "pull",
        head,
        "writer",
        "demo",
    )
    assert told[0] in PUBLISHED["arrived@1"].text(line)
    r.tick(FETCH)  # the same, already integrated upstream tells nothing more
    assert len(arrived(r)) == base + 1


def test_this_machines_writes_are_never_told_as_a_pull(rig: Callable[[], Rig]) -> None:
    r = rig()
    r.write(CH + "1-inbox/mine/01-intent.md")
    other_commit(r, "theirs", (None, "1-inbox/theirs"))
    r.tick()
    r.tick(QUIET)  # the same cycles commit this machine's CR, integrate the other's, and push
    r.tick(FETCH)
    assert [x["folder"] for x in arrived(r)] == ["1-inbox/theirs"]
    assert r.pushed() == r.head()
    r.write(CH + "1-inbox/mine-too/01-intent.md")
    r.tick(FETCH)
    r.tick(QUIET)
    assert [x["folder"] for x in arrived(r)] == ["1-inbox/theirs"]


def test_the_arrivals_of_a_conflict_are_told_when_it_ends_and_those_the_resolution_dropped_not(
    rig: Callable[[], Rig],
) -> None:
    r = rig()
    r.seat()
    path = "projects/demo/changes/notes.md"
    r.write(path, "base\n")
    r.settle()
    sh("git", "pull", "-q", cwd=r.other)
    r.write(path, "theirs\n", where=r.other)
    r.write(CH + "1-inbox/kept/01-intent.md", where=r.other)
    r.write(CH + "1-inbox/dropped/01-intent.md", where=r.other)
    sh("git", "add", "-A", cwd=r.other)
    sh("git", "commit", "-qm", "theirs", cwd=r.other)
    sh("git", "push", "-q", "origin", "main", cwd=r.other)
    r.write(path, "mine\n")
    r.tick()
    r.tick(QUIET)
    assert r.entry()["state"] == "conflict"
    upstream = r.entry()["conflict"]["upstream"]
    assert not arrived(r)  # the conflict cycle tells none
    sh("git", "fetch", "-q", cwd=r.root)
    sh("git", "checkout", "--", path, cwd=r.root)
    sh("git", "reset", "-q", "--hard", "origin/main", cwd=r.root)
    shutil.rmtree(r.root / CH / "1-inbox" / "dropped")
    sh("git", "commit", "-qam", "resolved: drop one", cwd=r.root)
    r.tick()
    r.tick()
    assert r.entry()["state"] != "conflict"
    (line,) = arrived(r)
    assert (line["folder"], line["via"], line["upstream"]) == ("1-inbox/kept", "pull", upstream)
    r.tick(FETCH)
    r.tick(FETCH)
    assert len(arrived(r)) == 1
