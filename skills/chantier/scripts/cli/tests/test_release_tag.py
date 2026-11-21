"""`just tag` and the release hand-off: ff-main, the recipe and the cards."""

import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from conftest import PLUGIN_ROOT, SKILL, load_script, shared_state
from stack_world import rewrite_paths


def _version_script() -> ModuleType:
    return load_script("version", PLUGIN_ROOT / "scripts" / "version.py")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def _commit(repo: Path, name: str, text: str, message: str) -> None:
    (repo / name).write_text(text, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", message)


def _build_ff(folder: Path) -> None:
    origin, work, other = folder / "origin.git", folder / "work", folder / "other"
    _git(folder, "init", "-q", "--bare", "-b", "main", str(origin))
    _git(folder, "clone", "-q", str(origin), str(work))
    _git(work, "checkout", "-q", "-B", "main")
    _commit(work, "uv.lock", "v1\n", "first")
    _commit(work, "a.txt", "a\n", "second")
    _git(work, "push", "-q", "origin", "main")
    _git(folder, "clone", "-q", str(origin), str(other))


@pytest.fixture(scope="session")
def ff_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A bare origin with two commits on main, a clone of it that pushed them (`work`) and
    another clone (`other`), built once per run."""
    return shared_state(tmp_path_factory, "ff-main", _build_ff)


@pytest.fixture
def ff_world(ff_template: Path, tmp_path: Path) -> tuple[Path, Path, Path]:
    """The template copied into `tmp_path`, each clone's `origin` url pointing at the copy."""
    for name in ("origin.git", "work", "other"):
        shutil.copytree(ff_template / name, tmp_path / name)
    for name in ("work", "other"):
        config = tmp_path / name / ".git" / "config"
        rewrite_paths([config], str(ff_template / "origin.git"), str(tmp_path / "origin.git"))
    return tmp_path / "origin.git", tmp_path / "work", tmp_path / "other"


@pytest.mark.parametrize(
    ("case", "code", "words"),
    [
        ("behind", 0, ("fast-forwarded to", "uv.lock changed: sync pending")),
        ("current", 0, ("already at",)),
        ("other-branch", 1, ("is on",)),
        ("dirty", 1, ("tracked changes",)),
        ("diverged", 1, ("cannot fast-forward",)),
        ("untracked", 0, ("fast-forwarded to",)),
    ],
)
def test_ff_main(
    ff_world: tuple[Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
    case: str,
    code: int,
    words: tuple[str, ...],
) -> None:
    """The shipped ff_main on prepared repositories (refusals and divergences)."""
    _, work, other = ff_world
    if case in ("behind", "untracked"):
        _commit(other, "uv.lock", "v2\n", "release")
        _git(other, "push", "-q", "origin", "main")
    elif case == "other-branch":
        _git(work, "checkout", "-q", "-b", "topic")
    elif case == "dirty":
        (work / "a.txt").write_text("changed\n", encoding="utf-8")
    elif case == "diverged":
        _commit(other, "b.txt", "b\n", "remote")
        _git(other, "push", "-q", "origin", "main")
        _commit(work, "c.txt", "c\n", "local")
    if case == "untracked":
        (work / "scratch.txt").write_text("keep\n", encoding="utf-8")
    before = _git(work, "rev-parse", "HEAD")
    assert _version_script().ff_main(work) == code
    out = capsys.readouterr()
    text = out.out + out.err
    for word in words:
        assert word in text, text
    after = _git(work, "rev-parse", "HEAD")
    if case in ("behind", "untracked"):
        assert after == _git(work, "rev-parse", "origin/main") != before
    else:
        assert after == before
    if case == "dirty":
        assert (work / "a.txt").read_text(encoding="utf-8") == "changed\n"
    if case == "untracked":
        assert (work / "scratch.txt").read_text(encoding="utf-8") == "keep\n"


def test_ff_main_command_runs_the_shipped_script(ff_world: tuple[Path, Path, Path]) -> None:
    """`version.py ff-main` itself, as the recipe runs it, from a copy in a prepared repo."""
    _, work, _ = ff_world
    (work / "scripts").mkdir()
    shutil.copy(PLUGIN_ROOT / "scripts" / "version.py", work / "scripts" / "version.py")
    done = subprocess.run(
        [sys.executable, str(work / "scripts" / "version.py"), "ff-main"],
        cwd=work,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert "main checkout: already at" in done.stdout


def test_tag_recipe_and_release_cards() -> None:
    """`just tag` fast-forwards first; the driver hand-back and foreman take-back match."""
    recipe = re.search(
        r"^tag:\r?\n((?:    .*\r?\n)+)", (PLUGIN_ROOT / "justfile").read_text("utf-8"), re.M
    )
    assert recipe is not None
    lines = [line.strip() for line in recipe.group(1).splitlines()]
    assert lines[0] == "uv run --script scripts/version.py ff-main"
    assert lines[1] == "uv run --script scripts/version.py check-tag"
    refs = SKILL / "references"
    driver = " ".join((refs / "driver.md").read_text("utf-8").split())
    foreman = " ".join((refs / "foreman.md").read_text("utf-8").split())
    section = driver.split("## Release driver", 1)[1]
    assert "blocked waits: the steering session runs" in section
    assert "tag done: steering session" in foreman
