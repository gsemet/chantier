"""A Driver's steps, in order, and the words of each (`chantier next <cr>` and the `next:` lines):
data only, light, importable by the parser. `status/advice.py` walks them; the rails keep their
refusals. The fields: `{cr}`, `{n}` (the CR's lease), `{h}` (the head's 7 characters), `{pr}`,
`{worktree}`, `{gate}` and `{named}` (the long gate's name, and the names when there are several),
`{remote}`, `{branch}`, `{pushed}`, `{to}` (who hears the hand-back) and `{no_gate}`."""

from __future__ import annotations

from typing import NamedTuple


class Step(NamedTuple):
    """One step: its name, its words while it is not done, and its other words (a failure, or no
    PR yet), empty when it has none."""

    name: str
    text: str
    other: str = ""


NEW_ROUND = "a new round (`round {cr} --lease {n}`)"
GATE_CALL = "`gate {cr} {gate} --lease {n}`{named}"
NO_GATE = 'chantier.yaml names no long gate: the hand-back takes --no-gate "<the project\'s rule>"'
DRIVER_STEPS = (
    Step("round", "`round {cr} --lease {n}` before the round's Coder"),
    Step(
        "in-round",
        "the round's Coder, then its reviews; commit in {worktree}; then the long gate ("
        + GATE_CALL
        + ")",
        "the round's Coder, then its reviews; commit in {worktree}; then the hand-back: " + NO_GATE,
    ),
    Step("dirty", "commit the worktree's changes: a gate, a push and a verdict bind to a commit"),
    Step(
        "gate",
        "the long gate at {h}: "
        + GATE_CALL
        + ", or `--no-gate \"<the project's rule>\"` on the hand-back when the project's rules "
        "exempt {cr}",
        "the long gate failed at {h}: fix it in " + NEW_ROUND,
    ),
    Step("push", "`push {cr} --lease {n}` ({remote}/{branch} is {pushed})"),
    Step(
        "ship",
        "`ship {cr} {pr} --lease {n}`",
        "open the PR, then `ship {cr} <pr link> --lease {n}`",
    ),
    Step(
        "ci",
        "CI on {pr} at {h}: green, start the Verifier at {h}; red, " + NEW_ROUND,
    ),
    Step(
        "verdict",
        'the Verifier\'s `verdict {cr} VERIFIED` (or "NOT VERIFIED") at {h}, with '
        "work/verify.md's Head: line",
        "verdict NOT VERIFIED at {h}: " + NEW_ROUND,
    ),
    Step("handback", "`handback {cr} ready {pr}{no_gate} --lease {n}`, then send its line to {to}"),
)
HANDED_BACK = "send the hand-back line above to {to}; nothing else is due from you"
