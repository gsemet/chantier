"""A Claude transcript and its prices: tokens, cache writes, wakes."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from chantier.core.errors import EXIT_EXTERNAL, ChantierError
from chantier.playbook.config import PRICE_NAMES as PRICE_KEYS

# $/MTok: input, 5-min write, 1-h write, cache read, output, per exact model (a dated id of the
# same model, `claude-sonnet-5-5-20261001`, has the same price). Each price is the provider's
# published one, never inferred. A model not here is not refused: its calls are counted and named
# as not priced, and a project adds its price under `prices:` in `chantier.yaml`.
CACHE_5M, CACHE_1H = 300, 3600  # seconds a cache write lives, by the write used


LONG_CONTEXT_TOKENS = 100_000
PRICE = {
    "claude-opus-5-5": (4, 5, 8, 0.20, 20),
    "claude-sonnet-5-5": (2, 2.5, 4, 0.10, 10),
    "claude-fable-5-2": (8, 10, 16, 0.20, 40),
    "claude-haiku-5-5": (0.10, 0.125, 0.20, 0.01, 0.50),
    "claude-haiku-5-5>100k": (0.50, 0.625, 1, 0.05, 2.50),
}


def projects_dir() -> Path:
    """`CHANTIER_CLAUDE_PROJECTS`, else the host's own ~/.claude/projects."""
    env = os.environ.get("CHANTIER_CLAUDE_PROJECTS")
    return Path(env).expanduser() if env else Path.home() / ".claude" / "projects"


def transcript_path(repo_root: Path, session_uuid: str) -> Path:
    base = projects_dir()
    if not base.is_absolute():
        base = repo_root / base
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(repo_root))
    path = base / slug / f"{session_uuid}.jsonl"
    if not path.exists():  # long folder names get a shortened slug: find the uuid instead
        path = next(base.glob(f"*/{session_uuid}.jsonl"), path)
    return path


def _price(model: str, prompt: int, extra: dict[str, Any] | None = None) -> tuple[Any, ...] | None:
    """The $/MTok of a model: the project's entry (`extra`, from `chantier.yaml`) above the
    built-in table, by the same id or by it without a trailing `-YYYYMMDD`. Nothing else matches:
    no prefix, no family, no nearest model. None: no price, so the calls are not priced. The
    long-context tier applies when the entry has one and the prompt is above its threshold."""
    ids = [model]
    dated = re.fullmatch(r"(.+)-\d{8}", model)
    if dated:
        ids.append(dated.group(1))
    for i in ids:
        entry = (extra or {}).get(i)
        if entry:
            tier = entry.get("long_context")
            if tier and prompt > tier["above"]:
                entry = tier
            return tuple(entry[k] for k in PRICE_KEYS)
        if i in PRICE:
            tier = PRICE.get(f"{i}>100k")
            return tier if tier and prompt > LONG_CONTEXT_TOKENS else PRICE[i]
    return None


def _transcript_lines(path: Path) -> Iterator[str]:
    try:
        with path.open(encoding="utf-8") as transcript:
            yield from transcript
    except (OSError, UnicodeError) as e:
        raise ChantierError(f"cannot read Claude transcript {path}: {e}", EXIT_EXTERNAL) from e


def _wakes(record: dict[str, Any]) -> bool:
    """Whether a user record starts a turn, rather than carrying a tool's result."""
    content = (record.get("message") or {}).get("content")
    return not (
        isinstance(content, list)
        and content
        and all(isinstance(p, dict) and p.get("type") == "tool_result" for p in content)
    )


def _when(text: Any, path: Path, number: int) -> datetime | None:
    """A record's time, to compare as a time and not as text; none when it has none."""
    if not text:
        return None
    try:
        when = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError as e:
        raise ChantierError(f"unreadable timestamp at {path}:{number}", EXIT_EXTERNAL) from e
    return when if when.tzinfo else when.replace(tzinfo=UTC)


GRILL_NAMES = ("01-intent.md", "02-answers.md", "03-change-spec.md", "work/specifying")


WRITE_PATHS = {
    "Write": "file_path",
    "Edit": "file_path",
    "MultiEdit": "file_path",
    "NotebookEdit": "notebook_path",
}  # the host's write tools, and their target


def _grill_use(block: Any, strict: bool = False) -> bool:
    """Whether a tool use belongs to the grill and the specifications.

    Loose (outside a steering window): its input names a CR's intent, answers, specification or
    `work/specifying` marker anywhere, or it starts a spec-writer. Strict (inside a steering
    window, where a turn that only names or reads a specification is steering): it starts a
    spec-writer, or it is a host write tool whose target path ends in one of those names; a shell
    command, a read, or a write to another file whose content names one is not."""
    if not isinstance(block, dict) or block.get("type") != "tool_use":
        return False
    given = block.get("input")
    if isinstance(given, dict) and str(given.get("subagent_type", "")).endswith("spec-writer"):
        return True
    if strict:
        key = WRITE_PATHS.get(str(block.get("name")))
        target = given.get(key) if key and isinstance(given, dict) else None
        return isinstance(target, str) and target.replace("\\", "/").endswith(GRILL_NAMES)
    text = json.dumps(given).replace("\\\\", "/")  # a Windows path, escaped by JSON
    return any(name in text for name in GRILL_NAMES)


