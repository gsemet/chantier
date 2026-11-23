"""Shared helpers of the tests that open a batch and call the CLI in-process."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from conftest import Chantier

from chantier.core import clock
from chantier.core.records import BatchRecord, read_batch_json
from chantier.core.repo import Repo
from chantier.hub import state

FROM_AGENTS_MD = ("--default-branch", "main")  # what the Chief of Staff read in the rules


def host(monkeypatch: pytest.MonkeyPatch, name: str = "claude") -> None:
    """Run as the given host, outside VS Code."""
    monkeypatch.setenv("CHANTIER_HOST", name)
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")


def prepared(repo: Path, chantier: Chantier, title: str) -> Path:
    """File a CR in the inbox and give it a spec; returns its folder. The helper stands for the
    Chief of Staff's own session: the `arrived@1` line another session's run leaves is dropped."""
    journal = changes(repo) / "forge-journal.jsonl"
    size = journal.stat().st_size if journal.is_file() else None
    _, out, _ = chantier("file", title)
    if size is None and journal.is_file():
        journal.unlink()
    elif size is not None:
        with journal.open("r+b") as kept:
            kept.truncate(size)
    folder = repo / out[0].removeprefix("filed ").split(";")[0]
    (folder / "03-change-spec.md").write_text(f"# {title}\n\nDo it.\n", encoding="utf-8")
    return folder


def name_gate(repo: Path, name: str, command: str) -> None:
    """The long gate `name` in the code repository's root `chantier.yaml`: what `gate` runs."""
    (repo / "chantier.yaml").write_text(
        f"long_gate:\n  commands:\n    {name}: {command}\n", encoding="utf-8"
    )


def changes(repo: Path) -> Path:
    return repo / ".agents" / "changes"


def record(repo: Path) -> dict[str, Any]:
    """The open batch's record."""
    path = changes(repo) / "4-batch" / "batch.json"
    data: dict[str, Any] = json.loads(path.read_text("utf-8"))
    return data


def batch_of(repo: Path) -> BatchRecord:
    """The open batch's record, read as the CLI reads it."""
    return read_batch_json(Repo.find().store, changes(repo) / "4-batch" / "batch.json")


def write_record(repo: Path, data: dict[str, Any]) -> None:
    (changes(repo) / "4-batch" / "batch.json").write_text(json.dumps(data), encoding="utf-8")


def open_batch(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    *titles: str,
    args: tuple[object, ...] = (),
    seat: bool = True,
) -> list[str]:
    """Open a batch of the titled CRs as the Foreman; returns the CR ids."""
    host(monkeypatch)
    folders = [prepared(repo, chantier, t) for t in titles]
    code, _, err = chantier("open", *map(str, folders), *FROM_AGENTS_MD, *args)
    assert code == 0, err
    monkeypatch.setenv("CHANTIER_BATCH", record(repo)["id"])
    if seat:
        assert chantier("foreman", "set", "local_foreman_t", "--epoch", 1)[0] == 0
    return [c["id"] for c in record(repo)["crs"]]


def has(out: list[str], line: str) -> bool:
    """A role line, whatever escalation ends it."""
    return any(ln == line or ln.startswith(f"{line} escalation=") for ln in out)


def events(repo: Path) -> list[dict[str, Any]]:
    """The open batch's events, oldest first."""
    path = changes(repo) / "4-batch" / "events.jsonl"
    return [json.loads(x) for x in path.read_text("utf-8").splitlines()]


def open_bare(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, *args: object
) -> str:
    """Open a batch with no CR unless `args` names one (born paused); returns its id."""
    host(monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "uuid-chief")
    code, _, err = chantier("open", *args, *FROM_AGENTS_MD)
    assert code == 0, err
    monkeypatch.setenv("CHANTIER_BATCH", record(repo)["id"])
    return str(record(repo)["id"])


DEAD = 2_000_000_000  # a PID no process has


def name_server(git_dir: Path, pid: int = 0, version: str = "9.9.9") -> None:
    """The `server` entry of `server.json`: of this process by default, else of a PID (`DEAD`)."""
    entry = {
        "pid": pid or os.getpid(),
        "host": "127.0.0.1",
        "port": 1,
        "version": version,
        "served": "x",
        "started": clock.now(),
    }
    state.modify(git_dir, lambda data: data.__setitem__(state.SERVER, entry))
