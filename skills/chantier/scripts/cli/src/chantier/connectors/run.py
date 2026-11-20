"""The one way a connector calls its forge: the user's own program, a read-only GraphQL query."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from chantier.core.errors import EXIT_EXTERNAL, ChantierError

TIMEOUT_S = 20  # a hung `gh` or `glab` holds one worker and the project's lock for this long
SHOWN_CHARS = 300


def _line(text: str) -> str:
    return " ".join(text.split())[:SHOWN_CHARS]


def guard(call: list[str]) -> None:
    """Only `api graphql ...` or `api --hostname <host> graphql ...` with one `query=` value that
    starts with `query` and holds no mutation; anything else is a code fault."""
    head = call[:4] if call[1:2] == ["--hostname"] else call[:2]
    ok = head[:1] == ["api"] and head[-1:] == ["graphql"] and len(head) in (2, 4)
    queries = [a[len("query=") :] for a in call if a.startswith("query=")]
    assert ok, f"a connector runs only `api [--hostname <host>] graphql`, not {call[:4]}"
    assert len(queries) == 1, "a connector sends one query"
    assert queries[0].lstrip().startswith("query"), "a connector sends a query"
    assert "mutation" not in queries[0].lower(), "a connector never sends a mutation"


def run(program: str, call: list[str]) -> dict[str, Any]:
    """One call, answered as JSON; a failure comes back as the forge's own one line."""
    guard(call)
    exe = shutil.which(program)
    if not exe:
        raise ChantierError(
            f"{program}: not found on PATH (the user's own `{program}` login is needed)",
            EXIT_EXTERNAL,
        )
    shown = f"{program} api graphql"
    try:
        p = subprocess.run(
            [exe, *call],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as e:
        raise ChantierError(f"{shown}: no answer in {TIMEOUT_S} s", EXIT_EXTERNAL) from e
    except OSError as e:
        raise ChantierError(f"{shown}: {_line(str(e))}", EXIT_EXTERNAL) from e
    if p.returncode != 0:
        raise ChantierError(f"{shown}: {_line(p.stderr or p.stdout)}", EXIT_EXTERNAL)
    try:
        got = json.loads(p.stdout)
    except ValueError as e:
        raise ChantierError(f"{shown}: not JSON: {_line(p.stdout)}", EXIT_EXTERNAL) from e
    if not isinstance(got, dict):
        raise ChantierError(f"{shown}: unexpected answer: {_line(p.stdout)}", EXIT_EXTERNAL)
    if got.get("errors"):
        said = "; ".join(
            str(e.get("message", e)) if isinstance(e, dict) else str(e) for e in got["errors"]
        )
        raise ChantierError(f"{shown}: {_line(said)}", EXIT_EXTERNAL)
    return got


def node(box: dict[str, Any], key: str, n: int) -> dict[str, Any]:
    """The PR or MR aliased `<key><n>` in an answer, or the error if the forge does not show it."""
    found = box.get(f"{key}{n}")
    if not found:
        raise ChantierError(f"the forge does not show #{n}", EXIT_EXTERNAL)
    out: dict[str, Any] = found
    return out
