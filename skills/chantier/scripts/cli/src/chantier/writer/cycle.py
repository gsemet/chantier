"""The writer's cycle (the spec's C.5): commit what the plan's published paths hold, fetch,
integrate the upstream, push; a conflict, a blocking precondition or a failed git step is told by
the entry and by `sync-*@1` lines. `Writer.cycle(now)` takes the monotonic time (a test drives it
with no sleep); the entry's stamps are `core.clock`'s.

The lifecycle locks of the projects are held from `git add` to the end of the commit, and from the
integrate's start to its end, and are let go before any journal append (which takes the same lock,
which one process cannot take twice)."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from chantier import __version__
from chantier.core import clock
from chantier.core.repo import Repo
from chantier.hub import state
from chantier.writer import paths as wpaths
from chantier.writer import record as rec
from chantier.writer import times
from chantier.writer.blocking import Look, blocking, foreign_autosync
from chantier.writer.git_ops import Failed, Git, network_failure, refused, too_long_path
from chantier.writer.late import Late
from chantier.writer.pulled import Pulled

PUSH_TRIES = 3
NAMED = 3  # paths named in a blocked text
GIT_ERROR = "git-error"
PATH_TOO_LONG = "path-too-long"
FAILED_STEPS = (GIT_ERROR, PATH_TOO_LONG)
PATH_SHOWN = 150
CYCLES_TO_BLOCK = 2


class Writer(Late, Pulled):
    """What the process that holds `writer.lock` does: its cycle and its `writer` entry."""

    def __init__(self, repo: Repo, version: str = __version__) -> None:
        self.repo = repo
        self.root: Path = repo.surface_root
        self.git_dir: Path = repo.git_dir
        self.git = Git(self.root)
        self.record = rec.new(version)
        self.last: float | None = None  # the monotonic time of the last cycle
        self.now = 0.0
        self.step = 0
        self.projects: dict[str, Repo] = {}
        self.finger: Any = None
        self.moved_at: float | None = None  # monotonic: when the changes last moved
        self.pending_mono: float | None = None
        self.unpushed_mono: float | None = None
        self.last_fetch_mono: float | None = None
        self.staged_prev: set[str] = set()
        self.late_told = False
        self.told: tuple[Any, ...] | None = None  # the blocked line of the episode, once
        self.episode: str | None = None  # the blocked reason of a precondition episode
        self.offline_since: str | None = None
        self.stash_text: str | None = None
        self.syncing = False
        self.events: list[tuple[list[Repo], dict[str, Any]]] = []
        self.publish()

    # the entry
    def publish(self) -> None:
        rec.publish(self.git_dir, self.record)

    def _set(self, kind: str, reason: str = "", text: str = "") -> None:
        r = self.record
        if (r["state"], r["reason"]) != (kind, reason):
            r["since"] = clock.now()
        r["state"], r["reason"], r["text"] = kind, reason, rec.cut(text)

    def close(self) -> None:
        with contextlib.suppress(OSError):
            state.remove_entry(self.git_dir, state.WRITER, self.record["pid"])

    def note_error(self, e: Exception) -> None:
        """A cycle that raised, a fault: told as a failed git step of step 0."""
        text = rec.cut(" ".join(str(e).split()) or type(e).__name__)
        self.step = 0
        self._remember_failure(text)
        self.publish()

    def due(self, now: float) -> bool:
        return self.last is None or now - self.last >= times.every_s()

    # the cycle
    def cycle(self, now: float, final: bool = False, asked: bool = False) -> None:
        """One cycle, steps 1 to 8. The entry's `last_cycle` is written at its end, whatever
        happened."""
        self.last, self.now = now, now
        self.syncing, self.stash_text = False, None
        self.step = 1
        try:
            self._run(final, asked)
        finally:
            self.record["last_cycle"] = clock.now()
            self.publish()
            self._flush()

    def _run(self, final: bool, asked: bool) -> None:
        r = self.record
        self._projects()
        try:
            if r["state"] == rec.CONFLICT:
                if not self._conflict_over():
                    self._late()
                    return
                self._conflict_arrivals(r["conflict"] or {})
                r["conflict"] = None
                self._tell({"type": "sync-resumed@1", "after": "conflict"})
            self.step = 2
            look = self._look()
            if self._preconditions(look):
                return
            self._steps(look, final, asked)
        except Failed as e:
            self._failed(e)

    def _conflict_over(self) -> bool:
        """Step 1: the Chief of Staff integrated: nothing in progress, HEAD on the default
        branch, the recorded upstream an ancestor of HEAD."""
        c = self.record["conflict"] or {}
        if self.git.busy():
            return False
        default = self.git.default_branch()
        return bool(
            default
            and self.git.branch() == default
            and c.get("upstream")
            and self.git.is_ancestor(c["upstream"], "HEAD")
        )

    def _look(self) -> Look:
        """The reads of steps 2 and 3: the branch and its upstream, the changes of the writer's
        paths (counted in the entry, their fingerprint kept), the nested repositories."""
        g = self.git
        look = Look(branch=g.branch())
        look.upstream = g.remote_and_branch(look.branch) if look.branch else None
        look.paths = wpaths.Paths(tuple(wpaths.excluded(self.root, list(self.projects.values()))))
        raw = g.status(look.paths.spec)
        look.changed, look.nested = wpaths.parse_status(raw, look.paths)
        look.nested += wpaths.gitlinks(g.staged_entries(look.paths.spec), look.paths)
        self._pending(look.changed)
        self._ahead(look)
        return look

    def _pending(self, changed: list[str]) -> None:
        r = self.record
        r["pending"] = len(changed)
        if not changed:
            r["pending_since"] = None
            self.pending_mono = self.moved_at = self.finger = None
            return
        if self.pending_mono is None:
            r["pending_since"], self.pending_mono = clock.now(), self.now
        finger = wpaths.fingerprint(self.root, changed)
        if finger != self.finger:
            self.finger, self.moved_at = finger, self.now

    def _ahead(self, look: Look) -> None:
        r = self.record
        if look.upstream:
            r["ahead"] = self.git.count(f"{look.upstream[0]}/{look.upstream[1]}..HEAD")
        else:
            r["ahead"] = 0
        if r["ahead"] == 0:
            r["unpushed_since"], self.unpushed_mono = None, None
        elif self.unpushed_mono is None:
            r["unpushed_since"], self.unpushed_mono = clock.now(), self.now

    # step 2
    def _preconditions(self, look: Look) -> bool:
        """Step 2. True when one fails: the state is `blocked` with its reason and the cycle
        ends."""
        g = self.git
        default = g.default_branch()
        staged = {p for p in g.staged() if not look.paths.owns(p)}
        seen, self.staged_prev = staged & self.staged_prev, staged
        foreign = foreign_autosync(self.git_dir)
        found = blocking(g, look, default, seen, foreign)
        if found is None:
            if self.episode is not None:
                self.episode = None
                self.told = None
                if (
                    self.record["state"] == rec.BLOCKED
                    and self.record["reason"] not in FAILED_STEPS
                ):
                    self._tell({"type": "sync-resumed@1", "after": "blocked"})
            return False
        reason, text, where = found
        self._set(rec.BLOCKED, reason, text)
        self._late()
        if self.episode is None:  # one line per episode, whatever its reason becomes
            self.episode = reason
            audience = self._holding(where) or None
            self._tell(
                {"type": "sync-blocked@1", "reason": reason, "text": rec.cut(text)}, audience
            )
        return True

    # steps 3 to 7
    def _steps(self, look: Look, final: bool, asked: bool) -> None:
        r = self.record
        self.step = 4
        if look.changed and (
            final
            or asked
            or (self.moved_at is not None and self.now - self.moved_at >= times.quiet_s())
            or (
                self.pending_mono is not None and self.now - self.pending_mono >= times.max_wait_s()
            )
        ):
            self._commit(look)
        remote, branch = look.upstream or ("", "")
        upstream = f"{remote}/{branch}"
        for attempt in range(PUSH_TRIES + 1):
            self.step = 5
            fetch_due = (
                self.last_fetch_mono is None
                or self.now - self.last_fetch_mono >= times.fetch_every_s()
            )
            if r["ahead"] > 0 or fetch_due or attempt > 0:
                self._syncing()
                self.git.fetch(remote, branch)
                r["last_fetch"], self.last_fetch_mono = clock.now(), self.now
            if self.git.count(f"HEAD..{upstream}") > 0:
                self.step = 6
                if self._integrate(look, upstream):
                    return
            self._ahead(look)
            if r["ahead"] == 0:
                break
            self.step = 7
            self._syncing()
            try:
                self.git.push(remote, branch)
            except Failed as e:
                if refused(e.text) and attempt < PUSH_TRIES:
                    continue
                if refused(e.text):
                    break  # the commits stay to push, the next cycle tries again
                raise
            r["last_push"] = {"sha": self.git.sha("HEAD"), "at": clock.now()}
            self._ahead(look)
            break
        self._finish()

    def _syncing(self) -> None:
        if not self.syncing:
            self.syncing = True
            self._set(rec.SYNCING)
            self.publish()

    def _commit(self, look: Look) -> None:
        """Step 4, and step 6's first move: everything pending in the writer's paths, committed
        under the projects' locks, as listed again under them."""
        g, r = self.git, self.record
        with self._locked():
            changed, nested = wpaths.parse_status(g.status(look.paths.spec), look.paths)
            if not changed or nested:  # a nested repository appeared: the next cycle blocks on it
                return
            self._syncing()
            g.run(
                "add",
                "-A",
                "--pathspec-from-file=-",
                "--pathspec-file-nul",
                input="\0".join(changed),
            )
            if not g.commit(wpaths.message(changed), changed):
                return
            r["last_commit"] = {"sha": g.sha("HEAD"), "at": clock.now()}
        r["pending"], r["pending_since"] = 0, None
        self.pending_mono, self.moved_at, self.finger = None, None, None
        self._ahead(look)

    def _integrate(self, look: Look, upstream: str) -> bool:
        """Step 6. True when the cycle ends here (a conflict)."""
        g, r = self.git, self.record
        if r["pending"]:
            self._commit(look)
        self._syncing()
        local, theirs = g.sha("HEAD"), g.sha(upstream)
        base = g.merge_base(local, theirs)
        self._ahead(look)
        before = len(g.stashes())
        conflict: list[str] | None = None
        with self._locked():
            try:
                if r["ahead"] == 0:
                    g.merge_ff(upstream)
                else:
                    g.rebase(upstream)
            except Failed:
                if r["ahead"] == 0 or not g.busy():
                    raise
                conflict = g.unmerged()
                g.rebase_abort()
                if not conflict:
                    raise
        if conflict is not None:
            self._conflict(local, theirs, conflict)
            return True
        self._arrived(base, theirs, theirs)
        stashes = g.stashes()
        if len(stashes) > before:
            self.stash_text = stashes[0]
        self._ahead(look)
        return False

    def _conflict(self, local: str, theirs: str, files: list[str]) -> None:
        """C.7: the rebase was aborted; state `conflict`, one line per project that holds a
        conflicted path (else to those with a seat)."""
        r = self.record
        r["conflict"] = {"upstream": theirs, "local": local, "files": files}
        self._set(rec.CONFLICT)
        holders = self._holding(files)
        event = {
            "type": "sync-conflict@1",
            "upstream": theirs,
            "local": local,
            "files": files,
            "projects": [n for n, p in self.projects.items() if p in (holders or [])],
        }
        self._tell(event, holders or None)

    # step 8 and the failures
    def _remember_failure(self, text: str, reason: str = GIT_ERROR, path: str = "") -> None:
        r = self.record
        f = r["failure"]
        if f and f["step"] == self.step and f["text"] == text:
            f["cycles"] += 1
        else:
            r["failure"] = {"step": self.step, "text": text, "cycles": 1}
            if reason != GIT_ERROR:
                r["failure"].update(reason=reason, path=path)

    def _failed(self, e: Failed) -> None:
        """A git command failed: a network failure is `offline`; any other is a failed step,
        retried at every cycle (`blocked` at the second in a row)."""
        if network_failure(e.git_args, e.text):
            if self.offline_since is None:
                self.offline_since = clock.now()
            self._finish(offline=True)
            return
        long = too_long_path(e.git_args, e.text)
        if long is not None:
            self._remember_failure(self._long_text(long), PATH_TOO_LONG, long)
        else:
            self._remember_failure(rec.cut(e.text))
        self._finish(failed=True)

    def _long_text(self, path: str) -> str:
        """`<n> characters: <path>`: n is the absolute path's length, the path as git names it
        (relative to the surface), whole up to PATH_SHOWN characters, else its start and `...`."""
        shown = path if len(path) <= PATH_SHOWN else path[:PATH_SHOWN] + "..."
        return rec.cut(f"{len(str(self.root / path))} characters: {shown}")

    def _finish(self, offline: bool = False, failed: bool = False) -> None:
        """Step 8: the state, the episodes that end, `sync-late@1`."""
        r = self.record
        if r["state"] == rec.CONFLICT and r["conflict"]:
            return
        if not offline and not failed:
            if r["failure"] is not None:
                r["failure"] = None
                if self.told is not None:  # the episode was told (`_syncing` moved the state)
                    self._tell({"type": "sync-resumed@1", "after": "blocked"})
                    self.told = None
            if self.offline_since is not None:
                self.offline_since = None
                self._tell({"type": "sync-resumed@1", "after": "offline"})
        if self.stash_text is not None and not offline:
            r["failure"] = {"step": 6, "text": rec.cut(self.stash_text), "cycles": 1}
            self._block_git_error(r["failure"])
        elif offline:
            self._set(rec.OFFLINE)
        elif failed and r["failure"]["cycles"] >= CYCLES_TO_BLOCK:
            self._block_git_error(r["failure"])
        else:
            self._set(rec.SYNCED if not r["pending"] and not r["ahead"] else rec.PENDING)
        self._late()

    def _block_git_error(self, failure: dict[str, Any]) -> None:
        reason = failure.get("reason", GIT_ERROR)
        self._set(rec.BLOCKED, reason, failure["text"])
        key = (failure["step"], failure["text"])
        if self.told != key:
            self.told = key
            audience = (
                (self._holding([failure["path"]]) or None) if reason == PATH_TOO_LONG else None
            )
            self._tell(
                {"type": "sync-blocked@1", "reason": reason, "text": failure["text"]}, audience
            )
