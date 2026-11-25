"""`roles.yaml` and `just roles` (`scripts/roles_check.py`): the shipped data and the hand-written
agent files of both hosts agree, the data has its frame, and each kind of mismatch is refused. The
shipped files are read at the head under test; a prepared copy holds only the mismatches."""

from __future__ import annotations

import contextlib
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import PLUGIN_ROOT, SKILL, load_script
from test_plugin_files import ALL_ROLES, agent_file

from chantier.cli import main as chantier_main
from chantier.roles_data import KINDS, WRITES, load_roles

CHECK = load_script("roles_check", PLUGIN_ROOT / "scripts" / "roles_check.py")
AGREE = "roles: 18 roles, 15 wrappers on 2 hosts agree"
STEERING = ("chief-of-staff", "griller", "foreman")
ROLE_COUNT = 18
CLAUDE, COPILOT = "agents/coder.md", "com.github.copilot/agents/chantier-coder.agent.md"
DATA = "skills/chantier/roles.yaml"


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str]:
    code = CHECK.main(list(argv))
    return code, capsys.readouterr().out


def test_the_shipped_files_agree(capsys: pytest.CaptureFixture[str]) -> None:
    assert _run(capsys, "--root", str(PLUGIN_ROOT)) == (0, AGREE + "\n")


def test_the_data_has_its_frame() -> None:
    roles = load_roles()
    assert len(roles) == ROLE_COUNT
    assert {r.name for r in roles} == {*ALL_ROLES, *STEERING}
    assert all(r.kind in KINDS and r.writes in WRITES for r in roles)
    for host in ("claude", "copilot"):
        named = {r.hosts[host].wrapper for r in roles} - {None}
        shipped = {agent_file(r, host).relative_to(PLUGIN_ROOT).as_posix() for r in ALL_ROLES}
        assert named == shipped
    assert {r.name for r in roles if r.first is None} == set(STEERING)


def _edit(root: Path, rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_bytes().decode("utf-8")
    assert old in text, (rel, old)
    path.write_bytes(text.replace(old, new, 1).encode("utf-8"))


def _prepared(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    for rel in ("agents", "com.github.copilot/agents", "skills/chantier/references"):
        shutil.copytree(PLUGIN_ROOT / rel, root / rel)
    for rel in (DATA, "skills/chief-of-staff/SKILL.md", "skills/griller/SKILL.md"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(PLUGIN_ROOT / rel, root / rel)
    return root


CASES = {
    "description": (
        (COPILOT, "Implements one round", "Implements a round"),
        "roles: coder (copilot): description differs from roles.yaml's",
    ),
    "tool": ((COPILOT, ', "search"]', "]"), "roles: coder (copilot): tools "),
    "body": ((COPILOT, "whole brief", "whole briefs"), "roles: coder (copilot): body differs"),
    "first": (
        (DATA, "'chantier coder for <cr>", "'chantier coder on <cr>"),
        "roles: coder (claude): description differs from roles.yaml's",
    ),
    "card-name": (
        (DATA, "card: coder.md\n", "card: debugger.md\n"),
        "roles: coder (claude): the body's card is `coder.md`, not `debugger.md`",
    ),
    "card-file": (
        (DATA, "card: coder.md\n", "card: coder-gone.md\n"),
        "roles: coder (data): card coder-gone.md: no such file",
    ),
    "reply-heading": (
        (DATA, "'coder.md#Your part'", "'coder.md#Your parts'"),
        "roles: coder (data): reply coder.md#Your parts: no heading `Your parts`",
    ),
    "extra-wrapper": (None, "roles: extra (claude): agents/extra.md has no entry in roles.yaml"),
    "missing-wrapper": (None, f"roles: coder (copilot): no file {COPILOT}"),
    "kind": (
        (DATA, "kind: review-step", "kind: reviewer"),
        "roles: roles.yaml: role inspector: kind: 'reviewer' is not one of",
    ),
}


@pytest.mark.parametrize("case", list(CASES))
def test_a_prepared_mismatch_is_refused(
    capsys: pytest.CaptureFixture[str], tmp_path: Path, case: str
) -> None:
    root = _prepared(tmp_path)
    change, expected = CASES[case]
    if change:
        _edit(root, *change)
    elif case == "extra-wrapper":
        shutil.copyfile(root / CLAUDE, root / "agents" / "extra.md")
    else:
        (root / COPILOT).unlink()
    code, out = _run(capsys, "--root", str(root))
    assert code == 1 and expected in out, out
    assert re.search(r"^roles: \d+ problem\(s\)$", out, re.M) or case == "kind", out


def _tracked() -> dict[str, bytes]:
    listed = subprocess.run(
        ["git", "ls-files", "-z", "agents", "com.github.copilot/agents", "skills/chantier"],
        cwd=PLUGIN_ROOT,
        capture_output=True,
        check=True,
    )
    names = [n for n in listed.stdout.decode("utf-8").split("\0") if n]
    return {n: (PLUGIN_ROOT / n).read_bytes() for n in names if (PLUGIN_ROOT / n).is_file()}


def test_write_prints_each_committed_wrapper_and_writes_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    before = _tracked()
    assert _run(capsys, "--write", "coder")[0] == 0
    for role in ALL_ROLES:
        for host in ("claude", "copilot"):
            path = agent_file(role, host)
            code, out = _run(capsys, "--write", role, "--host", host)
            committed = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
            head = f"=== {path.relative_to(PLUGIN_ROOT).as_posix()}\n"
            assert code == 0 and out == head + committed, (role, host)
    assert _tracked() == before
    assert _run(capsys, "--write", "foreman") == (1, "foreman has no wrapper\n")


def test_no_cli_command_is_named_roles(capsys: pytest.CaptureFixture[str]) -> None:
    with contextlib.suppress(SystemExit):
        chantier_main(["--help"])
    commands = re.search(r"\{([a-z,-]+)\}", capsys.readouterr().out)
    assert commands is not None and "roles" not in commands[1].split(",")
    assert (SKILL / "roles.yaml").is_file()
