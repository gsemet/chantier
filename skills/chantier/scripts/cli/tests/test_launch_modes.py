"""The launch's two modes: the dev mode only in chantier's checkout for the chantier project, the
plugin mode in every other case; the shipped texts that state the rule."""

import json
import shlex
from pathlib import Path

import pytest
from conftest import PLUGIN_ROOT, SKILL

from chantier.core.repo import Repo
from chantier.launch import is_chantier_project
from chantier.plugin_files import cli_command, sync_command


def _repo_for(tmp_path: Path, cell: str) -> Repo | None:
    """A prepared session project: chantier or another, in-project or in a planning surface."""
    if cell == "none":
        return None
    if cell.startswith("surface-"):
        surface = tmp_path / f"surface-{cell}"
        folder = surface / "projects" / cell.removeprefix("surface-")
        folder.mkdir(parents=True)
        return Repo(folder / ".repo", surface / ".git", {}, folder, surface)
    root = tmp_path / f"repo-{cell}"
    root.mkdir(parents=True)
    manifests = {
        "claude": (".claude-plugin/plugin.json", "chantier"),
        "copilot": (".github/plugin/plugin.json", "chantier"),
        "other-name": (".claude-plugin/plugin.json", "studio"),
        "broken": (".claude-plugin/plugin.json", None),
    }
    if cell in manifests:
        rel, name = manifests[cell]
        (root / rel).parent.mkdir(parents=True)
        body = json.dumps({"name": name}) if name else "{not json"
        (root / rel).write_text(body, encoding="utf-8")
    return Repo(root, root / ".git", {})


# cell -> (the session's project is chantier, the `--project` folder's name in a surface)
LAUNCH_CELLS = {
    "claude": (True, None),
    "copilot": (True, None),
    "surface-chantier": (True, "chantier"),
    "plain": (False, None),
    "other-name": (False, None),
    "broken": (False, None),
    "surface-studio": (False, "studio"),
    "none": (False, None),
}


def test_one_launch_two_modes_one_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def command_for(
        root: Path, *, git: bool, sync: bool = False, repo: Repo | None = None
    ) -> str | None:
        skill = root / "skills" / "chantier"
        skill.mkdir(parents=True, exist_ok=True)
        (skill / "SKILL.md").write_text("x\n", encoding="utf-8")
        if git:
            (root / ".git").mkdir(exist_ok=True)
        monkeypatch.setenv("CHANTIER_SKILL_DIR", str(skill))
        return sync_command(repo) if sync else cli_command(repo)

    for cell, (chantier, surface) in LAUNCH_CELLS.items():
        repo = _repo_for(tmp_path, cell)
        assert is_chantier_project(repo) is chantier, cell
        option = f' --project "{repo.project_folder.as_posix()}"' if repo and surface else ""
        for git in (True, False):
            root = tmp_path / f"{'dev' if git else 'plugin'}-{cell}"
            skill = (root / "skills" / "chantier").as_posix()
            launch = command_for(root, git=git, repo=repo)
            sync = command_for(root, git=git, sync=True, repo=repo)
            if git and chantier:
                assert launch == f'uv run --no-sync --project "{root.as_posix()}" chantier{option}'
                assert sync == f'uv sync --locked --project "{root.as_posix()}"'
            else:
                assert launch == (
                    f'uvx --from "{root.as_posix()}" chantier --skill "{skill}"{option}'
                ), cell
                assert sync is None, cell
    d, p = tmp_path / "with space" / "dev", tmp_path / "with space" / "plugin"
    mine = _repo_for(tmp_path / "with space", "claude")
    uv = ["uv", "run", "--no-sync", "--project", d.as_posix(), "chantier"]
    assert shlex.split(command_for(d, git=True, repo=mine) or "") == uv
    uvx = ["uvx", "--from", p.as_posix(), "chantier", "--skill", f"{p.as_posix()}/skills/chantier"]
    assert shlex.split(command_for(p, git=False, repo=mine) or "") == uvx


def test_the_four_skills_hold_one_launch_paragraph() -> None:
    """The paragraph that defines `$CHANTIER`, the same text in the four SKILL.md files: the dev
    mode's second condition, the plugin mode for another project, and the path sentence."""
    paragraphs = []
    for name in ("chantier", "chief-of-staff", "griller", "status"):
        text = (PLUGIN_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        for form in (
            "uv run --no-sync --project",
            "uv sync --locked --project",
            "uvx --from",
            "--skill",
            ".git",
        ):
            assert form in text, f"{name}/SKILL.md does not name `{form}`"
        assert "git+https" not in text, f"{name}/SKILL.md hard-codes a ref"
        paragraphs.append(
            next(
                line
                for line in text.splitlines()
                if line.startswith("`$CHANTIER` is the CLI, one launch in two modes")
            )
        )
    assert len(set(paragraphs)) == 1, "the four SKILL.md launch paragraphs differ"
    for phrase in (
        "when the session's project is chantier",
        "projects/chantier",
        "a host's plugin copy or another project, even with the plugin loaded from chantier's "
        "checkout",
        "`<plugin root>` is written absolute, with forward slashes, quoted, the same path as P10's "
        "rule holds",
    ):
        assert phrase in paragraphs[0], phrase
    core = (SKILL / "references" / "startup-core.md").read_text(encoding="utf-8")
    assert "never in a shell variable" in " ".join(core.split())


STALE_BUILD = (
    "Another project runs chantier from its checkout in plugin mode, a build uv caches by version: "
    "it changes at each version bump. The board server, its writer and the forge hub, started "
    "from another project's session, run that build and serve every project of the surface, "
    "chantier included, with no notice while the version is equal, until the next version bump "
    "or until stopped by hand and started again from a chantier session."
)


def test_the_shipped_docs_state_the_dev_mode_rule_and_the_stale_build() -> None:
    """The dev mode only for chantier itself, in the same words, and the accepted stale build."""
    refs = SKILL / "references"
    docs = {
        "AGENTS.md": PLUGIN_ROOT / "AGENTS.md",
        "CONTRIBUTING.md": PLUGIN_ROOT / "CONTRIBUTING.md",
        "concepts.md": refs / "concepts.md",
        "claude-code.md": refs / "hosts" / "claude-code.md",
        "session-start.md": refs / "session-start.md",
    }
    for name, path in docs.items():
        text = " ".join(path.read_text(encoding="utf-8").split())
        assert "when the session's project is chantier" in text, name
        if name in ("AGENTS.md", "CONTRIBUTING.md", "session-start.md"):
            assert text.count(STALE_BUILD) == 1, name
