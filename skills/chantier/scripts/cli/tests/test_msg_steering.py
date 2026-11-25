"""`msg steering` and `inbox`: a Driver's `msg@1` line, addressed to the batch's steering session,
wakes its watcher on `anomaly` and `blocked`, waits for its next block on a `note`, says when no
watcher is subscribed, and `inbox` lists and marks the batch's messages. No test sleeps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from batch_helpers import DEAD, events, name_server
from conftest import Chantier
from test_watch_foreman import MERGED, watcher
from watch_fakes import served

from chantier.board.projects import project_name
from chantier.core.errors import EXIT_CONFLICT, EXIT_PRECONDITION, EXIT_USAGE
from chantier.core.repo import Repo
from chantier.hub import autostart, journal, lock
from chantier.hub import times as hub_times
from chantier.hub.schemas import merged_text
from chantier.hub.schemas_msg import msg_text
from chantier.hub.watch import EVENTS, Watch
from chantier.hub.watch_reads import Rules

FM, COS, BATCH = "fm-1", "cos-1", "batch-01"
FUTURE = "2999-01-01T00:00:00Z"
NOT_DELIVERED = "not delivered: no watcher subscribed"


def write_batch(repo: Path, status: str = "running", foreman: str | None = FM, **more: Any) -> None:
    folder = repo / ".agents" / "changes" / "4-batch"
    folder.mkdir(parents=True, exist_ok=True)
    crs = [{"id": f"CR-{n}", "status": "working", "order": n} for n in (1, 2)]
    data: dict[str, Any] = {
        "id": BATCH,
        "status": status,
        "crs": crs,
        "foreman_transcript": foreman,
    }
    data |= {"foreman_epoch": 1, **more}
    (folder / "batch.json").write_text(json.dumps(data), encoding="utf-8")


def bare(chantier: Chantier, *args: object) -> tuple[int, list[str], str]:
    """The fixture's `bare` run (its type does not declare the attribute)."""
    return cast("tuple[int, list[str], str]", cast(Any, chantier).bare(*args))


def send(chantier: Chantier, kind: str, *rest: object) -> tuple[int, list[str], str]:
    return bare(
        chantier, "msg", "steering", kind, "the base moved", "--cr", "1", "--lease", 1, *rest
    )


def journal_file(repo: Path) -> Path:
    return repo / ".agents" / "changes" / journal.FILE


def messages() -> list[dict[str, Any]]:
    found = Repo.find()
    return [e for e in journal.read(found.store, found.changes)[0] if e["type"] == "msg@1"]


def blocks(w: Watch, until: int, at: dict[int, Any]) -> list[tuple[int, list[str]]]:
    """Poll `w` from 0 to `until` on the fake clock, running `at[t]` first; the blocks it tells."""
    told = []
    for t in range(until):
        if t in at:
            at[t]()
        if w.poll(float(t)) == EVENTS:
            told.append((t, w.tell(float(t))))
    return told


