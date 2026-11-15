"""`verdict VERIFIED` is refused unless the CR's `work/verify.md` names the head it records."""

from __future__ import annotations

from pathlib import Path

import pytest
from batch_helpers import changes, open_batch, record
from conftest import Chantier, sh

from chantier.core.errors import EXIT_PRECONDITION

STALE = "0123456789abcdef0123456789abcdef01234567"
# label, the note's text (None: no file; "{head}" is the worktree's head), code, part of stderr
CASES = [
    ("no file", None, EXIT_PRECONDITION, "no such file"),
    ("no Head line", "# Verify\nclaims\n", EXIT_PRECONDITION, "no Head: line"),
    ("short sha", "Head: {head7}\n", EXIT_PRECONDITION, "its Head: line names"),
    ("another commit", f"Head: {STALE}\n", EXIT_PRECONDITION, "its Head: line names"),
    ("full, indented, in backticks, trailing text", "  Head: `{head}` (worktree HEAD)\n", 0, ""),
]


def _verdicts(repo: Path) -> int:
    log = changes(repo) / "4-batch" / "events.jsonl"
    return sum('"verdict"' in ln for ln in log.read_text(encoding="utf-8").splitlines())


@pytest.mark.parametrize("case", CASES, ids=[c[0] for c in CASES])
def test_verified_needs_a_verify_note_naming_the_head(
    repo: Path,
    chantier: Chantier,
    monkeypatch: pytest.MonkeyPatch,
    case: tuple[str, str | None, int, str],
) -> None:
    label, text, code, part = case
    (one,) = open_batch(repo, chantier, monkeypatch, "Note one")
    assert chantier("take", one, "--epoch", 1)[0] == 0
    cr = record(repo)["crs"][0]
    sh("git", "worktree", "add", "-q", "-b", cr["branch"], cr["worktree"], "HEAD", cwd=repo)
    head = sh("git", "rev-parse", "HEAD", cwd=cr["worktree"])
    note = changes(repo) / cr["path"] / "work" / "verify.md"
    if text is not None:
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(text.format(head=head, head7=head[:7]), encoding="utf-8")
    before = _verdicts(repo)
    got, _, err = chantier("verdict", one, "VERIFIED")
    assert got == code and part in err, f"{label}: {got} {err}"
    assert _verdicts(repo) == before + (1 if code == 0 else 0), label
    if label == "no file":
        assert chantier("verdict", one, "NOT VERIFIED")[0] == 0
        assert _verdicts(repo) == before + 1
