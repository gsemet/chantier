import pytest

from tasks_cli.cli import main


@pytest.fixture(autouse=True)
def tasks_file(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKS_FILE", str(tmp_path / "tasks.json"))


def test_add_then_list(capsys):
    assert main(["add", "buy milk"]) == 0
    assert main(["add", "call Bob"]) == 0
    capsys.readouterr()
    assert main(["list"]) == 0
    assert capsys.readouterr().out.splitlines() == ["[ ] 1: buy milk", "[ ] 2: call Bob"]


def test_done_marks_the_task(capsys):
    main(["add", "buy milk"])
    assert main(["done", "1"]) == 0
    capsys.readouterr()
    main(["list"])
    assert capsys.readouterr().out.splitlines() == ["[x] 1: buy milk"]
