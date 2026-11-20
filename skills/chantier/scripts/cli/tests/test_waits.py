"""Typed waits: recorded by a blocked hand-back or `wait add`, cleared by the steering session,
carried through the backlog by `waits.json`, and shown by `status`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from batch_helpers import FROM_AGENTS_MD, changes, host, record
from conftest import Chantier
from test_batch_end import cr, patch, started
from test_came_back import dropped
from test_order_drop_to import PR

from chantier import __version__, connectors
from chantier.core import waits
from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE, ChantierError
from chantier.core.repo import Repo
from chantier.hub import journal, state
from chantier.store.folder import FolderStore

SHA = "a" * 40


def one(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch) -> str:
    (cr_id,) = started(repo, chantier, monkeypatch, 1, 1)
    patch(repo, cr_id, status="working", pr=PR, head=SHA)
    return cr_id


def test_a_blocked_handback_records_its_waits_and_the_steering_session_clears_them(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    cr_id = one(repo, chantier, monkeypatch)
    code, out, err = chantier(
        "handback", cr_id, "blocked", "waits: a review", "--wait", "approval", "--wait",
        'answer=which port?',
    )  # fmt: skip
    assert code == 0, err
    assert "; waits: w1 approval, w2 answer" in out[0]
    entry = cr(repo, cr_id)
    assert [(w["id"], w["type"], w["ref"]) for w in entry["waits"]] == [
        ("w1", "approval", PR),
        ("w2", "answer", "which port?"),
    ]
    status = chantier("status")[1]
    assert any(f"{cr_id} " in x and "| waits: approval, answer" in x for x in status)
    code, _, err = chantier("wait", cr_id, "clear", "w1")
    assert code in (EXIT_USAGE, EXIT_PRECONDITION)
    assert chantier("wait", cr_id, "clear", "w1", "--epoch", 1)[0] == 0
    got = cr(repo, cr_id)["waits"]
    assert got[0]["cleared_by"] == "epoch 1" and got[1]["cleared_at"] is None
    assert chantier("wait", cr_id, "clear", "w1", "--epoch", 1)[0] == EXIT_PRECONDITION
    assert "waits for: w2 answer" in chantier("wait", cr_id)[1][0]
    assert chantier("wait", cr_id, "add", "merge", "--note", "after", "--epoch", 1)[0] == 0
    assert cr(repo, cr_id)["waits"][-1]["id"] == "w3"  # ids continue from the highest ever


@pytest.mark.parametrize(
    ("args", "refusal"),
    [
        (("blocked", "r", "--wait", "mood"), (EXIT_PRECONDITION, "not a wait type")),
        (("blocked", "r", "--wait", "answer"), (EXIT_PRECONDITION, "needs the question")),
        (("ready", PR, "--wait", "merge"), (EXIT_USAGE, "--wait is for a blocked")),
    ],
)
def test_a_wait_the_cli_cannot_record_is_refused_and_changes_nothing(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    args: tuple[str, ...],
    refusal: tuple[int, str],
) -> None:
    code, text = refusal
    cr_id = one(repo, chantier, monkeypatch)
    before = (changes(repo) / "4-batch" / "batch.json").read_bytes()
    got, _, err = chantier("handback", cr_id, *args)
    assert got == code and text in err
    assert (changes(repo) / "4-batch" / "batch.json").read_bytes() == before


def test_a_backlog_cr_keeps_its_waits_in_a_file_that_the_join_consumes(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    _, out, _ = chantier("file", "Waits")
    folder = repo / out[0].removeprefix("filed ").split(";")[0]
    (folder / "03-change-spec.md").write_text("# Waits\n\nDo it.\n", encoding="utf-8")
    rel = folder.relative_to(changes(repo)).as_posix()
    code, _, err = chantier("wait", rel, "add", "answer", "--ref", "who?", "--note", "ask")
    assert code == 0, err
    assert chantier("wait", rel, "add", "answer", "--ref", "when?", "--note", "ask")[0] == 0
    assert chantier("wait", rel, "clear", "w1")[0] == 0
    data = json.loads((folder / waits.FILE).read_text("utf-8"))
    assert [(w["id"], w["cleared_by"]) for w in data["waits"]] == [("w1", "hand"), ("w2", None)]
    assert "waits for: w2 answer" in chantier("wait")[1][0]
    code, _, err = chantier("open", str(folder), *FROM_AGENTS_MD)
    assert code == 0, err
    (entry,) = record(repo)["crs"]
    assert [w["id"] for w in entry["waits"]] == ["w2"]
    assert not list((changes(repo) / "4-batch").rglob(waits.FILE))


def test_a_malformed_waits_file_refuses_the_join(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    _, out, _ = chantier("file", "Broken")
    folder = repo / out[0].removeprefix("filed ").split(";")[0]
    (folder / "03-change-spec.md").write_text("# Broken\n\nDo it.\n", encoding="utf-8")
    (folder / waits.FILE).write_text('{"schema": 1, "waits": [{"id": "x"}]}', encoding="utf-8")
    code, _, err = chantier("open", str(folder), *FROM_AGENTS_MD)
    assert code == EXIT_PRECONDITION and "waits.json is not valid" in err
    assert (folder / waits.FILE).is_file() and folder.is_dir()


def test_a_dropped_cr_takes_its_open_waits_back_to_the_backlog(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    cr_id = one(repo, chantier, monkeypatch)
    assert chantier("handback", cr_id, "blocked", "waits: x", "--wait", "merge")[0] == 0
    assert (
        chantier("wait", cr_id, "add", "answer", "--ref", "q", "--note", "n", "--epoch", 1)[0] == 0
    )
    assert chantier("wait", cr_id, "clear", "w1", "--epoch", 1)[0] == 0
    assert chantier("order", "drop", cr_id, "--note", "P2")[0] == 0
    (written,) = (changes(repo) / "2-backlog" / "P2").rglob(waits.FILE)
    assert [w["id"] for w in json.loads(written.read_text("utf-8"))["waits"]] == ["w2"]


@pytest.mark.parametrize(
    ("data", "why"),
    [
        ([], "not a JSON object"),
        ({"schema": 2, "waits": []}, "schema"),
        ({"schema": 1, "waits": [{"id": "w1", "type": "mood"}]}, "type"),
        (
            {"schema": 1, "waits": [_w for _w in [waits.make("w1", "answer", "q", None, "n")] * 2]},
            "repeated",
        ),
    ],
)
def test_a_waits_file_is_checked(data: object, why: str) -> None:
    assert why in (waits.problem(data) or "")
    assert (
        waits.problem({"schema": 1, "waits": [waits.make("w1", "answer", "q", None, "n")]}) is None
    )


def test_the_board_reads_the_open_waits_of_a_backlog_folder_and_nothing_from_a_broken_file(
    tmp_path: Path,
) -> None:
    from chantier.board.backlog import open_waits  # noqa: PLC0415

    assert open_waits(tmp_path) == []
    done = waits.make("w1", "answer", "q", None, "n") | {"cleared_at": "t", "cleared_by": "hand"}
    live = waits.make("w2", "merge", PR, PR, "n")
    (tmp_path / waits.FILE).write_text(waits.file_text([done, live]), encoding="utf-8")
    assert [w["id"] for w in open_waits(tmp_path)] == ["w2"]
    (tmp_path / waits.FILE).write_text("{", encoding="utf-8")
    assert open_waits(tmp_path) == []


OTHER = "https://github.com/o/elsewhere/pull/9"
NOT_HERE = "is not in the batch's repository"
CANNOT_TELL = "(the forge cannot tell: cleared by hand)"


def test_add_by_the_driver_or_the_steering_session_and_a_link_no_connector_claims(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    cr_id = one(repo, chantier, monkeypatch)
    before = (changes(repo) / "4-batch" / "batch.json").read_bytes()
    odd = "https://example.org/x/1"
    code, _, err = chantier(
        "wait", cr_id, "add", "merge", "--ref", odd, "--note", "n", "--epoch", 1
    )
    assert code == EXIT_PRECONDITION and connectors.UNCLAIMED.format(link=odd) in err
    assert (changes(repo) / "4-batch" / "batch.json").read_bytes() == before  # nothing written
    assert chantier("wait", cr_id, "add", "merge", "--note", "n")[0] == 0  # the Driver, defaults
    args = ("wait", cr_id, "add", "merge", "--ref", OTHER, "--note", "n", "--epoch", 1)
    code, out, err = chantier(*args)
    assert code == 0, err
    assert [x for x in out if NOT_HERE in x] == [  # recorded, with its line
        f"w2 merge: {OTHER} {NOT_HERE}: the hub does not read it; clear it by hand"
    ]
    assert [(w["id"], w["ref"]) for w in cr(repo, cr_id)["waits"]] == [("w1", PR), ("w2", OTHER)]
    assert f"w2 merge on {OTHER}" in chantier("wait", cr_id)[1][0]
    assert "(not in the batch's repository: cleared by hand)" in chantier("wait", cr_id)[1][0]


def test_a_refusing_store_refuses_a_backlog_wait_and_writes_nothing(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    _, out, _ = chantier("file", "Refused")
    folder = repo / out[0].removeprefix("filed ").split(";")[0]
    rel = folder.relative_to(changes(repo)).as_posix()
    assert chantier("wait", rel, "add", "answer", "--ref", "q", "--note", "n")[0] == 0
    before = (folder / waits.FILE).read_bytes()

    def refuse(*_: object, **__: object) -> None:
        raise ChantierError("the store refuses", EXIT_PRECONDITION)

    monkeypatch.setattr(FolderStore, "check_publish", refuse)
    for args in (("add", "answer", "--ref", "r", "--note", "n"), ("clear", "w1")):
        code, _, err = chantier("wait", rel, *args)
        assert code == EXIT_PRECONDITION and "the store refuses" in err
        assert (folder / waits.FILE).read_bytes() == before


def test_the_way_back_to_the_held_entry_keeps_its_list_and_adds_only_the_missing_ids(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    cr_id, _ = started(repo, chantier, monkeypatch, 2, 1)
    patch(repo, cr_id, pr=PR, head=SHA)
    for kind in ("merge", "pipeline"):
        assert chantier("wait", cr_id, "add", kind, "--note", "n", "--epoch", 1)[0] == 0
    folder = dropped(repo, cr_id, chantier)
    written = json.loads((folder / waits.FILE).read_text("utf-8"))
    assert [w["id"] for w in written["waits"]] == ["w1", "w2"]
    assert chantier("wait", cr_id)[1] == [f"{cr_id} waits for nothing"]  # a dropped CR's: none
    assert not any(x.startswith(f"{cr_id} ") and "| waits:" in x for x in chantier("status")[1])
    kept = [waits.make("w2", "answer", "mine", None, "n"), waits.make("w4", "merge", PR, PR, "n")]
    patch(repo, cr_id, waits=kept)  # the record's own list differs from the file's
    rel = folder.relative_to(changes(repo)).as_posix()
    assert chantier("order", "add", "--note", rel)[0] == 0
    assert [(w["id"], w["type"]) for w in cr(repo, cr_id)["waits"]] == [
        ("w2", "answer"),
        ("w4", "merge"),
        ("w1", "merge"),
    ]
    assert not (folder / waits.FILE).exists()
    assert chantier("wait", cr_id, "add", "merge", "--note", "n", "--epoch", 1)[0] == 0
    assert cr(repo, cr_id)["waits"][-1]["id"] == "w5"  # the numbering continues


def test_status_wait_and_handoff_tell_the_open_waits_the_cleared_lines_and_what_the_forge_cannot(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    cr_id = one(repo, chantier, monkeypatch)
    for kind in ("merge", "approval"):
        assert chantier("wait", cr_id, "add", kind, "--note", "n", "--epoch", 1)[0] == 0
    event = {
        "type": "wait-cleared@1", "batch": record(repo)["id"], "cr": cr_id, "wait_type": "merge",
        "ref": PR, "seen_at": "2026-11-20T10:00:00Z",
    }  # fmt: skip
    found = Repo.find()
    journal.append(found, [{**event, "wait": "w1"}, {**event, "wait": "w2"}], "hub")
    assert CANNOT_TELL not in chantier("wait", cr_id)[1][0]  # no hub running
    hub = state.hub_record(__version__)
    hub["projects"] = {(found.project_dir or found.root).name: {"waits_unseen": [f"{cr_id} w2"]}}
    state.write_hub(found.git_dir, hub)
    assert "w2 approval on " in chantier("wait", cr_id)[1][0]
    assert chantier("wait", cr_id)[1][0].endswith(CANNOT_TELL)  # w2 is the last one
    assert any(f"| waits: merge, approval {CANNOT_TELL}" in x for x in chantier("status")[1])
    told = [x for x in chantier("status")[1] if x.startswith("forge saw")]
    assert [f"{cr_id} w1" in told[0], f"{cr_id} w2" in told[1]] == [True, True]
    assert chantier("wait", cr_id, "clear", "w1", "--epoch", 1)[0] == 0
    told = [x for x in chantier("status")[1] if x.startswith("forge saw")]
    assert len(told) == 1 and f"{cr_id} w2" in told[0]
    handoff = chantier("handoff", cr_id)[1]
    assert any(x.startswith(f"{cr_id} waits for: w2 approval") for x in handoff)


def test_a_cr_with_an_open_wait_is_taken_as_any_other(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, cr_id = started(repo, chantier, monkeypatch, 2, 1)  # the second is still queued
    args = ("wait", cr_id, "add", "answer", "--ref", "q?", "--note", "n")
    assert chantier(*args)[0] == 0
    code, _, err = chantier("take", cr_id, "--epoch", 1)
    assert code == 0, err
    assert cr(repo, cr_id)["status"] == "working"
    assert [w["id"] for w in cr(repo, cr_id)["waits"]] == ["w1"]


def test_wait_with_no_cr_lists_the_batch_then_the_backlog_and_each_form_prints(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    cr_id = one(repo, chantier, monkeypatch)
    assert chantier("wait", cr_id, "add", "answer", "--ref", "q?", "--note", "n")[0] == 0
    _, out, _ = chantier("file", "Parked")
    folder = repo / out[0].removeprefix("filed ").split(";")[0]
    rel = folder.relative_to(changes(repo)).as_posix()
    assert chantier("wait", rel, "add", "answer", "--ref", "p?", "--note", "n")[0] == 0
    listed = chantier("wait")[1]
    assert [x.split(" waits for:")[0] for x in listed] == [cr_id, rel]
    assert listed[0].startswith(f"{cr_id} waits for: w1 answer since ") and 'q?"' in listed[0]
    assert chantier("wait", cr_id)[1] == [listed[0]]
    assert chantier("wait", rel)[1] == [listed[1]]
    assert chantier("wait", cr_id, "clear", "w1", "--epoch", 1)[0] == 0
    assert chantier("wait", cr_id)[1] == [f"{cr_id} waits for nothing"]
