"""The rules read again after a compaction: the `batch:` line of `status` points at the floor and
says to run the brief again."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from chantier.core.records import BatchRecord
from chantier.plugin_files import skill_dir
from chantier.status.ready_line import batch_line


def test_the_batch_line_ends_with_the_pointer_to_the_floor() -> None:
    repo: Any = SimpleNamespace(config={"default_branch": "main"})
    line = batch_line(repo, BatchRecord(id="batch-1", mode="parallel"), [], set())
    floor = skill_dir() / "references" / "floor.md"
    pointer = f"; rules: {floor.as_posix()} (after a compaction, run your brief again)"
    assert line.endswith(pointer)
    assert floor.is_file()
