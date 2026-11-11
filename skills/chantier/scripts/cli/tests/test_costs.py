"""Cost totals refuse missing or unreadable Claude usage and count the calls with no price."""
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
    (json.dumps({"type": "assistant", "message": {"model": "claude-sonnet-5-5",
                "usage": {"output_tokens": 1}}}) + "\n", "no message id"),
])
def test_claude_cost_refuses_unreadable_usage(tmp_path, contents, message):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(contents)
    with pytest.raises(ChantierError, match=message) as error:
        session_costs(transcript)
    assert error.value.code == EXIT_EXTERNAL


def test_a_model_with_no_price_is_counted_and_named_and_never_priced(tmp_path):
    other = record("unknown-model")
    other["message"]["id"] = "m2"
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(json.dumps(record()) + "\n" + json.dumps(other) + "\n")
    row = session_costs(transcript)[0]
    assert row["calls"] == 1 and row["unpriced"] == {"unknown-model": 1}
    assert row["usd"] == pytest.approx((1000 * 2 + 2000 * 10) / 1e6)
    assert row["peak_context"] == 1000  # the unpriced call's tokens are measured, not priced
    transcript.write_text(json.dumps(other) + "\n")  # only unpriced calls: not an empty window
    assert session_costs(transcript)[0]["unpriced"] == {"unknown-model": 1}


def test_a_dated_id_is_priced_by_its_model_and_the_project_prices_rank_first(tmp_path):
    dated = record("claude-sonnet-5-5-20261001")
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(json.dumps(dated) + "\n")
    assert session_costs(transcript)[0]["usd"] == pytest.approx((1000 * 2 + 2000 * 10) / 1e6)
    mine = {"claude-sonnet-5-5": {"input": 1, "cache_write_5m": 1, "cache_write_1h": 1,
                                  "cache_read": 1, "output": 1}}
    assert session_costs(transcript, prices=mine)[0]["usd"] == pytest.approx(3000 / 1e6)


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
