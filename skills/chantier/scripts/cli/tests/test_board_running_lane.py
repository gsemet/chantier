"""The board's running-batch lane: a drop on it writes the mark (or, from `3-ready`, a journal line
only, or, with no open batch, moves the CR to `3-ready`); a move of a marked CR clears the mark;
an item carries `running_batch`; the `board@1` sentences; the shipped files name the lane."""

from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import changes, host, open_bare, prepared
from conftest import PLUGIN_ROOT, Chantier

from chantier.board import write_api
from chantier.board.backlog import running_batch_of
from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.repo import Repo
from chantier.hub import journal as forge_journal
from chantier.hub.board_text import board_text
from chantier.store import FolderStore

OK = HTTPStatus.OK
CONFLICT = HTTPStatus.CONFLICT
MARK = Path("work") / "running-batch"
WEB = PLUGIN_ROOT / "skills/chantier/scripts/cli/src/chantier/clients/web"


def lines(repo: Path) -> list[dict[str, Any]]:
    found = forge_journal.read(Repo.find().store, Repo.find().changes)[0]
    return [e for e in found if e["type"] == "board@1"]


def drop(repo: Path, slugs: list[str], to: str, **more: Any) -> tuple[dict[str, Any], int]:
    return write_api._move(Repo.find(), {"items": slugs, "to": to, **more})


def where(repo: Path, slug: str) -> Path:
    return next(p for p in changes(repo).rglob(slug) if p.is_dir() and "4-batch" not in str(p))


def grilled(repo: Path, chantier: Chantier, title: str, spec: bool = True) -> Path:
    """A CR in the inbox: with `work/specifying` (spec False) or a specification (spec True)."""
    folder = prepared(repo, chantier, title)
    if not spec:
        (folder / "03-change-spec.md").unlink()
        (folder / "work").mkdir(exist_ok=True)
        (folder / "work" / "specifying").write_text("", encoding="utf-8")
    return folder


