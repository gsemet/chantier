"""`order drop <cr> --note trash|ready|P1..P4`: where the CR goes, and what follows."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from batch_helpers import changes, record
from conftest import Chantier
from test_batch_end import cr, done_orders, exists, patch, started

from chantier.commands.closing import _kept, _to_remove
from chantier.core import waits
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE
from chantier.core.records import read_batch_json
from chantier.core.repo import Repo
from chantier.history import cr_entry

PR = "https://github.com/o/r/pull/346"
FOLDERS = {"trash": "6-trash", "ready": "3-ready", "p2": "2-backlog/P2"}


def one(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, **fields: object) -> str:
    (cr_id,) = started(repo, chantier, monkeypatch, 1, 1)
    if fields:
        patch(repo, cr_id, **fields)
    return cr_id


@pytest.mark.parametrize(
    ("note", "code"),
    [(None, EXIT_USAGE), ("P5", EXIT_USAGE), ("3-ready", EXIT_USAGE)],
)
def test_a_drop_with_no_known_destination_is_refused_and_records_nothing(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, note: str | None, code: int
) -> None:
    cr_id = one(repo, chantier, monkeypatch, status="ready")
    before = (changes(repo) / "4-batch" / "batch.json").read_bytes()
    args = ("--note", note) if note else ()
    got, _, err = chantier("order", "drop", cr_id, *args)
    assert got == code and "trash|ready|P1..P4" in err
    assert (changes(repo) / "4-batch" / "batch.json").read_bytes() == before


@pytest.mark.parametrize(
    "case", [("release", "P2", 2), ("fix", "ready", 2), ("release", "trash", 0)]
)
def test_a_release_or_fix_cr_leaves_the_batch_only_to_the_trash(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, case: tuple[str, str, int]
) -> None:
    kind, note, code = case
    cr_id = one(repo, chantier, monkeypatch, status="ready", kind=kind)
    got, _, err = chantier("order", "drop", cr_id, "--note", note)
    assert got == code, err
    if code:
        assert f"a {kind} CR" in err and cr(repo, cr_id)["status"] == "ready"


def test_cancel_with_no_drop_order_is_refused_and_changes_nothing(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    cr_id = one(repo, chantier, monkeypatch)
    before = (changes(repo) / "4-batch" / "batch.json").read_bytes()
    code, _, err = chantier("cancel", cr_id, "--epoch", 1)
    assert code == EXIT_PRECONDITION and "no destination recorded" in err
    assert (changes(repo) / "4-batch" / "batch.json").read_bytes() == before


@pytest.mark.parametrize("dest", ["trash", "ready", "p2"])
@pytest.mark.parametrize("live", [False, True])
def test_a_dropped_cr_goes_where_the_order_names_with_its_work(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, dest: str, live: bool
) -> None:
    wait = waits.make("w1", "answer", "which port?", None, "")
    fields = {} if live else {"status": "ready"}
    cr_id = one(repo, chantier, monkeypatch, **fields, pr=PR, waits=[wait])
    folder = FOLDERS[dest]
    code, out, err = chantier("order", "drop", cr_id, "--note", dest.upper())  # any case
    assert code == 0, err
    if live:
        assert cr(repo, cr_id)["status"] == "working" and cr(repo, cr_id)["left_to"] == folder
        done_orders(repo)
        code, out, err = chantier("cancel", cr_id, "--epoch", 1)
        assert code == 0, err
    c = cr(repo, cr_id)
    assert c["status"] == "cancelled" and c["left_to"] == folder
    assert c["path"].startswith(f"{folder}/") and (changes(repo) / c["path"]).is_dir()
    assert exists(repo, cr_id) == (True, True)  # the work stays, whatever the destination
    assert record(repo)["status"] == "paused"
    if dest == "trash":
        assert any("close its PR" in x for x in out) and not list(changes(repo).rglob("formerly*"))
        return
    assert not any("close its PR" in x for x in out)
    at = changes(repo) / c["path"]
    formerly = json.loads((at / "formerly.json").read_text("utf-8"))
    assert formerly["cr"] == cr_id and formerly["batch"] == record(repo)["id"]
    assert formerly["pr"] == PR and formerly["branch"] == c["branch"]
    assert formerly["worktree"] == c["worktree"] and "pr_draft" in formerly
    assert waits.read_file(Repo.find().store, at) == [wait]  # the open wait goes with the CR
    keep = "01-intent.md" if (at / "01-intent.md").exists() else "notes.md"
    assert (at / keep).read_text("utf-8").rstrip().endswith(f"formerly {cr_id} of batch-01")
    assert at.name.split("-")[0] in (changes(repo) / "restored.json").read_text("utf-8")
    assert f"dropped to {folder}" in (changes(repo) / "4-batch" / "STATUS.md").read_text("utf-8")
    kept = _kept(
        Repo.find(), read_batch_json(Repo.find().store, changes(repo) / "4-batch" / "batch.json")
    )
    assert any(
        x.startswith(f"{cr_id} ({folder}/")
        and all(str(c[k]) in x for k in ("worktree", "branch"))
        and PR in x
        for x in kept
    ), kept


def test_a_held_cr_dropped_is_no_longer_held(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    cr_id = one(repo, chantier, monkeypatch, status="ready", held="O-1")
    code, out, err = chantier("order", "drop", cr_id, "--note", "P2")
    assert code == 0, err
    assert f"{cr_id} was held: no stack driver needed" in out
    assert not cr(repo, cr_id).get("held")


@pytest.mark.parametrize(("note", "folder"), [("p2", "2-backlog/P2"), ("ready", "3-ready")])
def test_a_drop_to_a_name_in_use_is_refused_at_the_order(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, note: str, folder: str
) -> None:
    cr_id = one(repo, chantier, monkeypatch, status="ready")
    name = Path(cr(repo, cr_id)["path"]).name
    (changes(repo) / folder / name).mkdir(parents=True)
    code, _, err = chantier("order", "drop", cr_id, "--note", note)
    assert code == EXIT_PRECONDITION and "is already used by" in err
    assert cr(repo, cr_id)["status"] == "ready" and not cr(repo, cr_id).get("left_to")


@pytest.mark.parametrize(
    "case",
    [
        ("parallel", "trash", False, "close its PR"),
        ("stack", "trash", False, ""),
        ("parallel", "P2", False, "turn its PR to draft"),
        ("parallel", "ready", False, "turn its PR to draft"),
        ("stack", "ready", False, ""),
        ("parallel", "P2", True, ""),
    ],
)
def test_the_pr_clause_closes_a_trashed_pr_and_drafts_a_kept_one_outside_a_stack_only(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    case: tuple[str, str, bool, str],
) -> None:
    steering, note, draft, clause = case
    cr_id = one(repo, chantier, monkeypatch, status="ready", pr=PR, pr_draft=draft)
    if steering == "stack":
        assert chantier("order", "mode", "--note", "stack")[0] == 0
    code, out, err = chantier("order", "drop", cr_id, "--note", note)
    assert code == 0, err
    got = [x for x in out if "its PR" in x]
    assert len(got) == (1 if clause else 0)
    assert not clause or f"; {clause} {PR}" in got[0]
    if note != "trash":
        at = changes(repo) / cr(repo, cr_id)["path"]
        recorded = json.loads((at / "formerly.json").read_text("utf-8"))["pr_draft"]
        assert recorded is (True if draft else None)


@pytest.mark.parametrize("note", ["P2", "ready"])
def test_a_live_cr_cancelled_to_the_backlog_or_ready_carries_the_draft_clause(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, note: str
) -> None:
    cr_id = one(repo, chantier, monkeypatch, pr=PR, pr_draft=False)
    assert chantier("order", "drop", cr_id, "--note", note)[0] == 0
    done_orders(repo)
    code, out, err = chantier("cancel", cr_id, "--epoch", 1)
    assert code == 0, err
    assert f"turn its PR to draft {PR}" in out


@pytest.mark.parametrize("case", [("queued", {}), ("live", {}), ("ready", {"pr": PR})])
def test_a_drop_to_the_inbox_is_refused_for_every_cr_and_changes_nothing(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    case: tuple[str, dict[str, str]],
) -> None:
    kind, fields = case
    cr_id = one(repo, chantier, monkeypatch, **fields, **({"status": "ready"} if fields else {}))
    if kind == "queued":
        patch(repo, cr_id, status="queued")
    before = (changes(repo) / "4-batch" / "batch.json").read_bytes()
    code, _, err = chantier("order", "drop", cr_id, "--note", "inbox")
    assert code == EXIT_USAGE and "order drop never sends a CR to the inbox" in err
    assert (changes(repo) / "4-batch" / "batch.json").read_bytes() == before
    assert not list(changes(repo).rglob("formerly*"))


def test_the_status_close_and_record_tell_a_trashed_cr_from_a_moved_one(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    merged, trashed, moved = started(repo, chantier, monkeypatch, 3, 3)
    assert chantier("order", "merged", merged, "--epoch", 1)[0] == 0
    for cr_id, note in ((trashed, "trash"), (moved, "P2")):
        assert chantier("order", "drop", cr_id, "--note", note)[0] == 0
    done_orders(repo)
    for cr_id in (trashed, moved):
        assert chantier("cancel", cr_id, "--epoch", 1)[0] == 0
    out = (changes(repo) / "4-batch" / "STATUS.md").read_text("utf-8")
    assert "[⚪ dropped](" in out and "[⚪ dropped to 2-backlog/P2](" in out
    batch = read_batch_json(Repo.find().store, changes(repo) / "4-batch" / "batch.json")
    lines = _to_remove(Repo.find(), batch)
    assert any(x.startswith(f"{trashed} (dropped) worktree") for x in lines)
    assert not any(x.startswith(moved) for x in lines)
    kept = _kept(Repo.find(), batch)
    assert len(kept) == 1 and kept[0].startswith(f"{moved} (2-backlog/P2/")
    shutil.move(str(changes(repo) / cr(repo, moved)["path"]), str(changes(repo) / "3-ready" / "x"))
    assert f"{moved} (moved since from 2-backlog/P2)" in _kept(Repo.find(), batch)[0]
    entries = {e["cr"]: e for e in (cr_entry(c, {}) for c in batch.crs)}
    assert "to" not in entries[merged] and entries[merged]["archive"]
    assert entries[trashed]["to"] == "6-trash" and entries[trashed]["archive"]
    assert entries[moved]["to"] == "2-backlog/P2" and entries[moved]["archive"] is None


def test_validate_reads_a_formerly_json_in_a_cr_folder_as_part_of_its_layout(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    cr_id = one(repo, chantier, monkeypatch, status="ready")
    assert chantier("order", "drop", cr_id, "--note", "ready")[0] == 0
    path = changes(repo) / cr(repo, cr_id)["path"]
    assert (path / "formerly.json").is_file()
    _, out, _ = chantier("validate")
    assert not any("formerly.json" in x for x in out)
