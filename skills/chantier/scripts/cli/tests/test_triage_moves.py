"""`triage` moves an item between the inbox, the backlog and 3-ready; it refuses a non-move."""

from __future__ import annotations

from pathlib import Path

import pytest
from batch_helpers import FROM_AGENTS_MD, changes, host, prepared
from conftest import Chantier

from chantier.core.errors import EXIT_PRECONDITION

SPEC = "03-change-spec.md"


def moved(repo: Path, out: list[str]) -> Path:
    return repo / out[0].removeprefix("triaged ").split(";", 1)[0].rsplit(" (", 1)[0]


def test_triage_moves_between_the_folders_and_refuses_what_is_not_a_move(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    tree = changes(repo)
    spec = prepared(repo, chantier, "Tree with spec")
    bare = repo / chantier("file", "Tree without spec")[1][0].removeprefix("filed ").split(";")[0]
    ready_spec = moved(repo, chantier("triage", str(spec), "--ready")[1])
    ready_bare = moved(repo, chantier("triage", str(bare), "--ready")[1])
    assert ready_spec.parent == ready_bare.parent == tree / "3-ready"  # with a spec or without
    assert (ready_spec / SPEC).is_file() and not (ready_bare / SPEC).exists()
    assert not spec.exists() and not bare.exists()
    with pytest.raises(SystemExit):  # a target is required
        chantier("triage", str(ready_spec))
    assert ready_spec.is_dir()
    code, _, _ = chantier("triage", str(ready_spec), "--ready")
    assert code == EXIT_PRECONDITION and ready_spec.is_dir()  # already in 3-ready
    back = moved(repo, chantier("triage", str(ready_spec), "--priority", "P2")[1])
    assert back.parent == tree / "2-backlog" / "P2" and not ready_spec.exists()
    chantier("triage", str(back), "--ready")
    inboxed = moved(repo, chantier("triage", str(tree / "3-ready" / back.name), "--inbox")[1])
    assert inboxed.parent == tree / "1-inbox" and not back.exists()
    code, _, err = chantier("triage", str(inboxed), "--inbox")
    assert code == EXIT_PRECONDITION and "already in 1-inbox" in err and inboxed.is_dir()
    with pytest.raises(SystemExit):  # two targets move nothing
        chantier("triage", str(inboxed), "--inbox", "--ready")
    assert inboxed.is_dir()
    chantier("triage", str(inboxed), "--ready")
    backlog_bare = prepared(repo, chantier, "Tree backlog bare")
    (backlog_bare / SPEC).unlink()
    code, _, _ = chantier("open", str(backlog_bare), *FROM_AGENTS_MD)
    assert code == EXIT_PRECONDITION and backlog_bare.is_dir()
    assert not (tree / "4-batch" / "batch.json").exists()
    assert chantier("abandon", str(backlog_bare))[0] == 0
