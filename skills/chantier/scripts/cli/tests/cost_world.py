"""A batch with Claude transcripts on disk: a Foreman, a Chief of Staff, two Drivers, workers."""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import host, open_batch, record, write_record
from conftest import Chantier

CALL_USD = {"in": 20, "cache_read": 4000, "cache_write_1h": 6000}  # micro-dollars of one call
FOREMAN_CALLS, DRIVER_CALLS, WORKER_CALLS = 30, 12, 4


def call_usd(out: int) -> float:
    """What one `claude-sonnet-5-5` call of the fixture costs (10 in, 20k read, 2k 1h write)."""
    return (sum(CALL_USD.values()) + out * 10) / 1e6


def msg(mid: str, out: int, model: str = "claude-sonnet-5-5", **fields: Any) -> str:
    usage = {
        "input_tokens": 10,
        "output_tokens": out,
        "cache_read_input_tokens": 20_000,
        "cache_creation": {"ephemeral_1h_input_tokens": 2_000},
    }
    body = {"id": mid, "model": model, "usage": usage}
    return json.dumps({"type": "assistant", **fields, "message": body}) + "\n"


def user(content: Any, **fields: Any) -> str:
    return json.dumps({"type": "user", **fields, "message": {"content": content}}) + "\n"


def stamp(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%S.000Z")


@dataclass
class CostWorld:
    repo: Path
    chantier: Chantier
    projects: Path
    ids: list[str]

    @property
    def main(self) -> Path:
        slug = "".join(ch if ch.isalnum() else "-" for ch in str(self.repo.resolve()))
        return self.projects / slug / "uuid-foreman.jsonl"

    @property
    def chief(self) -> Path:
        return self.main.with_name("uuid-chief.jsonl")

    @property
    def subagents(self) -> Path:
        return self.main.with_suffix("") / "subagents"

    @property
    def state(self) -> Path:
        return self.repo / ".agents" / "changes" / "4-batch" / "batch.json"

    @property
    def batch(self) -> str:
        return str(record(self.repo)["id"])

    @property
    def opened(self) -> datetime:
        return datetime.fromisoformat(record(self.repo)["created"].replace("Z", "+00:00"))

    def paused(self) -> None:
        """Mark the batch paused, as the Foreman does once every CR is merged."""
        write_record(self.repo, {**record(self.repo), "status": "paused"})

    def cost(self, *args: str) -> list[str]:
        code, out, err = self.chantier("cost", *args, "--batch", self.batch)
        assert code == 0, err
        return out

    def agent(
        self, name: str, kind: str, calls: int, parent: str | None = None, **fields: Any
    ) -> None:
        file = self.subagents / f"agent-{name}.jsonl"
        file.write_text(
            "".join(msg(f"{name}{i}", 900, **fields.get(str(i), {})) for i in range(calls))
        )
        meta = {"agentType": kind, **({"parentAgentId": parent} if parent else {})}
        file.with_suffix("").with_suffix(".meta.json").write_text(json.dumps(meta))


def money(line: str) -> float:
    found = re.search(r"\$(\d+\.\d+)", line)
    assert found, line
    return float(found[1])


CostFixture = Callable[[], CostWorld]


def slug(folder: Path) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in str(folder.resolve()))


def build(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> CostWorld:
    """The world, built once per pytest process (so once per xdist worker) and copied into each
    test's repository: what it holds, the batch's record, the transcripts and their times, is the
    same for every test; the paths and the environment are the test's own."""
    # the pytest base folder is the process's own (a worker has its own): the template lives there
    template = tmp_path.parent / "cost-world-template"
    if not template.is_dir():
        world = _build(repo, chantier, monkeypatch, tmp_path)
        shutil.copytree(repo, template / "proj")
        shutil.copytree(world.projects, template / "claude-projects")
        (template / "built-in").write_text(str(repo.resolve()), encoding="utf-8")
        return world
    built_in = (template / "built-in").read_text(encoding="utf-8")
    # the repository's own `.git` is the test's (no command of the world commits)
    shutil.copytree(
        template / "proj", repo, ignore=shutil.ignore_patterns(".git"), dirs_exist_ok=True
    )
    for status in (repo / ".agents").rglob("STATUS.*"):  # the only files that name the folder
        text = status.read_text(encoding="utf-8")
        status.write_bytes(text.replace(built_in, str(repo.resolve())).encode("utf-8"))
    projects = tmp_path / "claude-projects"
    shutil.copytree(template / "claude-projects", projects)
    (projects / slug(Path(built_in))).rename(projects / slug(repo))
    monkeypatch.setenv("CHANTIER_CLAUDE_PROJECTS", str(projects))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "uuid-chief")
    host(monkeypatch)
    monkeypatch.setenv("CHANTIER_BATCH", record(repo)["id"])
    return CostWorld(repo, chantier, projects, [c["id"] for c in record(repo)["crs"]])


def _build(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> CostWorld:
    projects = tmp_path / "claude-projects"
    monkeypatch.setenv("CHANTIER_CLAUDE_PROJECTS", str(projects))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "uuid-chief")
    ids = open_batch(repo, chantier, monkeypatch, "Cost one", "Cost two", args=("--budget", 50))
    w = CostWorld(repo, chantier, projects, ids)
    assert chantier("foreman", "transcript", "uuid-foreman", "--epoch", 1)[0] == 0
    w.subagents.mkdir(parents=True)
    earlier = msg("old", 900_000, timestamp="2000-01-01T00:00:00.000Z")
    synthetic = msg("syn", 0, model="<synthetic>")  # an API error: costs nothing
    opening = stamp(w.opened).removesuffix("000Z") + "250Z"  # a call in the opening second
    result = [{"type": "tool_result", "content": "ok"}]
    w.main.write_text(
        earlier
        + synthetic
        + "".join(
            user("a wake" if i % 3 == 0 else result)
            + msg(f"f{i}", 300, **({"timestamp": opening} if i == 0 else {}))
            for i in range(FOREMAN_CALLS)
        )
    )
    w.chief.write_text(earlier + msg("c1", 300))
    (w.subagents / "agent-earlier.jsonl").write_text(earlier)  # an earlier batch: costs nothing
    for cr in ids:
        assert chantier("take", cr, "--epoch", 1)[0] == 0
        assert chantier("agents", "set", cr, f"agent-{cr}", "--epoch", 1)[0] == 0
        w.agent(f"agent-{cr}", "cr-driver", DRIVER_CALLS)
        w.agent(f"worker-{cr}", "coder", WORKER_CALLS, parent=f"agent-{cr}")
    return w


def later(w: CostWorld, minutes: int) -> str:
    return stamp(w.opened + timedelta(minutes=minutes))
