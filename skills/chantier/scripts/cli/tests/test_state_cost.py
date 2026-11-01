"""Locking, output size, batch resolution, reports and transcript pricing."""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from chantier import costs

SRC = Path(__file__).resolve().parents[1] / "src"


def test_concurrent_writers_lose_nothing(ready):
    env = {**os.environ, "PYTHONPATH": str(SRC)}

    def report(i):
        return subprocess.run([sys.executable, "-m", "chantier", "report", "CR-101", "note", f"n{i}"],
                              cwd=ready, env=env, capture_output=True, text=True).returncode

    with ThreadPoolExecutor(12) as pool:
        assert set(pool.map(report, range(24))) == {0}
    d = json.loads((ready / ".agents/changes/batches/b1/batch.json").read_text())
    assert len(d["crs"][0]["notes"]) == 24
    events = (ready / ".agents/changes/batches/b1/events.jsonl").read_text().splitlines()
    assert sum(1 for e in events if json.loads(e)["kind"] == "report") == 24


def test_output_is_at_most_ten_lines(repo, chantier):
    chantier("setup")
    code, out, _ = chantier("open", "big", *[f"Item {i}" for i in range(15)], "--no-worktrees")
    assert code == 0 and len(out) == 10 and out[-1].startswith("…")
    assert len(chantier("status")[1]) == 10
    assert json.loads("\n".join(chantier("status", "--json")[1]))["id"] == "big"


def test_batch_resolution(repo, chantier, monkeypatch):
    chantier("setup")
    chantier("open", "one", "A", "--no-worktrees")
    chantier("open", "two", "B", "--no-worktrees")
    assert chantier("status")[1][0].startswith("two ")
    monkeypatch.setenv("CHANTIER_BATCH", "one")
    assert chantier("status")[1][0].startswith("one ")
    assert chantier("status", "--batch", "two")[1][0].startswith("two ")
    assert chantier("report", "CR-102", "note", "x")[0] == 0  # found in `two` by CR id


def test_cr_numbers_are_unique_across_batches(repo, chantier):
    chantier("setup")
    chantier("open", "one", "A", "B", "--no-worktrees")
    chantier("open", "two", "C", "--no-worktrees")
    assert chantier("status", "--batch", "two")[1][1].startswith("CR-103 ")


def test_open_from_a_backlog_file(repo, chantier):
    chantier("setup")
    item = repo / "backlog.md"
    item.write_text("# Fix the flaky upload\n\nDetails.\n")
    chantier("open", "f1", f"@{item}", "--no-worktrees")
    d = json.loads((repo / ".agents/changes/batches/f1/batch.json").read_text())
    assert d["crs"][0]["title"] == "Fix the flaky upload"


def test_open_requires_setup_and_a_valid_id(repo, chantier):
    assert chantier("open", "x", "A")[0] == 2
    chantier("setup")
    assert chantier("open", "Bad Id", "A")[0] == 1


def test_reports_update_the_cr(ready, chantier):
    chantier("report", "CR-101", "pr-opened", "https://github.com/acme/demo/pull/3")
    chantier("report", "CR-101", "ci-red", "lint")
    chantier("report", "CR-101", "round-done", "--note", "r1 APPROVE")
    row = chantier("status", "--notes")[1][1]
    assert row == "CR-101 queued r1 https://github.com/acme/demo/pull/3 ci red | round-done: r1 APPROVE"


def test_heartbeat(ready, chantier):
    chantier("foreman", "set", "local_x")
    chantier("order", "pause")
    code, out, _ = chantier("heartbeat", "--epoch", 1)
    assert out[0] == "heartbeat b1: 0 live, 1 orders pending"
    assert "heartbeat 0 min" in chantier("status")[1][0]


def _assistant(mid, model, inp=0, w5=0, w1=0, read=0, out=0):
    return json.dumps({"type": "assistant", "message": {
        "id": mid, "model": model, "usage": {
            "input_tokens": inp, "cache_read_input_tokens": read, "output_tokens": out,
            "cache_creation": {"ephemeral_5m_input_tokens": w5,
                               "ephemeral_1h_input_tokens": w1}}}})


