"""`transcript_state`: a Claude transcript's end says whether its agent ran, not its age."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from chantier.costs.sessions import transcript_state


def turn(kind: str, *blocks: dict[str, Any], stop: str | None = None) -> str:
    message: dict[str, Any] = {"role": kind, "content": list(blocks)}
    if kind == "assistant":
        message["stop_reason"] = stop
    return json.dumps({"type": kind, "message": message})


def call(name: str, ident: str = "t1") -> str:
    return turn("assistant", {"type": "tool_use", "id": ident, "name": name}, stop="tool_use")


def result(ident: str = "t1") -> str:
    return turn("user", {"type": "tool_result", "tool_use_id": ident, "content": "ok"})


PROMPT = turn("user", {"type": "text", "text": "do it"})
TEXT = {"type": "text", "text": "done"}
NOISE = [
    json.dumps({"type": "api-request", "params": {}}),
    json.dumps({"type": "api-request-blob", "message": {"role": "assistant", "content": []}}),
    json.dumps({"type": "attachment"}),
]

ENDED = ("ended", "")
CASES = {
    "handback and its result": ([PROMPT, call("SubagentHandback"), result()], ENDED),
    "end_turn text": ([PROMPT, turn("assistant", TEXT, stop="end_turn")], ENDED),
    "stop_sequence text": ([PROMPT, turn("assistant", TEXT, stop="stop_sequence")], ENDED),
    "noise after the hand-back": (
        [PROMPT, call("SubagentHandback"), result(), *NOISE],
        ENDED,
    ),
    "tool call without result": (
        [PROMPT, call("Bash")],
        ("running", "its tool call Bash has no result yet"),
    ),
    "trailing tool result": (
        [PROMPT, call("Bash"), result()],
        ("running", "its last record is a tool's result with no answer yet"),
    ),
    "trailing prompt": (
        [PROMPT],
        ("running", "its last record is a prompt with no answer yet"),
    ),
    "tool_use stop and nothing after": (
        [PROMPT, turn("assistant", TEXT, stop="tool_use")],
        ("running", "its last call stopped on tool_use"),
    ),
    "null stop": (
        [PROMPT, turn("assistant", TEXT)],
        ("running", "its last call stopped on null"),
    ),
    "cut last line": (
        [PROMPT, call("SubagentHandback"), result(), '{"type": "assistant", "mess'],
        ("unreadable", "its last line is not complete JSON"),
    ),
    "no user or assistant record": (NOISE, ("unreadable", "it holds no user or assistant record")),
    "missing file": (None, ("unreadable", "the file is missing")),
}


@pytest.mark.parametrize("lines, expected", CASES.values(), ids=CASES.keys())
def test_transcript_state(
    tmp_path: Path, lines: list[str] | None, expected: tuple[str, str]
) -> None:
    path = tmp_path / "agent-a1.jsonl"
    if lines is not None:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert transcript_state(path) == expected
