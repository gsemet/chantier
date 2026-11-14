"""`cost` and `status` on Claude transcripts: exact pricing, the levels, the windows, the floor."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
from batch_helpers import record, write_record
from conftest import Chantier
from cost_world import (
    DRIVER_CALLS,
    FOREMAN_CALLS,
    WORKER_CALLS,
    CostWorld,
    build,
    call_usd,
    later,
    money,
    msg,
    user,
)

from chantier.core.errors import EXIT_PRECONDITION

CRS = 2
FOREMAN_USD = FOREMAN_CALLS * call_usd(300)
DRIVER_USD = DRIVER_CALLS * call_usd(900)
WORKER_USD = WORKER_CALLS * call_usd(900)
TOTAL_USD = FOREMAN_USD + CRS * (DRIVER_USD + WORKER_USD)
TOTAL_CALLS = FOREMAN_CALLS + CRS * (DRIVER_CALLS + WORKER_CALLS)
PERCENT = 100
TOLERANCE = 1e-3


def mystery(mid: str, model: str) -> str:
    usage = {"input_tokens": 1000, "output_tokens": 2000}
    return (
        json.dumps({"type": "assistant", "message": {"id": mid, "model": model, "usage": usage}})
        + "\n"
    )


MYSTERY = mystery("mys-1", "mystery-model")  # 3000 tokens at $1 a million: $0.003
FLOOR = 0.003
CHIEF_STEERING = "Chief of Staff, steering the batch (outside the budget): "
CHIEF_GRILL = "Chief of Staff, grill and specifications with the user (outside the budget): "


@pytest.fixture
def world(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> CostWorld:
    return build(repo, chantier, monkeypatch, tmp_path)


def check_the_levels_and_the_chief_of_staff_apart(world: CostWorld) -> None:
    out = world.cost("--by", "cr")
    assert out[:2] == [
        f"batch-01: ${TOTAL_USD:.3f} over {TOTAL_CALLS} model calls",
        f"foreman: ${FOREMAN_USD:.3f} ({FOREMAN_CALLS} calls)",
    ]
    each = DRIVER_USD + WORKER_USD
    assert sorted(ln.split(";")[0] for ln in out[2:-3]) == [
        f"{cr}: ${each:.3f} ({DRIVER_CALLS + WORKER_CALLS} calls" for cr in world.ids
    ]
    assert out[-3] == CHIEF_STEERING + "unknown (1 calls without a time, not placed)"
    assert out[-2] == CHIEF_GRILL + (
        "$0.00 since the batch opened (0 calls, 0 spec-writers, 0 spec critics)"
    )
    assert out[-1].startswith(
        "Chief of Staff, whole session: $9.02, context 22,010 tokens; not counted"
    )
    assert json.loads(world.state.read_text())["chief_transcript"] == "uuid-chief"


def check_status_shares_summary_and_pages(world: CostWorld) -> None:
    world.cost("--by", "cr")
    world.chantier("status", "--refresh", "--batch", world.batch)
    assert abs(json.loads(world.state.read_text())["spent_usd"] - TOTAL_USD) < TOLERANCE
    first = record(world.repo)["crs"][0]
    write_record(
        world.repo,
        {
            **record(world.repo),
            "crs": [
                {**c, "status": "merged"} if c["id"] == first["id"] else c
                for c in record(world.repo)["crs"]
            ],
        },
    )
    world.chantier("order", "merged", first["id"], "--batch", world.batch)
    world.paused()
    world.chantier("status", "--refresh", "--batch", world.batch)
    _, priced, _ = world.chantier("status", "--batch", world.batch)
    folder = world.state.parent
    assert re.search(r"spent \$\d+\.\d\d", priced[0])
    assert re.search(r"spent \$\d+\.\d\d", (folder / "STATUS.md").read_text(encoding="utf-8"))
    assert re.search(
        r"\$\d+\.\d\d of \$50", (world.repo / ".agents/changes/STATUS.md").read_text("utf-8")
    )
    out = world.cost()
    spend = [ln for ln in out if re.match(r"(Foreman|Driver|Worker|Agent)\b", ln)]
    shares = [re.search(r"\((\d+) calls, (\d+)%\)$", ln) for ln in spend]
    assert spend and all(shares) and sum(int(m[2]) for m in shares if m) == PERCENT
    steering = sum(
        int(m[2])
        for ln, m in zip(spend, shares, strict=True)
        if m and ln.startswith(("Foreman", "Driver"))
    )
    assert f"Orchestration (steering + Drivers): {steering}% of the batch's spend" in out
    assert not any("%" in ln for ln in out if ln.startswith("Chief of Staff"))
    out = world.cost("--summary")
    assert out[0] == "Total: $1.00 of a $50 budget"
    assert out[1] == "Foreman $0.39 (39%), Drivers $0.46 (46%), workers $0.15 (15%)"
    assert out[2].startswith("Most: CR-10") and out[-1].startswith("Not counted: compaction calls")
    assert out[3] == "Foreman: 10 wakes, context 22,010 tokens on average, 22,010 at its peak"
    assert "Driver cr-driver with its workers: $0.61 (32 calls)" in out
    amounts = [int(a.replace(".", "")) for a in re.findall(r"\$(\d+\.\d\d) \(", out[1])]
    assert sum(amounts) == round(money(out[0]) * PERCENT)
    assert sum(int(s) for s in re.findall(r"\((\d+)%\)", out[1])) == PERCENT
    report = (folder / "STATUS.md").read_text(encoding="utf-8")
    each = DRIVER_USD + WORKER_USD
    assert f"| ${each:.2f} |" in report and "## Cost" in report and "Total: $1.00" in report
    page = (world.repo / ".agents/changes" / first["path"] / "STATUS.md").read_text("utf-8")
    assert f"${each:.2f} so far" in page and "(../../STATUS.md)" in page and "- [x] Merged" in page


def check_a_call_after_the_pause_and_a_relay(world: CostWorld) -> None:
    world.paused()
    original = world.main.read_text()
    world.main.write_text(original + msg("later", 900_000, timestamp="2999-01-01T00:00:00.000Z"))
    first = world.cost()[0]  # `pause` ends no window; the `<synthetic>` record costs nothing
    assert first.startswith("batch-01: $10.") and f"over {TOTAL_CALLS + 1} model calls" in first
    world.main.write_text(original)
    world.main.with_name("uuid-foreman-2.jsonl").write_text(msg("r1", 300) + msg("r2", 300))
    data = json.loads(world.state.read_text())
    both = {**data, "foreman_transcripts": ["uuid-foreman", "uuid-foreman-2"]}
    world.state.write_text(json.dumps(both))
    relay = world.cost()[0]
    world.state.write_text(json.dumps(data))
    world.state.write_text(json.dumps(data))
    assert (
        relay
        == f"batch-01: ${TOTAL_USD + 2 * call_usd(300):.3f} over {TOTAL_CALLS + 2} model calls"
    )


def check_each_agent_type_has_its_line(
    world: CostWorld,
) -> None:
    events = world.state.parent / "events.jsonl"
    when = [later(world, 0), later(world, 120)]  # two hours apart: the 1-hour cache has expired
    agent = {"t": when[0], "actor": "foreman", "kind": "agent"}
    events.write_text(
        events.read_text(encoding="utf-8")
        + json.dumps({**agent, "cr": world.ids[0], "agent": "odd"})
        + "\n"  # a Driver after another
        + json.dumps({**agent, "cr": "O-1", "agent": "lone"})
        + "\n",  # a QA Driver
        encoding="utf-8",
    )
    odd: Any = {str(i): {"timestamp": when[i]} for i in range(2)}
    world.agent("odd", "my-own-driver", 2, **odd)
    world.agent("odd-worker", "coder", 1, parent="odd")
    world.agent("lone", "qa-driver", 3)
    out = world.cost()
    lines = [ln for ln in out[1:] if ln.startswith(("Foreman", "Driver", "Worker", "Agent"))]
    assert [ln.split(":")[0] for ln in lines] == [
        "Foreman",
        "Driver cr-driver",
        "Driver qa-driver",
        "Driver my-own-driver",
        "Worker coder",
    ]
    assert any(ln.startswith("Driver my-own-driver: $0.038 (2 calls, ") for ln in out)
    printed = [
        int(a.replace(".", "")) for ln in lines for a in re.findall(r"\$(\d+\.\d{3}) \(", ln)
    ]
    extra = 2 + 1 + 3  # my-own-driver, its worker, the QA Driver
    assert sum(printed) == round(money(out[0]) * 1000)
    assert out[0].endswith(f"over {TOTAL_CALLS + extra} model calls")
    check_explain(world, when)


def check_explain(world: CostWorld, when: list[str]) -> None:
    explained = world.cost("--explain")
    text = "\n".join(explained)
    shares = [int(s) for s in re.findall(r"(?:reads|writes|output|input) (\d+)%", explained[2])]
    assert explained[2].startswith(
        "  1 agent, 30 calls; model claude-sonnet-5-5; cost: cache reads"
    )
    assert sum(shares) == PERCENT and "no timestamps" in explained[2]
    assert "3 agents, 24 calls" in text or "2 agents, 24 calls" in text
    assert (
        "1 of 1 timed calls after the cache expired; 1 restarted on a CR that already had one"
        in text
    )
    assert "5 min after a 5-minute cache write, 1 h after a 1-hour one" in explained[-2]
    assert (
        explained[-1]
        == "Not counted: 0 compaction calls, which leave no record (about $0.12 each, $0.00)"
    )
    boundary = json.dumps({"type": "system", "subtype": "compact_boundary", "timestamp": when[0]})
    world.main.write_text(world.main.read_text() + boundary + "\n")
    last = world.cost("--explain")[-1]
    assert last.startswith("Not counted: 1 compaction calls") and "$0.12 each, $0.12" in last
    by_cr = world.cost("--by", "cr")
    assert "foreman: $0.391 (30 calls)" in by_cr and any(
        ln.startswith("O-1: $0.057 (3 calls") for ln in by_cr
    )


def check_the_chief_lines_add_up(world: CostWorld) -> None:
    world.chantier("status", "--refresh", "--batch", world.batch)
    spent = json.loads(world.state.read_text())["spent_usd"]

    def ts(minutes: int) -> str:
        return later(world, minutes)

    answers = {"type": "tool_use", "name": "Edit", "input": {"file_path": "x/02-answers.md"}}
    writer = {
        "type": "tool_use",
        "name": "Agent",
        "input": {"subagent_type": "chantier:spec-writer"},
    }
    reads = {"type": "tool_use", "name": "Read", "input": {"file_path": "x/03-change-spec.md"}}

    def call(mid: str, minutes: int, *blocks: dict[str, Any]) -> str:
        record = json.loads(msg(mid, 1_000_000, timestamp=ts(minutes)))
        record["message"]["content"] = list(blocks)
        return json.dumps(record) + "\n"

    def wake(minutes: int) -> str:
        return user("go", timestamp=ts(minutes))

    world.chief.write_text(
        wake(1)
        + call("f-steer", 2)
        + wake(3)
        + call("f-g1", 4, answers)
        + wake(5)
        + call("f-g2", 6, writer)
        + wake(7)
        + call("f-g3", 8, reads),
        encoding="utf-8",
    )
    out = world.cost()
    steer = next(ln for ln in out if ln.startswith(CHIEF_STEERING))
    grill = next(ln for ln in out if ln.startswith("Chief of Staff, grill and"))
    whole = next(ln for ln in out if ln.startswith("Chief of Staff, whole session"))
    a, b, total = money(steer), money(grill), money(whole)
    assert "(1 calls)" in steer and "(3 calls, 0 spec-writers, 0 spec critics)" in grill
    assert abs(a + b - total) <= 0.02 and abs(a * 3 - b) <= 0.02 and a > 0  # noqa: PLR2004
    assert abs(json.loads(world.state.read_text())["spent_usd"] - spent) < TOLERANCE
    check_the_specification_agents_sit_on_the_grill_line(world, out, b)


def check_the_specification_agents_sit_on_the_grill_line(
    world: CostWorld, out: list[str], b: float
) -> None:
    own = world.chief.with_suffix("") / "subagents"  # the Chief of Staff's own agents
    own.mkdir(parents=True)
    for name, kind in (("spec", "spec-writer"), ("critic", "spec-critic")):
        file = own / f"agent-{name}.jsonl"
        stamp = later(world, 9)
        file.write_text("".join(msg(f"{name}{i}", 900, timestamp=stamp) for i in range(2)))
        file.with_suffix("").with_suffix(".meta.json").write_text(json.dumps({"agentType": kind}))
    both = world.cost()
    assert both[0] == out[0] and not any("spec-" in ln for ln in both if "grill" not in ln)
    grill_now = next(ln for ln in both if ln.startswith("Chief of Staff, grill and"))
    assert "(7 calls, 1 spec-writers, 1 spec critics)" in grill_now
    assert money(grill_now) > b


def check_no_price_is_a_floor_until_chantier_yaml_prices_it(
    world: CostWorld,
) -> None:
    yaml = world.repo / "chantier.yaml"
    before = world.main.read_text()
    world.main.write_text(before + MYSTERY)
    out = world.cost()
    unpriced = (
        "mystery-model has no price: add it under prices: in chantier.yaml "
        "(exact id: mystery-model)"
    )
    assert out[0] == (
        f"batch-01: at least ${TOTAL_USD:.3f} over {TOTAL_CALLS} priced model calls; "
        "1 calls of mystery-model not priced"
    )
    shared = [ln for ln in out if re.match(r"(Foreman|Driver|Worker|Agent)\b", ln)]
    assert shared and all("share not measured" in ln for ln in shared)
    assert "Orchestration (steering + Drivers): not measured (calls not priced)" in out
    assert out.count(unpriced) == 1
    explained = world.cost("--explain")
    assert any("mystery-model (not priced)" in ln for ln in explained)
    assert any("cost of the priced calls:" in ln for ln in explained)
    summary = world.cost("--summary")
    assert summary[0].startswith("Total: at least $") and "(not measured)" in summary[1]
    _, refreshed, _ = world.chantier("status", "--refresh", "--batch", world.batch)
    assert not any("spend not updated" in ln for ln in refreshed)
    assert any(ln.startswith("spent at least $") for ln in refreshed)
    assert json.loads(world.state.read_text())["unpriced"] == {"mystery-model": 1}
    prices = "prices:\n  mystery-model:\n" + "".join(
        f"    {k}: 1\n"
        for k in ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output")
    )
    yaml.write_text(prices, encoding="utf-8")
    priced = world.cost()
    assert (
        "at least" not in "\n".join(priced) and f"over {TOTAL_CALLS + 1} model calls" in priced[0]
    )
    assert abs(money(priced[0]) - TOTAL_USD - FLOOR) <= 0.0011  # noqa: PLR2004
    dated = mystery("mys-2", "mystery-model-20270101")
    world.main.write_text(before + MYSTERY + dated)
    both = world.cost()
    assert "at least" not in "\n".join(both) and f"over {TOTAL_CALLS + 2} model calls" in both[0]
    assert (
        "prices: mystery-model (chantier.yaml, above the built-in table)"
        in world.chantier("playbook")[1]
    )
    yaml.write_text("prices:\n  mystery-model:\n    input: 1\n", encoding="utf-8")
    code, out, err = world.chantier("cost", "--batch", world.batch)
    assert code == EXIT_PRECONDITION and not out
    assert "chantier.yaml:2:" in err and "$CHANTIER playbook" in err


def test_the_levels_the_pages_the_pause_and_a_relay(world: CostWorld) -> None:
    check_the_levels_and_the_chief_of_staff_apart(world)
    check_status_shares_summary_and_pages(world)
    check_a_call_after_the_pause_and_a_relay(world)


def test_each_agent_type_has_its_line_and_explain_gives_the_cache_and_restarts(
    world: CostWorld,
) -> None:
    check_each_agent_type_has_its_line(world)


def test_the_chief_lines_and_a_model_with_no_price(world: CostWorld) -> None:
    check_the_chief_lines_add_up(world)
    check_no_price_is_a_floor_until_chantier_yaml_prices_it(world)


def test_a_retro_critic_of_the_foreman_is_counted_on_the_foreman_own_subagents_line(
    world: CostWorld,
) -> None:
    before = world.cost()
    world.agent("retro", "retro-critic", 2)  # no parent that a Driver owns, on no grill line
    out = world.cost()
    assert any(ln.startswith("Foreman's own subagents") and "(2 calls," in ln for ln in out)
    assert not any("grill" in ln and "retro" in ln for ln in out) and out[0] != before[0]