@pytest.mark.parametrize("kind", ["anomaly", "blocked", "note"])
def test_a_message_wakes_the_foremans_watcher_by_its_kind_and_no_other(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    write_batch(repo)
    fm = watcher(repo, monkeypatch)
    monkeypatch.setattr(autostart, "session_key", lambda: COS)
    found = Repo.find()
    cos = Watch(found, 0, "x", Rules(stream=True), served(found))
    name_server(found.git_dir)
    fm.poll(0.0)  # the Foreman's watcher holds its lock
    other = {"type": "msg@1", "audience": [f"session:{FM}"], **messages_payload(), "batch": "b-2"}
    quiet = 2 * int(hub_times.quiet_s())

    def sent() -> None:
        code, out, err = send(chantier, kind)
        tail = ", told at its next wake" if kind == "note" else ""
        assert code == 0 and out[0].endswith(f"delivered to its watcher{tail}"), err
        journal.append(found, [other], "cli")

    merged = {quiet + 2: lambda: journal.append(found, [MERGED], "hub")}
    told = blocks(fm, quiet + 30, {1: sent, **merged})
    line = messages()[0]
    assert line["source"] == "cli" and line["audience"] == [f"session:{FM}"]
    assert {k: line[k] for k in messages_payload()} == {
        **messages_payload(),
        "kind": kind,
        "wakes": kind != "note",
    }
    first_t, first = told[0]
    assert first[0] == msg_text(line) and not any("b-2" in x for x in first)
    if kind == "note":  # told only in the next block that something else wakes
        assert first_t > quiet + 2 and first[1] == merged_text(MERGED)
    else:
        assert first_t < quiet
    assert not any("message from" in x for _, b in blocks(cos, quiet + 30, {}) for x in b)
    fm.close()
    cos.close()


def messages_payload() -> dict[str, Any]:
    return {
        "batch": BATCH,
        "unit": "CR-1",
        "kind": "blocked",
        "text": "the base moved",
        "wakes": True,
        "steering": "foreman",
    }


def test_in_direct_mode_the_chief_of_staffs_plain_watcher_tells_the_message(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_batch(repo, foreman=COS, steering="direct")
    monkeypatch.setattr(autostart, "session_key", lambda: COS)
    found = Repo.find()
    w = Watch(found, 0, "x", Rules(), served(found))
    name_server(found.git_dir)
    w.poll(0.0)
    code, out, _ = send(chantier, "blocked")
    assert code == 0 and "to the Chief of Staff (direct): delivered" in out[0]
    line = messages()[0]
    assert line["audience"] == [f"session:{COS}"] and line["steering"] == "direct"
    reason = next(r for t in range(1, 60) if (r := w.poll(float(t))))
    assert reason == EVENTS and w.lines(reason)[0] == msg_text(line)
    w.close()


@pytest.mark.parametrize("case", ["no lock", "no server", "no key"])
def test_with_no_watcher_subscribed_the_line_is_kept_and_msg_exits_2(
    repo: Path, chantier: Chantier, case: str
) -> None:
    write_batch(repo, foreman=None if case == "no key" else FM)
    found = Repo.find()
    held = lock.WatcherLock(found.git_dir, project_name(found), FM)
    if case != "no lock":
        assert held.acquire()
    name_server(found.git_dir, DEAD if case == "no server" else 0)
    code, out, _ = send(chantier, "anomaly")
    if case != "no lock":
        held.release()
    assert code == EXIT_PRECONDITION and out[1].startswith(NOT_DELIVERED)
    assert out[0] == f"msg: seq 1 anomaly from CR-1 to the Foreman ({BATCH})"
    want = "role:steering" if case == "no key" else f"session:{FM}"
    assert [m["audience"] for m in messages()] == [[want]]


def test_inbox_lists_the_unread_messages_and_marks_them_in_the_batchs_events(
    repo: Path, chantier: Chantier
) -> None:
    write_batch(repo)
    assert send(chantier, "note")[0] == send(chantier, "blocked")[0] == EXIT_PRECONDITION
    before = journal_file(repo).read_bytes()
    code, out, _ = bare(chantier, "inbox", "--epoch", 1)
    assert code == 0 and out[0].startswith("#1 ") and "CR-1 note: " in out[0]
    assert out[1].startswith("#2 ") and "CR-1 blocked: " in out[1]
    assert out[2:] == ["inbox: 2 unread; once handled: inbox --read <seq>|all --epoch 1"]
    assert bare(chantier, "inbox", "--read", 1, "--epoch", 1)[1] == ["inbox: #1 read; 1 unread"]
    assert bare(chantier, "inbox", "--read", 1, "--epoch", 1)[1] == ["inbox: #1 already read"]
    assert bare(chantier, "inbox", "--read", "all", "--epoch", 1)[1] == [
        "inbox: 1 read; nothing unread"
    ]
    assert bare(chantier, "inbox", "--epoch", 1)[1] == ["inbox: nothing unread"]
    assert bare(chantier, "inbox", "--read", 9, "--epoch", 1)[0] == EXIT_USAGE
    assert bare(chantier, "inbox", "--read", "x", "--epoch", 1)[0] == EXIT_USAGE
    assert bare(chantier, "inbox")[0] == EXIT_PRECONDITION
    assert bare(chantier, "inbox", "--epoch", 2)[0] == EXIT_CONFLICT
    marks = [e["seqs"] for e in events(repo) if e["kind"] == "inbox-read"]
    assert marks == [[1], [2]] and journal_file(repo).read_bytes() == before


@pytest.mark.parametrize(
    ("words", "batch", "code"),
    [
        (("a\nb",), {}, EXIT_USAGE),
        (("x" * 301,), {}, EXIT_USAGE),
        (("ok",), {"lease": 2}, EXIT_CONFLICT),
        (("ok",), {"status": "closed"}, EXIT_PRECONDITION),
    ],
)
def test_the_refusals_of_msg_write_nothing(
    repo: Path, chantier: Chantier, words: tuple[str, ...], batch: dict[str, Any], code: int
) -> None:
    write_batch(repo, batch.get("status", "running"))
    if "lease" in batch:
        data = json.loads((repo / ".agents/changes/4-batch/batch.json").read_text("utf-8"))
        lease = {"n": batch["lease"], "taken": FUTURE, "renewed": FUTURE, "expires": FUTURE}
        data["crs"][0]["lease"] = lease
        (repo / ".agents/changes/4-batch/batch.json").write_text(json.dumps(data), "utf-8")
    got = bare(chantier, "msg", "steering", "blocked", *words, "--cr", "CR-1", "--lease", 1)
    assert got[0] == code, got
    assert not journal_file(repo).exists()
