"""The cost of a batch's sessions and agents, from the transcripts on disk."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from chantier.core.errors import EXIT_EXTERNAL, ChantierError
from chantier.costs.copilot import copilot_home
from chantier.costs.transcripts import Reading, transcript_path, usage


def _held(row: dict[str, Any]) -> int:
    """The calls of a row, priced or not."""
    return int(row["calls"] + sum(row["unpriced"].values()))


@dataclass(frozen=True)
class Scope:
    """How a transcript is read: `kind` (the Foreman or the Chief of Staff), whether a window
    without a call is allowed, whether the grill is split off, the prices, and the main
    transcript's steering window (see `usage`)."""

    kind: str = "foreman"
    allow_empty: bool = False
    split: bool = False
    prices: dict[str, Any] | None = None
    steering: tuple[tuple[str, str], ...] | None = None
    windows: tuple[tuple[str, str], ...] | None = None  # priced instead of `since`/`until`


def session_costs(
    main: Path, since: str = "", until: str = "", scope: Scope | None = None
) -> list[dict[str, Any]]:
    """One row for the main transcript and one per subagent with calls in the window. A window
    without a call is an error unless allowed."""
    scope = scope or Scope()
    kind, split, prices, steering = scope.kind, scope.split, scope.prices, scope.steering
    allow_empty = scope.allow_empty
    label = kind.replace("-", " ").capitalize()
    if not main.is_file():
        raise ChantierError(f"{label} transcript not found: {main}", EXIT_EXTERNAL)
    windows = scope.windows
    foreman = usage(main, since, until, Reading(split, prices, steering, windows))
    if not _held(foreman) + (_held(foreman["grill"]) if split else 0) and not allow_empty:
        raise ChantierError(f"no priced calls in {label} transcript: {main}", EXIT_EXTERNAL)
    rows = [{"agent": "main", "type": kind, "description": "", **foreman}]
    sub = main.with_suffix("") / "subagents"
    if sub.exists():
        for f in sorted(sub.glob("agent-*.jsonl")):
            meta_path = f.with_suffix("").with_suffix(".meta.json")
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            row = usage(f, since, until, Reading(prices=prices, windows=windows))
            if _held(row):
                rows.append(
                    {
                        "agent": f.stem.removeprefix("agent-"),
                        "type": meta.get("agentType", "?"),
                        "parent": meta.get("parentAgentId"),
                        "description": meta.get("description", ""),
                        **row,
                    }
                )
    return rows


