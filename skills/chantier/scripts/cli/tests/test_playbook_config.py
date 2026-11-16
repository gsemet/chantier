"""The optional chantier.yaml: absent, valid, kept by a running batch, and refused with its line."""

from __future__ import annotations

from pathlib import Path

import pytest
from batch_helpers import FROM_AGENTS_MD, changes, host, open_batch, prepared, record
from conftest import PLUGIN_ROOT, Chantier
from cost_world import CostWorld, build

from chantier.core.errors import EXIT_PRECONDITION

PROMPTERS = ("retro-critic", "spec-critic", "spec-writer")
ESCALATE = "escalate: opus (claude-opus-5-5, Claude Opus 5.5)"
CODER = "coder: agent=chantier:coder model=(its file's)"
PRICES = "prices:\n  mystery-model:\n"
FOUR = "".join(f"    {k}: 1\n" for k in ("input", "cache_write_5m", "cache_write_1h", "cache_read"))
FIVE = FOUR + "    output: 1\n"
ROLES = "hosts:\n  claude:\n    roles:\n"
HEAD = ROLES + "      coder:\n"
COPILOT_HEAD = HEAD.replace("claude", "copilot")
A = "        "  # a role's key
DRIVER = ROLES + "      cr-driver:\n" + A + "agent: my-driver\n"
OPUS = "opus (claude-opus-5-5, Claude Opus 5.5)"
TERRA = "gpt-6.1-terra (gpt-6.1-terra, GPT-6.1 Terra)"
NOT_RESTRICTED = "tools=(the caller's, not restricted)"
REFUSAL = (
    'role "coder": Copilot cannot start a named agent with a model '
    '(hosts/copilot.md, "Models at an agent\'s start"): remove "model" for coder under '
    "hosts.copilot.roles, or name the model in your agent's own file"
)
REFUSAL_END = REFUSAL.rsplit(", ", 1)[1]


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
    )  # the retro, spec-critic and spec-writer, not the Demo explorer
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
    prompts = [
        ln for ln in out if " prompt, first line: " in ln
    ]  # the Foreman's: the retro critic's only
    assert len(prompts) == 1 and prompts[0].startswith(
        "retro-critic prompt, first line: chantier retro-critic for the Chief of Staff, "
    )


