"""The plugin's launcher (`skills/chantier/scripts/chantier.py`): the mode it picks matches the
CLI's own rule, the form it prints is `cli_command`'s, the command it runs keeps the argument list,
and its `--sync` names the holders and never syncs past them. No uv, uvx or powershell is started:
a fake runner answers."""

from __future__ import annotations

import ast
import json
import os
import sys
import tomllib
from pathlib import Path

import pytest
from conftest import PLUGIN_ROOT, sh

from chantier import launcher, plugin_files
from chantier.core.errors import ChantierError
from chantier.core.repo import Repo
from chantier.launch import (
    LAUNCHER,
    is_chantier_project,
    launcher_line,
    launcher_rule,
    project_is_chantier,
)

SRC = PLUGIN_ROOT / "skills" / "chantier" / "scripts" / "cli" / "src" / "chantier"
MANIFESTS = {
    "claude": (".claude-plugin/plugin.json", "chantier"),
    "copilot": (".github/plugin/plugin.json", "chantier"),
    "other-name": (".claude-plugin/plugin.json", "studio"),
    "broken": (".claude-plugin/plugin.json", None),
}
GIT_ID = ("-c", "user.name=t", "-c", "user.email=t@example.com")


def _surface(base: Path, name: str, projects: tuple[str, ...]) -> None:
    sh("git", "init", "--quiet", str(base / name))
    for p in projects:
        (base / name / "projects" / p / "changes").mkdir(parents=True)


