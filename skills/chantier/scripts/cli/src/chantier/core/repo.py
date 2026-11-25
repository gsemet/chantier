"""The repository and the planning folder: where chantier reads and writes."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

from chantier.core.errors import EXIT_USAGE, ChantierError
from chantier.core.files import read_text, rel_in
from chantier.core.git import git
from chantier.core.ids import normalize_batch
from chantier.core.planning_readings import other_readings
from chantier.store import FolderStore, PlanStore, SurfaceStore
from chantier.store.base import inside_path

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
    return inside_path(root, value, label, where)


def read_keyed(path: Path) -> dict[str, str]:
    """A tiny `key: value` reader for `checkout.yml`: `#` comments, optional quotes."""
    out: dict[str, str] = {}
    for line in read_text(path).splitlines() if path.is_file() else []:  # direct: checkout.yml
        clean = re.sub(r"(^|\s)#.*$", "", line).strip()
        if ":" in clean:
            key, value = clean.split(":", 1)
            out[key.strip()] = value.strip().strip("\"'")
    return out


PROJECT: str | None = None  # `--project`, set by the CLI before the command runs
COMMAND: str | None = None  # the command the CLI runs (as `file`, `order merged`), for a refusal


def surface_projects(root: Path) -> list[str]:
    base = root / "projects"  # direct: the surface's projects/, not the planning folder
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


GIT_LINES = 3  # `rev-parse --show-toplevel --git-dir --git-common-dir`


class SessionCheckout(NamedTuple):
    """What the session's folder is: its top, whether it is a linked worktree, whose repository
    it belongs to (`surface`, `clone`, `project`, `other`, `none`) and that owner's main
    checkout."""

    top: Path | None
    linked: bool
    owner: str
    main: Path


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
    archive_in_pr: bool = False
    command: str | None = None  # a board route's own name, for a refusal; else the CLI's
    _store: PlanStore | None = field(default=None, init=False, repr=False, compare=False)

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
        `readonly` (used by `board` and `validate`) writes nothing: no `.gitignore`."""
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
            names = (
                [] if (git_dir.parent / CHANGES).is_dir() else surface_projects(git_dir.parent)
            )  # direct: no store yet
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
        if not folder.is_dir():  # direct: no store yet
            raise ChantierError(f"no project folder {folder} in a planning surface", EXIT_USAGE)
        top = git("rev-parse", "--show-toplevel", cwd=folder, check=False)
        common = git(
            "rev-parse", "--path-format=absolute", "--git-common-dir", cwd=folder, check=False
        )
        if not top or not common:
            raise ChantierError(f"{folder} is not inside a git repository (the surface)")
        spec = read_keyed(folder / "checkout.yml")

        def resolve(v: str) -> Path:
            return (folder / v.replace("\\", "/")).resolve()

        clone = resolve(spec.get("repo") or ".repo")
        work = resolve(spec.get("worktrees") or ".worktrees")
        mine = re.search(
            r"^\W*Archive in the PR:\s*(yes|no)\b",
            read_text(folder / "project.md") if (folder / "project.md").is_file() else "",  # direct
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
            bool(mine and mine[1].lower() == "yes"),
        )

    @property
    def external(self) -> bool:
        return self.project_dir is not None

    def _external_dir(self, folder: Path | None, what: str) -> Path:
        if folder is None:
            raise ChantierError(f"no {what}: the project is not in a planning surface")
        return folder

    @property
    def project_folder(self) -> Path:
        """External: `<surface>/projects/<name>`."""
        return self._external_dir(self.project_dir, "project folder")

    @property
    def surface_root(self) -> Path:
        """External: the surface's root."""
        return self._external_dir(self.surface, "planning surface")

    @property
    def clone(self) -> Path:
        """External: the project's clone."""
        return self._external_dir(self.clone_dir, "clone")

    def missing_clone(self) -> str | None:
        """External: the line saying the project's clone is missing, None when it is there (or
        the project is not in a surface)."""
        if not self.external or self.clone.is_dir():  # direct: the clone
            return None
        text = self.project_folder / "project.md"  # direct: the project's folder
        remote = (
            re.search(r"^\W*remote\W*:?\s*(\S+)", read_text(text), re.I | re.M)
            if text.is_file()
            else None
        )
        return (
            f"no clone of the project at {self.clone.as_posix()} "
            f"(remote {remote[1] if remote else 'see project.md'}): clone it there"
        )

    @property
    def session_root(self) -> Path:
        """The folder a chantier session runs in: the project's repository, or in external mode
        the surface's checkout (the session may run in the project's clone too: see
        `session_checkout`)."""
        return self.surface or self.root

    def session_checkout(self, cwd: Path | None = None) -> SessionCheckout:
        """Which checkout the process's folder is (`cwd`, default the real working folder, never
        `CHANTIER_ROOT`): the surface's, the project's clone, the project's, or another."""
        folder = Path(cwd) if cwd is not None else Path(os.getcwd())
        lines = git(
            "rev-parse",
            "--path-format=absolute",
            "--show-toplevel",
            "--git-dir",
            "--git-common-dir",
            cwd=folder,
            check=False,
        ).splitlines()
        if len(lines) != GIT_LINES:
            return SessionCheckout(None, False, "none", self.session_root)
        top, gitdir, common = (Path(x).resolve() for x in lines)
        linked = gitdir != common
        if not self.external:
            owner, main = ("project", self.root) if common == self.git_dir else ("other", self.root)
        elif common == self.git_dir:
            owner, main = "surface", self.surface_root
        else:
            owner, main = "other", self.session_root
            if self.clone.is_dir():
                clone_common = git(
                    "rev-parse", "--path-format=absolute", "--git-common-dir",
                    cwd=self.clone, check=False,
                )  # fmt: skip
                if clone_common and Path(clone_common).resolve() == common:
                    owner, main = "clone", self.clone
        return SessionCheckout(top, linked, owner, main)

    def linked_text(self, here: SessionCheckout, top: Path | None) -> str:
        """P7's refusal for a session folder that is a linked worktree."""
        both = "the Foreman must start in the surface's main checkout or the project's clone"
        why = {
            "project": f"of {self.root}: the Foreman must start in the main checkout",
            "surface": f"of the surface {self.surface}: {both}",
            "clone": f"of the project's clone {self.clone_dir}: {both}",
        }.get(here.owner, "of another repository")
        return f"session folder {top} is a linked worktree {why}"

    @property
    def changes(self) -> Path:
        """The planning folder, the one folder chantier writes in: `.agents/changes/` of the
        project, or `changes/` of the project's folder in a surface."""
        return self.project_dir / "changes" if self.project_dir else self.root / CHANGES

    @property
    def store(self) -> PlanStore:
        """The planning folder's store, built once: no file is created by building it."""
        if self._store is None:
            self._store = (
                SurfaceStore(self.changes, self.project_folder, self.git_dir)
                if self.external
                else FolderStore(self.changes)
            )
        return self._store

    def ensure_gitignore(self) -> None:
        self.store.ensure_gitignore()

    def check_publish(self, paths: list[Path], *, config: bool = False) -> None:
        """The published paths a command is about to change (absolute, in the planning folder),
        checked by the store before any change, under the CLI's command name."""
        self.store.check_publish(
            [self.rel(p) for p in paths], config=config, command=self.command or COMMAND
        )

    def rel(self, path: Path) -> str:
        """A path in the planning folder, as the record keeps it: relative to that folder."""
        return Path(path).resolve().relative_to(self.changes.resolve()).as_posix()

    def planning_path(self, value: str | Path, label: str = "path") -> Path:
        """A CR folder or file inside the planning folder. A relative value is read from that
        folder; when that path does not exist, two more readings are tried (`_other_readings`)."""
        text = str(value).replace("\\", "/")
        try:
            path: Path | None = project_path(self.changes, text, label, "the planning folder")
        except ChantierError:
            if not self._other_readings(text):
                raise
            path = None
        if path is not None and self._exists(path):
            return path
        found = self._other_readings(text)
        if len(found) > 1:
            a, b = (self.rel(x) for x in found[:2])
            raise ChantierError(f"{value} is ambiguous: name it as `{a}` or `{b}`", EXIT_USAGE)
        return found[0] if found else project_path(self.changes, text, label, "the planning folder")

    def _exists(self, path: Path) -> bool:
        return self.store.exists(rel_in(self.store.root, path))

    def _other_readings(self, text: str) -> list[Path]:
        return other_readings(self.changes, self.surface or self.root, self._exists, text)

    @property
    def batches(self) -> Path:
        """`4-batch/`: the current batch's own files and, in its state folders, its CRs."""
        return self.changes / "4-batch"

    @property
    def worktrees(self) -> Path:
        return self.worktrees_dir or self.root.parent / f"{self.root.name}.worktrees"

    def batch_folders(self) -> list[Path]:
        """The folder of the current batch, if there is one: `[4-batch]` or `[]`."""
        found = self.store.is_file(rel_in(self.store.root, self.batches / "batch.json"))
        return [self.batches] if found else []

    def batch_ids(self) -> list[str]:
        """The id of the current batch, read from its `batch.json`, never from a folder name."""
        from chantier.core.records import read_batch_json  # noqa: PLC0415 - lazy pydantic

        return [read_batch_json(self.store, d / "batch.json").id for d in self.batch_folders()]

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
        kept = (
            int(self.store.read_text(".batch-number")) if self.store.is_file(".batch-number") else 0
        )
        recorded = (
            int(m[1])
            for n in self.store.glob(RECORDS.as_posix(), "batch-*.json")
            if (m := re.fullmatch(r"batch-(\d+)\.json", n))
        )
        live = (int(m.group()) for i in self.batch_ids() if (m := re.search(r"\d+", i)))
        return max([kept, *recorded, *live]) + 1

    def open_batches(self) -> list[str]:
        from chantier.core.records import read_batch_json  # noqa: PLC0415 - lazy pydantic

        states = [read_batch_json(self.store, d / "batch.json") for d in self.batch_folders()]
        return sorted(s.id for s in states if s.status != "paused")

    def paused_batches(self) -> list[str]:
        from chantier.core.records import read_batch_json  # noqa: PLC0415 - lazy pydantic

        states = [read_batch_json(self.store, d / "batch.json") for d in self.batch_folders()]
        return sorted(s.id for s in states if s.status == "paused")
