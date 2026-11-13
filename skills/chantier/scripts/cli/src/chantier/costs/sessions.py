"""The cost of a batch's sessions and agents, from the transcripts on disk."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from chantier.core.errors import EXIT_EXTERNAL, ChantierError
from chantier.costs.copilot import copilot_home
from chantier.costs.transcripts import Reading, transcript_path, usage


def _held(row: dict[str, Any]) -> int:
    """The calls of a row, priced or not."""
    return row["calls"] + sum(row["unpriced"].values())


@dataclass(frozen=True)
class Scope:
    """How a transcript is read: `kind` (the Foreman or the Chief of Staff), whether a window
    without a call is allowed, whether the grill is split off, the prices, and the main
    transcript's steering window (see `usage`)."""

    kind: str = "foreman"
    allow_empty: bool = False
    split: bool = False
    prices: dict[str, Any] | None = None
    steering: tuple[str, str] | None = None


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
    foreman = usage(main, since, until, Reading(split, prices, steering))
    if not _held(foreman) + (_held(foreman["grill"]) if split else 0) and not allow_empty:
        raise ChantierError(f"no priced calls in {label} transcript: {main}", EXIT_EXTERNAL)
    rows = [{"agent": "main", "type": kind, "description": "", **foreman}]
    sub = main.with_suffix("") / "subagents"
    if sub.exists():
        for f in sorted(sub.glob("agent-*.jsonl")):
            meta_path = f.with_suffix("").with_suffix(".meta.json")
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            row = usage(f, since, until, Reading(prices=prices))
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


def without_spec_writers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The Chief of Staff's subagents of type spec-writer (`spec-writer`, `chantier:spec-writer`,
    `chantier-spec-writer`) belong to no batch: they stay on the Chief of Staff's own line."""
    return [r for r in rows if not is_spec_writer(r)]


def is_spec_writer(row: dict[str, Any]) -> bool:
    return str(row.get("type", "")).endswith("spec-writer")


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
    if d.get("type") != "assistant" or not isinstance(u, dict) or m.get("model") == "<synthetic>":
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