@pytest.mark.parametrize("case", ["marked", "again", "paused", "group-one"])
def test_a_drop_with_an_open_batch_writes_the_mark(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    batch = open_bare(repo, chantier, monkeypatch)
    folder = grilled(repo, chantier, "Lane")
    slug = folder.name
    if case == "group-one":
        write_api._group(Repo.find(), {"items": [slug], "name": "g"})
    body, status = drop(repo, [slug], "running-batch")
    written = [e for e in lines(repo) if e["action"] != "group"]
    assert status == OK and where(repo, slug) == folder
    assert (folder / MARK).read_text("utf-8").split()[-1] == batch
    assert [(e["action"], e["wakes"]) for e in written] == [("running-batch", True)]
    assert body["journal"][0]["text"] == f"{slug} → running batch {batch} (marked)"
    if case == "again":  # the same drop again writes nothing
        assert drop(repo, [slug], "running-batch")[1] == OK and len(lines(repo)) == 1
    if case == "group-one":  # a single post-it leaves its group
        assert json.loads((folder / "summary.json").read_text("utf-8")).get("group") is None


@pytest.mark.parametrize(
    "case", ["not-grilled", "ready", "group-ready", "no-batch", "closed-batch"]
)
def test_a_drop_that_marks_nothing(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    host(monkeypatch)
    batch = None if case in ("no-batch", "closed-batch") else open_bare(repo, chantier, monkeypatch)
    if case == "closed-batch":  # the batch's folder is gone once it is closed: no open batch
        open_bare(repo, chantier, monkeypatch)
        (changes(repo) / "4-batch" / "batch.json").unlink()
    folder = grilled(repo, chantier, "Lane", spec=case != "not-grilled")
    if case == "not-grilled":
        (folder / "work" / "specifying").unlink()
        (folder / "02-answers.md").write_text("# Answers\n", encoding="utf-8")
    slug = folder.name
    if case in ("ready", "group-ready"):
        chantier("triage", str(folder), "--ready")
    if case == "group-ready":
        write_api._group(Repo.find(), {"items": [slug], "name": "g"})
    body, status = drop(repo, [slug], "running-batch")
    after = where(repo, slug)
    written = [e for e in lines(repo) if e["action"] != "group"]
    assert not (after / MARK).exists()
    if case == "not-grilled":
        assert status == CONFLICT and "the grill is not finished" in body["error"]
        assert written == []
    elif case in ("no-batch", "closed-batch"):
        assert status == OK and after.parent.name == "3-ready"
        assert body["lines"] == [f"{slug} → 3-ready (no running batch)"]
        assert written[-1]["action"] == "move"
    else:  # a journal line only; the folder stays in 3-ready, in its group
        assert status == OK and after.parent.name == "3-ready"
        assert written[-1]["action"] == "running-batch"
        assert "order add" in written[-1]["text"]
        assert body["lines"] == [f"{slug}: the Chief of Staff adds it to {batch}"]
        if case == "group-ready":
            assert json.loads((after / "summary.json").read_text("utf-8")).get("group") == "g"


@pytest.mark.parametrize("to", ["3-ready", "inbox", "P2", "own", "stale"])
def test_a_move_of_a_marked_cr_clears_its_mark(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, to: str
) -> None:
    batch = open_bare(repo, chantier, monkeypatch)
    folder = grilled(repo, chantier, "Marked")
    slug = folder.name
    if to in ("own", "stale"):
        chantier("triage", str(folder), "--priority", "P2")
        folder = where(repo, slug)
    chantier("triage", str(folder), "--running-batch")
    if to == "stale":
        (folder / MARK).write_text(f"2026-01-01T00:00:00Z {batch}-old\n", encoding="utf-8")
    target = "P2" if to in ("own", "stale") else to
    body, status = drop(repo, [slug], target)
    after = where(repo, slug)
    assert status == OK
    if to == "stale":
        assert body["journal"] == [] and (after / MARK).exists()
        return
    assert not (after / MARK).exists()
    assert body["journal"][0]["text"].endswith("; running-batch mark cleared")
    if to == "own":
        assert (
            after == folder
            and body["journal"][0]["text"] == f"{slug} → P2; running-batch mark cleared"
        )
        assert lines(repo)[-1]["action"] == "move"
    else:
        assert after.parent.name == (
            "3-ready" if to == "3-ready" else "1-inbox" if to == "inbox" else "P2"
        )


def test_triage_to_its_own_priority_clears_a_mark_and_moves_nothing(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_bare(repo, chantier, monkeypatch)
    folder = grilled(repo, chantier, "Own row")
    chantier("triage", str(folder), "--priority", "P2")
    folder = where(repo, folder.name)
    chantier("triage", str(folder), "--running-batch")
    code = chantier("triage", str(folder), "--priority", "P2")[0]
    assert code == 0 and folder.is_dir() and not (folder / MARK).exists()
    assert chantier("triage", str(folder), "--priority", "P2")[0] != 0  # no mark: still refused


def test_an_unknown_target_is_refused_and_names_the_lane(repo: Path) -> None:
    with pytest.raises(ChantierError) as refused:
        drop(repo, ["x"], "nowhere")
    assert refused.value.code == EXIT_USAGE and "running-batch" in str(refused.value)


@pytest.mark.parametrize("case", ["marked", "stale", "no-batch", "none"])
def test_an_item_carries_the_batch_its_mark_names(tmp_path: Path, case: str) -> None:
    folder = tmp_path / "1-inbox" / "a"
    (folder / "work").mkdir(parents=True)
    if case != "none":
        mark = "batch-02" if case == "stale" else "batch-01"
        (folder / MARK).write_text(f"2026-11-21T00:00:00Z {mark}\n", encoding="utf-8")
    batch = None if case == "no-batch" else "batch-01"
    found = running_batch_of(FolderStore(tmp_path), folder, batch)
    assert found == ("batch-01" if case == "marked" else None)


MARKED = "an-idea → running batch batch-30 (marked)"
READY_LINE = "an-idea → 3-ready (specified)"


@pytest.mark.parametrize(
    ("action", "text", "ends"),
    [
        (
            "running-batch",
            MARKED,
            "once its specification is final (at once for a CR in `3-ready`)",
        ),
        ("running-batch", MARKED, "`order add --note <folder>`"),
        (
            "move",
            "an-idea → P2; running-batch mark cleared",
            "write its destination, act on nothing else",
        ),
        ("move", READY_LINE, "write its destination, act on nothing else"),
        ("move", "an-idea → inbox", "tell the user, act on nothing"),
        ("edit", "a/b.md edited", "tell the user, act on nothing"),
    ],
)
def test_the_board_line_tells_the_chief_of_staff_what_to_do(
    action: str, text: str, ends: str
) -> None:
    said = board_text({"action": action, "text": text})
    assert said.startswith(f"board wrote ({action}): {text}; ") and ends in said


def test_the_shipped_files_name_the_lane() -> None:
    web = {
        p.relative_to(WEB / "js").as_posix(): p.read_text("utf-8")
        for p in (WEB / "js").rglob("*.js")
    }
    model = (WEB / "js/model/triage.js").read_text("utf-8")
    cols = web["triage/columns.js"]
    assert "drop: RUNNING" in cols and "triage.running'" not in cols
    assert (
        "triage.idle" not in cols
        and "ctx.batch" not in cols.split("function readyFoot")[1].split("// The Inbox")[0]
    )
    assert "TARGETS.map" in web["triage/selection.js"] and "RUNNING = 'running-batch'" in model
    for name in ("i18n/en-write.js", "i18n/fr-write.js"):
        keys = ("running_lane", "no_running", "state_specifying", "state_written", "state_queued")
        assert all(f"'triage.{k}'" in web[name] for k in keys)
        assert "'triage.running'" not in web[name] and "'triage.idle'" not in web[name]
    agents = (PLUGIN_ROOT / "AGENTS.md").read_text("utf-8")
    assert "action `running-batch`" in agents and "writes no file in the CR's folder" in agents
    cards = PLUGIN_ROOT / "skills/chantier/references"
    for card in ("griller.md", "chief-of-staff.md"):
        assert "last `Destination:` line" in (cards / card).read_text("utf-8")