def without_specification_agents(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The Chief of Staff's subagents of type spec-writer or spec-critic (`spec-writer`,
    `chantier:spec-writer`, `chantier-spec-writer`, and the same for `spec-critic`) belong to no
    batch: they stay on the Chief of Staff's own line. A named exception to the CLI knowing no
    role: the cost code knows these two agent types, to put them on the grill line."""
    return [r for r in rows if not is_specification_agent(r)]


def is_specification_agent(row: dict[str, Any]) -> bool:
    return str(row.get("type", "")).endswith(("spec-writer", "spec-critic"))


def is_spec_critic(row: dict[str, Any]) -> bool:
    return str(row.get("type", "")).endswith("spec-critic")


def idle_seconds(
    root: Path, host: str, sessions: list[str], own: list[str] | None = None
) -> list[tuple[str, float | None]]:
    """How long ago each session record of the batch was last written, whatever the agent.

    Claude: the Foreman's transcript and every `subagents/agent-*.jsonl` beside it, a Driver, a
    worker, a QA or a user's own one alike. Copilot: the session's `events.jsonl`, the only record
    the CLI reads, subagents included. A file's time is its modification time: many records carry
    no time of their own. None: a file that is not there, so the time is not measured. `own`: the
    sessions that ask (every Chief of Staff session of a direct batch): a file of its own is written
    by the very call that asks, so only the subagents count."""
    own = own or []
    found: list[tuple[str, float | None]] = []
    clock = datetime.now(UTC).timestamp()

    def age(path: Path) -> float | None:
        try:
            return max(0.0, clock - path.stat().st_mtime)
        except OSError:
            return None

    for session in sessions:
        if host == "copilot":
            path = copilot_home() / "session-state" / session / "events.jsonl"
            if session not in own:
                found.append((f"Copilot session {session}", age(path)))
            continue
        main = transcript_path(root, session)
        if session not in own:
            found.append((f"transcript {session}", age(main)))
        for f in sorted((main.with_suffix("") / "subagents").glob("agent-*.jsonl")):
            found.append((f"transcript {session} {f.stem}", age(f)))
    return found


HANDBACK_TOOL = "SubagentHandback"  # the host's hand-back tool (Claude Code)
_TURN_ENDS = {"end_turn", "stop_sequence"}


@dataclass(frozen=True)
class Ending:
    """One Claude transcript's state: `label` (`transcript <session>` plus ` agent-<id>` for a
    subagent), `name` as `close --stopped` takes it (the subagent's file stem, the session id of a
    main transcript), the file's `path`, and a `state`: `ended`, `running` (with its `cause`) or
    `unreadable` (with its reason in `cause`)."""

    label: str
    name: str
    path: Path
    state: str
    cause: str = ""
    missing: bool = False  # a held agent whose file is nowhere: no path to print

    def text(self) -> str:
        """The cause line `close` prints for a transcript that runs or cannot be read."""
        verb = "still runs" if self.state == "running" else "cannot be read"
        where = "" if self.missing else f" ({self.path})"
        return f"{self.label} {verb}: {self.cause}{where}"


def _lines_from_end(path: Path) -> Iterator[bytes]:
    """The lines of a file, last first, read from the end in growing chunks."""
    with path.open("rb") as f:
        pos = f.seek(0, os.SEEK_END)
        buf, chunk = b"", 1 << 16
        while pos:
            size = min(chunk, pos)
            pos -= size
            f.seek(pos)
            parts = (f.read(size) + buf).split(b"\n")
            buf = parts[0]
            yield from reversed(parts[1:])
            chunk *= 2
        yield buf


def _blocks(record: dict[str, Any]) -> list[dict[str, Any]]:
    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


class _Unreadable(Exception):
    """A transcript that cannot be read, with the reason."""


def _turns_from_end(path: Path) -> Iterator[dict[str, Any]]:
    """The `user` and `assistant` records of a transcript, last first; every other record type
    (`api-request`, `api-request-blob`, `attachment`...) is skipped. The last non-empty line must
    be complete JSON."""
    first = True
    for raw in _lines_from_end(path):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except ValueError:
            record = None
        if first and not isinstance(record, dict):
            raise _Unreadable("its last line is not complete JSON")
        first = False
        if isinstance(record, dict) and record.get("type") in {"user", "assistant"}:
            yield record


def _assistant_state(record: dict[str, Any]) -> tuple[str, str]:
    calls = [b for b in _blocks(record) if b.get("type") == "tool_use"]
    if calls:
        return "running", f"its tool call {calls[-1].get('name', '?')} has no result yet"
    message = record.get("message")
    reason = message.get("stop_reason") if isinstance(message, dict) else None
    if reason in _TURN_ENDS:
        return "ended", ""
    return "running", f"its last call stopped on {reason or 'null'}"


def _result_state(record: dict[str, Any], earlier: Iterator[dict[str, Any]]) -> tuple[str, str]:
    """The last record is a user record: ended when it answers the hand-back, else running."""
    wanted = {str(b.get("tool_use_id")) for b in _blocks(record) if b.get("type") == "tool_result"}
    if not wanted:
        return "running", "its last record is a prompt with no answer yet"
    calls = (b for before in earlier for b in _blocks(before) if b.get("type") == "tool_use")
    for call in calls:
        if str(call.get("id")) in wanted:
            if call.get("name") == HANDBACK_TOOL:
                return "ended", ""
            wanted.discard(str(call.get("id")))
        if not wanted:
            break
    return "running", "its last record is a tool's result with no answer yet"


def transcript_state(path: Path) -> tuple[str, str]:
    """The state of one Claude transcript, from the end of its file: (`ended`, ""), (`running`,
    the cause) or (`unreadable`, the reason). Only the `user` and `assistant` records count; the
    others (`api-request`, `api-request-blob`, `attachment`...) are skipped. It has ended when its
    last such record is the result of the hand-back tool's call, or an assistant record with no
    tool call whose `stop_reason` is `end_turn` or `stop_sequence`. Anything else runs: a tool
    call with no result yet, a tool's result or a prompt with no answer yet, or another
    `stop_reason`. A last line that is not complete JSON, a file that is missing or that cannot be
    opened or decoded, or no user or assistant record at all, cannot be read. The file's age is
    never looked at."""
    try:
        records = _turns_from_end(path)
        last = next(records, None)
        if last is None:
            return "unreadable", "it holds no user or assistant record"
        if last["type"] == "assistant":
            return _assistant_state(last)
        return _result_state(last, records)
    except _Unreadable as e:
        return "unreadable", str(e)
    except FileNotFoundError:
        return "unreadable", "the file is missing"
    except (OSError, UnicodeError) as e:
        return "unreadable", f"{type(e).__name__}: {e}"


def agent_records(root: Path, sessions: list[str]) -> dict[str, tuple[str | None, float | None]]:
    """Claude: agent id -> (parent agent id, seconds since its record was last written), for every
    `subagents/agent-<id>.jsonl` beside each steering transcript. None: a record that cannot be
    read, so its time is not measured."""
    clock = datetime.now(UTC).timestamp()
    found: dict[str, tuple[str | None, float | None]] = {}
    for session in sessions:
        folder = transcript_path(root, session).with_suffix("") / "subagents"
        for f in sorted(folder.glob("agent-*.jsonl")):
            try:
                age: float | None = max(0.0, clock - f.stat().st_mtime)
            except OSError:
                age = None
            try:
                meta = json.loads(
                    f.with_suffix("").with_suffix(".meta.json").read_text(encoding="utf-8")
                )
            except (OSError, ValueError):
                meta = {}
            found[f.stem.removeprefix("agent-")] = (meta.get("parentAgentId"), age)
    return found


def _line_context(raw: bytes) -> int | None:
    """The prompt size of an assistant record (input, cache writes and reads), else None."""
    try:
        d = json.loads(raw)
    except ValueError:
        return None
    m = d.get("message") if isinstance(d, dict) else None
    u = m.get("usage") if isinstance(m, dict) else None
    if (
        d.get("type") != "assistant"
        or not isinstance(u, dict)
        or not isinstance(m, dict)
        or m.get("model") == "<synthetic>"
    ):
        return None
    cc = u.get("cache_creation") or {}
    t = (
        u.get("input_tokens", 0),
        cc.get("ephemeral_5m_input_tokens", 0),
        cc.get("ephemeral_1h_input_tokens", 0),
        u.get("cache_read_input_tokens", 0),
    )
    if any(isinstance(v, int) and v for v in t):
        return sum(v for v in t if isinstance(v, int))
    return None


def _tail_context(path: Path) -> int | None:
    """The last call's prompt size, read from the end of the file, never the whole of it."""
    with path.open("rb") as f:
        size = f.seek(0, os.SEEK_END)
        chunk = 1 << 18
        while True:
            start = max(0, size - chunk)
            f.seek(start)
            lines = f.read(size - start).split(b"\n")
            if start:
                lines = lines[1:]  # the first line may be cut
            found = next((c for c in map(_line_context, reversed(lines)) if c is not None), None)
            if found is not None or not start:
                return found
            chunk *= 2