def test_a_valid_file_is_resolved_recorded_and_kept_by_the_running_batch(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    yaml = repo / "chantier.yaml"  # with a BOM, as a Windows editor writes it
    yaml.write_text(
        "# the team\n" + ROLES + "      coder:\n        model: opus\n        skills: [jira]\n"
        "      cr-driver:\n        agent: my-driver  # my own\n",
        encoding="utf-8-sig",
    )
    opus = f"model={OPUS} [repository]"
    coder = f"coder: agent=chantier:coder {opus} skills=jira [repository]"
    code, now, _ = chantier("playbook")
    assert code == 0 and now[0] == "playbook: chantier.yaml, valid, host claude"
    assert coder in now and "cr-driver: agent=my-driver [repository] model=(its file's)" in now
    ids = open_batch(repo, chantier, monkeypatch, "Playbook set one", "Playbook set two")
    _, took, _ = chantier("take", ids[0], "--epoch", 1)
    roles = record(repo)["playbook"]["roles"]
    assert roles["cr-driver"] == {"agent": "my-driver", "start": "named"}
    assert roles["coder"]["start"] == "named"
    want = f"team: coder model={OPUS} [repository] skills=jira [repository]"
    assert team(took) == [want, "team: cr-driver agent=my-driver [repository]"]
    _, out, _ = chantier("playbook", "--batch", record(repo)["id"])
    assert now[-1] == ESCALATE and out[-1] == ESCALATE and "opened it" in out[0]
    kept = [ln for ln in now[1:] if " prompt, first line: " not in ln]
    assert [ln for ln in out[1:] if " prompt, first line: " not in ln] == kept
    yaml.write_text(HEAD + A + "agent: other-coder\n", encoding="utf-8")
    _, took, _ = chantier("take", ids[1], "--epoch", 1)  # S3: the batch keeps its opening's
    _, out, _ = chantier("playbook", "--batch", record(repo)["id"])
    assert "other-coder" not in "".join(took + out) and "agent=my-driver" in "".join(team(took))
    assert [ln for ln in out[1:] if " prompt, first line: " not in ln] == kept


def test_ci_beside_the_gate_is_printed_recorded_and_kept_after_the_key_is_dropped(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    yaml = repo / "chantier.yaml"
    yaml.write_text("ci:\n  beside_gate: true\n" + DRIVER)
    code, out, _ = chantier("playbook")
    ids = open_batch(repo, chantier, monkeypatch, "Playbook ci one", "Playbook ci two")
    _, took, _ = chantier("take", ids[0], "--epoch", 1)
    _, shown, _ = chantier("handoff", ids[0])
    brief = next(changes(repo).rglob("brief.md")).read_text(encoding="utf-8")
    assert code == 0 and len(ci_line(out)) == 1 and "(repository)" in ci_line(out)[0]
    assert record(repo)["playbook"]["ci"] == {"beside_gate": True}
    assert len(ci_line(took)) == 1 and len(ci_line(shown)) == 1
    assert "CI beside the long gate: on (repository)" in brief
    yaml.write_text(DRIVER)
    _, took, _ = chantier("take", ids[1], "--epoch", 1)
    _, out, _ = chantier("playbook", "--batch", record(repo)["id"])
    assert len(ci_line(took)) == 1 and len(ci_line(out)) == 1


@pytest.mark.parametrize(
    "text",
    ["ci:\n  beside_gate: false\n" + DRIVER, DRIVER],
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


ROLES_MOVED = '"roles" goes under a host'
REFUSALS = [
    (
        "an unknown role",
        ROLES + "      codr:\n" + A + "agent: x\n",
        4,
        "is not one of the plugin's",
    ),
    ("an unknown key", HEAD + A + "colour: red\n", 5, 'unknown key "colour"'),
    ("an empty role", HEAD, 4, "is empty"),
    ("a tab", HEAD + "\tagent: x\n", 5, "a tab"),
    ("an anchor", HEAD + A + "agent: &a x\n", 5, "anchors"),
    ("a duplicate key", HEAD + A + "agent: x\n" + A + "agent: y\n", 6, "duplicate key"),
    ("a flow mapping", HEAD + A + "agent: {a: b}\n", 5, "flow mappings"),
    ("a second document", HEAD + A + "agent: x\n---\n", 6, "several documents"),
    ("an unknown model", HEAD + A + "model: opus 5.6\n", 5, "is unknown on Claude Code; known:"),
    ("a model with no letter", HEAD + A + "model: 5.5\n", 5, "name the model, not only"),
    ("a top-level roles", "roles:\n  coder:\n    agent: x\n", 1, ROLES_MOVED),
    ("roles: default", "roles: default\n", 1, ROLES_MOVED),
    ("an unknown host", "hosts:\n  gemini:\n    roles:\n", 2, 'unknown host "gemini"'),
    ("a host key", "hosts:\n  claude:\n    colour: red\n", 3, 'unknown key "colour"'),
    ("a quoted default model", HEAD + A + 'model: "default"\n', 5, '"default" resets the value'),
    ("a quoted default agent", HEAD + A + 'agent: "default"\n', 5, '"default" resets the value'),
    ("an empty agent", HEAD + A + "agent:\n", 5, '"agent" is one string'),
    (
        "a reset under an unknown role",
        ROLES + "      codr: default\n",
        4,
        "is not one of the plugin's",
    ),
    ("a reset under an unknown key", HEAD + A + "colour: default\n", 5, 'unknown key "colour"'),
    ("a bad model of another host", COPILOT_HEAD + A + "model: gpt\n", 5, "ambiguous on Copilot"),
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
    host(monkeypatch)  # one repo for all the texts: each is refused, none moves the CR
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
        ln.startswith("chantier.yaml:4:") for ln in out + err.splitlines()
    )
    code, pre, _ = chantier("preflight")
    assert code == EXIT_PRECONDITION and pre[-1].endswith("start nothing")
    assert any(ln.startswith("P12 FAIL chantier.yaml:4:") for ln in pre)
    yaml.write_text(COPILOT_HEAD + A + "model: gpt\n", encoding="utf-8")
    code, out, err = chantier("playbook", "--host", "copilot")
    text = "".join(out) + err
    assert code == EXIT_PRECONDITION and "ambiguous" in text and "Luna" in text and "Sol" in text
    yaml.write_text(COPILOT_HEAD + A + "model: opus\n", encoding="utf-8")
    code, out, err = chantier("playbook", "--host", "copilot")  # several Opus models: ambiguous
    text = "".join(out) + err
    assert code == EXIT_PRECONDITION and "ambiguous" in text
    assert all(i in text for i in ("claude-opus-4.8 ", "claude-opus-5 ", "claude-opus-5.5 "))
    yaml.write_text(COPILOT_HEAD + A + "model: claude-opus-5.5\n", encoding="utf-8")
    code, out, err = chantier("playbook", "--host", "copilot")  # a model, no agent: generic
    assert code == 0, err
    assert any(ln.startswith("coder: agent=(generic) model=claude-opus-5.5 (") for ln in out)
    yaml.write_text(COPILOT_HEAD + A + "model: claude-opus-5.5\n" + A + "agent: mine\n", "utf-8")
    code, out, err = chantier("playbook", "--host", "copilot")  # the user's agent, a model
    assert code == EXIT_PRECONDITION and any(
        ln.startswith("chantier.yaml:5:") and ln.endswith(REFUSAL_END) and REFUSAL in ln
        for ln in out + err.splitlines()
    )
    assert chantier("playbook", "--host", "claude")[0] == 0  # the Claude view of it is valid
    host(monkeypatch, "copilot")
    code, pre, _ = chantier("preflight")
    assert code == EXIT_PRECONDITION and any(
        ln.startswith("P12 FAIL chantier.yaml:5:") for ln in pre
    )


def test_with_no_chantier_yaml_again_the_next_batch_records_nothing(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    yaml = repo / "chantier.yaml"
    yaml.write_text(HEAD + A + "skills: [jira]\n")
    host(monkeypatch)
    yaml.unlink()
    open_batch(repo, chantier, monkeypatch, "Playbook none again")
    assert "playbook" not in record(repo)


FOUR_STARTS = [
    ("claude", "model: opus\n", f"coder: agent=chantier:coder model={OPUS} [repository]"),
    (
        "claude",
        "agent: mine\nmodel: opus\n",
        f"coder: agent=mine [repository] model={OPUS} [repository]",
    ),
    (
        "copilot",
        "model: gpt-6.1-terra\n",
        f"coder: agent=(generic) model={TERRA} [repository] {NOT_RESTRICTED}",
    ),
    ("copilot", "agent: mine\n", "coder: agent=mine [repository] model=(its file's)"),
]


@pytest.mark.parametrize("case", FOUR_STARTS)
def test_a_role_starts_the_plugin_agent_a_named_one_or_a_generic_one_per_host(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, case: tuple[str, str, str]
) -> None:
    host_name, keys, line = case
    host(monkeypatch, host_name)
    body = "".join(A + ln + "\n" for ln in keys.splitlines())
    (repo / "chantier.yaml").write_text(HEAD.replace("claude", host_name) + body, encoding="utf-8")
    code, out, err = chantier("playbook", "--host", host_name)
    assert code == 0 and line in out, err


def test_a_copilot_batch_records_a_generic_start_and_take_prints_its_contract(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch, "copilot")
    (repo / "chantier.yaml").write_text(COPILOT_HEAD + A + "model: gpt-6.1-terra\n", "utf-8")
    code, _, err = chantier("open", str(prepared(repo, chantier, "Generic coder")), *FROM_AGENTS_MD)
    assert code == 0, err
    monkeypatch.setenv("CHANTIER_BATCH", record(repo)["id"])
    assert chantier("foreman", "set", "local_foreman_t", "--epoch", 1)[0] == 0
    _, took, _ = chantier("take", record(repo)["crs"][0]["id"], "--epoch", 1)
    assert record(repo)["playbook"]["roles"]["coder"]["start"] == "generic"
    assert team(took) == [
        f"team: coder agent=(generic) model={TERRA} [repository] {NOT_RESTRICTED}"
    ]
    heading = (
        "coder contract (a generic agent: copy it unchanged, without the two leading spaces, "
        "after the opening lines):"
    )
    agent = PLUGIN_ROOT / "com.github.copilot" / "agents" / "chantier-coder.agent.md"
    body = agent.read_text(encoding="utf-8").split("\n---\n", 1)[1].strip("\n").splitlines()
    at = took.index(heading)
    assert took[at - 1].startswith("  the project's rules rank above it")
    assert took[at + 1 : at + 1 + len(body)] == [f"  {ln}" for ln in body]
    assert not any(
        "contract (a generic agent" in ln for ln in took[:at] + took[at + 1 + len(body) :]
    )
    _, out, _ = chantier("playbook", "--batch", record(repo)["id"])
    assert f"coder: agent=(generic) model={TERRA} [repository] {NOT_RESTRICTED}" in out


@pytest.fixture
def world(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> CostWorld:
    return build(repo, chantier, monkeypatch, tmp_path)


@pytest.mark.parametrize(
    ("keys", "note"),
    [
        (
            "agent: mine\n",
            "Grill line: spec-writer starts as your agent mine, so its spend is counted with the "
            "Chief of Staff's steering, not on the grill line",
        ),
        ("model: sonnet\n", None),  # the plugin's own agent, another model: its type is kept
    ],
)
def test_cost_explain_says_when_a_spec_agent_leaves_the_grill_line(
    world: CostWorld, keys: str, note: str | None
) -> None:
    body = "".join(A + ln + "\n" for ln in keys.splitlines())
    (world.repo / "chantier.yaml").write_text(ROLES + "      spec-writer:\n" + body, "utf-8")
    out = world.cost("--explain")
    assert [ln for ln in out if ln.startswith("Grill line:")] == ([note] if note else [])
