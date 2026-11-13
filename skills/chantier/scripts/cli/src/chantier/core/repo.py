"""The repository and the planning folder: where chantier reads and writes."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.files import ensure_gitignore, read_text
from chantier.core.git import git
from chantier.core.records import normalize_batch, read_batch_json

CHANGES = Path(".agents") / "changes"
RECORDS = Path("5-archives") / "batches"  # each batch's `batch-NN.json` and `batch-NN.md`


# What `chantier open` records in batch.json (SETTINGS: the branch and the remote the Chief of
# Staff read in the project's AGENTS.md), and the fixed rules every batch runs on.
DEFAULT_CONFIG = {
    "default_branch": None,
    "remote": "origin",
    "first_cr_number": 101,
    "max_rounds": 3,
}


SETTINGS = ("default_branch", "remote", "max_rounds")


def project_path(
    root: Path, value: str | Path, label: str = "path", where: str = "the repository"
) -> Path:
    path = Path(value).expanduser()
    path = (path if path.is_absolute() else root / path).resolve()
    root = root.resolve()
    if path == root or not path.is_relative_to(root):
        raise ChantierError(f"{label} must be inside {where}: {value}", EXIT_USAGE)
    return path


def read_keyed(path: Path) -> dict[str, str]:
    """A tiny `key: value` reader for `checkout.yml`: `#` comments, optional quotes."""
    out: dict[str, str] = {}
    for line in read_text(path).splitlines() if path.is_file() else []:
        clean = re.sub(r"(^|\s)#.*$", "", line).strip()
        if ":" in clean:
            key, value = clean.split(":", 1)
            out[key.strip()] = value.strip().strip("\"'")
    return out


PROJECT: str | None = None  # `--project`, set by the CLI before the command runs


def surface_projects(root: Path) -> list[str]:
    base = root / "projects"
    return (
        sorted(
            d.name
            for d in base.iterdir()
            if (d / "checkout.yml").is_file() or (d / "changes").is_dir()
        )
        if base.is_dir()
        else []
    )


class SurfaceChoice(ChantierError):
    """The folder is a planning surface with several projects and none was named."""

    def __init__(self, names: list[str]):
        super().__init__(
            f"this is a planning surface with projects {', '.join(names)}: pass --project <name>"
        )
        self.names = names


@dataclass
class Repo:
    """The main repository, even when called from a CR worktree."""

    root: Path  # the project's code repository (in external mode: its clone)
    git_dir: Path  # of the session's repository: the project's, or the surface's
    config: dict[str, Any]
    project_dir: Path | None = None  # external: `<surface>/projects/<name>`
    surface: Path | None = None  # external: the surface's root
    clone_dir: Path | None = None
    worktrees_dir: Path | None = None
    archive_in_pr: bool = True

    @classmethod
    def find(
        cls,
        cwd: Path | None = None,
        project: str | None = None,
        readonly: bool = False,
    ) -> Repo:
        """`--project` names the project's folder in a planning surface (external mode); else a
        git root that is a surface, with one project, is taken as that. Otherwise in-project.
        `CHANTIER_ROOT` wins over the working folder, so agents elsewhere reach the same state.
        `readonly` (used by `board` only) writes nothing: no `.gitignore`. The conversion of an
        old tree is not done here but by `open_repo` (`lifecycle.convert`)."""
        cwd = Path(cwd or os.environ.get("CHANTIER_ROOT") or os.getcwd())
        project = project or PROJECT
        if project:
            repo = cls._external(cwd, project)
        else:
            try:
                common = git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd)
            except ChantierError as e:
                raise ChantierError(f"not inside a git repository: {cwd}") from e
            git_dir = Path(common).resolve()
            names = [] if (git_dir.parent / CHANGES).is_dir() else surface_projects(git_dir.parent)
            if len(names) > 1:
                raise SurfaceChoice(names)
            if names:
                repo = cls._external(cwd, str(git_dir.parent / "projects" / names[0]))
            else:
                repo = cls(git_dir.parent, git_dir, json.loads(json.dumps(DEFAULT_CONFIG)))
        if readonly:
            return repo
        repo.ensure_gitignore()
        return repo

    @classmethod
    def _external(cls, cwd: Path, project: str) -> Repo:
        """The project's folder in the surface: absolute, or a bare name inside the surface."""
        folder = Path(project).expanduser()
        if not folder.is_absolute():
            if len(folder.parts) == 1:  # a bare name, in the surface the session is in
                top = git("rev-parse", "--show-toplevel", cwd=cwd, check=False)
                folder = Path(top or cwd) / "projects" / folder
            else:
                folder = cwd / folder
        folder = folder.resolve()
        if not folder.is_dir():
            raise ChantierError(f"no project folder {folder} in a planning surface", EXIT_USAGE)
        top = git("rev-parse", "--show-toplevel", cwd=folder, check=False)
        common = git(
            "rev-parse", "--path-format=absolute", "--git-common-dir", cwd=folder, check=False
        )
        if not top or not common:
            raise ChantierError(f"{folder} is not inside a git repository (the surface)")
        spec = read_keyed(folder / "checkout.yml")

        def resolve(v):
            return (folder / v.replace("\\", "/")).resolve()

        clone = resolve(spec.get("repo") or ".repo")
        work = resolve(spec.get("worktrees") or ".worktrees")
        mine = re.search(
            r"^\W*Archive in the PR:\s*(yes|no)\b",
            read_text(folder / "project.md") if (folder / "project.md").is_file() else "",
            re.M | re.I,
        )
        return cls(
            clone,
            Path(common).resolve(),
            json.loads(json.dumps(DEFAULT_CONFIG)),
            folder,
            Path(top).resolve(),
            clone,
            work,
            not (mine and mine[1].lower() == "no"),
        )

    @property
    def external(self) -> bool:
        return self.project_dir is not None

    @property
    def session_root(self) -> Path:
        """The folder a chantier session runs in: the project's repository, or the surface."""
        return self.surface or self.root

    @property
    def changes(self) -> Path:
        """The planning folder, the one folder chantier writes in: `.agents/changes/` of the
        project, or `changes/` of the project's folder in a surface."""
        return self.project_dir / "changes" if self.project_dir else self.root / CHANGES

    def ensure_gitignore(self) -> None:
        ensure_gitignore(self.changes)

    def rel(self, path: Path) -> str:
        """A path in the planning folder, as the record keeps it: relative to that folder."""
        return Path(path).resolve().relative_to(self.changes.resolve()).as_posix()

    def planning_path(self, value: str | Path, label: str = "path") -> Path:
        """A CR folder or file inside the planning folder. A relative value is read from that
        folder; the older record's form, `.agents/changes/...`, still reads."""
        text = str(value).replace("\\", "/")
        if text.startswith(".agents/changes/"):
            text = text[len(".agents/changes/") :]
        return project_path(self.changes, text, label, "the planning folder")

    @property
    def batches(self) -> Path:
        """`4-batch/`: the current batch's own files and, in its state folders, its CRs."""
        return self.changes / "4-batch"

    @property
    def worktrees(self) -> Path:
        return self.worktrees_dir or self.root.parent / f"{self.root.name}.worktrees"

    def batch_folders(self) -> list[Path]:
        """The folder of the current batch, if there is one: `[4-batch]` or `[]`."""
        return [self.batches] if (self.batches / "batch.json").is_file() else []

    def batch_ids(self) -> list[str]:
        """The id of the current batch, read from its `batch.json`, never from a folder name."""
        return [read_batch_json(d / "batch.json")["id"] for d in self.batch_folders()]

    def batch_dir(self, batch: str) -> Path:
        """`--batch` is a batch's number, `4` or `batch-04`: it must be the current batch's, whose
        folder is `4-batch/`; any other number is unknown."""
        if normalize_batch(batch) not in self.batch_ids():
            raise ChantierError(f"unknown batch {normalize_batch(batch)}")
        return self.batches

    def next_batch_number(self) -> int:
        """The highest of the records in `5-archives/batches/`, the live batch and
        `.batch-number`, plus one: numbers keep rising after a batch's folder is deleted, on every
        machine that has the records."""
        last = self.changes / ".batch-number"
        kept = int(read_text(last)) if last.is_file() else 0
        recorded = (
            int(m[1])
            for p in (self.changes / RECORDS).glob("batch-*.json")
            if (m := re.fullmatch(r"batch-(\d+)\.json", p.name))
        )
        live = (int(m.group()) for i in self.batch_ids() if (m := re.search(r"\d+", i)))
        return max([kept, *recorded, *live]) + 1

    def open_batches(self) -> list[str]:
        states = [read_batch_json(d / "batch.json") for d in self.batch_folders()]
        return sorted(s["id"] for s in states if s.get("status") != "paused")
