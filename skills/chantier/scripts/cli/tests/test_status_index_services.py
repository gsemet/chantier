"""The planning folder's `STATUS.json`: a batch's merged CRs, its creation time and its CRs per
status, and the `services` snapshot (no key in it)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import changes, open_batch, record, write_record
from conftest import Chantier

from chantier.core.repo import Repo
from chantier.hub import lock, state
from chantier.lifecycle.stages import stage_layout
from chantier.status.write import write_dashboard

KEY, READ_KEY = "private-key-text-aaaa", "public-key-text-bbbb"


def written(repo: Path) -> dict[str, Any]:
    r = Repo.find()
    write_dashboard(r, stage_layout(r))
    data: dict[str, Any] = json.loads((changes(repo) / "STATUS.json").read_text("utf-8"))
    return data


def test_batch_entry_holds_merged_created_and_counts(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_batch(repo, chantier, monkeypatch, "One", "Two", "Three", "Four", "Five", "Six")
    data = record(repo)
    states = ["queued", "working", "ready", "merged", "merged", "cancelled"]
    merges = {3: ("2026-11-20T10:00:00Z", 1.0), 4: ("2026-11-22T10:00:00Z", 3.0)}
    for n, (c, status) in enumerate(zip(data["crs"], states, strict=True)):
        c["status"] = status
        if n in merges:
            c["merged_at"], c["cost_usd"] = merges[n]
    write_record(repo, data)

    entry = written(repo)["batches"][0]

    assert entry["counts"] == {"queued": 1, "working": 1, "ready": 1, "merged": 2, "cancelled": 1}
    assert entry["created"] == data["created"]
    assert [m["cr"] for m in entry["merged"]] == [data["crs"][4]["id"], data["crs"][3]["id"]]
    assert [m["cost_usd"] for m in entry["merged"]] == [3.0, 1.0]
    assert entry["merged"][0]["when"] == "2026-11-22T10:00:00Z"
    assert (entry["crs_total"], len(entry["crs"])) == (len(states), len(states) - 3)  # active only


def test_services_name_the_live_processes_and_hold_no_key(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_batch(repo, chantier, monkeypatch, "One")
    git = Repo.find().git_dir
    state.write_server(git, "127.0.0.1", 8765, "0.0.1", "x")
    state.set_key(git, KEY, READ_KEY)
    name = (Repo.find().project_dir or Repo.find().root).name
    held = lock.WatcherLock(git, name, "sess-a")
    assert held.acquire()
    try:
        services = written(repo)["services"]
    finally:
        held.release()

    server = services["server"]
    assert server["pid"] == os.getpid()
    assert server["url"] == "http://127.0.0.1:8765/" and server["local_url"] is None
    assert server["build_note"] == "server is chantier 0.0.1, this is chantier " + (
        __import__("chantier").__version__
    )
    assert services["hub"] is None and services["writer"] is None
    assert services["watchers"] == ["sess-a"] and services["at"]
    text = (changes(repo) / "STATUS.json").read_text("utf-8")
    assert KEY not in text and READ_KEY not in text
    assert "?k=" not in text


def test_no_server_gives_a_null_server(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_batch(repo, chantier, monkeypatch, "One")
    services = written(repo)["services"]
    assert services["server"] is None and services["watchers"] == []
