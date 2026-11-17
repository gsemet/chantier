"""`cost` on Copilot: usage from the session-usage command, attributed by agent, and refusals."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from batch_helpers import FROM_AGENTS_MD, host, open_batch, prepared, record, write_record
from conftest import PLUGIN_ROOT, Chantier

from chantier.core.errors import EXIT_EXTERNAL, EXIT_PRECONDITION
from chantier.costs import copilot as costs

FAKE_USAGE = PLUGIN_ROOT / "scenario" / "fake_session_usage.py"
NOT_MEASURED = "unknown: not measured on this host"
CHIEF = [
    f"Chief of Staff, steering the batch (outside the budget): {NOT_MEASURED}",
    f"Chief of Staff, grill and specifications with the user (outside the budget): {NOT_MEASURED}",
    f"Chief of Staff, whole session: {NOT_MEASURED}; compactions: not measured on this host",
]


def command(*argv: str) -> str:
    return subprocess.list2cmdline(argv) if sys.platform == "win32" else shlex.join(argv)


def call(
    agent: str | None, usd: float | None, source: str = "billed", role: str | None = None
) -> dict[str, Any]:
    return {
        "agent_id": agent,
        "agent": role,
        "model": "gpt-5.6-luna",
        "llm_calls": 1,
        "estimated_usd": usd,
        "cost_source": source,
    }


class Usage:
    """A Copilot home with a session's events and a records file the fake usage command prints."""

    def __init__(self, tmp: Path, ids: list[str]) -> None:
        self.home = tmp / "copilot-home"
        self.records = tmp / "copilot-usage.jsonl"
        self.assigned, self.named = ids
        events = self.home / "session-state" / "uuid-foreman" / "events.jsonl"
        events.parent.mkdir(parents=True)
        agents = [
            ("agent-a", "cr-driver", "driver"),
            ("cost-coder", "coder", f"{self.named} coder"),
        ]
        events.write_text(
            "".join(
                json.dumps(
                    {
                        "type": "subagent.started",
                        "agentId": a,
                        "data": {"agentType": r, "agentDisplayName": n},
                    }
                )
                + "\n"
                for a, r, n in agents
            ),
            encoding="utf-8",
        )
        self.write(
            [
                call(None, 1.0),
                call("agent-a", 0.5),
                call("cost-coder", 0.25, "estimated"),
                call("unmapped", 0.125, role="coder"),
            ]
        )

    def write(self, calls: list[dict[str, Any]]) -> None:
        self.records.write_text("".join(json.dumps(c) + "\n" for c in calls), encoding="utf-8")

    def env(self, **more: str) -> dict[str, str]:
        env = {
            "COPILOT_HOME": str(self.home),
            "CHANTIER_SESSION_USAGE": command(sys.executable, str(FAKE_USAGE)),
            "FAKE_USAGE_RECORDS": str(self.records),
            "FAKE_USAGE_SESSION": "uuid-foreman",
            "FAKE_USAGE_EXIT": "0",
            "FAKE_USAGE_ERROR": " ",  # an empty value is no value on Windows
            "UV_INDEX": "https://example.invalid/simple",
            "FAKE_EXPECT_UV_INDEX": "https://example.invalid/simple",
        }
        return {**env, **more}


