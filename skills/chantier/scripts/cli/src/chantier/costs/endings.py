"""The states of a batch's Claude transcripts, split for `close`: the agents the batch holds and
every other transcript."""

from __future__ import annotations

from collections.abc import Collection
from pathlib import Path

from chantier.costs.sessions import Ending, transcript_state
from chantier.costs.transcripts import transcript_path


def _key(stem: str, ids: Collection[str]) -> str | None:
    """The recorded id a subagent file stem stands for (the stem or without its `agent-`)."""
    return next((k for k in (stem, stem.removeprefix("agent-")) if k in ids), None)


def _missing(agent: str, owner: str) -> Ending:
    """A held id with no transcript file anywhere: it cannot be read, and the way out is named."""
    return Ending(
        f"transcript of {agent} ({owner})",
        agent,
        Path(),
        "unreadable",
        f"no transcript found; if it is not running, clear it: agents set {owner} - --epoch <n>",
        missing=True,
    )


def transcript_endings(
    root: Path,
    sessions: list[str],
    own: list[str] | None = None,
    held: dict[str, str] | None = None,
    record_only: set[str] | None = None,
) -> tuple[list[Ending], list[Ending]]:
    """Claude: (the held agents' states, the other transcripts' states), each read once (see
    `transcript_state`). Held: the current Foreman's main transcript (the last session) and each
    `subagents/agent-<id>.jsonl` whose stem is, or minus its `agent-` prefix is, a key of `held`
    (a recorded id -> the label that names its owner, a CR or an order: the same two spellings
    `close --stopped` takes); a held id with no file under any session is `unreadable` ("no
    transcript found", the way out named). Other: every other subagent file, and the main
    transcript of each earlier session (a replaced Foreman). `record_only` (recorded ids): a
    recorded stack agent, a record cause alone, its transcript is not read. `own`: the sessions
    that ask (a direct batch's Chief of Staff): their main file is skipped, their subagents are
    read."""
    own, held, record_only = own or [], held or {}, record_only or set()
    mine: list[Ending] = []
    others: list[Ending] = []
    seen: set[str] = set()
    for i, session in enumerate(sessions):
        main = transcript_path(root, session)
        if session not in own:
            ending = Ending(f"transcript {session}", session, main, *transcript_state(main))
            (mine if i == len(sessions) - 1 else others).append(ending)
        for f in sorted((main.with_suffix("") / "subagents").glob("agent-*.jsonl")):
            if _key(f.stem, record_only):
                continue
            ending = Ending(f"transcript {session} {f.stem}", f.stem, f, *transcript_state(f))
            found = _key(f.stem, held)
            if found:
                seen.add(found)
            (mine if found else others).append(ending)
    mine += [_missing(agent, owner) for agent, owner in held.items() if agent not in seen]
    return mine, others
