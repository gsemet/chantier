"""`open` that fails leaves the CR where it was, the batch number is read from the records, and
`restore` puts a trashed CR back in the inbox."""

from __future__ import annotations

from pathlib import Path

import pytest
from batch_helpers import FROM_AGENTS_MD, changes, events, host, prepared, record
from conftest import Chantier
from pytest import MonkeyPatch

from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION, EXIT_USAGE

SPEC = "03-change-spec.md"


def test_an_opening_that_fails_names_why_and_restores_what_it_moved(
    repo: Path, chantier: Chantier, monkeypatch: MonkeyPatch
) -> None:
    host(monkeypatch)
    item = prepared(repo, chantier, "Latin one specification")
    batch = changes(repo) / "4-batch" / "batch.json"
    code, _, err = chantier("open", str(item), "--remote", "nowhere", *FROM_AGENTS_MD)
    assert code == EXIT_EXTERNAL and "nowhere" in err  # refused before anything moves
    assert (item / SPEC).is_file() and not batch.exists()
    good = (item / SPEC).read_bytes()
    (item / SPEC).write_bytes("# Spécification\n".encode("latin-1"))
    code, _, err = chantier("open", str(item), *FROM_AGENTS_MD)
    assert code == EXIT_PRECONDITION and "not UTF-8" in err and "Traceback" not in err
    (item / SPEC).write_bytes(good)
    code, _, _ = chantier("open", str(item), str(repo / "nowhere"), *FROM_AGENTS_MD)
    assert code != 0 and (item / SPEC).is_file() and not batch.exists()


def test_the_next_batch_number_is_read_from_the_records(
    repo: Path, chantier: Chantier, monkeypatch: MonkeyPatch
) -> None:
    host(monkeypatch)
    item = prepared(repo, chantier, "Number from the records")
    records = changes(repo) / "5-archives" / "batches"
    records.mkdir(parents=True)
    (records / "batch-03.json").write_text("{}\n")
    (changes(repo) / ".batch-number").write_text("1\n")
    assert chantier("open", str(item), *FROM_AGENTS_MD)[0] == 0
    assert record(repo)["id"] == "batch-04" and (records / "batch-04.json").is_file()
    assert (changes(repo) / ".batch-number").read_text().strip() == "4"


def filed(repo: Path, chantier: Chantier, title: str) -> Path:
    return repo / chantier("file", title)[1][0].removeprefix("filed ").split(";")[0]


def abandoned(repo: Path, chantier: Chantier, folder: Path) -> Path:
    return repo / chantier("abandon", str(folder))[1][0].removeprefix("abandoned ")


def test_restore_puts_a_trashed_cr_back_whole_and_refuses_a_clash_or_an_archive(
    repo: Path, chantier: Chantier
) -> None:
    inbox = changes(repo) / "1-inbox"
    plain = filed(repo, chantier, "Restore plain")
    (plain / "01-intent.md").write_text("# Restore plain\n")
    (plain / "work").mkdir()
    (plain / "work" / "notes.md").write_text("kept\n")
    old = abandoned(repo, chantier, plain)
    assert chantier("restore", str(old))[0] == 0
    assert (inbox / "restore-plain" / "work" / "notes.md").is_file() and not old.exists()
    assert (inbox / "restore-plain" / "intake" / "request.md").is_file()
    assert "restore-plain" in (changes(repo) / "STATUS.md").read_text("utf-8")
    gone = abandoned(repo, chantier, filed(repo, chantier, "2026 plan"))
    chantier("restore", str(gone))  # a leading number of a plain slug is not stripped
    assert (inbox / "2026-plan").is_dir() and not (inbox / "plan").exists()
    gone = abandoned(repo, chantier, inbox / "restore-plain")
    filed(repo, chantier, "Restore plain")
    assert chantier("restore", str(gone))[0] == EXIT_PRECONDITION and gone.is_dir()
    assert chantier("restore", str(gone), "--slug", "restore-again")[0] == 0
    assert (inbox / "restore-again").is_dir()
    archive = changes(repo) / "5-archives" / "260101-0000-9-old"
    archive.mkdir(parents=True)
    assert chantier("restore", str(archive))[0] == EXIT_PRECONDITION and archive.is_dir()


def three_ready(repo: Path, chantier: Chantier, title: str) -> Path:
    """A CR made ready in a project with no batch yet."""
    out = chantier("triage", str(prepared(repo, chantier, title)), "--ready")[1]
    return repo / out[0].removeprefix("triaged ")


@pytest.mark.parametrize("how", ["no-cr", "flag", "plain"])
def test_open_makes_a_factory_only_with_no_cr_or_the_flag(
    repo: Path, chantier: Chantier, monkeypatch: MonkeyPatch, how: str
) -> None:
    host(monkeypatch)
    waiting = three_ready(repo, chantier, "Waiting in ready")
    item = prepared(repo, chantier, "Opened") if how != "no-cr" else None
    args = (str(item),) if item else ()
    code, out, err = chantier(
        "open", *args, *(("--factory",) if how == "flag" else ()), *FROM_AGENTS_MD
    )
    assert code == 0, err
    on = how != "plain"
    brief = (changes(repo) / "4-batch" / "brief.md").read_text("utf-8")
    assert record(repo)["factory"] is on and f"Factory: {'on' if on else 'off'}." in brief
    assert out[0].endswith(", factory") == on
    assert ("(factory)" in out[1]) == on
    held = [x for x in out if x.startswith("3-ready holds")]
    assert bool(held) == on  # the CR left in 3-ready is named, the factory's go covers it
    if held:
        assert "1 CRs not joined" in held[0] and waiting.name in held[0] and "order add" in held[0]
    opened = next(e for e in events(repo) if e["kind"] == "open")
    assert opened.get("factory") is (True if on else None)


def test_open_refuses_a_release_in_a_factory(
    repo: Path, chantier: Chantier, monkeypatch: MonkeyPatch
) -> None:
    host(monkeypatch)
    item = prepared(repo, chantier, "Release")
    code, _, err = chantier("open", "--factory", "--release", 1, str(item), *FROM_AGENTS_MD)
    assert code == EXIT_USAGE and "order add --release" in err and "turns the factory off" in err
    assert not (changes(repo) / "4-batch" / "batch.json").exists()
