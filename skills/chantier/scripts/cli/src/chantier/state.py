"""Repository paths and the locked batch state.

Everything chantier keeps lives in `.agents/changes/` at the repository's root, as plain JSON and
Markdown: the stage folders, and in `4-batch/` the project's one current batch: its own files
(`batch.json` holds the batch's limits and what the Chief of Staff passed to `open`) beside the
state folders `1-pending/`, `2-actives/` and `3-done/` that hold its CRs. The batch keeps its id,
`batch-<n>`, in `batch.json`; its folder carries no number.

Only this module writes `batch.json` and `events.jsonl`: under an exclusive lock (`fcntl` on POSIX,
`msvcrt` on Windows), by atomic rename, and every change appends one event.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

EXIT_USAGE, EXIT_PRECONDITION, EXIT_CONFLICT, EXIT_EXTERNAL, EXIT_BUDGET = 1, 2, 3, 4, 5
LOCK_TIMEOUT_S = 30


def _try_lock(f) -> bool:
    """Take the exclusive lock on an open lock file without waiting; False if another holds it."""
    if sys.platform == "win32":
        f.seek(0)
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    return True


def _unlock(f) -> None:
    if sys.platform == "win32":
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(f, fcntl.LOCK_UN)


def _retry(op, *args):
    """Windows refuses to open a file while another process renames over it, and to rename over
    one another process has open: both are brief, so try again for up to a second."""
    for _ in range(100):
        try:
            return op(*args)
        except PermissionError:
            if sys.platform != "win32":
                raise
            time.sleep(0.01)
    return op(*args)


def _read_json(path: Path):
    return json.loads(_retry(path.read_text, "utf-8"))


def read_batch_json(path: Path) -> dict:
    """A `batch.json`, in today's words. Batches written before the words running and paused
    recorded `status: "open"` and `status: "landed"` (with a `landed` time): read them as running
    and paused. Nothing is written here; the next write through `Batch` stores the new words."""
    data = _read_json(path)
    if data.get("status") == "landed":
        data["status"] = "paused"
        if "landed" in data:
            data["paused"] = data.pop("landed")
    elif data.get("status") == "open":
        data["status"] = "running"
    return data


def write_file(path: Path, text: str) -> None:
    """Write by atomic rename, so a reader never sees half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    _retry(os.replace, tmp, path)


def write_json(path: Path, data) -> None:
    write_file(path, json.dumps(data, indent=2) + "\n")


CHANGES = Path(".agents") / "changes"
# What `chantier open` records in batch.json (SETTINGS: the branch and the remote the Chief of
# Staff read in the project's AGENTS.md), and the fixed rules every batch runs on.
DEFAULT_CONFIG = {
    "default_branch": None,
    "remote": "origin",
    "first_cr_number": 101,
    "max_rounds": 3,
}
SETTINGS = ("default_branch", "remote", "max_rounds")

# The statuses a live Driver owns; the others are queued, ready, blocked, cancelled, merged.
# A batch is running or paused (a closed batch has no folder).
LIVE = {"working"}


class ChantierError(Exception):
    """An error with the exit code the CLI must return."""

    def __init__(self, message: str, code: int = EXIT_PRECONDITION):
        super().__init__(message)
        self.code = code


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp() -> str:
    """The date in an archive's name: its order is the date's."""
    return datetime.now(timezone.utc).strftime("%y%m%d-%H%M")


def chief_sessions(d: dict) -> list[str]:
    """Every session that was the batch's Chief of Staff, the current one last; an old batch has
    only `chief_transcript`."""
    return list(d.get("chief_transcripts") or ([d["chief_transcript"]] if d.get("chief_transcript")
                                               else []))


def round_limit(d: dict, c: dict) -> int:
    """The batch's limit, or the one the user granted this CR (`order rounds`)."""
    return c.get("rounds") or d.get("settings", {}).get("max_rounds", 3)


def read_events(folder: Path) -> list[dict]:
    """The batch's `events.jsonl`, in order; a half-written last line is skipped."""
    path = folder / "events.jsonl"
    out = []
    for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else []:
        try:
            out.append(json.loads(line))
        except ValueError:  # the last line of a process killed while appending
            continue
    return out


def age_minutes(ts: str | None) -> float | None:
    if not ts:
        return None
    then = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - then).total_seconds() / 60