@pytest.fixture(scope="module")
def world(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The session projects of `test_launch_modes.py`'s cells, and the surfaces, the worktree and
    the two plugin roots (a checkout with `.git`, a host's copy without), under a path with a
    space."""
    base = tmp_path_factory.mktemp("launcher").resolve()
    for cell in ("claude", "copilot", "plain", "other-name", "broken"):
        root = base / f"repo-{cell}"
        sh("git", "init", "--quiet", str(root))
        if cell in MANIFESTS:
            rel, name = MANIFESTS[cell]
            (root / rel).parent.mkdir(parents=True)
            body = json.dumps({"name": name}) if name else "{not json"
            (root / rel).write_text(body, encoding="utf-8")
    sh("git", *GIT_ID, "-C", str(base / "repo-claude"), "add", ".")
    sh("git", *GIT_ID, "-C", str(base / "repo-claude"), "commit", "--quiet", "-m", "m")
    sh("git", "-C", str(base / "repo-claude"), "worktree", "add", "--quiet", str(base / "wt"))
    _surface(base, "surface-chantier", ("chantier",))
    _surface(base, "surface-studio", ("studio",))
    _surface(base, "surface-two", ("alpha", "chantier"))
    (base / "none").mkdir()
    for kind in ("dev", "copy"):
        skill = base / "with space" / kind / "skills" / "chantier"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("x\n", encoding="utf-8")
    (base / "with space" / "dev" / ".git").mkdir()
    return base


# case -> (working folder, --project (`@` = under the world), CHANTIER_ROOT, chantier?)
CASES = {
    "claude": ("repo-claude", None, None, True),
    "copilot": ("repo-copilot", None, None, True),
    "surface-chantier": ("repo-plain", "@surface-chantier/projects/chantier", None, True),
    "plain": ("repo-plain", None, None, False),
    "other-name": ("repo-other-name", None, None, False),
    "broken": ("repo-broken", None, None, False),
    "surface-studio": ("repo-plain", "@surface-studio/projects/studio", None, False),
    "none": ("none", None, None, False),
    "surface-only-chantier": ("surface-chantier", None, None, True),
    "surface-two-projects": ("surface-two", None, None, False),
    "bare-name-in-surface": ("surface-two", "chantier", None, True),
    "worktree-of-chantier": ("wt", None, None, True),
    "chantier-root-elsewhere": ("repo-plain", None, "repo-claude", True),
}


class Fake(launcher.Runner):
    """Answers each captured command from a queue and records every command."""

    def __init__(self, *answers: tuple[int, str, str], missing: bool = False) -> None:
        self.answers = list(answers)
        self.captured: list[list[str]] = []
        self.ran: list[list[str]] = []
        self.missing = missing

    def capture(self, cmd: list[str]) -> tuple[int, str, str]:
        self.captured.append(cmd)
        return self.answers.pop(0)

    def run(self, cmd: list[str]) -> int:
        if self.missing:
            raise FileNotFoundError(cmd[0])
        self.ran.append(cmd)
        return 0


@pytest.mark.parametrize("case", list(CASES))
def test_the_mode_matches_the_cli_rule_and_the_print_and_the_run_keep_the_form(
    case: str, world: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    where, project, chantier_root, chantier = CASES[case]
    cwd = world / where
    if project and project.startswith("@"):
        project = str(world / project[1:])
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(world))
    monkeypatch.delenv("CHANTIER_ROOT", raising=False)
    if chantier_root:
        monkeypatch.setenv("CHANTIER_ROOT", str(world / chantier_root))
    monkeypatch.setattr(plugin_files, "SKILL", None)
    monkeypatch.chdir(cwd)
    try:
        repo: Repo | None = Repo.find(project=project, readonly=True)
    except ChantierError:
        repo = None
    assert project_is_chantier(cwd, project) is chantier, case
    assert is_chantier_project(repo) is chantier, case
    opts = ["--project", project] if project else []
    for kind in ("dev", "copy"):
        root = world / "with space" / kind
        skill = root / "skills" / "chantier"
        monkeypatch.setenv("CHANTIER_SKILL_DIR", str(skill))
        mode = launcher.mode(root, cwd, project)
        assert mode == ("dev" if kind == "dev" and chantier else "plugin"), (case, kind)
        assert (mode == "dev") is plugin_files.is_dev_mode(repo), (case, kind)
        assert launcher.main(["--print", *opts], root=root, cwd=cwd) == 0
        assert capsys.readouterr().out == plugin_files.cli_command(repo) + "\n", (case, kind)
        fake = Fake()
        argv = [*opts, "status", "--batch", "batch-1"]
        assert launcher.main(argv, root=root, cwd=cwd, runner=fake) == 0
        prefix = (
            ["uv", "run", "--no-sync", "--project", root.as_posix(), "chantier"]
            if mode == "dev"
            else ["uvx", "--from", root.as_posix(), "chantier", "--skill", skill.as_posix()]
        )
        assert fake.ran == [[*prefix, *argv]] and not fake.captured, (case, kind)


def test_the_argument_list_is_kept_and_skill_added_once(tmp_path: Path) -> None:
    root = tmp_path / "plug"
    skill = (root / "skills" / "chantier").as_posix()
    head = ["uvx", "--from", root.as_posix(), "chantier"]
    for argv, options in (
        (
            ["--profile", "local", "--project=x/y", "status", "--project", "z"],
            {"--profile": "local", "--project": "x/y"},
        ),
        (["--skill=/s", "watch", "--stream"], {"--skill": "/s"}),
        (["--skill", "/s", "status"], {"--skill": "/s"}),
        (["--version"], {}),
    ):
        assert launcher.root_options(argv) == options, argv
        added = [] if "--skill" in options else ["--skill", skill]
        assert launcher.command("plugin", root, argv) == [*head, *added, *argv], argv
    assert launcher.command("dev", root, ["--skill", "/s", "status"]) == [
        "uv",
        "run",
        "--no-sync",
        "--project",
        root.as_posix(),
        "chantier",
        "--skill",
        "/s",
        "status",
    ]
    assert launcher_line(root) == f'uv run --script "{(root / LAUNCHER).as_posix()}"'
    assert launcher_rule(root) == f"{launcher_line(root)} *"


def _listing(root: Path, rows: list[tuple[int, int, str]]) -> str:
    """The host's listing of `rows` (pid, parent, command line after the executable's folder)."""
    if os.name == "nt":
        venv = str(root).replace("/", "\\") + "\\.venv\\Scripts\\"
        items = [
            {"ProcessId": p, "ParentProcessId": pp, "CommandLine": f'"{venv}{line}'}
            for p, pp, line in rows
        ]
        return json.dumps(items[0] if len(items) == 1 else items)
    venv = f"{root.as_posix()}/.venv/bin/"
    lines = ["  PID  PPID COMMAND", "    5     1 /usr/bin/zsh"]
    exe = '.exe"'
    lines += [f"{p:5d} {pp:5d} {venv}{line.replace(exe, '')}" for p, pp, line in rows]
    return "\n".join(lines) + "\n"


OUTDATED = (1, "", "Would install 1 package\nThe environment is outdated; run `uv sync`\n")


@pytest.mark.parametrize(
    ("answers", "said", "result"),
    [
        ([(0, "", "")], "in sync", (0, False)),
        ([OUTDATED, "listing:", (0, "", "Installed 1 package")], "synced", (0, True)),
        (
            [OUTDATED, "listing:board"],
            "sync pending: held by PID 10 serve chantier, PID 30 serve chantier (started by webui)",
            (0, False),
        ),
        (
            [OUTDATED, "listing:", (2, "", "error: failed to remove file (os error 32)")],
            "sync pending: held by an unlisted process",
            (0, True),
        ),
        ([(2, "", "error: uv.lock needs to be updated")], "", (2, False)),
        ([OUTDATED, "listing:", (1, "", "error: no network")], "", (1, True)),
    ],
    ids=["in-sync", "synced", "held", "os-error-32", "check-fails", "sync-fails"],
)
def test_the_checked_sync_names_the_holders_and_never_syncs_past_them(
    answers: list[tuple[int, str, str] | str],
    said: str,
    result: tuple[int, bool],
    world: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    code, synced = result
    root = world / "with space" / "dev"
    board = [
        (10, 2, 'chantier.exe" --project "C:/s/projects/chantier" serve --seat abc --ui none'),
        (20, 10, 'python.exe" chantier serve'),
        (30, 2, 'chantier.exe" --project chantier serve --stop-idle'),
    ]
    filled = [
        (0, _listing(root, board if a == "listing:board" else []), "") if isinstance(a, str) else a
        for a in answers
    ]
    fake = Fake(*filled)
    project = str(world / "x" / "projects" / "chantier")
    assert launcher.main(["--sync", "--project", project], root=root, runner=fake) == code
    out = capsys.readouterr()
    assert out.out == (f"{said}\n" if said else ""), out
    if not said:
        assert filled[-1][2].strip() in out.err
    check = ["uv", "sync", "--locked", "--check", "--project", root.as_posix()]
    assert fake.captured[0] == check and not fake.ran
    sync = ["uv", "sync", "--locked", "--project", root.as_posix()]
    assert (sync in fake.captured) is synced
    assert not fake.answers


def test_the_plugin_mode_syncs_nothing_and_no_ordinary_call_syncs(
    world: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = str(world / "x" / "projects" / "studio")
    fake = Fake()
    assert (
        launcher.main(["--sync", "--project", project], world / "with space" / "dev", None, fake)
        == 0
    )
    assert capsys.readouterr().out == launcher.PLUGIN_NO_SYNC + "\n"
    calls = (("dev", "chantier"), ("copy", "chantier"), ("dev", "studio"))
    for kind, name in calls:
        argv = ["--project", str(world / "x" / "projects" / name), "status"]
        assert launcher.main(argv, world / "with space" / kind, None, fake) == 0
    assert not fake.captured and len(fake.ran) == len(calls)
    assert not any("sync" in cmd for cmd in fake.ran)
    assert capsys.readouterr().out == ""


def test_a_missing_uv_is_one_line_and_127(world: Path, capsys: pytest.CaptureFixture[str]) -> None:
    argv = ["--project", str(world / "x" / "projects" / "chantier"), "--version"]
    code = launcher.main(argv, world / "with space" / "dev", None, Fake(missing=True))
    assert code == launcher.MISSING_CODE
    out = capsys.readouterr()
    assert out.out == "" and out.err == launcher.MISSING_UV + "\n"


def _imports(path: Path) -> set[str]:
    """The modules a file imports at run time (a `TYPE_CHECKING` block is not run)."""
    found: set[str] = set()

    def walk(nodes: list[ast.stmt]) -> None:
        for node in nodes:
            if isinstance(node, ast.If) and ast.unparse(node.test) == "TYPE_CHECKING":
                walk(node.orelse)
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Import):
                    found.update(a.name for a in sub.names)
                elif isinstance(sub, ast.ImportFrom) and sub.module and not sub.level:
                    found.add(sub.module)

    walk(ast.parse(path.read_text(encoding="utf-8")).body)
    return found


def test_the_shipped_launcher_needs_no_package() -> None:
    text = (PLUGIN_ROOT / LAUNCHER).read_text(encoding="utf-8")
    block = text.split("# /// script\n", 1)[1].split("# ///\n", 1)[0]
    meta = tomllib.loads("\n".join(ln.removeprefix("#").strip() for ln in block.splitlines()))
    project = tomllib.loads((PLUGIN_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert meta["dependencies"] == []
    assert meta["requires-python"] == project["project"]["requires-python"]
    for name, extra in (("launcher.py", {"chantier.launch"}), ("launch.py", set())):
        imported = _imports(SRC / name)
        assert {m for m in imported if m.split(".")[0] not in sys.stdlib_module_names} == extra