@pytest.mark.parametrize("model,tokens,usd", [
    ("claude-opus-5-5", dict(out=1_000_000), 20.0),
    ("claude-sonnet-5-5", dict(w1=1_000_000), 4.0),
    ("claude-haiku-5-5", dict(read=50_000, out=1_000), 0.0005 + 0.0005),
    ("claude-haiku-5-5", dict(read=200_000), 0.01),  # above 100k: 0.05 $/MTok
])
def test_pricing(tmp_path, model, tokens, usd):
    f = tmp_path / "t.jsonl"
    f.write_text(_assistant("m1", model, **tokens) + "\n" + _assistant("m1", model, **tokens))
    assert costs.usage(f)["usd"] == pytest.approx(usd)
    assert costs.usage(f)["calls"] == 1  # a message id is counted once


def test_cost_by_role_and_cr(ready, chantier, tmp_path):
    chantier("foreman", "set", "local_x")
    chantier("foreman", "transcript", "uuid-1", "--epoch", 1)
    chantier("event", "start")
    chantier("agents", "set", "CR-101", "a1")
    main = costs.transcript_path(ready.resolve(), "uuid-1")
    sub = main.with_suffix("") / "subagents"
    sub.mkdir(parents=True)
    main.write_text(_assistant("f1", "claude-sonnet-5-5", out=100_000) + "\n")
    (sub / "agent-a1.jsonl").write_text(_assistant("d1", "claude-sonnet-5-5", out=50_000) + "\n")
    (sub / "agent-a1.meta.json").write_text(json.dumps({"agentType": "cr-driver"}))
    (sub / "agent-c9.jsonl").write_text(_assistant("c1", "claude-sonnet-5-5", out=10_000) + "\n")
    (sub / "agent-c9.meta.json").write_text(json.dumps({"agentType": "coder"}))
    code, out, _ = chantier("cost", "--update")
    assert out[0] == "b1: $1.600 over 3 model calls"
    assert out[1:] == ["foreman: $1.000 (1 calls)", "cr-driver: $0.500 (1 calls)",
                       "coder: $0.100 (1 calls)"]
    assert chantier("cost", "--by", "cr")[1][1:] == ["foreman: $1.000 (1 calls)",
                                                "CR-101: $0.500 (1 calls)",
                                                "other: $0.100 (1 calls)"]
    assert "spent $1.60" in chantier("status")[1][0]


def test_cost_without_transcript_is_explained(ready, chantier):
    code, _, err = chantier("cost")
    assert code == 2 and "chantier foreman transcript" in err


def test_second_foreman_cannot_claim_the_epoch(ready, chantier):
    chantier("foreman", "set", "chat-1")
    assert chantier("foreman", "transcript", "uuid-1", "--epoch", 1)[0] == 0
    assert chantier("foreman", "transcript", "uuid-1", "--epoch", 1)[0] == 0  # the same Foreman again
    code, _, err = chantier("foreman", "transcript", "uuid-2", "--epoch", 1)
    assert code == 3 and "already run by transcript uuid-1" in err
    chantier("foreman", "set", "chat-2")
    assert chantier("foreman", "transcript", "uuid-2", "--epoch", 2)[0] == 0


# ---- Copilot: copilot-session-usage --------------------------------------------------------

def _fake_session_usage(tmp_path, monkeypatch, records=(), stderr="", code=0):
    """A fake `copilot-session-usage` that checks its argv and prints `records` as JSONL."""
    out = tmp_path / "csu-out.jsonl"
    out.write_text("".join(json.dumps(r) + "\n" for r in records))
    fake = tmp_path / "fake_csu.py"
    fake.write_text(
        "import sys\n"
        "a = sys.argv[1:]\n"
        "assert a[:2] == ['--agent', 'cli'] and a[2] == '--session-root', a\n"
        "assert a[4:6] == ['calls', '--name'] and a[6] == '^uuid\\\\-c$', a\n"
        f"sys.stdout.write(open({str(out)!r}).read())\n"
        f"sys.stderr.write({stderr!r})\n"
        f"sys.exit({code})\n")
    monkeypatch.setenv("CHANTIER_SESSION_USAGE", f"{sys.executable} {fake}")


def _call(agent_id, usd, source="billed", agent=None):
    return {"session_id": "uuid-c", "model": "gpt-5.6-luna", "llm_calls": 1,
            "estimated_usd": usd, "cost_source": source, "agent": agent, "agent_id": agent_id}