def git(*args: str, cwd: Path | str | None = None, check: bool = True) -> str:
    env = {**os.environ, "GIT_EDITOR": "true", "GIT_PAGER": "cat", "GIT_TERMINAL_PROMPT": "0"}
    p = subprocess.run(["git", "--no-pager", *args], cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    if check and p.returncode != 0:
        raise ChantierError(f"git {' '.join(args)}: {p.stderr.strip() or p.stdout.strip()}",
                       EXIT_EXTERNAL)
    return p.stdout.strip()


def default_branch(root: Path, remote: str = "origin") -> str | None:
    """The remote's recorded HEAD branch, if Git knows it."""
    head = git("symbolic-ref", "--short", f"refs/remotes/{remote}/HEAD", cwd=root, check=False)
    return head.removeprefix(f"{remote}/") if head else None


def project_path(root: Path, value: str | Path, label: str = "path",
                 where: str = "the repository") -> Path:
    path = Path(value).expanduser()
    path = (path if path.is_absolute() else root / path).resolve()
    root = root.resolve()
    if path == root or not path.is_relative_to(root):
        raise ChantierError(f"{label} must be inside {where}: {value}", EXIT_USAGE)
    return path


# The files that stay on the steering machine, never published by the surface's git: a running
# batch's own files, the locks, the seat, the detailed logs.
IGNORED = ("STATUS.md", "STATUS.json", ".lock", ".lifecycle.lock", ".long-gate.lock",
           ".batch-number", ".closing-*", "seat.json", "/4-batch/batch.json",
           "/4-batch/events.jsonl", "/4-batch/brief.md", "work/gates/", "*.log", "*.tmp")
_IGNORE_HEAD = "# chantier: local files of a running batch and detailed logs, never published"
_ignored_done: set[str] = set()


def ensure_gitignore(changes: Path) -> None:
    """Write or complete the planning folder's own `.gitignore`, before any local file exists."""
    key = str(changes)
    if key in _ignored_done or not changes.is_dir():
        return
    path = changes / ".gitignore"
    have = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    missing = [e for e in IGNORED if e not in have]
    if missing:
        add = ([] if _IGNORE_HEAD in have else [_IGNORE_HEAD]) + missing
        write_file(path, "\n".join([*have, *add]) + "\n")
    _ignored_done.add(key)


def read_keyed(path: Path) -> dict[str, str]:
    """A tiny `key: value` reader for `checkout.yml`: `#` comments, optional quotes."""
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines() if path.is_file() else []:
        line = re.sub(r"(^|\s)#.*$", "", line).strip()
        if ":" in line:
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip().strip("\"'")
    return out


PROJECT: str | None = None  # `--project`, set by the CLI before the command runs


def surface_projects(root: Path) -> list[str]:
    base = root / "projects"
    return sorted(d.name for d in base.iterdir() if (d / "checkout.yml").is_file()
                  or (d / "changes").is_dir()) if base.is_dir() else []


class SurfaceChoice(ChantierError):
    """The folder is a planning surface with several projects and none was named."""

    def __init__(self, names: list[str]):
        super().__init__(f"this is a planning surface with projects {', '.join(names)}: "
                         "pass --project <name>")
        self.names = names


def move_directory(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise ChantierError(f"CR folder not found: {source}", EXIT_USAGE)
    if destination.exists() or destination.is_symlink():
        raise ChantierError(f"refusing to overwrite CR folder: {destination}", EXIT_CONFLICT)
    if source == destination or source in destination.parents:
        raise ChantierError(f"invalid CR move: {source} to {destination}", EXIT_USAGE)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        _retry(source.rename, destination)
    except OSError as e:
        raise ChantierError(f"cannot move CR folder {source} to {destination}: {e}",
                            EXIT_EXTERNAL) from e


def apply_batch_settings(repo: "Repo", data: dict) -> None:
    """A batch runs on the settings it was opened with, whatever changed since."""
    settings = data.get("settings")
    if settings is None:
        return
    if not isinstance(settings, dict):
        raise ChantierError("invalid batch settings; refusing to run")
    for key in SETTINGS:
        if key in settings:
            repo.config[key] = settings[key]


@dataclass
class Repo:
    """The main repository, even when called from a CR worktree."""

    root: Path  # the project's code repository (in external mode: its clone)
    git_dir: Path  # of the session's repository: the project's, or the surface's
    config: dict
    project_dir: Path | None = None  # external: `<surface>/projects/<name>`
    surface: Path | None = None  # external: the surface's root
    clone_dir: Path | None = None
    worktrees_dir: Path | None = None
    archive_in_pr: bool = True

    @classmethod
    def find(cls, cwd: Path | None = None, convert: bool = True,
             project: str | None = None, readonly: bool = False) -> "Repo":
        """`--project` names the project's folder in a planning surface (external mode); else a
        git root that is a surface, with one project, is taken as that. Otherwise in-project.
        `CHANTIER_ROOT` wins over the working folder, so agents elsewhere reach the same state.
        The first command run after an update converts a tree of the old layout, once, before
        anything else (`convert_old_tree`); `init` converts after its own checks.
        `readonly` (used by `board` only) skips both writes: no `.gitignore`, no conversion."""
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
        if convert:
            from .lifecycle import convert_old_tree  # avoid an import cycle
            convert_old_tree(repo)
        return repo

    @classmethod
    def _external(cls, cwd: Path, project: str) -> "Repo":
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
        common = git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=folder,
                     check=False)
        if not top or not common:
            raise ChantierError(f"{folder} is not inside a git repository (the surface)")
        spec = read_keyed(folder / "checkout.yml")
        resolve = lambda v: (folder / v.replace("\\", "/")).resolve()  # noqa: E731
        clone = resolve(spec.get("repo") or ".repo")
        work = resolve(spec.get("worktrees") or ".worktrees")
        mine = re.search(r"^\W*Archive in the PR:\s*(yes|no)\b",
                         (folder / "project.md").read_text(encoding="utf-8")
                         if (folder / "project.md").is_file() else "", re.M | re.I)
        return cls(clone, Path(common).resolve(), json.loads(json.dumps(DEFAULT_CONFIG)),
                   folder, Path(top).resolve(), clone, work,
                   not (mine and mine[1].lower() == "no"))

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
            text = text[len(".agents/changes/"):]
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
        """Numbers keep rising after a batch's folder is deleted: the last one is on file."""
        last = self.changes / ".batch-number"
        kept = int(last.read_text(encoding="utf-8")) if last.is_file() else 0
        return max([kept, *(int(m.group()) for i in self.batch_ids()
                          if (m := re.search(r"\d+", i)))]) + 1

    def open_batches(self) -> list[str]:
        states = [read_batch_json(d / "batch.json") for d in self.batch_folders()]
        return sorted(s["id"] for s in states if s.get("status") != "paused")


class Batch:
    """A locked, read-modify-write view of one batch. Use as a context manager."""

    def __init__(self, repo: Repo, batch_id: str | None, actor: str = "cli",
                 create: dict | None = None):
        """`create` opens a new batch: its number is the next, its id `batch-<n>` on two digits."""
        self._create = create
        self._number = None
        if create is not None:
            self._number = repo.next_batch_number()
            batch_id = f"batch-{self._number:02d}"
            create["id"] = batch_id
        else:
            batch_id = normalize_batch(batch_id)
        self.repo, self.id, self.actor = repo, batch_id, actor
        self.dir = repo.batches
        self._lock = None
        self.data: dict = {}
        self._events: list[dict] = []
        self._moves: list[tuple[Path, Path]] = []

    def __enter__(self) -> "Batch":
        if self._create is None and self.id not in self.repo.batch_ids():
            raise ChantierError(f"unknown batch {self.id}")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.repo.ensure_gitignore()
        self._lock = open(self.dir / ".lock", "a+")
        acquired, entered = False, False
        try:
            deadline = time.monotonic() + LOCK_TIMEOUT_S
            while not _try_lock(self._lock):
                if time.monotonic() > deadline:
                    raise ChantierError(f"batch {self.id} is locked for over {LOCK_TIMEOUT_S} s")
                time.sleep(0.05)
            acquired = True
            path = self.dir / "batch.json"
            if path.exists():
                if self._create is not None:
                    raise ChantierError(f"batch {self.id} already exists")
                self.data = read_batch_json(path)
            else:
                self.data = self._create
            apply_batch_settings(self.repo, self.data)
            entered = True
            return self
        finally:
            if not entered:
                if acquired:
                    _unlock(self._lock)
                self._lock.close()

    def __exit__(self, exc_type, exc, tb) -> None:
        state_written = False
        try:
            if exc_type is None and self._events:
                write_json(self.dir / "batch.json", self.data)
                state_written = True
                with open(self.dir / "events.jsonl", "a", encoding="utf-8") as f:
                    for e in self._events:
                        f.write(json.dumps(e) + "\n")
                if self._number:
                    write_file(self.repo.changes / ".batch-number", f"{self._number}\n")
                from .lifecycle import stage_layout  # avoid an import cycle
                from .status import write_batch, write_dashboard
                try:
                    write_batch(self.repo, self.data, self.dir)
                    write_dashboard(self.repo, stage_layout(self.repo))
                except Exception as e:  # the state is saved: only a view is stale, until next change
                    print(f"warning: STATUS not rewritten: {e}", file=sys.stderr)
        finally:
            try:
                if not state_written:
                    self._rollback_moves()
            finally:
                with contextlib.suppress(Exception):
                    _unlock(self._lock)
                self._lock.close()
                # a failed `open` leaves none of the batch's own files, and touches no CR folder:
                # the state folders stay
                if self._number and not state_written:
                    for name in (".lock", "brief.md"):
                        with contextlib.suppress(OSError):
                            (self.dir / name).unlink()

    def log(self, kind: str, cr: str | None = None, **fields) -> None:
        self._events.append({"t": now(), "actor": self.actor, "kind": kind, "cr": cr, **fields})

    def cr(self, cr_id: str) -> dict:
        cr_id = normalize_cr(cr_id)
        for c in self.data["crs"]:
            if c["id"] == cr_id:
                return c
        raise ChantierError(f"unknown CR {cr_id} in batch {self.id}", EXIT_USAGE)

    def touch(self, c: dict, **fields) -> None:
        c.update(fields)
        c["updated"] = now()

    def move(self, source: Path, destination: Path) -> None:
        move_directory(source, destination)
        self._moves.append((source, destination))

    def _rollback_moves(self) -> None:
        for source, destination in reversed(self._moves):
            if not destination.exists() or source.exists():
                raise ChantierError(f"cannot roll back CR move {destination} to {source}; "
                                    "preserve both paths and resolve manually")
            source.parent.mkdir(parents=True, exist_ok=True)
            _retry(destination.rename, source)
        self._moves.clear()


def normalize_batch(batch: str) -> str:
    """`4`, `04` and `batch-04` all name `batch-04`; anything else is left as given."""
    match = re.fullmatch(r"(?:batch-)?(\d+)", batch.strip())
    return f"batch-{int(match.group(1)):02d}" if match else batch


def normalize_cr(value):
    """`165`, `CR-165` and `cr-165` all name `CR-165`; anything else (`stack`, `-`, an `O-k`
    order, a QA folder) is left as given."""
    if not isinstance(value, str):
        return value
    match = re.fullmatch(r"(?:cr-)?(\d+)", value.strip(), re.I)
    return f"CR-{match.group(1)}" if match else value


def resolve_batch(repo: Repo, batch: str | None) -> str:
    """`--batch`, else `CHANTIER_BATCH`, else the only running batch; never a guess among several."""
    if batch or os.environ.get("CHANTIER_BATCH"):
        return normalize_batch(batch or os.environ["CHANTIER_BATCH"])
    names = repo.open_batches()
    if len(names) == 1:
        return names[0]
    if not names:
        raise ChantierError("no running batch: run `chantier open` first")
    raise ChantierError(f"several running batches ({', '.join(names)}): pass --batch", EXIT_USAGE)


def check_epoch(b: "Batch", epoch: int | None) -> None:
    """A Foreman command carries the epoch it was started with; a stale Foreman is refused."""
    if epoch is None:
        return
    current = b.data.get("foreman_epoch", 0)
    if epoch != current:
        raise ChantierError(f"stale Foreman: epoch {epoch}, batch {b.id} is at epoch {current}; "
                       "stop now", EXIT_CONFLICT)


def read_batch(repo: Repo, batch_id: str) -> dict:
    data = read_batch_json(repo.batch_dir(batch_id) / "batch.json")
    apply_batch_settings(repo, data)
    return data


def find_cr_batch(repo: Repo, cr_id: str, batch: str | None) -> str:
    """The batch holding a CR: the one given, else the batch that has it (a paused batch
    can hold queued CRs)."""
    cr_id = normalize_cr(cr_id)
    if batch:
        return normalize_batch(batch)
    for d in reversed(repo.batch_folders()):
        b = read_batch_json(d / "batch.json")
        if any(c["id"] == cr_id for c in b["crs"]):
            return b["id"]
    raise ChantierError(f"no batch holds {cr_id}", EXIT_USAGE)


RESTORED_NUMBER_FILE = "restored.json"


def next_cr_number(repo: Repo, roots: tuple[Path, ...] = ()) -> int:
    """Choose a number under the lifecycle lock, without reserving it on a failed move."""
    previous = repo.config["first_cr_number"] - 1
    try:  # a number `restore` took off a folder: once given, a number is never given again
        previous = max(previous,
                       int(json.loads((repo.changes / RESTORED_NUMBER_FILE)
                                      .read_text("utf-8"))["last_number"]))
    except (OSError, ValueError, KeyError, TypeError):
        pass
    for root in roots:
        if root.is_dir():
            for child in root.iterdir():
                if child.is_dir():
                    name = re.sub(r"^(?:\d{6}-\d{4}-)+", "", child.name)  # the date is no number
                    match = re.match(r"^(?:CR-)?(\d+)(?:-|$)", name, re.I)
                    if match:
                        previous = max(previous, int(match.group(1)))
    for batch in repo.batch_folders():
        for cr in read_batch_json(batch / "batch.json").get("crs", []):
            match = re.fullmatch(r"CR-(\d+)", cr.get("id", ""))
            if match:
                previous = max(previous, int(match.group(1)))
    return previous + 1
