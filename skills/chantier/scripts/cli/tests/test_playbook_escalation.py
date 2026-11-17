"""The `escalation` key of a role: set, defaulted, printed, recorded and refused."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from batch_helpers import FROM_AGENTS_MD, host, open_batch, prepared, record, write_record
from conftest import PLUGIN_ROOT, Chantier
from test_playbook_config import (
    COPILOT_HEAD,
    ESCALATE,
    HEAD,
    OPUS_COPILOT,
    REFUSAL,
    A,
    team,
)

from chantier.core.errors import EXIT_PRECONDITION
from chantier.playbook import escalation
from chantier.playbook.lines import escalate_line

SONNET = "sonnet (claude-sonnet-5-5, Claude Sonnet 5.5)"


def test_an_escalation_is_set_per_role_and_a_plain_default_takes_it_back(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    yaml = repo / "chantier.yaml"
    yaml.write_text(HEAD + A + "escalation: sonnet\n", encoding="utf-8")
    _, out, _ = chantier("playbook")
    assert f"coder: agent=chantier:coder model=(its file's) escalation={SONNET} [repository]" in out
    assert out[-1] == ESCALATE.replace(
        "coder opus (claude-opus-5-5, Claude Opus 5.5)", f"coder {SONNET}"
    )
    yaml.write_text(HEAD + A + "escalation: default\n", encoding="utf-8")
    _, out, _ = chantier("playbook")
    assert out[-1] == ESCALATE and not any("[repository]" in ln for ln in out)
    opus = "opus (claude-opus-5-5, Claude Opus 5.5)"
    assert f"coder: agent=chantier:coder model=(its file's) escalation={opus}" in out
    assert team(out) == []


def test_a_user_escalation_is_on_the_team_line_and_the_recorded_map_is_kept(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    yaml = repo / "chantier.yaml"
    yaml.write_text(HEAD + A + "escalation: sonnet\n", encoding="utf-8")
    ids = open_batch(repo, chantier, monkeypatch, "Escalation one", "Escalation two")
    held = record(repo)["escalation"]
    assert held["coder"] == {
        "id": "claude-sonnet-5-5",
        "name": "Claude Sonnet 5.5",
        "start": "sonnet",
        "mode": "named",
        "layer": "repository",
    }
    assert held["debugger"]["id"] == "claude-opus-5-5" and "layer" not in held["debugger"]
    _, took, _ = chantier("take", ids[0], "--epoch", 1)
    assert team(took) == [f"team: coder escalation={SONNET} [repository]"]
    yaml.write_text(HEAD + A + "escalation: haiku\n", encoding="utf-8")  # the batch keeps its map
    _, out, _ = chantier("playbook", "--batch", record(repo)["id"])
    assert out[-1].startswith(f"escalate: coder {SONNET}; conflict-resolver opus")
    assert chantier("playbook")[1][-1].startswith("escalate: coder haiku")
    data = record(repo)
    del data["escalation"]  # a record from before the setting: the shipped defaults'
    write_record(repo, data)
    assert chantier("playbook", "--batch", record(repo)["id"])[1][-1] == ESCALATE


def test_open_records_the_shipped_escalation_with_no_user_file(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    open_batch(repo, chantier, monkeypatch, "Escalation default")
    held = record(repo)["escalation"]
    assert sorted(held) == ["coder", "conflict-resolver", "debugger"]
    assert all(e["id"] == "claude-opus-5-5" and e["mode"] == "named" for e in held.values())
    assert "playbook" not in record(repo)


def test_escalation_lines_with_no_role_that_has_one() -> None:
    assert escalate_line({}) == "escalate: (none on this host)"
    assert escalation.escalation_map(None, None, "claude") == {}


def test_on_copilot_an_escalation_starts_generic_unless_the_role_has_the_users_agent(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch, "copilot")
    yaml = repo / "chantier.yaml"
    yaml.write_text(COPILOT_HEAD + A + "escalation: gpt-6.1-sol\n", encoding="utf-8")
    code, out, err = chantier("playbook", "--host", "copilot")
    sol = "gpt-6.1-sol (gpt-6.1-sol, GPT-6.1 Sol) (generic)"
    assert code == 0, err
    assert f"escalation={sol} [repository]" in next(ln for ln in out if ln.startswith("coder: "))
    assert out[-1].startswith(f"escalate: coder {sol}; conflict-resolver {OPUS_COPILOT}")
    yaml.write_text(COPILOT_HEAD + A + "agent: mine\n", encoding="utf-8")  # the shipped one is off
    code, out, err = chantier("playbook", "--host", "copilot")
    assert code == 0, err
    assert "coder: agent=mine [repository] model=(its file's)" in out
    assert out[-1] == "escalate: " + "; ".join(
        f"{role} {OPUS_COPILOT}" for role in ("conflict-resolver", "debugger")
    )
    yaml.write_text(
        COPILOT_HEAD + A + "agent: mine\n" + A + "escalation: gpt-6.1-sol\n", encoding="utf-8"
    )
    code, out, err = chantier("playbook", "--host", "copilot")
    refusal = REFUSAL.replace('remove "model"', 'remove "escalation"')
    assert code == EXIT_PRECONDITION and any(
        ln.startswith("chantier.yaml:6:") and refusal in ln for ln in out + err.splitlines()
    )


def test_defaults_that_carry_no_escalation_print_none_on_this_host(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plugin = tmp_path / "plugin"
    shutil.copytree(PLUGIN_ROOT / "agents", plugin / "agents")
    shutil.copytree(PLUGIN_ROOT / "com.github.copilot", plugin / "com.github.copilot")
    (plugin / "config").mkdir()
    lines = (PLUGIN_ROOT / "config" / "chantier.defaults.yml").read_text(encoding="utf-8")
    kept = [ln for ln in lines.splitlines() if not ln.lstrip().startswith("escalation:")]
    (plugin / "config" / "chantier.defaults.yml").write_text("\n".join(kept), encoding="utf-8")
    monkeypatch.setenv("CHANTIER_PLUGIN_ROOT", str(plugin))
    host(monkeypatch)
    code, out, err = chantier("playbook")
    assert code == 0, err
    assert out[-1] == "escalate: (none on this host)"


@pytest.mark.parametrize("user", ["", A + "escalation: gpt-6.1-sol\n"], ids=["shipped", "user"])
def test_a_generic_escalation_prints_the_contract_with_or_without_a_user_file(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, user: str
) -> None:
    host(monkeypatch, "copilot")
    if user:
        (repo / "chantier.yaml").write_text(COPILOT_HEAD + user, encoding="utf-8")
    code, _, err = chantier("open", str(prepared(repo, chantier, "Esc coder")), *FROM_AGENTS_MD)
    assert code == 0, err
    assert record(repo)["escalation"]["coder"]["mode"] == "generic"
    assert ("playbook" in record(repo)) == bool(user)
    monkeypatch.setenv("CHANTIER_BATCH", record(repo)["id"])
    assert chantier("foreman", "set", "local_foreman_t", "--epoch", 1)[0] == 0
    crid = record(repo)["crs"][0]["id"]
    heading = (
        "coder contract (a generic agent: copy it unchanged, without the two leading spaces, "
        "after the opening lines):"
    )
    for args, want in (
        (("take", crid, "--epoch", 1), [heading, f"  {heading}"]),  # the Driver's copy, once
        (("round", crid), [heading]),
        (("handoff", crid), [heading]),
    ):
        code, out, err = chantier(*args)
        assert code == 0, err
        assert [ln for ln in out if "coder contract (a generic" in ln] == want, args
