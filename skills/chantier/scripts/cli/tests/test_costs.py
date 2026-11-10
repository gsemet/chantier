"""Cost totals refuse missing or unpriceable Claude usage."""
import json

import pytest

from chantier.costs import session_costs
from chantier.state import ChantierError, EXIT_EXTERNAL


def record(model="claude-sonnet-5-5"):
    return {"type": "assistant", "message": {"id": "m1", "model": model,
            "usage": {"input_tokens": 1_000, "output_tokens": 2_000}}}


def test_claude_cost_deduplicates_and_prices_known_usage(tmp_path):
    transcript = tmp_path / "session.jsonl"
    line = json.dumps(record()) + "\n"
    transcript.write_text(line * 2)
    rows = session_costs(transcript)
    assert rows[0]["calls"] == 1
    assert rows[0]["usd"] == pytest.approx((1000 * 2 + 2000 * 10) / 1e6)


@pytest.mark.parametrize(("contents", "message"), [
    ("", "no priced calls"),
    ("not JSON\n", "unreadable Claude transcript"),
    (json.dumps(record("unknown-model")) + "\n", "no Claude price"),
    (json.dumps({"type": "assistant", "message": {"model": "claude-sonnet-5-5",
                "usage": {"output_tokens": 1}}}) + "\n", "no message id"),
])
def test_claude_cost_refuses_unpriced_or_unreadable_usage(tmp_path, contents, message):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(contents)
    with pytest.raises(ChantierError, match=message) as error:
        session_costs(transcript)
    assert error.value.code == EXIT_EXTERNAL


def test_claude_cost_requires_main_transcript_even_if_subagents_exist(tmp_path):
    transcript = tmp_path / "session.jsonl"
    subagents = tmp_path / "session" / "subagents"
    subagents.mkdir(parents=True)
    (subagents / "agent-one.jsonl").write_text(json.dumps(record()) + "\n")
    with pytest.raises(ChantierError, match="Foreman transcript not found"):
        session_costs(transcript)


def test_a_turn_naming_the_answers_is_grill_and_a_turn_without_is_not(tmp_path):
    def call(mid, blocks):  # one record per content block, as Claude writes them
        return json.dumps({"type": "assistant", "timestamp": "2026-03-01T00:00:00Z", "message": {
            "id": mid, "model": "claude-sonnet-5-5", "content": blocks,
            "usage": {"input_tokens": 1_000, "output_tokens": 10}}}) + "\n"

    wake = json.dumps({"type": "user", "message": {"content": "go"}}) + "\n"
    result = json.dumps({"type": "user", "message": {"content": [
        {"type": "tool_result", "content": "ok"}]}}) + "\n"
    use = {"type": "tool_use", "name": "Edit", "input": {"file_path": "x/02-answers.md"}}
    boundary = json.dumps({"type": "system", "subtype": "compact_boundary",
                           "timestamp": "2026-03-01T00:00:00Z"}) + "\n"
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        wake + call("a", [{"type": "text", "text": "I record it"}]) + call("a", [use]) + result
        + call("b", [{"type": "text", "text": "done"}]) + boundary + call("b", [use])  # a repeat
        + wake + call("c", [{"type": "tool_use", "name": "Bash", "input": {"command": "status"}}]))
    row = session_costs(transcript, "2026-01-01T00:00:00Z", split=True)[0]
    assert (row["grill"]["calls"], row["calls"], row["compactions"]) == (2, 1, 1)
