"""Units of the CLI: the spelling of a CR, a gate and a verdict at a head, the cost breakdown and
the sandbox checks.
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from conftest import PLUGIN_ROOT, load_script

from chantier.commands.cost.breakdown import breakdown, cost_kind, cost_label
from chantier.commands.cost.sessions import OWN_CHIEF
from chantier.commands.crs import gate_passed, last_verdict
from chantier.core.ids import normalize_cr
from chantier.core.records import EventRecord

FULL_ROWS = 13


def test_a_cr_has_one_spelling_and_a_passed_gate_and_a_verdict_are_read_at_a_head() -> None:
    assert [normalize_cr(x) for x in ("165", "CR-165", "cr-165", "stack", "O-2", "-")] == [
        "CR-165",
        "CR-165",
        "CR-165",
        "stack",
        "O-2",
        "-",
    ]

    def g(result: str, run: str, head: str = "abc1234") -> EventRecord:
        return EventRecord(t="t", actor="driver", kind="gate", result=result, head=head, run=run)

    assert gate_passed([g("pass", "1"), g("pass", "1")], "abc1234")
    assert not gate_passed([g("pass", "1"), g("fail", "1")], "abc1234")  # the second command failed
    assert not gate_passed(
        [g("fail", "1"), g("pass", "2"), g("fail", "3")], "abc1234"
    )  # the last run
    assert gate_passed([g("fail", "1"), g("pass", "2")], "abc1234")
    assert not gate_passed([g("pass", "1")], "other")

    def v(result: str, head: str = "abc1234") -> EventRecord:
        return EventRecord(t="t", actor="driver", kind="verdict", result=result, head=head)

    assert last_verdict([v("VERIFIED"), v("NOT VERIFIED")], "abc1234") == "NOT VERIFIED"
    assert last_verdict([v("NOT VERIFIED"), v("VERIFIED")], "abc1234") == "VERIFIED"
    assert last_verdict([v("VERIFIED", "old")], "abc1234") is None


def test_cost_puts_the_steering_sessions_own_subagents_on_their_own_line_and_qa_on_a_driver() -> (
    None
):
    def row(agent: str, parent: str | None, **more: Any) -> dict[str, Any]:
        return {
            "agent": agent,
            "type": "Explore",
            "parent": parent,
            "calls": 1,
            "usd": 1.0,
            **more,
        }

    assert cost_kind(row("a", None)) == "Driver"  # tied to a CR, the stack or a QA order by the log
    own = row("b", None, own=OWN_CHIEF)  # `_cost_rows` marks the others
    assert (cost_kind(own), cost_label(own)) == ("Foreman", OWN_CHIEF)
    labels = [e["label"] for e in breakdown([row("a", None), own, row("c", "a")])]
    assert labels == [OWN_CHIEF, "Driver Explore", "Worker Explore"]


def test_the_eval_sandbox_builds_its_recorded_base() -> None:
    script = PLUGIN_ROOT / "evals" / "kit" / "sandbox.py"
    done = subprocess.run(
        [sys.executable, str(script), "build"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    found = re.search(r"^base ([0-9a-f]+)$", done.stdout, re.MULTILINE)
    assert found, done.stdout + done.stderr
    built = found.group(1)
    recorded = json.loads(
        (PLUGIN_ROOT / "evals" / "kit" / "sandbox.json").read_text(encoding="utf-8")
    )["base"]
    assert built == recorded
    assert re.fullmatch(r"[0-9a-f]{40}", recorded)


def test_the_sandbox_campaigns_name_only_frozen_crs_with_hidden_tests() -> None:
    kit = Path(__file__).resolve().parents[5] / "evals" / "kit"
    if not (kit / "setup.py").is_file():
        pytest.skip("the eval kit is not part of this install")
    setup = load_script("eval_setup", kit / "setup.py")
    sandbox = {name: c for name, c in setup.CAMPAIGNS.items() if "batches" in c}
    assert set(sandbox) == {"full", "real-foreman", "real-direct", "copilot"}
    for name, campaign in sandbox.items():
        for slug in setup.sandbox_crs(campaign):
            folder = kit / "sandbox-crs" / slug
            for part in ("intake/request.md", "01-intent.md", "02-answers.md", "03-change-spec.md"):
                assert (folder / part).is_file(), f"{name}: {slug} lacks {part}"
            if not slug.startswith("release-"):
                assert list((kit / "sandbox-judge" / slug).glob("test_judge_*.py")), (
                    f"{name}: {slug} has no hidden test"
                )
            else:  # a release bumps the version: its lock moves with it (the judge checks it)
                spec_text = (folder / "03-change-spec.md").read_text(encoding="utf-8")
                files = spec_text.split("## Files", 1)[-1].split("\n## ", 1)[0]
                assert "uv.lock" in files, f"{name}: {slug} does not name uv.lock in its Files"
    assert not list((kit / "sandbox-crs").rglob("test_*.py")), "a hidden test sits in a frozen CR"
    full = setup.sandbox_crs(sandbox["full"])
    assert len(full) == FULL_ROWS
    for quick in ("real-foreman", "real-direct"):
        assert setup.sandbox_crs(sandbox[quick]) == setup.QUICK and set(setup.QUICK) <= set(full)