def agent_context(root: Path, sessions: list[str], agent: str) -> int | None:
    """Claude: the prompt size of an agent's last call (input, cache writes and cache reads), read
    from the end of its `subagents/agent-<id>.jsonl` beside a steering transcript, never from the
    whole file. None: no record found, or no call in it."""
    for session in sessions:
        path = transcript_path(root, session).with_suffix("") / "subagents" / f"agent-{agent}.jsonl"
        if not path.is_file():
            continue
        try:
            found = _tail_context(path)
        except OSError:
            continue
        if found is not None:
            return found
    return None


def last_tool_call(path: Path) -> str | None:
    """The name of the last tool call in a Claude transcript, from the end of its file (the same
    reader as `transcript_state`). None: no tool call in it, or a file that cannot be read."""
    try:
        for record in _turns_from_end(path):
            calls = [b for b in _blocks(record) if b.get("type") == "tool_use"]
            if record["type"] == "assistant" and calls:
                return str(calls[-1].get("name"))
    except (_Unreadable, OSError, UnicodeError):
        return None
    return None


def agent_handed_back(root: Path, sessions: list[str], agent: str) -> bool | None:
    """Claude: whether an agent's last tool call is the host's `SubagentHandback`, read from the
    end of its `subagents/agent-<id>.jsonl` beside a steering transcript. None: not measured (no
    file, unreadable, or no tool call in it), never "ended"."""
    for session in sessions:
        path = transcript_path(root, session).with_suffix("") / "subagents" / f"agent-{agent}.jsonl"
        if not path.is_file():
            continue
        tool = last_tool_call(path)
        if tool is not None:
            return tool == HANDBACK_TOOL
    return None