def _copilot_batch(ready, chantier, tmp_path, monkeypatch):
    monkeypatch.setenv("CHANTIER_HOST", "copilot")
    chantier("foreman", "set", "local_x")
    chantier("foreman", "transcript", "uuid-c", "--epoch", 1)
    chantier("event", "start")
    chantier("agents", "set", "CR-101", "a1")
    events = tmp_path / "copilot-home" / "session-state" / "uuid-c" / "events.jsonl"
    events.parent.mkdir(parents=True)
    events.write_text("".join(json.dumps(
        {"type": "subagent.started", "agentId": aid,
         "data": {"agentType": role, "agentDisplayName": name}}) + "\n"
        for aid, role, name in (("a1", "cr-driver", "driver"), ("c9", "coder", "CR-102 coder"),
                                ("x7", "coder", "coder"))))


def test_copilot_cost_uses_session_usage_records(ready, chantier, tmp_path, monkeypatch):
    _copilot_batch(ready, chantier, tmp_path, monkeypatch)
    _fake_session_usage(tmp_path, monkeypatch, [
        _call(None, 1.0), _call("a1", 0.5), _call("c9", 0.25), _call("x7", 0.125)])
    code, out, _ = chantier("cost", "--update")
    assert code == 0
    assert out == ["b1: $1.875 over 4 model calls", "foreman: $1.000 (1 calls)",
                   "cr-driver: $0.500 (1 calls)", "coder: $0.375 (2 calls)"]
    assert chantier("cost", "--by", "cr")[1][1:] == [
        "foreman: $1.000 (1 calls)", "CR-101: $0.500 (1 calls)", "CR-102: $0.250 (1 calls)",
        "other: $0.125 (1 calls)"]
    assert "spent $1.88" in chantier("status")[1][0]


def test_copilot_cost_says_when_calls_are_estimated(ready, chantier, tmp_path, monkeypatch):
    _copilot_batch(ready, chantier, tmp_path, monkeypatch)
    _fake_session_usage(tmp_path, monkeypatch, [_call(None, 1.0), _call("a1", 0.5, "estimated")])
    assert chantier("cost")[1][0] == "b1: $1.500 over 2 model calls (1 estimated, not billed)"


def test_session_usage_runs_through_uv_with_inline_metadata(monkeypatch):
    from chantier import costs
    seen = {}
    monkeypatch.delenv("CHANTIER_SESSION_USAGE", raising=False)
    monkeypatch.setattr(costs.subprocess, "run", lambda argv, **kw: seen.setdefault("argv", argv)
                        and type("P", (), {"returncode": 0, "stdout": json.dumps(
                            _call(None, 1.0)) + "\n", "stderr": ""})())
    monkeypatch.setattr(costs, "_copilot_agents", lambda session: {})
    costs.copilot_session_costs("uuid-c")
    assert seen["argv"][:3] == ["uv", "run", "--script"]
    assert seen["argv"][3].endswith("scripts/cli/session_usage.py")
    assert "# dependencies = [\"copilot-session-usage>=1\"]" in Path(seen["argv"][3]).read_text()


@pytest.mark.parametrize("setup, message", [
    (lambda tmp, mp: mp.setenv("CHANTIER_SESSION_USAGE", str(tmp / "nowhere")), "not found"),
    (lambda tmp, mp: _fake_session_usage(tmp, mp, stderr="boom", code=1), "failed (1): boom"),
    (lambda tmp, mp: _fake_session_usage(tmp, mp), "no priced call"),
    (lambda tmp, mp: _fake_session_usage(tmp, mp, [_call(None, None)]), "has no price"),
])
def test_copilot_cost_fails_instead_of_guessing(ready, chantier, tmp_path, monkeypatch, setup,
                                                message):
    _copilot_batch(ready, chantier, tmp_path, monkeypatch)
    setup(tmp_path, monkeypatch)
    code, out, err = chantier("cost")
    assert code != 0 and message in err and not out


def test_copilot_cost_without_transcript_names_the_copilot_variable(ready, chantier, monkeypatch):
    monkeypatch.setenv("CHANTIER_HOST", "copilot")
    code, _, err = chantier("cost")
    assert code == 2 and "$COPILOT_AGENT_SESSION_ID" in err