@pytest.fixture
def usage(repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Usage:
    ids = open_batch(repo, chantier, monkeypatch, "Copilot one", "Copilot two")
    assert chantier("take", ids[0], "--epoch", 1)[0] == 0
    assert chantier("agents", "set", ids[0], "agent-a", "--epoch", 1)[0] == 0
    chantier("foreman", "transcript", "uuid-foreman", "--epoch", 1)
    write_record(repo, {**record(repo), "host": "copilot"})  # it ran on Claude: say Copilot here
    found = Usage(tmp_path, ids)
    for name, value in found.env().items():
        monkeypatch.setenv(name, value)
    return found


def test_copilot_cost_lists_the_foreman_then_each_agent_type_and_attributes_by_cr(
    usage: Usage, chantier: Chantier
) -> None:
    code, out, _ = chantier("cost", "--batch", "batch-01")
    assert code == 0 and out == [
        "batch-01: $1.875 over 4 model calls (1 estimated, not billed)",
        "Foreman: $1.000 (1 calls, 53%)",
        "Agent cr-driver: $0.500 (1 calls, 27%)",
        "Agent coder: $0.375 (2 calls, 20%)",
        "Orchestration (steering + Drivers): not measured (no parent link on this host)",
        *CHIEF,
    ]
    assert "$0.00" not in "\n".join(out[-3:])
    code, out, _ = chantier("cost", "--explain", "--batch", "batch-01")
    assert out[2].count("not measured") == 1 and "restarts: not measured" in out[4]
    assert out[-2:] == [
        "Cache expiry: not measured on this host",
        "Not counted: compaction calls are not measured on this host",
    ]
    code, out, _ = chantier("cost", "--batch", "batch-01", "--by", "cr")
    assert out[1:] == [
        "foreman: $1.000 (1 calls)",
        f"{usage.assigned}: $0.500 (1 calls)",
        f"{usage.named}: $0.250 (1 calls)",
        "other: $0.125 (1 calls)",
        *CHIEF,
    ]


REFUSALS: list[tuple[str, Any, dict[str, str], int, str]] = [
    ("empty usage", [], {}, EXIT_EXTERNAL, "no priced call"),
    (
        "a failed usage command",
        None,
        {"FAKE_USAGE_EXIT": "1", "FAKE_USAGE_ERROR": "boom"},
        EXIT_EXTERNAL,
        "failed (1): boom",
    ),
    ("a call without a price", [call(None, None)], {}, EXIT_EXTERNAL, "has no price"),
    ("unreadable records", "not JSON\n", {}, EXIT_EXTERNAL, "unreadable record"),
    (
        "a missing command",
        None,
        {"CHANTIER_SESSION_USAGE": "MISSING"},
        EXIT_PRECONDITION,
        "not found",
    ),
]


def test_copilot_cost_refuses_what_it_cannot_read(
    usage: Usage, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    good = usage.records.read_text(encoding="utf-8")
    for label, records, env, code, message in REFUSALS:
        usage.records.write_text(good, encoding="utf-8")
        if isinstance(records, str):
            usage.records.write_text(records, encoding="utf-8")
        elif records is not None:
            usage.write(records)
        with monkeypatch.context() as scoped:
            for name, value in env.items():
                missing = command(str(tmp_path / "missing-session-usage"))
                scoped.setenv(name, missing if value == "MISSING" else value)
            got, out, err = chantier("cost", "--batch", "batch-01")
        assert got == code and not out and message in err, label


def test_a_missing_copilot_transcript_names_the_session_variable(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    host(monkeypatch, "copilot")
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path / "copilot-home"))
    item = prepared(repo, chantier, "Missing transcript")
    assert chantier("open", str(item), *FROM_AGENTS_MD)[0] == 0
    code, out, err = chantier("cost", "--batch", "batch-01")
    assert code == EXIT_PRECONDITION and not out and "$COPILOT_AGENT_SESSION_ID" in err


def test_uv_runs_the_usage_script_with_no_inherited_index_but_offline_and_proxy_kept(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    indexes = (
        "UV_INDEX",
        "UV_DEFAULT_INDEX",
        "UV_INDEX_URL",
        "UV_EXTRA_INDEX_URL",
        "UV_FIND_LINKS",
    )
    env = {name: "https://example.invalid/simple" for name in indexes}
    env.update(
        {
            "CHANTIER_SESSION_USAGE": "",
            "COPILOT_HOME": str(tmp_path / "empty-copilot"),
            "UV_OFFLINE": "1",
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "SSL_CERT_FILE": str(tmp_path / "cert.pem"),
        }
    )
    payload = json.dumps({"estimated_usd": 1.0, "llm_calls": 1, "cost_source": "billed"}) + "\n"
    result = subprocess.CompletedProcess([], 0, stdout=payload, stderr="")
    with (
        mock.patch.dict("os.environ", env),
        mock.patch("shutil.which", return_value="uv"),
        mock.patch("subprocess.run", return_value=result) as run,
    ):
        costs.copilot_session_costs("uuid-foreman")
    argv, child = run.call_args.args[0], run.call_args.kwargs["env"]
    assert argv == [
        "uv", "run", "--no-config", "--script", str(costs.session_usage_script()),
        "--agent", "cli", "--session-root", str(Path(env["COPILOT_HOME"]) / "session-state"),
        "calls", "--name", r"^uuid\-foreman$",
    ]  # fmt: skip
    assert child is not None and all(name not in child for name in indexes)
    assert child.get("UV_OFFLINE") == "1" and child.get("HTTPS_PROXY") == "http://127.0.0.1:9"
    assert child.get("SSL_CERT_FILE") == env["SSL_CERT_FILE"]


def test_a_copilot_row_keeps_its_calls_and_dollars_by_model_and_has_no_models_key() -> None:
    lines = [
        {**call(None, 1.0), "model": "gpt-5.6-luna", "llm_calls": 2},
        {**call(None, 0.5), "model": "claude-opus-5-5"},
        {**call(None, 0.25), "model": None},
    ]
    (row,) = costs._rows("uuid-foreman", "\n".join(json.dumps(c) for c in lines))
    assert row["by_model"] == {
        "gpt-5.6-luna": {"calls": 2, "usd": 1.0},
        "claude-opus-5-5": {"calls": 1, "usd": 0.5},
        "?": {"calls": 1, "usd": 0.25},
    }
    assert "models" not in row
