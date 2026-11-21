"""Running batch or next batch: `triage --running-batch` marks a grilled CR for the open batch
(`work/running-batch`) and moves nothing; any other destination clears the mark; `status` names
the marked CRs and the stale marks; `triage --ready` joins no batch; `order factory` is gone."""

from __future__ import annotations

from pathlib import Path

import pytest
from batch_helpers import changes, host, open_bare, prepared, record
from conftest import Chantier

from chantier.core.errors import EXIT_PRECONDITION, EXIT_USAGE

MARK = Path("work") / "running-batch"


def marks(repo: Path) -> list[Path]:
    return sorted(changes(repo).rglob("running-batch"))


def moved(repo: Path, name: str) -> Path:
    return next(p for p in changes(repo).rglob(name) if p.is_dir())


def test_a_grilled_cr_is_marked_for_the_running_batch_and_nothing_moves(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    batch = open_bare(repo, chantier, monkeypatch)
    written = prepared(repo, chantier, "Written")
    specifying = repo / chantier("file", "Specifying")[1][0].removeprefix("filed ").split(";")[0]
    (specifying / "work").mkdir(exist_ok=True)
    (specifying / "work" / "specifying").write_text("", encoding="utf-8")
    for folder in (written, specifying):
        code, out, err = chantier("triage", str(folder), "--running-batch")
        assert code == 0, err
        assert f"marked for the running batch {batch}" in out[0] and "order add --note" in out[0]
        assert (folder / MARK).read_text("utf-8").split()[-1] == batch
    assert record(repo)["crs"] == [] and record(repo)["status"] == "paused"
    line = next(x for x in chantier("status")[1] if x.startswith("running batch: 2 CRs marked"))
    assert f"{written.name} (written)" in line and f"{specifying.name} (specifying)" in line
    assert line.endswith("once no critic runs and no open question remains")


@pytest.mark.parametrize("case", ["ungrilled", "ready", "no-batch"])
def test_the_mark_is_refused_where_it_cannot_hold(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    host(monkeypatch)
    folder = prepared(repo, chantier, "Refused")
    if case == "ungrilled":
        (folder / "03-change-spec.md").unlink()
    if case == "ready":
        out = chantier("triage", str(folder), "--ready")[1]
        folder = repo / out[0].removeprefix("triaged ")
    if case != "no-batch":
        open_bare(repo, chantier, monkeypatch)
    code, _, err = chantier("triage", str(folder), "--running-batch")
    assert code == EXIT_PRECONDITION
    expected = {
        "ungrilled": "is not grilled: grill it first",
        "ready": "is in 3-ready: `order add --note",
        "no-batch": f"no open batch: {folder.name} goes to the next batch",
    }[case]
    assert expected in err and marks(repo) == []


@pytest.mark.parametrize("how", ["ready", "priority", "inbox", "abandon", "add"])
def test_any_other_destination_clears_the_mark(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, how: str
) -> None:
    batch = open_bare(repo, chantier, monkeypatch)
    folder = prepared(repo, chantier, "Bound")
    if how == "inbox":
        out = chantier("triage", str(folder), "--priority", "P2")[1]
        folder = repo / out[0].removeprefix("triaged ").split(" (")[0]
    code, _, err = chantier("triage", str(folder), "--running-batch")
    assert code == 0, err
    action = {
        "ready": ("triage", str(folder), "--ready"),
        "priority": ("triage", str(folder), "--priority", "P3"),
        "inbox": ("triage", str(folder), "--inbox"),
        "abandon": ("abandon", str(folder)),
        "add": ("order", "add", "--note", str(folder), "--batch", batch),
    }[how]
    code, _, err = chantier(*action)
    assert code == 0, err
    assert marks(repo) == []
    if how == "add":
        assert len(record(repo)["crs"]) == 1 and "1-pending" in record(repo)["crs"][0]["path"]
    else:
        assert record(repo)["crs"] == []


def test_a_stale_mark_is_named_with_or_without_an_open_batch(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    folder = prepared(repo, chantier, "Stale")
    (folder / "work").mkdir(exist_ok=True)
    (folder / MARK).write_text("2026-11-01T00:00:00Z batch-00\n", encoding="utf-8")
    stale = "marked for batch-00, which is closed: `triage"
    code, _, err = chantier("status")
    assert code != 0 and stale in err
    open_bare(repo, chantier, monkeypatch)
    assert any(stale in x for x in chantier("status")[1])


def test_triage_ready_joins_no_batch_and_order_factory_is_gone(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_bare(repo, chantier, monkeypatch)
    folder = prepared(repo, chantier, "Next")
    code, out, err = chantier("triage", str(folder), "--ready")
    assert code == 0 and len(out) == 1 and out[0].startswith("triaged "), err
    assert record(repo)["crs"] == [] and moved(repo, folder.name).parent.name == "3-ready"
    assert chantier("order", "factory", "on", "--note", "the user's word")[0] == EXIT_USAGE
