"""Repository paths and the locked batch state.

Everything chantier keeps lives in `.agents/changes/` at the repository's root, as plain JSON and
Markdown: `backlog/` (the CR folders) and `batches/<batch>/` (`batch.json` holds what the Chief of
Staff passed to `open` from the project's AGENTS.md).

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

EXIT_OK, EXIT_USAGE, EXIT_PRECONDITION, EXIT_CONFLICT, EXIT_EXTERNAL, EXIT_BUDGET = 0, 1, 2, 3, 4, 5
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


def write_json(path: Path, data) -> None:
    """Write by atomic rename, so a reader never sees half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    _retry(os.replace, tmp, path)


CHANGES = Path(".agents") / "changes"
# What `chantier open` records in batch.json from the project's AGENTS.md (SETTINGS), and the
# fixed rules every batch runs on.
DEFAULT_CONFIG = {
    "default_branch": None,
    "remote": "origin",
    "gates": {"fast": [], "long": []},
    "agents": {},
    "reviews": {},
    "claude_projects_dir": None,
    "first_cr_number": 101,
    "forge": "github",
    "max_rounds": 3,
    "stale_minutes": 90,
}
SETTINGS = ("default_branch", "remote", "gates", "agents", "reviews", "claude_projects_dir",
            "max_rounds")

# Statuses a CR can hold. `working` means a live Driver owns it.
LIVE = {"working", "qa"}
DONE = {"ready", "blocked", "cancelled", "merged", "landed"}


class ChantierError(Exception):
    """An error with the exit code the CLI must return."""

    def __init__(self, message: str, code: int = EXIT_PRECONDITION):
        super().__init__(message)
        self.code = code


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def project_path(root: Path, value: str | Path, label: str = "path") -> Path:
    path = Path(value).expanduser()
    path = (path if path.is_absolute() else root / path).resolve()
    root = root.resolve()
    if path == root or not path.is_relative_to(root):
        raise ChantierError(f"{label} must be inside the repository: {value}", EXIT_USAGE)
    return path


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

    root: Path
    git_dir: Path
    config: dict

    @classmethod
    def find(cls, cwd: Path | None = None) -> "Repo":
        """`CHANTIER_ROOT` wins, so agents in a CR worktree or elsewhere reach the same state."""
        cwd = Path(cwd or os.environ.get("CHANTIER_ROOT") or os.getcwd())
        try:
            common = git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd)
        except ChantierError as e:
            raise ChantierError(f"not inside a git repository: {cwd}") from e
        git_dir = Path(common).resolve()
        return cls(git_dir.parent, git_dir, json.loads(json.dumps(DEFAULT_CONFIG)))

    @property
    def changes(self) -> Path:
        """`.agents/changes/`: the one folder chantier writes in."""
        return self.root / CHANGES

    @property
    def batches(self) -> Path:
        return self.changes / "batches"

    @property
    def worktrees(self) -> Path:
        return self.root.parent / f"{self.root.name}.worktrees"

    def batch_dir(self, batch: str) -> Path:
        return self.batches / batch

    def open_batches(self) -> list[str]:
        if not self.batches.exists():
            return []
        return sorted(d.name for d in self.batches.iterdir() if (d / "batch.json").exists()
                      and _read_json(d / "batch.json").get("status") != "landed")