def _new_row() -> dict[str, Any]:
    return {
        "calls": 0,
        "usd": 0.0,
        "model": "?",
        "models": set(),
        "w5m": 0,
        "w1h": 0,
        "read": 0,
        "out": 0,
        "wakes": 0,
        "wake_context": 0,
        "peak_context": 0,
        "last_context": 0,
        "usd_in": 0.0,
        "usd_write": 0.0,
        "usd_read": 0.0,
        "usd_out": 0.0,  # dollars by kind
        "compactions": 0,
        "timed": 0,
        "expired": 0,
        "untimed": 0,
        "unpriced": {},
    }  # model id -> calls of a model with no price


def _add(row: dict[str, Any], c: dict[str, Any]) -> None:
    t = c["tokens"]
    row["model"] = c["model"]
    row["models"].add(c["model"])
    if c["parts"] is None:  # no price: counted apart, never in the dollars or the priced calls
        row["unpriced"][c["model"]] = row["unpriced"].get(c["model"], 0) + 1
    else:
        row["calls"] += 1
        for k, v in zip(("w5m", "w1h", "read", "out"), t[1:], strict=False):
            row[k] += v
        row["usd"] += sum(c["parts"])
        row["usd_in"] += c["parts"][0]
        row["usd_write"] += c["parts"][1] + c["parts"][2]
        row["usd_read"] += c["parts"][3]
        row["usd_out"] += c["parts"][4]
    if c["expired"] is not None:  # measured: the gap since the agent's previous call
        row["timed"] += 1
        row["expired"] += c["expired"]
    row["peak_context"] = max(row["peak_context"], sum(t[:4]))
    row["last_context"] = sum(t[:4])
    if c["woke"]:
        row["wakes"] += 1
        row["wake_context"] += sum(t[:4])


def _record(line: str, path: Path, number: int) -> dict[str, Any] | None:
    """One transcript line as a record; none for a blank line."""
    if not line.strip():
        return None
    try:
        d = json.loads(line)
    except ValueError as e:
        raise ChantierError(
            f"unreadable Claude transcript record {path}:{number}", EXIT_EXTERNAL
        ) from e
    if not isinstance(d, dict):
        raise ChantierError(f"invalid Claude transcript record {path}:{number}", EXIT_EXTERNAL)
    return d


def _tokens(u: dict[str, Any], path: Path, number: int) -> tuple[Any, ...]:
    """The five token counts of a usage record, checked: input, 5m and 1h writes, read, out."""
    cc = u.get("cache_creation") or {}
    if not isinstance(cc, dict):
        raise ChantierError(f"invalid Claude cache usage at {path}:{number}", EXIT_EXTERNAL)
    t = (
        u.get("input_tokens", 0),
        cc.get("ephemeral_5m_input_tokens", 0),
        cc.get("ephemeral_1h_input_tokens", 0),
        u.get("cache_read_input_tokens", 0),
        u.get("output_tokens", 0),
    )
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in t):
        raise ChantierError(f"invalid Claude token counts at {path}:{number}", EXIT_EXTERNAL)
    return t


