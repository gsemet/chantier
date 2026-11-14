"""The optional chantier.yaml: absent, valid, kept by a running batch, and refused with its line."""

from __future__ import annotations

from pathlib import Path

import pytest
from batch_helpers import FROM_AGENTS_MD, changes, host, open_batch, prepared, record
from conftest import PLUGIN_ROOT, Chantier

from chantier.core.errors import EXIT_PRECONDITION

PROMPTERS = ("spec-critic", "spec-writer")
ESCALATE = "escalate: opus (claude-opus-5-5, Claude Opus 5.5)"
CODER = "coder: agent=chantier:coder model=(its file's)"
PRICES = "prices:\n  mystery-model:\n"
FOUR = "".join(f"    {k}: 1\n" for k in ("input", "cache_write_5m", "cache_write_1h", "cache_read"))
FIVE = FOUR + "    output: 1\n"
HEAD = "roles:\n  coder:\n"


def team(out: list[str]) -> list[str]:
    return [ln for ln in out if ln.startswith("team:")]


def ci_line(out: list[str]) -> list[str]:
    return [ln for ln in out if ln.startswith("ci: beside the long gate")]


def test_with_no_chantier_yaml_playbook_prints_the_plugin_agents(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    code, out, _ = chantier("playbook")
    assert code == 0 and out[0].startswith("playbook: no chantier.yaml") and CODER in out
    assert out[-1] == ESCALATE
    assert "stack-driver: agent=chantier:stack-driver model=(its file's)" in out
    assert "release-driver: agent=chantier:release-driver model=(its file's)" in out
    prompts = sorted(ln for ln in out if " prompt, first line: " in ln)
    assert len(prompts) == len(
        PROMPTERS
    )  # the spec-critic and the spec-writer, not the Demo explorer
    for who, line in zip(PROMPTERS, prompts, strict=True):
        assert line.startswith(f"{who} prompt, first line: chantier {who} for the Chief of Staff, ")
        assert "in the project " in line and "proj" in line and line.endswith(".")
    assert chantier("playbook", "--host", "copilot")[1][-1] == "escalate: (none on this host)"
    for role in ("stack-driver", "release-driver"):
        agent = (PLUGIN_ROOT / "agents" / f"{role}.md").read_text(encoding="utf-8")
        assert "model: claude-sonnet-5-5" in agent
    _, pre, _ = chantier("preflight")
    assert any(ln.startswith("P12 ok") and "no chantier.yaml" in ln for ln in pre)


def test_with_no_chantier_yaml_open_records_nothing_and_take_prints_no_team(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    ids = open_batch(repo, chantier, monkeypatch, "Playbook none one", "Playbook none two")
    _, took, _ = chantier("take", ids[0], "--epoch", 1)
    _, shown, _ = chantier("handoff", ids[1])
    code, out, _ = chantier("playbook", "--batch", record(repo)["id"], "--host", "copilot")
    assert "playbook" not in record(repo) and not team(took) and not team(shown)
    assert code == 0 and out[0].startswith("playbook: no chantier.yaml") and CODER in out


def test_a_valid_file_is_resolved_recorded_and_kept_by_the_running_batch(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    yaml = repo / "chantier.yaml"  # with a BOM, as a Windows editor writes it
    yaml.write_text(
        "# the team\nroles:\n  coder:\n    model: opus\n    skills: [jira]\n"
        "  cr-driver:\n    agent: my-driver  # my own\n",
        encoding="utf-8-sig",
    )
    opus = "model=opus (claude-opus-5-5, Claude Opus 5.5)"
    coder = f"coder: agent=chantier:coder {opus} skills=jira"
    code, now, _ = chantier("playbook")
    assert code == 0 and now[0] == "playbook: chantier.yaml, valid, host claude"
    assert coder in now and "cr-driver: agent=my-driver model=(its file's)" in now
    ids = open_batch(repo, chantier, monkeypatch, "Playbook set one", "Playbook set two")
    _, took, _ = chantier("take", ids[0], "--epoch", 1)
    assert record(repo)["playbook"]["roles"]["cr-driver"] == {"agent": "my-driver"}
    want = "team: coder model=opus (claude-opus-5-5, Claude Opus 5.5) skills=jira"
    assert team(took) == [want, "team: cr-driver agent=my-driver"]
    _, out, _ = chantier("playbook", "--batch", record(repo)["id"])
    assert now[-1] == ESCALATE and out[-1] == ESCALATE and "opened it" in out[0]
    kept = [ln for ln in now[1:] if " prompt, first line: " not in ln]
    assert out[1:] == kept
    yaml.write_text("roles:\n  coder:\n    agent: other-coder\n", encoding="utf-8")
    _, took, _ = chantier("take", ids[1], "--epoch", 1)  # S3: the batch keeps its opening's
    _, out, _ = chantier("playbook", "--batch", record(repo)["id"])
    assert "other-coder" not in "".join(took + out) and "agent=my-driver" in "".join(team(took))
    assert out[1:] == kept


def test_ci_beside_the_gate_is_printed_recorded_and_kept_after_the_key_is_dropped(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    yaml = repo / "chantier.yaml"
    yaml.write_text("ci:\n  beside_gate: true\nroles:\n  cr-driver:\n    agent: my-driver\n")
    code, out, _ = chantier("playbook")
    ids = open_batch(repo, chantier, monkeypatch, "Playbook ci one", "Playbook ci two")
    _, took, _ = chantier("take", ids[0], "--epoch", 1)
    _, shown, _ = chantier("handoff", ids[0])
    brief = next(changes(repo).rglob("brief.md")).read_text(encoding="utf-8")
    assert code == 0 and len(ci_line(out)) == 1
    assert record(repo)["playbook"]["ci"] == {"beside_gate": True}
    assert len(ci_line(took)) == 1 and len(ci_line(shown)) == 1
    assert "CI beside the long gate: on" in brief
    yaml.write_text("roles:\n  cr-driver:\n    agent: my-driver\n")
    _, took, _ = chantier("take", ids[1], "--epoch", 1)
    _, out, _ = chantier("playbook", "--batch", record(repo)["id"])
    assert len(ci_line(took)) == 1 and len(ci_line(out)) == 1


@pytest.mark.parametrize(
    "text",
    [
        "ci:\n  beside_gate: false\nroles:\n  cr-driver:\n    agent: my-driver\n",
        "roles:\n  cr-driver:\n    agent: my-driver\n",
    ],
    ids=["beside_gate false", "no ci key"],
)
def test_ci_is_off_by_default_and_prints_nothing(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    host(monkeypatch)
    (repo / "chantier.yaml").write_text(text)
    code, out, _ = chantier("playbook")
    ids = open_batch(repo, chantier, monkeypatch, "Playbook off one", "Playbook off two")
    _, took, _ = chantier("take", ids[0], "--epoch", 1)
    _, shown, _ = chantier("handoff", ids[1])
    brief = next(changes(repo).rglob("brief.md")).read_text(encoding="utf-8")
    assert code == 0 and not ci_line(out + took + shown)
    assert "CI beside the long gate" not in brief


REFUSALS = [
    ("an unknown role", "roles:\n  codr:\n    agent: x\n", 2, "is not one of the plugin's agents"),
    ("an unknown key", HEAD + "    colour: red\n", 3, 'unknown key "colour"'),
    ("an empty role", HEAD, 2, "is empty"),
    ("a tab", HEAD + "\tagent: x\n", 3, "a tab"),
    ("an anchor", HEAD + "    agent: &a x\n", 3, "anchors"),
    ("a duplicate key", HEAD + "    agent: x\n    agent: y\n", 4, "duplicate key"),
    ("a flow mapping", HEAD + "    agent: {a: b}\n", 3, "flow mappings"),
    ("a second document", "roles:\n  coder:\n    agent: x\n---\n", 4, "several documents"),
    ("an unknown model", HEAD + "    model: opus 5.6\n", 3, "is unknown on Claude Code; known:"),
    ("a model with no letter", HEAD + "    model: 5.5\n", 3, "name the model, not only"),
    ("a ci that is not a mapping", "ci: true\n", 1, '"ci" holds its keys'),
    ("an unknown key under ci", "ci:\n  colour: red\n", 2, 'ci: unknown key "colour"'),
    (
        "a beside_gate that is not a boolean",
        "ci:\n  beside_gate: maybe\n",
        2,
        'ci: "beside_gate" is true or false, found "maybe"',
    ),
    ("an unknown top-level key", "colour: red\n", 1, '"ci" and "long_gate"'),
    ("a price missing", PRICES + FOUR, 2, "missing output"),
    (
        "a price that is not a number",
        PRICES + FOUR + "    output: cheap\n",
        7,
        '"output" is a number',
    ),
    ("a negative price", PRICES + FOUR + "    output: -1\n", 7, '"output" is a number, not neg'),
    (
        "an unknown key under a price entry",
        PRICES + FIVE + "    colour: red\n",
        8,
        'unknown key "colour"',
    ),
    (
        "a long_context without above",
        PRICES
        + FIVE
        + "    long_context:\n"
        + "".join(
            f"      {k}: 1\n"
            for k in ("input", "cache_write_5m", "cache_write_1h", "cache_read", "output")
        ),
        8,
        "missing above",
    ),
]


def test_open_refuses_a_bad_chantier_yaml_at_its_line_and_moves_nothing(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)  # one repo for the 19 texts: each is refused, none moves the CR
    item = prepared(repo, chantier, "Playbook refused")
    for label, text, line, why in REFUSALS:
        (repo / "chantier.yaml").write_text(text, encoding="utf-8")
        code, _, err = chantier("open", str(item), *FROM_AGENTS_MD)
        assert code == EXIT_PRECONDITION and f"chantier.yaml:{line}:" in err and why in err, (
            label,
            err,
        )
        assert (item / "03-change-spec.md").is_file()
        assert not list((changes(repo) / "4-batch").glob("batch.json")), label


def test_playbook_and_preflight_name_the_problem_and_its_line(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    yaml = repo / "chantier.yaml"
    yaml.write_text(REFUSALS[0][1], encoding="utf-8")
    code, out, err = chantier("playbook")
    assert code == EXIT_PRECONDITION and any(
        ln.startswith("chantier.yaml:2:") for ln in out + err.splitlines()
    )
    code, pre, _ = chantier("preflight")
    assert code == EXIT_PRECONDITION and pre[-1].endswith("start nothing")
    assert any(ln.startswith("P12 FAIL chantier.yaml:2:") for ln in pre)
    yaml.write_text(HEAD + "    model: gpt\n", encoding="utf-8")
    code, out, err = chantier("playbook", "--host", "copilot")
    text = "".join(out) + err
    assert code == EXIT_PRECONDITION and "ambiguous" in text and "Luna" in text and "Sol" in text
    yaml.write_text(HEAD + "    model: opus\n", encoding="utf-8")
    code, out, err = chantier("playbook", "--host", "copilot")  # a host that cannot set a model
    assert code == EXIT_PRECONDITION and any(
        "cannot set a model when it starts an agent" in ln and 'hosts/copilot.md, "Models"' in ln
        for ln in out + err.splitlines()
    )


def test_with_no_chantier_yaml_again_the_next_batch_records_nothing(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    yaml = repo / "chantier.yaml"
    yaml.write_text(HEAD + "    skills: [jira]\n")
    host(monkeypatch)
    yaml.unlink()
    open_batch(repo, chantier, monkeypatch, "Playbook none again")
    assert "playbook" not in record(repo)
