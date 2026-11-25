"""The CLI's near-miss argument forms: each one that can mean one thing is accepted, and says so in
`--help`; a form that could mean two is refused with the two readings named."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from batch_helpers import changes, events, host, prepared, record
from conftest import Surface
from stack_world import Batch, stack_of
from test_leases import T0, Cli, Led, at, cr_of, leased  # noqa: F401 - the `leased` fixture

from chantier import cli as cli_module
from chantier import near_misses
from chantier.board import cli_run
from chantier.core import clock
from chantier.core.errors import EXIT_CONFLICT, EXIT_PRECONDITION
from chantier.core.records import SUMMARY_MAX, TITLE_MAX
from chantier.core.remote_wire import VIA_SERVER

ARGPARSE = 2  # argparse's own exit code for a form it refuses

# --- S1: `--lease` on the commands that name a unit's CR ----------------------------------------

LEASED_COMMANDS = [
    ("handoff", "{cr}"),
    ("log", "{cr}"),
    ("wait", "{cr}", "add", "answer", "--ref", "q", "--note", "n"),
    ("wait", "{cr}"),
]


def _run(cli: Cli, form: tuple[str, ...], cr: str, *more: object) -> tuple[int, list[str], str]:
    return cli.bare(*(a.format(cr=cr) for a in form), *more)


@pytest.mark.parametrize("form", LEASED_COMMANDS, ids=lambda f: " ".join(f[:2]))
def test_a_lease_on_a_command_that_names_a_cr_renews_or_is_lost(leased: Led, form: Any) -> None:  # noqa: F811
    repo, chantier, (one, _) = leased
    at(5)
    code, _, err = _run(chantier, form, one, "--lease", 1)
    assert code == 0, err
    assert cr_of(repo, one)["lease"]["renewed"] != T0  # renewed in the record
    before = json.dumps(record(repo), sort_keys=True)
    code, _, err = _run(chantier, form, one, "--lease", 9)
    assert code == EXIT_CONFLICT and "claim lost" in err
    assert json.dumps(record(repo), sort_keys=True) == before


@pytest.mark.parametrize("form", LEASED_COMMANDS[:2], ids=lambda f: f[0])
def test_a_read_with_no_lease_checks_and_writes_nothing(leased: Led, form: Any) -> None:  # noqa: F811
    repo, chantier, (one, _) = leased
    at(5)
    before = json.dumps(record(repo), sort_keys=True)
    assert _run(chantier, form, one)[0] == 0
    assert json.dumps(record(repo), sort_keys=True) == before


def test_rules_ignores_a_lease(leased: Led) -> None:  # noqa: F811
    _, chantier, _ = leased
    plain = chantier.bare("rules")
    assert plain[0] == 0 and chantier.bare("rules", "--lease", 3) == plain


def test_a_stack_lease_on_handoff_renews_the_stack_not_the_cr(leased: Led) -> None:  # noqa: F811
    repo, chantier, (one, _) = leased
    data = record(repo)
    data["mode"] = "stack"
    data["stack_lease"] = {
        "n": 4,
        "taken": T0,
        "renewed": T0,
        "expires": clock.after(600, T0),
        "ended": None,
    }
    data["crs"][0]["lease"]["ended"] = T0
    path = changes(repo) / "4-batch" / "batch.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    at(5)
    code, _, err = chantier.bare("handoff", one, "--lease", 4)
    assert code == 0 and "claim lost" not in err, err
    assert record(repo)["stack_lease"]["renewed"] != T0


def test_lease_numbers_before_and_after_the_unit_mean_the_same(leased: Led) -> None:  # noqa: F811
    _repo, chantier, (one, _) = leased
    at(5)
    after = chantier.bare("lease", one, "renew", "--lease", 1)
    assert after[0] == 0
    assert chantier.bare("lease", "--lease", 1, one, "renew") == after
    assert chantier.bare("lease", one, "--lease", 1) == after  # no action: renew
    code, _, err = chantier.bare("lease", "--lease", 1, one, "renew", "--lease", 2)
    assert code == 1 and "--lease given twice (1 and 2)" in err


def test_a_verdict_with_a_lease_renews_it(
    repo: Path, chantier: Cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(clock, "_fixed", [])
    clock.fix(T0)
    one = Batch("lease-wt", ("Lease one",), ("--slots", 1), took=1, worktrees=True)
    (cr,) = [c["id"] for c in stack_of(one, repo, chantier, monkeypatch)]
    at(5)
    cli = chantier
    code, _, err = cli.bare("verdict", cr, "NOT", "VERIFIED", "--lease", 9)
    assert code == EXIT_CONFLICT and "claim lost" in err
    code, _, err = cli.bare("verdict", cr, "NOT", "VERIFIED", "--lease", 1)
    assert code == 0, err
    assert cr_of(repo, cr)["lease"]["renewed"] != T0
    assert events(repo)[-1]["kind"] == "verdict"


# --- S2: `phase <cr> "<step> <detail>"` --------------------------------------------------------


def test_a_phase_given_as_one_quoted_word_is_split(leased: Led) -> None:  # noqa: F811
    repo, chantier, (one, _) = leased

    def last() -> dict[str, Any]:
        return {k: v for k, v in events(repo)[-1].items() if k not in ("at", "ts")}

    assert chantier("phase", one, "gate", "preflight")[0] == 0
    split = last()
    assert chantier("phase", one, "gate preflight")[0] == 0
    assert last() == split and split["phase"] == "gate"
    with pytest.raises(SystemExit) as refused:
        chantier("phase", one, "gate-ish x")
    assert refused.value.code == ARGPARSE


def test_normalize_rewrites_only_the_near_misses() -> None:
    n = near_misses.normalize
    assert n(["phase", "CR-1", "gate preflight"]) == ["phase", "CR-1", "gate", "preflight"]
    assert n(["--project", "p", "phase", "CR-1", "gate x y"]) == [
        "--project",
        "p",
        "phase",
        "CR-1",
        "gate",
        "x y",
    ]
    assert n(["phase", "CR-1", "gate-ish x"]) == ["phase", "CR-1", "gate-ish x"]
    assert n(["--project", "p", "--epoch", "3", "take", "CR-7", "--note", "n"]) == [
        "--project",
        "p",
        "take",
        "--epoch",
        "3",
        "CR-7",
        "--note",
        "n",
    ]
    assert n(["--epoch=3", "status"]) == ["status", "--epoch=3"]
    assert n(["--epoch", "3", "handoff", "CR-7"]) == ["--epoch", "3", "handoff", "CR-7"]
    assert n(["status", "--epoch", "3"]) == ["status", "--epoch", "3"]


def test_the_epoch_commands_are_the_parsers() -> None:
    parser = cli_module._parser()
    subs = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    holding = {
        name
        for name, p in subs.choices.items()
        if any("--epoch" in a.option_strings for a in p._actions)
    }
    assert set(near_misses.EPOCH_COMMANDS) == holding


def test_an_epoch_before_the_command_is_read_and_one_before_handoff_is_refused(
    leased: Led,  # noqa: F811
) -> None:
    _, chantier, (one, _) = leased
    assert chantier.bare("--epoch", 1, "status")[0] == 0
    with pytest.raises(SystemExit) as refused:
        chantier.bare("--epoch", 1, "handoff", one)
    assert refused.value.code == ARGPARSE


def test_the_server_reads_the_same_forms_as_the_cli() -> None:
    for argv in (["phase", "CR-1", "gate preflight"], ["--epoch", "3", "status"]):
        ns = SimpleNamespace(argv=argv, env={}, project=None, stdin=None)
        assert cli_run.judge(ns) is not None


# --- S3: `take` without `--epoch` ---------------------------------------------------------------


def test_take_with_no_epoch_points_to_handoff_and_the_agent_rail_is_unchanged(leased: Led) -> None:  # noqa: F811
    repo, chantier, (_one, two) = leased
    code, _, err = chantier.bare("take", two)
    assert code == ARGPARSE and "the steering session's command" in err
    assert f"`handoff {two}`" in err
    code, _, err = chantier.bare("take", "stack")
    assert "handoff" not in err and "the steering session's command" in err
    data = record(repo)
    data["crs"][1]["agent"] = "agent-x"
    (changes(repo) / "4-batch" / "batch.json").write_text(json.dumps(data), encoding="utf-8")
    code, _, err = chantier.bare("take", two, "--epoch", 1)
    assert code == EXIT_PRECONDITION
    assert (
        f"{two} still has an agent recorded (agent-x): `agents set {two} - --epoch <n>` first, "
        "once it ended"
    ) in err


# --- S6: the planning folder a CR path names ----------------------------------------------------

LAYOUTS = ["project", "surface"]


@pytest.fixture(params=LAYOUTS)
def planning(request: pytest.FixtureRequest, repo: Path, chantier: Cli) -> tuple[Cli, Path, str]:
    """(cli, the planning folder, the session-relative prefix a copied path carries)."""
    if request.param == "project":
        return chantier, changes(repo), ".agents/changes/"
    surface: Surface = request.getfixturevalue("surface")
    return chantier, surface.project / "changes", "projects/demo/changes/"


def _file(planning: tuple[Cli, Path, str], title: str) -> str:
    cli, _folder, _ = planning
    code, out, err = cli("file", title)
    assert code == 0, err
    return out[0].removeprefix("filed ").split(";")[0].rsplit("changes/", 1)[-1]


def _tree(folder: Path) -> dict[str, bytes]:
    return {
        p.relative_to(folder).as_posix(): p.read_bytes()
        for p in sorted(folder.rglob("*"))
        if p.is_file() and p.suffix != ".jsonl"
    }


def _stable(tree: dict[str, bytes]) -> dict[str, bytes]:
    """The tree without the one time a summary records."""
    return {k: re.sub(rb'"summarized": "[^"]*"', b"", v) for k, v in tree.items()}


def _twin(
    planning: tuple[Cli, Path, str],
    good: list[str],
    odd: list[str],
    inside: Path | None = None,
) -> None:
    """The command with `odd` arguments leaves the planning folder as with `good` ones (run from
    `inside`, when given)."""
    cli, folder, _ = planning
    start = _tree(folder)
    assert cli.bare(*good)[0] == 0
    done = _tree(folder)
    for rel in set(done) - set(start):
        (folder / rel).unlink()
    for rel, data in start.items():
        (folder / rel).write_bytes(data)
    with pytest.MonkeyPatch.context() as here:
        if inside is not None:
            here.chdir(inside)
        code, _, err = cli.bare(*odd)
    assert code == 0, err
    assert _stable(_tree(folder)) == _stable(done)


def test_a_path_with_the_planning_prefix_once_twice_or_a_short_name_is_one_folder(
    planning: tuple[Cli, Path, str],
) -> None:
    _, _, prefix = planning
    rel = _file(planning, "Near miss")
    assert rel.startswith("1-inbox/")
    name = rel.rsplit("/", 1)[1]
    title = ["--title", "T", "--summary", "S"]
    good = ["summary", "set", rel, *title]
    for odd in (
        ["summary", "set", f"{prefix}{rel}", *title],
        ["summary", "set", f"{prefix}{prefix}{rel}", *title],
        ["summary", "set", name, *title],
    ):
        _twin(planning, good, odd)
    for odd in (["summary", "lint", name], ["summary", "lint", f"{prefix}{rel}"]):
        assert planning[0].bare(*odd)[0] == planning[0].bare("summary", "lint", rel)[0]


def test_a_short_name_reaches_triage_and_wait(
    planning: tuple[Cli, Path, str],
) -> None:
    cli, folder, _ = planning
    rel = _file(planning, "Triage me")
    name = rel.rsplit("/", 1)[1]
    code, _out, err = cli.bare("triage", name, "--priority", "P2")
    assert code == 0, err
    assert (folder / "2-backlog" / "P2" / name).is_dir() and not (folder / rel).exists()


def test_a_path_from_inside_the_cr_folder_reads_dot(
    planning: tuple[Cli, Path, str],
) -> None:
    _cli, folder, _ = planning
    rel = _file(planning, "From inside")
    good = ["summary", "set", rel, "--title", "T", "--summary", "S"]
    odd = ["summary", "set", ".", "--title", "T", "--summary", "S"]
    _twin(planning, good, odd, inside=folder / rel)


def test_an_ambiguous_short_name_is_refused_with_both_readings(
    planning: tuple[Cli, Path, str],
) -> None:
    cli, folder, _ = planning
    rel = _file(planning, "Twice")
    name = rel.rsplit("/", 1)[1]
    shutil.copytree(folder / rel, folder / "5-archives" / name)
    code, _, err = cli.bare("summary", "lint", name)
    assert code == 1 and f"1-inbox/{name}" in err and f"5-archives/{name}" in err


def test_the_shell_folder_reading_stops_when_the_server_runs_the_command(
    planning: tuple[Cli, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    cli, folder, _ = planning
    rel = _file(planning, "Server side")
    name = rel.rsplit("/", 1)[1]
    monkeypatch.chdir(folder / "1-inbox")
    assert "no summary" in "\n".join(cli.bare("summary", "lint", f"1-inbox/{name}")[1])
    assert "no summary" in "\n".join(cli.bare("summary", "lint", name)[1])
    monkeypatch.setenv(VIA_SERVER, "1")
    assert "no summary" in "\n".join(cli.bare("summary", "lint", name)[1])  # by its name alone


def test_open_takes_a_short_name(
    repo: Path, chantier: Cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    host(monkeypatch)
    folder = prepared(repo, chantier, "Open by name")
    code, _, err = chantier("open", folder.name, "--default-branch", "main")
    assert code == 0, err
    assert record(repo)["crs"]


# --- S9: a summary gap says its limits ----------------------------------------------------------


def test_the_summary_gaps_name_their_limits_and_the_whole_form(repo: Path, chantier: Cli) -> None:
    _code, out, _ = chantier("file", "Gap")
    rel = out[0].removeprefix("filed ").split(";")[0]
    _code, out, err = chantier.bare("summary", "lint", rel.removeprefix(".agents/changes/"))
    text = "\n".join(out) + err
    assert f"at most {TITLE_MAX} characters" in text and f"at most {SUMMARY_MAX} characters" in text
    assert "summary set " in text and '--title "' in text and '--summary "' in text
    assert "no summary →" in text
    name = rel.removeprefix(".agents/changes/")
    assert chantier.bare("summary", "set", name, "--title", "T", "--summary", "S")[0] == 0
    (changes(repo) / name / "intake" / "request.md").write_text(
        "# Gap\n\nchanged\n", encoding="utf-8"
    )
    _, out, err = chantier.bare("summary", "lint", name)
    late = "\n".join(out) + err
    assert "summary late" in late and "--unchanged" in late
    assert f'--summary "<at most {SUMMARY_MAX} characters>"' in late
