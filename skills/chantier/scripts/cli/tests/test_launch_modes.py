"""The launch's two modes: the dev mode only in chantier's checkout for the chantier project, the
plugin mode in every other case; the shipped texts that state the rule."""

import json
import shlex
from pathlib import Path

import pytest
from conftest import PLUGIN_ROOT, SKILL

from chantier.core.repo import Repo
from chantier.host_rows import load_rows
from chantier.launch import is_chantier_project
from chantier.plugin_files import cli_command, sync_check_command, sync_command


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
        root: Path,
        *,
        git: bool,
        sync: bool = False,
        check: bool = False,
        repo: Repo | None = None,
    ) -> str | None:
        skill = root / "skills" / "chantier"
        skill.mkdir(parents=True, exist_ok=True)
        (skill / "SKILL.md").write_text("x\n", encoding="utf-8")
        if git:
            (root / ".git").mkdir(exist_ok=True)
        monkeypatch.setenv("CHANTIER_SKILL_DIR", str(skill))
        if check:
            return sync_check_command(repo)
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
            check = command_for(root, git=git, check=True, repo=repo)
            if git and chantier:
                assert launch == f'uv run --no-sync --project "{root.as_posix()}" chantier{option}'
                assert sync == f'uv sync --locked --project "{root.as_posix()}"'
                assert check == f'uv sync --locked --check --project "{root.as_posix()}"'
            else:
                assert launch == (
                    f'uvx --from "{root.as_posix()}" chantier --skill "{skill}"{option}'
                ), cell
                assert sync is None and check is None, cell
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
    sync = (SKILL / "references" / "sync-checkout.md").read_text(encoding="utf-8")
    assert 'uv sync --locked --project "<plugin root>"' in sync
    for topic in ("worker-shell.md", "session-shell-p1.md"):
        assert "never in a shell variable" in _flat(SKILL / "references" / "topics" / topic), topic


STALE_BUILD = (
    "Another project runs chantier from its checkout in plugin mode, a build uv caches by version: "
    "it changes at each version bump. The board server, its writer and the forge hub, started "
    "from another project's session, run that build and serve every project of the surface, "
    "chantier included, with no notice while the version is equal, until the next version bump "
    "or until replaced; while a chantier dev session holds its seat (its `seat.json` names a "
    "`build`, its watcher's lock is held) its checkout's build serves the surface and other "
    "projects' watchers start no board, and a board of another build is replaced by `serve "
    "--restart` on the user's yes; a chantier session in the dev mode is told, on `status`, the "
    "watcher's start line and `serve`, when the board runs another build than its checkout's, "
    "even at the same version string (`server.json` records each entry's `source`)."
)


def test_the_shipped_docs_state_the_dev_mode_rule_and_the_stale_build() -> None:
    """The dev mode only for chantier itself, in the same words, and the accepted stale build."""
    refs = SKILL / "references"
    for path in (
        PLUGIN_ROOT / "AGENTS.md",
        PLUGIN_ROOT / "CONTRIBUTING.md",
        SKILL / "SKILL.md",
        refs / "hosts" / "claude-code.md",
    ):
        assert "when the session's project is chantier" in _flat(path), path.name
    for name in ("AGENTS.md", "CONTRIBUTING.md"):
        assert _flat(PLUGIN_ROOT / name).count(STALE_BUILD) == 1, name
    surface = _flat(refs / "topics" / "session-start-surface-p2.md")
    assert "the session's project being chantier" in surface
    assert (
        "A board started from another project's session runs that build for every project, "
        "chantier too, with no notice at equal versions."
    ) in _flat(refs / "topics" / "board-restart.md")


def _flat(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


SYNC_PARAGRAPH_PHRASES = (
    "its mode checked once",
    'uv sync --locked --check --project "<plugin root>"',
    "The environment is outdated",
    "Never stop or kill",
    "sync pending: held by",
    "3 minutes",
    "but a reload",
    "`sync-checkout.md`",
    "Any failure of the sync or of `$CHANTIER`, in either mode, at any call, is a stop: report "
    "its exact error (floor 4), except a sync held as above (`sync pending`).",
)

SYNC_SECTION_PHRASES = (
    "Name the holders before syncing",
    "never stop or kill",
    "sync pending: held by",
    "but a reload",
)

SYNC_OFFER_PHRASES = (
    "stop them on the user's yes",
    "own board or watcher",
    "Anything else is not own.",
    "unless another session's watcher takes the hub",
    "no third line",
    "the yes covers the restart",
)


def test_the_four_skills_hold_the_checked_sync_that_waits_and_never_kills() -> None:
    for name in ("chantier", "chief-of-staff", "griller", "status"):
        text = (PLUGIN_ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        paragraph = " ".join(
            next(ln for ln in text.splitlines() if ln.startswith("`$CHANTIER` is the CLI")).split()
        )
        for phrase in SYNC_PARAGRAPH_PHRASES:
            assert phrase in paragraph, f"{name}/SKILL.md lacks: {phrase}"
        assert "once, before the first" not in paragraph, name
    refs = SKILL / "references"
    section = _flat(refs / "sync-checkout.md")
    for phrase in SYNC_SECTION_PHRASES:
        assert phrase in section, f"sync-checkout.md lacks: {phrase}"
    offer = " ".join(_flat(refs / "topics" / f"sync-offer-p{n}.md") for n in (1, 2))
    for phrase in SYNC_OFFER_PHRASES:
        assert phrase in offer, f"sync-offer lacks: {phrase}"


def test_the_cards_and_hosts_state_the_exception_the_row_and_the_for_you_item() -> None:
    refs = SKILL / "references"
    assert "4. A CLI that cannot run is a stop." in _flat(refs / "floor.md")
    held = _flat(refs / "sync-checkout.md")
    assert "go on unsynced, saying `sync pending: held by <holders>`" in held
    for host in ("claude", "copilot"):
        row = next(r for r in load_rows(host) if r.capability == "name-env-holders")
        means = " ".join(row.means)
        assert "Get-CimInstance Win32_Process" in means, host
        assert 'grep -F "<plugin root>/.venv/"' in means, host
        assert host != "copilot" or row.mark == "untested"
    own = _flat(refs / "topics" / "sync-offer-p1.md")
    assert "`--seat <this session's id>`" in own and "`board already running`" in own
    assert "stop none but your own board and watcher, on the user's yes" in _flat(
        refs / "topics" / "session-start-surface-p2.md"
    )
    notes = _flat(refs / "topics" / "status-notes-more.md")
    for phrase in (
        "Not a **For you** item",
        "except a sync pending over 3 minutes",
        "until answered",
        '"a later yes still counts"',
    ):
        assert phrase in notes, phrase


def test_the_restart_topic_tells_the_chief_of_staff_to_pass_on_a_foreign_build() -> None:
    """The foreign-build lines bring one offer of the restart."""
    text = _flat(SKILL / "references" / "topics" / "board-restart.md")
    assert (
        "On `board runs another build`, `board runs a build of chantier <v> older than this notice`"
    ) in text
    assert "offer the restart once, in one line with its cost" in text
