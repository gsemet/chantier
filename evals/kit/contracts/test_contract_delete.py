"""CI contract for `tasks delete`: its specification, checked as written.

The local forge adds this file to the CI clone of a branch whose name contains `delete`; the
agents never see it in their worktree. A requirement the CR's own tests missed turns CI red.
"""
import os

import pytest

from tasks_cli.cli import main


@pytest.fixture(autouse=True)
def tasks_file(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKS_FILE", str(tmp_path / "tasks.json"))


def stored() -> str:
    with open(os.environ["TASKS_FILE"], encoding="utf-8") as f:
        return f.read()


def test_contract_delete_keeps_the_other_ids(capsys):
    for title in ("a", "b", "c"):
        main(["add", title])
    capsys.readouterr()
    assert main(["delete", "2"]) == 0
    assert capsys.readouterr().out.strip() == "deleted 2: b"
    main(["list"])
    assert capsys.readouterr().out.splitlines() == ["[ ] 1: a", "[ ] 3: c"]


def test_contract_delete_an_unknown_id_changes_nothing(capsys):
    main(["add", "a"])
    before = stored()
    capsys.readouterr()
    assert main(["delete", "9"]) == 1
    out = capsys.readouterr()
    assert "error: no task 9" in out.out + out.err
    assert stored() == before


def test_contract_delete_several_ids_is_all_or_nothing(capsys):
    for title in ("a", "b", "c"):
        main(["add", title])
    before = stored()
    capsys.readouterr()
    assert main(["delete", "1", "9"]) == 1
    assert stored() == before
    assert main(["delete", "1", "3"]) == 0
    capsys.readouterr()
    main(["list"])
    assert capsys.readouterr().out.splitlines() == ["[ ] 2: b"]
