"""The board's reading of what a batch left: the 127.0.0.1 link of a board on every address, and the
dependencies of a closed batch recovered from its archived CR folders."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from chantier.board import address
from chantier.board.archived import recovered_after
from chantier.store import FolderStore


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("0.0.0.0", "http://127.0.0.1:8765/?k=KEY"),
        ("::", "http://[::1]:8765/?k=KEY"),
        ("192.168.1.20", None),
    ],
)
def test_local_url_is_the_loopback_link_of_a_board_on_every_address(
    monkeypatch: pytest.MonkeyPatch, host: str, expected: str | None
) -> None:
    monkeypatch.setattr(address, "_default_route_address", lambda: "192.168.1.20")
    assert address.local_url(host, 8765, "KEY") == expected


def _crs(**extra: Any) -> list[dict[str, Any]]:
    return [
        {"cr": "CR-1", "archive": "5-archives/261101-1000-1-first", **extra},
        {"cr": "CR-2", "archive": "5-archives/261101-1100-2-second", **extra},
    ]


@pytest.mark.parametrize("kind", ["record", "archives", "none"])
def test_recovered_after(tmp_path: Path, kind: str) -> None:
    if kind == "record":
        record = {"crs": _crs(after=["CR-1"])}
        assert recovered_after(FolderStore(tmp_path), tmp_path, record) == {
            **record,
            "after_source": "record",
        }
        return
    if kind == "archives":
        folder = tmp_path / "5-archives" / "261101-1100-2-second"
        folder.mkdir(parents=True)
        (folder / "depends.json").write_text(
            json.dumps({"after": ["first", "CR-1", "an-earlier-batch", "CR-9"]}), encoding="utf-8"
        )
        out = recovered_after(FolderStore(tmp_path), tmp_path, {"crs": _crs()})
        assert out["after_source"] == "archives"
        assert [c["after"] for c in out["crs"]] == [[], ["CR-1"]]
        return
    out = recovered_after(FolderStore(tmp_path), tmp_path, {"crs": [{"cr": "CR-1"}]})
    assert out["after_source"] == "none"
    assert out["crs"] == [{"cr": "CR-1", "after": []}]
