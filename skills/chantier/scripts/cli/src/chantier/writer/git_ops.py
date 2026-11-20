"""The writer's git commands, every one through `core.git.git` with `LC_ALL=C` and `LANGUAGE=C` (a
translated git still prints the English messages `network_failure` reads). Nothing is forced, no
hook is skipped, and no command other than these is run."""

from __future__ import annotations

from pathlib import Path

from chantier.core.errors import ChantierError
from chantier.core.git import git

ENV = {"LC_ALL": "C", "LANGUAGE": "C"}
NETWORK = (
    "Could not resolve host",
    "unable to access",
    "Connection timed out",
    "Connection refused",
    "Could not read from remote repository",
    "Network is unreachable",
)
# git-lfs's transport failures, in a `batch response`; git-lfs 3.8.1 prints, for an unresolvable
# host (test_an_lfs_push_that_cannot_reach_the_lfs_server_is_offline): `batch response: Post
# "https://lfs.invalid/objects/batch": dial tcp: lookup lfs.invalid: no such host`
LFS_NETWORK = ("dial tcp", "no such host")
REFUSED = ("non-fast-forward", "fetch first")  # not `[remote rejected]`: a hook's refusal
BUSY = ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD")
NOTHING = ("nothing to commit", "no changes added")


class Failed(Exception):
    """A git command that failed: its message on one line."""

    def __init__(self, args: tuple[str, ...], text: str) -> None:
        super().__init__(text)
        self.git_args, self.text = args, text


def network_failure(args: tuple[str, ...], text: str) -> bool:
    """Whether a failed fetch or push is a transport failure (the machine is offline)."""
    if not args or args[0] not in ("fetch", "push"):
        return False
    if any(m in text for m in NETWORK):
        return True
    return args[0] == "push" and "batch response" in text and any(m in text for m in LFS_NETWORK)


def refused(text: str) -> bool:
    """Whether a failed push was refused because the remote moved (not a fast-forward); a
    `[remote rejected]` (a hook of the remote, a protected branch) is a failed step."""
    return any(m in text for m in REFUSED)


def _one_line(message: str) -> str:
    """The message on one line, without git's `warning:` and `hint:` lines (line-ending notices
    and advice come before the error itself); all of it when nothing else is left."""
    kept = [x for x in message.splitlines() if not x.startswith(("warning:", "hint:"))]
    return " ".join(" ".join(kept or message.splitlines()).split())


class Git:
    """The surface's checkout."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def run(self, *args: str, raw: bool = False, input: str | None = None) -> str:
        try:
            return git(*args, cwd=self.root, env=ENV, raw=raw, input=input)
        except ChantierError as e:
            prefix = f"git {' '.join(args)}: "
            raise Failed(args, _one_line(str(e).removeprefix(prefix))) from e

    def read(self, *args: str) -> str:
        """A read that may fail without it being a fault: empty then."""
        try:
            return self.run(*args)
        except Failed:
            return ""

    # reads
    def branch(self) -> str:
        """The branch HEAD is on, empty when it is detached."""
        return self.read("symbolic-ref", "--short", "-q", "HEAD")

    def default_branch(self, remote: str = "origin") -> str:
        """The remote's recorded HEAD branch (`origin/HEAD`), empty when git does not know it."""
        head = self.read("symbolic-ref", "--short", "-q", f"refs/remotes/{remote}/HEAD")
        return head.removeprefix(f"{remote}/")

    def remote_and_branch(self, branch: str) -> tuple[str, str] | None:
        """The upstream's remote and branch name, None when the branch has none."""
        remote = self.read("config", f"branch.{branch}.remote")
        merge = self.read("config", f"branch.{branch}.merge")
        if not remote or not merge:
            return None
        return remote, merge.removeprefix("refs/heads/")

    def sha(self, ref: str) -> str:
        return self.read("rev-parse", "--verify", "--quiet", ref)

    def count(self, spec: str) -> int:
        out = self.read("rev-list", "--count", spec)
        return int(out) if out.isdigit() else 0

    def busy(self) -> bool:
        """A rebase, merge, cherry-pick or revert is in progress."""
        args = [x for name in BUSY for x in ("--git-path", name)]
        found = self.run("rev-parse", *args).splitlines()
        return any((self.root / p).exists() for p in found)

    def unmerged(self) -> list[str]:
        return [p for p in self.read("diff", "--name-only", "--diff-filter=U").splitlines() if p]

    def staged(self) -> list[str]:
        return [
            p for p in self.run("diff", "--cached", "--name-only", "-z", raw=True).split("\0") if p
        ]

    def stashes(self) -> list[str]:
        return [x for x in self.read("stash", "list").splitlines() if x]

    def is_ancestor(self, ancestor: str, ref: str) -> bool:
        try:
            self.run("merge-base", "--is-ancestor", ancestor, ref)
        except Failed:
            return False
        return True

    def status(self, spec: list[str]) -> str:
        return self.run(
            "status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *spec, raw=True
        )

    def staged_entries(self, spec: list[str]) -> str:
        return self.run("ls-files", "--stage", "-z", "--", *spec, raw=True)

    # writes
    def add(self, spec: list[str]) -> None:
        self.run("add", "-A", "--", *spec)

    def commit(self, message: str, paths: list[str]) -> bool:
        """Commit only these paths (on standard input, NUL-separated); False when git had
        nothing to commit. The user's hooks run."""
        try:
            self.run(
                "commit",
                "-m",
                message,
                "--pathspec-from-file=-",
                "--pathspec-file-nul",
                input="\0".join(paths),
            )
        except Failed as e:
            if any(m in e.text for m in NOTHING):
                return False
            raise
        return True

    def fetch(self, remote: str, branch: str) -> None:
        self.run("fetch", remote, branch)

    def merge_ff(self, upstream: str) -> None:
        self.run("merge", "--ff-only", "--autostash", upstream)

    def rebase(self, upstream: str) -> None:
        self.run("rebase", "--autostash", upstream)

    def rebase_abort(self) -> None:
        self.run("rebase", "--abort")

    def push(self, remote: str, branch: str) -> None:
        self.run("push", remote, f"HEAD:{branch}")
