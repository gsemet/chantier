"""Repository paths, configuration and the locked batch state.

Only this module writes `batch.json` and `events.jsonl`: under an exclusive `fcntl` lock, by
atomic rename, and every change appends one event.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

EXIT_OK, EXIT_USAGE, EXIT_PRECONDITION, EXIT_CONFLICT, EXIT_EXTERNAL, EXIT_BUDGET = 0, 1, 2, 3, 4, 5
LOCK_TIMEOUT_S = 30

DEFAULT_CONFIG = {
    "changes_dir": ".agents/changes",
    "default_branch": "main",
    "remote": "origin",
    "worktrees_dir": "",
    "forge": "github",
    "max_rounds": 3,
    "stale_minutes": 90,
    "gates": {"fast": [], "long": []},
}

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
                       env=env)
    if check and p.returncode != 0:
        raise ChantierError(f"git {' '.join(args)}: {p.stderr.strip() or p.stdout.strip()}",
                       EXIT_EXTERNAL)
    return p.stdout.strip()


@dataclass
class Repo:
    """The main repository, even when called from a CR worktree."""

    root: Path
    config: dict

    @classmethod
    def find(cls, cwd: Path | None = None) -> "Repo":
        """`CHANTIER_ROOT` wins, so agents in a CR worktree or elsewhere reach the same state."""
        cwd = Path(cwd or os.environ.get("CHANTIER_ROOT") or os.getcwd())
        try:
            common = git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=cwd)
        except ChantierError as e:
            raise ChantierError(f"not inside a git repository: {cwd}") from e
        root = Path(common).resolve().parent
        cfg = dict(DEFAULT_CONFIG)
        path = root / ".agents" / "chantier.json"
        if path.exists():
            cfg.update(json.loads(path.read_text()))
        return cls(root, cfg)

    @property
    def config_path(self) -> Path:
        return self.root / ".agents" / "chantier.json"

    @property
    def changes(self) -> Path:
        return self.root / self.config["changes_dir"]

    @property
    def batches(self) -> Path:
        return self.changes / "batches"

    @property
    def worktrees(self) -> Path:
        w = self.config.get("worktrees_dir")
        return Path(w).expanduser() if w else self.root.parent / f"{self.root.name}.worktrees"

    def batch_dir(self, batch: str) -> Path:
        return self.batches / batch

    def latest_batch(self) -> str:
        """The most recently created batch that is not landed."""
        if not self.batches.exists():
            raise ChantierError("no batch yet: run `chantier open` first")
        open_batches = []
        for d in self.batches.iterdir():
            f = d / "batch.json"
            if f.exists():
                b = json.loads(f.read_text())
                if b.get("status") != "landed":
                    open_batches.append((b.get("created", ""), d.name))
        if not open_batches:
            raise ChantierError("no open batch")
        return max(open_batches)[1]


class Batch:
    """A locked, read-modify-write view of one batch. Use as a context manager."""

    def __init__(self, repo: Repo, batch_id: str, actor: str = "cli", create: dict | None = None):
        self.repo, self.id, self.actor = repo, batch_id, actor
        self.dir = repo.batch_dir(batch_id)
        self._create = create
        self._lock = None
        self.data: dict = {}
        self._events: list[dict] = []

    def __enter__(self) -> "Batch":
        if self._create is None and not (self.dir / "batch.json").exists():
            raise ChantierError(f"unknown batch {self.id}")
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = open(self.dir / ".lock", "a+")
        deadline = time.monotonic() + LOCK_TIMEOUT_S
        while True:
            try:
                fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() > deadline:
                    raise ChantierError(f"batch {self.id} is locked for over {LOCK_TIMEOUT_S} s")
                time.sleep(0.05)
        path = self.dir / "batch.json"
        if path.exists():
            if self._create is not None:
                raise ChantierError(f"batch {self.id} already exists")
            self.data = json.loads(path.read_text())
        else:
            self.data = self._create
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None and self._events:
                tmp = self.dir / "batch.json.tmp"
                tmp.write_text(json.dumps(self.data, indent=2) + "\n")
                os.replace(tmp, self.dir / "batch.json")
                with open(self.dir / "events.jsonl", "a") as f:
                    for e in self._events:
                        f.write(json.dumps(e) + "\n")
        finally:
            with contextlib.suppress(Exception):
                fcntl.flock(self._lock, fcntl.LOCK_UN)
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


def resolve_batch(repo: Repo, batch: str | None) -> str:
    """`--batch`, else `CHANTIER_BATCH` (set in every agent's brief), else the latest open batch."""
    return batch or os.environ.get("CHANTIER_BATCH") or repo.latest_batch()


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
    return json.loads(path.read_text())


def find_cr_batch(repo: Repo, cr_id: str, batch: str | None) -> str:
    """The batch holding a CR: the one given, else the open batch that has it."""
    if batch:
        return batch
    if repo.batches.exists():
        for d in sorted(repo.batches.iterdir(), reverse=True):
            f = d / "batch.json"
            if f.exists():
                b = json.loads(f.read_text())
                if b.get("status") != "landed" and any(c["id"] == cr_id for c in b["crs"]):
                    return d.name
    raise ChantierError(f"no open batch holds {cr_id}", EXIT_USAGE)


def next_cr_number(repo: Repo) -> int:
    """CR numbers are unique in the repository; the counter is locked like a batch."""
    repo.changes.mkdir(parents=True, exist_ok=True)
    counter = repo.changes / ".chantier-counter"
    with open(repo.changes / ".chantier-counter.lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        n = int(counter.read_text()) + 1 if counter.exists() else 101
        counter.write_text(str(n))
    return n