class _Scan:
    """What one pass over a transcript collects: the priced calls, the turns that grill."""

    def __init__(
        self, path: Path, prices: dict[str, Any] | None, in_steering: Callable[[Any], bool]
    ):
        self.path = path
        self.prices = prices
        self.in_steering = in_steering
        self.row = _new_row()
        self.seen: set[str] = set()
        self.calls: list[dict[str, Any]] = []
        self.grill_turns: set[int] = set()  # turns with a grill use, by that use's window rule
        self.window_turns: set[int] = set()  # turns with a strict grill use in the steering window
        self.turn = 0
        self.woken = False  # a prompt, a message or a notification came in; a tool result is not

    def _note_grill(self, d: dict[str, Any], when: Any) -> None:
        """An assistant record: a grill use puts its turn among the grill turns."""
        content = d["message"].get("content")  # one record per block, the same message id
        strict = self.in_steering(when)
        if isinstance(content, list) and any(_grill_use(b, strict) for b in content):
            self.grill_turns.add(self.turn)
            if strict:
                self.window_turns.add(self.turn)

    def _call(self, d: dict[str, Any], when: Any, number: int) -> None:
        """An assistant record inside the window: a priced call, unless it carries no tokens."""
        path = self.path
        m = d.get("message")
        if not isinstance(m, dict):
            raise ChantierError(f"invalid Claude assistant record {path}:{number}", EXIT_EXTERNAL)
        if not m.get("usage") or m.get("model") == "<synthetic>":
            return  # an API error or a session limit: no tokens, no price
        message_id, model, u = m.get("id"), m.get("model"), m["usage"]
        if not isinstance(message_id, str) or not message_id:
            raise ChantierError(f"Claude usage has no message id at {path}:{number}", EXIT_EXTERNAL)
        if message_id in self.seen:
            return
        if not isinstance(model, str) or not model or not isinstance(u, dict):
            raise ChantierError(f"invalid Claude usage at {path}:{number}", EXIT_EXTERNAL)
        t = _tokens(u, path, number)
        if not any(t):
            return  # a record without tokens
        self.seen.add(message_id)
        rate = _price(model, sum(t[:4]), self.prices)
        self.calls.append(
            {
                "turn": self.turn,
                "when": when,
                "model": model,
                "tokens": t,
                "woke": self.woken,
                "parts": None
                if rate is None
                else [a * b / 1e6 for a, b in zip(t, rate, strict=False)],
            }
        )
        self.woken = False

    def feed(self, d: dict[str, Any], when: Any, number: int, inside: bool) -> None:
        """One record: it moves the turn, may mark a grill turn, and, inside the window, may be
        a call, a compaction or a wake."""
        kind = d.get("type")
        if kind == "user" and _wakes(d):
            self.turn += 1
        if kind == "assistant" and isinstance(d.get("message"), dict):
            self._note_grill(d, when)
        if not inside:
            return  # outside the window: neither a call nor a wake
        if kind == "system" and d.get("subtype") == "compact_boundary":
            self.row["compactions"] += 1  # the compaction call itself leaves no priced record
        if kind == "user":
            self.woken = self.woken or _wakes(d)
        if kind == "assistant":
            self._call(d, when, number)


def _place(scan: _Scan, split: bool, window: tuple[Any, Any]) -> dict[str, Any]:
    """Give each call its expiry and its row: the grill's or the rest's."""
    row = scan.row
    grill = _new_row() if split else None
    previous, lifetime = None, 0  # the last call's time, and how long its cache write lives
    for c in scan.calls:
        c["expired"] = None
        if previous and c["when"] and lifetime:
            c["expired"] = (c["when"] - previous).total_seconds() > lifetime
        previous = c["when"]
        t = c["tokens"]
        lifetime = CACHE_1H if t[2] else CACHE_5M if t[1] else lifetime
        row["untimed"] += c["when"] is None
        if split and c["when"] is None and any(window):
            continue  # not placed in the window: counted, in neither share
        turns = scan.window_turns if scan.in_steering(c["when"]) else scan.grill_turns
        _add(grill if grill is not None and c["turn"] in turns else row, c)
    if split:
        row["grill"] = grill
    return row


@dataclass(frozen=True)
class Reading:
    """How `usage` reads a transcript: `split`, `prices` and `steering`, described there."""

    split: bool = False
    prices: dict[str, Any] | None = None
    steering: tuple[str, str] | None = None


def usage(
    path: Path, since: str = "", until: str = "", reading: Reading | None = None
) -> dict[str, Any]:
    """A transcript's calls from `since` to `until`: a session can have run another batch.

    `split`: the calls of the turns that grill with the user or write specifications (a turn is
    from a wake to the next, attributed whole) go to `row["grill"]`, a row of the same shape; the
    row itself keeps the others. `prices`: the project's, above the built-in table; a call of a
    model with none is counted in `row["unpriced"]`, by model. A call with no time cannot be
    placed in a window: with `split` and a window it is in neither, and `untimed` counts it.

    `steering`: the (since, until) of the steering window, when the transcript has one. A tool use
    is judged by the rule of the window its record's `timestamp` falls in: the strict one inside
    it (see `_grill_use`), the loose one elsewhere, a record with no time included. Each call is
    classified by its own window: a call inside the steering window goes to the grill only if its
    turn has a strict grill use inside that window (a loose use outside it, in the same turn, does
    not move it); any other call uses the turns that have a grill use by that use's own window.
    So the calls of the steering window are the same whichever `since`/`until` prices them. With
    no `steering`, every use is loose."""
    reading = reading or Reading()
    split, prices, steering = reading.split, reading.prices, reading.steering
    start, end = _when(since, path, 0), _when(until, path, 0)
    steer_from, steer_to = (
        (_when(steering[0], path, 0), _when(steering[1], path, 0)) if steering else (None, None)
    )

    def in_steering(when: Any) -> bool:
        return bool(
            steering
            and when
            and not (steer_from and when < steer_from)
            and not (steer_to and when > steer_to)
        )

    scan = _Scan(path, prices, in_steering)
    for number, line in enumerate(_transcript_lines(path), 1):
        d = _record(line, path, number)
        if d is None:
            continue
        when = _when(d.get("timestamp"), path, number)
        inside = not ((start and when and when < start) or (end and when and when > end))
        scan.feed(d, when, number, inside)
    return _place(scan, split, (start, end))
