"""Shared helpers of the tests that open a batch and call the CLI in-process."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import Chantier

FROM_AGENTS_MD = ("--default-branch", "main")  # what the Chief of Staff read in the rules


def host(monkeypatch: pytest.MonkeyPatch, name: str = "claude") -> None:
    """Run as the given host, outside VS Code."""
    monkeypatch.setenv("CHANTIER_HOST", name)
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")


def prepared(repo: Path, chantier: Chantier, title: str) -> Path:
    """File a CR in the inbox and give it a spec; returns its folder."""
    _, out, _ = chantier("file", title)
    folder = repo / out[0].removeprefix("filed ").split(";")[0]
    (folder / "03-change-spec.md").write_text(f"# {title}\n\nDo it.\n", encoding="utf-8")
    return folder


def changes(repo: Path) -> Path:
    return repo / ".agents" / "changes"


def record(repo: Path) -> dict[str, Any]:
    """The open batch's record."""
    path = changes(repo) / "4-batch" / "batch.json"
    data: dict[str, Any] = json.loads(path.read_text("utf-8"))
    return data


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


def open_factory(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, *args: object
) -> str:
    """Open a factory batch (no CR unless `args` names one); returns its id."""
    host(monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "uuid-chief")
    code, _, err = chantier("open", *args, *FROM_AGENTS_MD)
    assert code == 0, err
    monkeypatch.setenv("CHANTIER_BATCH", record(repo)["id"])
    return str(record(repo)["id"])
