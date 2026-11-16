"""The Copilot model catalog: the identifier rule, the copy's drift and the admission rules."""

import json
from pathlib import Path

import pytest

from chantier.playbook import copilot_catalog as cc

SHA_LENGTH = 40
TABLES = {
    cc.CLIENTS: "- name: GPT Kept\n  cli: true\n- name: GPT Off\n  cli: false\n",
    cc.AUTO: "- name: GPT Sol Two\n  cli: false\n  app: true\n",
    cc.STATUS: "- name: 'GPT KEPT[^x]'\n  release_status: 'GA'\n",
    cc.PLANS: "- name: GPT Sol Two\n  pro: false\n  pro_plus: true\n",
    cc.CLI_REFERENCE: "## Supported models\n\n| Model | x |\n|---|---|\n| `gpt-kept` | a |\n",
}


def tables(tmp_path: Path, **change: str) -> Path:
    for name, text in {**TABLES, **change}.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    return tmp_path


def ids(tmp_path: Path, **change: str) -> dict[str, dict[str, object]]:
    return {m["id"]: m for m in cc.build(tables(tmp_path, **change))["models"]}


@pytest.mark.parametrize(
    ("name", "ident", "shown"),
    [
        ("GPT-6.1 Terra", "gpt-6.1-terra", "GPT-6.1 Terra"),
        ("Claude Sonnet 5[^promo]", "claude-sonnet-5", "Claude Sonnet 5"),
        ("GPT-5.3-Codex", "gpt-5.3-codex", "GPT-5.3-Codex"),
        (
            "Claude Opus 4.8 (fast mode) (preview)",
            "claude-opus-4.8-(fast-mode)",
            "Claude Opus 4.8 (fast mode)",
        ),
        ("Claude Sonnet 5.5", "claude-sonnet-5.5", "Claude Sonnet 5.5"),
    ],
)
def test_the_identifier_and_the_display_name_follow_the_one_rule(
    name: str, ident: str, shown: str
) -> None:
    assert cc.identifier(name) == ident and cc.display_name(name) == shown


def test_the_committed_catalog_is_what_the_committed_tables_build() -> None:
    source = json.loads((cc.TABLES / "SOURCE.json").read_text(encoding="utf-8"))
    built = cc.dump(cc.document(source))
    assert cc.CATALOG_FILE.read_bytes().decode("utf-8") == built
    assert len(source["commit"]) == SHA_LENGTH and "\r" not in built


def test_the_admission_rules_and_their_difference_lines(tmp_path: Path) -> None:
    built = cc.build(tables(tmp_path))
    found = {m["id"]: m for m in built["models"]}
    assert set(found) == {"gpt-kept", "gpt-sol-two"}  # Sol: app only; Off: cli false, not listed
    assert found["gpt-sol-two"]["plans"]["pro"] is False and found["gpt-sol-two"]["app"] is True
    assert found["gpt-kept"]["name"] == "GPT KEPT"  # the status table's cleaned name
    assert found["gpt-kept"]["in_cli_reference"] is True
    assert (
        "gpt-sol-two: in the tables, not in the CLI reference's Supported models"
        in (built["differences"])
    )
    assert any(
        ln.startswith("gpt-sol-two: absent from model-supported-clients.yml")
        for ln in built["differences"]
    )


def test_a_reference_identifier_no_table_names_is_in_by_its_identifier(tmp_path: Path) -> None:
    only = TABLES[cc.CLI_REFERENCE] + "| `mystery-1` | a |\n"
    built = cc.build(tables(tmp_path, **{cc.CLI_REFERENCE: only}))
    found = {m["id"]: m for m in built["models"]}
    assert found["mystery-1"]["name"] == "mystery-1" and found["mystery-1"]["plans"] is None
    assert "mystery-1: in the CLI reference, named by no table" in built["differences"]


def test_a_name_two_tables_write_differently_is_one_model_and_a_twin_pair_is_named(
    tmp_path: Path,
) -> None:
    clients = "- name: A B (fast mode)\n  cli: true\n- name: A B fast mode\n  cli: true\n"
    first = {m["id"]: m for m in cc.build(tables(tmp_path, **{cc.CLIENTS: clients}))["models"]}
    assert "a-b-(fast-mode)" in first and "a-b-fast-mode" in first
    lines = cc.build(tmp_path)["differences"]
    assert any("a-b-(fast-mode) and a-b-fast-mode: share the normalise key" in ln for ln in lines)
    status = TABLES[cc.STATUS] + "- name: GPT SOL TWO\n  release_status: 'GA'\n"
    same = ids(tmp_path, **{cc.STATUS: status})  # the same identifier: one model
    assert len(same) == len(ids(tmp_path)) and same["gpt-sol-two"]["name"] == "GPT SOL TWO"


def test_the_agent_files_are_compared_with_the_catalog_and_never_written_to_it(
    tmp_path: Path,
) -> None:
    built = cc.build(tables(tmp_path))
    agents = tmp_path / "com.github.copilot" / "agents"
    agents.mkdir(parents=True)
    (agents / "a.agent.md").write_text("---\nmodel: [GPT KEPT, gpt-kept]\n---\n", encoding="utf-8")
    (agents / "b.agent.md").write_text("---\nmodel: [GPT Old, gpt-old]\n---\n", encoding="utf-8")
    (agents / "c.agent.md").write_text("---\nmodel: [Wrong, gpt-sol-two]\n---\n", encoding="utf-8")
    lines = cc.agent_file_differences(built["models"], agents)
    assert [ln.split(":")[0] for ln in lines] == ["gpt-old", "gpt-sol-two"]
    assert (
        "gpt-old: named by com.github.copilot/agents/b.agent.md, not listed by GitHub" in lines[0]
    )
    assert "gpt-sol-two" in lines[1] and "'Wrong'" in lines[1]
    assert "gpt-old" not in cc.dump(cc.document({}, tmp_path))
