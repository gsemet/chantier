"""The configuration in layers: the surface, its project's folder and the code repository, the
resets, the shipped defaults, and what a running batch keeps."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from batch_helpers import FROM_AGENTS_MD, host, prepared
from conftest import PLUGIN_ROOT, Chantier, Surface
from test_playbook_config import CODER, DRIVER, HEAD, OPUS, A, ci_line
from test_plugin_files import ROLES, _front, agent_file

from chantier.board.address import settings
from chantier.core.errors import EXIT_PRECONDITION
from chantier.core.repo import Repo
from chantier.playbook import config, layers
from chantier.playbook.yaml_subset import is_reset
from chantier.plugin_files import plugin_roles, read_playbook

COPILOT_CODER = "hosts:\n  copilot:\n    roles:\n      coder:\n"
RESET_LINE = (
    "coder: agent=chantier:coder [reset in surface project] "
    "model=(its file's) [reset in repository]"
)
PORT = 8123


def plain(result: tuple[int, list[str], str]) -> tuple[int, list[str], str]:
    """A `playbook` run with each role line cut before its escalation, which these tests leave to
    test_playbook_config.py."""
    code, out, err = result
    return code, [re.sub(r" escalation=.*$", "", ln) for ln in out], err


DEFAULTS = PLUGIN_ROOT / "config" / "chantier.defaults.yml"


def put(path: Path, text: str | None) -> None:
    if text is not None:
        path.write_text(HEAD + "".join(f"{A}{ln}\n" for ln in text.splitlines()), encoding="utf-8")


@pytest.mark.parametrize("host_name", ["claude", "copilot"])
def test_the_shipped_defaults_give_each_role_the_model_its_agent_file_declares(
    host_name: str,
) -> None:
    tree, problems = config.read_tree(DEFAULTS, "config/chantier.defaults.yml")
    assert tree is not None and not problems
    found: list[tuple[int, str]] = []
    roles_by_host = {h: plugin_roles(h) for h in ("claude", "copilot")}
    config.check(tree, roles_by_host, lambda n, m: found.append((n, m)))
    assert not found and set(tree.value) == {
        "hosts",
        "specifying",
        "batch",
    }  # valid, and nothing else
    assert set(tree.value["hosts"][1].value) == {"claude", "copilot"}
    held = tree.value["hosts"][1].value[host_name][1].value
    assert set(held) == {"roles", "timing"}
    roles = held["roles"][1].value
    assert sorted(roles) == sorted(ROLES) == sorted(plugin_roles(host_name))  # one per agent file
    for role, (_, node) in roles.items():
        assert set(node.value) in ({"model"}, {"model", "escalation"})
        assert not any(is_reset(n) for _, n in node.value.values())  # no reset
        declared = _front(agent_file(role, host_name))[0]["model"].strip("[]").split(", ")[-1]
        assert node.value["model"][1].value == declared, role


def test_the_layers_merge_in_order_and_each_value_names_its_layer(
    surface: Surface, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    put(surface.root / "chantier.yaml", "model: opus\nskills: [a, b]\nagent: root-coder")
    put(surface.project / "chantier.yaml", "skills: [jira]\nagent: project-coder")
    put(surface.clone / "chantier.yaml", "agent: repo-coder")
    code, out, err = plain(chantier("playbook"))
    files = "chantier.yaml, projects/demo/chantier.yaml, projects/demo/.repo/chantier.yaml"
    assert code == 0, err
    assert out[0] == f"playbook: {files}, valid, host claude"
    want = (
        f"coder: agent=repo-coder [repository] model={OPUS} [surface] skills=jira [surface project]"
    )
    assert want in out  # the list [jira] replaced [a, b] whole


@pytest.mark.parametrize(
    "case",
    [
        ("default", "agent: x", "agent: default\nmodel: opus", "model: default", RESET_LINE),
        ("tilde", "agent: x", "agent: ~\nmodel: opus", "model: ~", RESET_LINE),
        ("null", "agent: x", "agent: null\nmodel: opus", "model: null", RESET_LINE),
        (
            "set again",
            "agent: x",
            "agent: default",
            "agent: repo-coder",
            "coder: agent=repo-coder [repository] model=(its file's)",
        ),
        (
            "a quoted tilde",
            None,
            None,
            'agent: "~"',
            "coder: agent=~ [repository] model=(its file's)",
        ),
        ("nothing weaker", None, None, "skills: default", CODER),
    ],
)
def test_a_plain_default_tilde_or_null_takes_a_value_back_and_the_print_says_where(
    surface: Surface,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    case: tuple[str, str | None, str | None, str, str],
) -> None:
    label, root, project, clone, line = case
    host(monkeypatch)
    put(surface.root / "chantier.yaml", root)
    put(surface.project / "chantier.yaml", project)
    put(surface.clone / "chantier.yaml", clone)
    code, out, err = plain(chantier("playbook"))
    assert code == 0, err
    assert line in out, (label, out)
    assert ("reset in" in " ".join(out)) == (line == RESET_LINE), label


@pytest.mark.parametrize("where", ["clone", "root", "project"])
def test_both_file_names_in_one_place_are_refused_with_both_paths(
    surface: Surface, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, where: str
) -> None:
    host(monkeypatch)
    folder = getattr(surface, where)
    for name in ("chantier.yaml", "chantier.yml"):
        put(folder / name, "agent: x")
    code, out, err = plain(chantier("playbook"))
    shown = folder.relative_to(surface.root).as_posix()
    paths = [f"{shown}/{n}" if shown != "." else n for n in ("chantier.yaml", "chantier.yml")]
    assert code == EXIT_PRECONDITION
    assert f"{paths[0]} and {paths[1]} are both present: keep one" in "\n".join(out) + err


def test_a_yml_file_alone_is_read_and_a_problem_names_the_file_it_is_in(
    surface: Surface, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    put(surface.project / "chantier.yml", "agent: project-coder")
    code, out, err = plain(chantier("playbook"))
    assert code == 0 and out[0] == "playbook: projects/demo/chantier.yml, valid, host claude", err
    assert "coder: agent=project-coder [surface project] model=(its file's)" in out
    (surface.project / "chantier.yml").unlink()
    put(surface.project / "chantier.yaml", "colour: red")
    code, out, err = plain(chantier("playbook"))
    assert code == EXIT_PRECONDITION
    assert any(ln.startswith("projects/demo/chantier.yaml:5: ") for ln in out + err.splitlines())
    _, pre, _ = chantier("preflight")
    assert any(ln.startswith("P12 FAIL projects/demo/chantier.yaml:5: ") for ln in pre)


def test_a_model_equal_to_its_agents_is_not_passed_unless_the_agent_is_set_too(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    yaml = repo / "chantier.yaml"
    yaml.write_text(COPILOT_CODER + A + "model: gpt-6.1-sol\n", encoding="utf-8")
    code, out, err = plain(
        chantier("playbook", "--host", "copilot")
    )  # the file's own: accepted, silent
    assert code == 0 and "coder: agent=chantier-coder model=(its file's)" in out, err
    yaml.write_text(
        COPILOT_CODER + A + "model: gpt-6.1-sol\n" + A + "agent: mine\n", encoding="utf-8"
    )
    code, out, err = plain(
        chantier("playbook", "--host", "copilot")
    )  # with an agent: passed, refused
    assert code == EXIT_PRECONDITION
    assert "chantier.yaml:5:" in err + "".join(out)
    assert "cannot start a named agent with a model" in err + "".join(out)
    yaml.write_text(HEAD + A + "model: sonnet\n" + A + "agent: mine\n", encoding="utf-8")
    code, out, err = plain(chantier("playbook"))  # on Claude the model is passed beside the agent
    model = "sonnet (claude-sonnet-5-5, Claude Sonnet 5.5) [repository]"
    assert code == 0 and f"coder: agent=mine [repository] model={model}" in out, err
    yaml.write_text(HEAD + A + "model: sonnet\n", encoding="utf-8")
    assert "coder: agent=chantier:coder model=(its file's)" in plain(chantier("playbook"))[1]


def test_a_batch_opened_in_a_surface_keeps_its_configuration_when_a_surface_file_changes(
    surface: Surface, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    root_file = surface.root / "chantier.yaml"
    root_file.write_text(DRIVER + "ci:\n  beside_gate: true\n", encoding="utf-8")
    item = prepared(surface.root, chantier, "Playbook surface")
    code, _, err = chantier("open", str(item), *FROM_AGENTS_MD)
    assert code == 0, err
    saved = json.loads(next((surface.project / "changes").rglob("batch.json")).read_text("utf-8"))
    frozen = saved["playbook"]
    assert frozen["files"] == ["chantier.yaml"] and frozen["layers"]["ci"] == "surface"
    assert frozen["roles"] == {"cr-driver": {"agent": "my-driver", "start": "named"}}
    assert "prices" not in frozen and "price_layers" not in frozen
    root_file.write_text(HEAD + A + "agent: other-coder\n", encoding="utf-8")
    code, out, err = plain(chantier("playbook", "--batch", saved["id"]))
    assert code == 0 and "opened it" in out[0], err
    assert "cr-driver: agent=my-driver [surface] model=(its file's)" in out
    assert "other-coder" not in "".join(out) and len(ci_line(out)) == 1


def test_the_light_readers_see_the_board_and_long_gate_keys_of_any_layer(
    surface: Surface,
) -> None:
    (surface.root / "chantier.yml").write_text(
        f"long_gate:\n  parallel: 2\nboard:\n  port: {PORT}\n", "utf-8"
    )
    (surface.clone / "chantier.yaml").write_text("long_gate:\n  parallel: 3\n", encoding="utf-8")
    repo = Repo.find()
    assert layers.load_long_gate(repo) == (3, [])  # the stronger layer wins
    board, problems = layers.load_board(repo)
    assert problems == [] and board.get("port") == PORT
    assert settings(repo, None, None) == ("0.0.0.0", PORT)
    (surface.clone / "chantier.yaml").write_text("long_gate: default\n", encoding="utf-8")
    assert layers.load_long_gate(repo) == (1, [])  # a reset takes the weaker value back too


def test_a_prices_entry_is_replaced_whole_and_a_reset_model_is_accepted_on_copilot(
    surface: Surface, chantier: Chantier, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    entry = "prices:\n  mystery-model:\n" + "".join(
        f"    {k}: {n}\n" for n, k in enumerate(config.PRICE_NAMES)
    )
    long = "    long_context:\n      above: 200000\n" + entry.split("\n", 2)[2].replace(
        "    ", "      "
    )
    (surface.root / "chantier.yaml").write_text(entry + long, encoding="utf-8")
    (surface.clone / "chantier.yaml").write_text(entry.replace("input: 0", "input: 7"), "utf-8")
    made, problems = read_playbook(Repo.find(), "claude")
    assert made and not problems  # the repository's entry stands alone: no long_context left
    assert made["prices"]["mystery-model"] == {
        **dict.fromkeys(config.PRICE_NAMES, 0),
        "input": 7,
    } | {k: float(n) for n, k in enumerate(config.PRICE_NAMES) if k != "input"}
    assert made["price_layers"] == {"mystery-model": "repository"}
    (surface.clone / "chantier.yaml").unlink()
    (surface.root / "chantier.yaml").write_text(
        COPILOT_CODER + A + "model: gpt-5.6-luna\n", encoding="utf-8"
    )
    (surface.project / "chantier.yaml").write_text(COPILOT_CODER + A + "model: default\n", "utf-8")
    code, out, err = plain(chantier("playbook", "--host", "copilot"))  # reset: no model, accepted
    assert code == 0, err
    assert "coder: agent=chantier-coder model=(its file's) [reset in surface project]" in out
