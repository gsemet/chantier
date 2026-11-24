"""The rules read again after a compaction, on the shipped cards and manifest (the fallback form:
the `batch:` line of `status` carries the pointer, the manifest holds no `reload:rules`)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from chantier.core.records import BatchRecord
from chantier.plugin_files import skill_dir
from chantier.status.ready_line import batch_line

REFERENCES = Path(__file__).resolve().parents[3] / "references"
SHIPPED = "reload-rules.md"
LIMIT = 2_500  # bytes
KEYS = (
    "status-layout.md",
    "handed back:",
    "owed before the merge",
    "batch:",
    "batch:stack",
    "under the grant",
    "order merged",
)


def _read(name: str) -> str:
    return (REFERENCES / name).read_text(encoding="utf-8")


def _manifest() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(_read("startup-manifest.json"))
    return data


def test_the_fallback_form_has_no_manifest_action_and_no_reload_sentence() -> None:
    manifest = _manifest()
    assert "reload:rules" not in manifest["actions"]
    assert SHIPPED not in json.dumps(manifest)
    assert "reload:rules" not in _read("session-start.md")


def test_the_batch_line_ends_with_the_pointer_to_the_piece() -> None:
    repo: Any = SimpleNamespace(config={"default_branch": "main"})
    line = batch_line(repo, BatchRecord(id="batch-1", mode="parallel"), [], set())
    pointer = f"; rules: {skill_dir().as_posix()}/references/{SHIPPED} (reread after a compaction)"
    assert line.endswith(pointer)
    assert (skill_dir() / "references" / SHIPPED).is_file()


def test_the_foremans_opening_names_the_pointer() -> None:
    opening = "\n".join(_read("foreman.md").splitlines()[:20])
    assert "`rules:` pointer of `status`'s `batch:` line" in opening


@pytest.mark.parametrize("key", KEYS)
def test_the_piece_holds_the_four_rules_key_words(key: str) -> None:
    assert key in _read(SHIPPED)


def test_the_piece_stays_short() -> None:
    assert len(_read(SHIPPED).encode("utf-8")) <= LIMIT


@pytest.mark.parametrize(
    "words",
    [
        "`handed back:` line",
        "prefix `handed back:` is never said",
        "ask and the line differ, the ask wins",
    ],
)
def test_the_words_to_the_user_name_the_line_its_prefix_and_the_ask(words: str) -> None:
    merge = " ".join(_read("chief-of-staff-merge.md").split())
    assert words in merge
