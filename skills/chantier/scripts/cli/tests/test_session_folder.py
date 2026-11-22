"""The session folder beside a planning surface: the surface's checkout or the project's clone
passes P6 and P7, a linked worktree of either fails P7, and every git read goes to the right
repository whatever the folder the session runs in."""

import json
from pathlib import Path

import pytest
from conftest import Chantier, Surface, sh

from chantier.commands.allow_samples import filled_allow
from chantier.core.errors import EXIT_PRECONDITION

BOTH = "the Foreman must start in the surface's main checkout or the project's clone"


@pytest.fixture(autouse=True)
def _claude(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHANTIER_HOST", "claude")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "claude-desktop")


def _lines(chantier: Chantier, surface: Surface, *args: str) -> tuple[int, dict[str, str]]:
    code, out, _ = chantier("--project", surface.project, *args)
    return code, {ln.split()[0]: ln for ln in out if ln[:1] == "P" and ln[1:2].isdigit()}


def _beside(surface: Surface, repo: Path) -> Surface:
    """The `beside` layout: the clone is the `repo` fixture's folder, beside the surface."""
    surface.clone.rename(repo.parent / "gone")  # `.repo` removed from the surface
    (surface.project / "checkout.yml").write_text(
        "repo: ../../../proj\nworktrees: ../../../wt\n", encoding="utf-8"
    )
    return surface._replace(clone=repo.resolve())


def _worktree(of: Path, where: Path, branch: str) -> Path:
    sh("git", "worktree", "add", "-q", str(where), "-b", branch, cwd=of)
    return where.resolve()


def _world(
    layout: str, surface: Surface, repo: Path, tmp_path: Path, folder: str
) -> tuple[Surface, Path]:
    if layout == "beside":
        surface = _beside(surface, repo)
    cwd = {
        "surface": lambda: surface.root,
        "clone": lambda: surface.clone,
        "surface-worktree": lambda: _worktree(surface.root, tmp_path / "swt", "s"),
        "clone-worktree": lambda: _worktree(surface.clone, tmp_path / "cwt", "c"),
        "other": lambda: _other(tmp_path),
    }[folder]()
    return surface, cwd


def _other(tmp_path: Path) -> Path:
    other = tmp_path / "other"
    sh("git", "init", "--quiet", "-b", "main", str(other))
    return other.resolve()


@pytest.mark.parametrize(
    "case",
    [
        (layout, folder)
        for layout in ("nested", "beside")
        for folder in ("surface", "clone", "surface-worktree", "clone-worktree", "other")
    ],
    ids="-".join,
)
def test_p6_and_p7_accept_both_main_checkouts_and_refuse_the_rest(
    surface: Surface,
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    case: tuple[str, str],
) -> None:
    layout, folder = case
    tmp_path = repo.parent
    surface, cwd = _world(layout, surface, repo, tmp_path, folder)
    monkeypatch.chdir(cwd)
    code, p = _lines(chantier, surface, "preflight")
    neither = (
        f"P6 FAIL session folder {cwd} is neither the surface's checkout {surface.root} "
        f"nor the project's clone {surface.clone}: start the session in one of them"
    )
    expected = {
        "surface": (
            f"P6 ok   in the main checkout of the surface {surface.root.name}",
            "P7 ok   not a linked worktree",
        ),
        "clone": (
            f"P6 ok   in the project's main checkout {surface.clone}; the plan is in the "
            f"surface {surface.root}",
            "P7 ok   not a linked worktree",
        ),
        "surface-worktree": (
            neither,
            f"P7 FAIL session folder {cwd} is a linked worktree of the surface "
            f"{surface.root}: {BOTH}",
        ),
        "clone-worktree": (
            neither,
            f"P7 FAIL session folder {cwd} is a linked worktree of the project's clone "
            f"{surface.clone}: {BOTH}",
        ),
        "other": (neither, "P7 ok   not a linked worktree"),
    }[folder]
    assert p["P6"] == expected[0]
    assert p["P7"] == expected[1]
    assert code == (0 if folder in ("surface", "clone") else EXIT_PRECONDITION)


def test_in_project_keeps_its_texts(
    repo: Path, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _, out, _ = chantier("preflight")
    assert f"P6 ok   in the main checkout of {repo.name}" in out
    assert "P7 ok   not a linked worktree" in out
    wt = _worktree(repo, tmp_path / "wt", "w")
    monkeypatch.chdir(wt)
    code, out, _ = chantier("preflight")
    assert code == EXIT_PRECONDITION
    assert (
        f"P7 FAIL session folder {wt} is a linked worktree of {repo.resolve()}: the Foreman "
        "must start in the main checkout"
    ) in out


@pytest.mark.parametrize(
    "case",
    [
        ("side", "main", "P11 warn the surface is on side, its default branch is main: "),
        ("main", "feature", "P11 ok   the surface is on its default branch (main)"),
    ],
    ids=["surface-off-main", "clone-off-main"],
)
def test_p11_reads_the_surface_whatever_the_session_folder(
    surface: Surface,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    case: tuple[str, str, str],
) -> None:
    surface_on, clone_on, expected = case
    sh("git", "update-ref", "refs/remotes/origin/main", "HEAD", cwd=surface.root)
    sh(
        "git",
        "symbolic-ref",
        "refs/remotes/origin/HEAD",
        "refs/remotes/origin/main",
        cwd=surface.root,
    )
    if surface_on != "main":
        sh("git", "checkout", "-q", "-b", surface_on, cwd=surface.root)
    if clone_on != "main":
        sh("git", "checkout", "-q", "-b", clone_on, cwd=surface.clone)
    monkeypatch.chdir(surface.clone)
    _, p = _lines(chantier, surface, "preflight")
    assert p["P11"].startswith(expected)


@pytest.mark.parametrize("folder", ["clone", "surface"])
def test_p10_reads_the_session_folders_settings(
    surface: Surface, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, folder: str
) -> None:
    where = surface.clone if folder == "clone" else surface.root
    (where / ".claude").mkdir()
    (where / ".claude" / "settings.local.json").write_text(
        json.dumps({"permissions": {"allow": list(filled_allow())}}), encoding="utf-8"
    )
    monkeypatch.chdir(where)
    _, p = _lines(chantier, surface, "preflight")
    assert p["P10"].startswith("P10 ok"), p["P10"]


def test_init_from_the_clone_is_not_refused_but_from_its_worktree_is(
    surface: Surface, chantier: Chantier, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(surface.clone)
    assert chantier("--project", surface.project, "init")[0] == 0
    wt = _worktree(surface.clone, tmp_path / "cwt", "c")
    monkeypatch.chdir(wt)
    code, _, err = chantier("--project", surface.project, "init")
    assert code == EXIT_PRECONDITION
    assert (
        f"session folder {wt} is a linked worktree of the project's clone {surface.clone}: {BOTH}"
        in err
    )