class Batch:
    """A locked, read-modify-write view of one batch. Use as a context manager."""

    def __init__(self, repo: Repo, batch_id: str, actor: str = "cli", create: dict | None = None):
        self.repo, self.id, self.actor = repo, batch_id, actor
        self.dir = repo.batch_dir(batch_id)
        self._create = create
        self._lock = None
        self.data: dict = {}
        self._events: list[dict] = []
        self._moves: list[tuple[Path, Path]] = []
        self._new_worktrees: list[tuple[Path, str, str]] = []

    def __enter__(self) -> "Batch":
        if self._create is None and not (self.dir / "batch.json").exists():
            raise ChantierError(f"unknown batch {self.id}")
        self.dir.mkdir(parents=True, exist_ok=True)
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
                self.data = _read_json(path)
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
        finally:
            try:
                if not state_written:
                    try:
                        self._rollback_moves()
                    finally:
                        self._rollback_worktrees()
            finally:
                with contextlib.suppress(Exception):
                    _unlock(self._lock)
                self._lock.close()

    def log(self, kind: str, cr: str | None = None, **fields) -> None:
        self._events.append({"t": now(), "actor": self.actor, "kind": kind, "cr": cr, **fields})

    def cr(self, cr_id: str) -> dict:
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

    def created_worktree(self, path: Path, branch: str, initial_head: str) -> None:
        self._new_worktrees.append((path, branch, initial_head))

    def _rollback_moves(self) -> None:
        for source, destination in reversed(self._moves):
            if not destination.exists() or source.exists():
                raise ChantierError(f"cannot roll back CR move {destination} to {source}; "
                                    "preserve both paths and resolve manually")
            source.parent.mkdir(parents=True, exist_ok=True)
            _retry(destination.rename, source)
        self._moves.clear()

    def _rollback_worktrees(self) -> None:
        for path, branch, initial_head in reversed(self._new_worktrees):
            if path.exists():
                dirty = git("status", "--porcelain", cwd=path, check=False)
                head = git("rev-parse", "HEAD", cwd=path, check=False)
                if dirty or head != initial_head:
                    raise ChantierError(f"worktree {path} changed while opening the batch; "
                                        "it was preserved and needs manual recovery")
                git("worktree", "remove", str(path), cwd=self.repo.root)
            current = git("rev-parse", "--verify", "--quiet", branch, cwd=self.repo.root,
                          check=False)
            if current == initial_head:
                git("branch", "-d", branch, cwd=self.repo.root)
            elif current:
                raise ChantierError(f"branch {branch} changed while opening the batch; "
                                    "it was preserved and needs manual recovery")
        self._new_worktrees.clear()


def resolve_batch(repo: Repo, batch: str | None) -> str:
    """`--batch`, else `CHANTIER_BATCH`, else the only open batch; never a guess among several."""
    if batch or os.environ.get("CHANTIER_BATCH"):
        return batch or os.environ["CHANTIER_BATCH"]
    names = repo.open_batches()
    if len(names) == 1:
        return names[0]
    if not names:
        raise ChantierError("no open batch: run `chantier open` first")
    raise ChantierError(f"several open batches ({', '.join(names)}): pass --batch", EXIT_USAGE)


def check_epoch(b: "Batch", epoch: int | None) -> None:
    """A Foreman command carries the epoch it was started with; a stale Foreman is refused."""
    if epoch is None:
        return
    current = b.data.get("foreman_epoch", 0)
    if epoch != current:
        raise ChantierError(f"stale Foreman: epoch {epoch}, batch {b.id} is at epoch {current}; "
                       "stop now", EXIT_CONFLICT)


def read_batch(repo: Repo, batch_id: str) -> dict:
    path = repo.batch_dir(batch_id) / "batch.json"
    if not path.exists():
        raise ChantierError(f"unknown batch {batch_id}")
    data = _read_json(path)
    apply_batch_settings(repo, data)
    return data


def find_cr_batch(repo: Repo, cr_id: str, batch: str | None) -> str:
    """The batch holding a CR: the one given, else the open batch that has it."""
    if batch:
        return batch
    if repo.batches.exists():
        for d in sorted(repo.batches.iterdir(), reverse=True):
            f = d / "batch.json"
            if f.exists():
                b = _read_json(f)
                if b.get("status") != "landed" and any(c["id"] == cr_id for c in b["crs"]):
                    return d.name
    raise ChantierError(f"no open batch holds {cr_id}", EXIT_USAGE)


def next_cr_number(repo: Repo, roots: tuple[Path, ...] = ()) -> int:
    """Choose a number under the lifecycle lock, without reserving it on a failed move."""
    previous = repo.config["first_cr_number"] - 1
    for root in roots:
        if root.is_dir():
            for child in root.iterdir():
                if child.is_dir():
                    match = re.match(r"^(?:CR-)?(\d+)(?:-|$)", child.name, re.I)
                    if match:
                        previous = max(previous, int(match.group(1)))
    if repo.batches.exists():
        for batch in repo.batches.iterdir():
            state = batch / "batch.json"
            if state.is_file():
                for cr in _read_json(state).get("crs", []):
                    match = re.fullmatch(r"CR-(\d+)", cr.get("id", ""))
                    if match:
                        previous = max(previous, int(match.group(1)))
    return previous + 1
