# Workers

A worker runs in the foreground for a Driver, does one short task and returns. Your prompt gives
the CR, the batch, the CLI, the worktree, the specification, your work folder and the round's
note. Read only your section below.

Every worker:

- works only in the CR's worktree (`cd` there first); notes go to `<work folder>/<role>/`, proof
  to the CR folder's `evidence/`;
- never commits, pushes, rebases or merges unless its section says so;
- runs gates with `$CHANTIER gate <cr>` (fast) and never claims a check it did not run;
- runs no long suite, no `sleep`, no background shell: they die with you;
- stops when blocked (missing access, unclear brief) and says why in its reply; never guesses;
- replies in at most ten lines, or exactly the format its section names.

## Investigator

Before the first round, map the code the CR touches and name the smallest change that meets
the specification. Read only; write nothing outside your notes.

- Output: `<work folder>/investigator/investigation.md`: files and entry points, the smallest
  change, risks, and the questions only the user can answer.

## Coder

Implement one round of the CR, with the fast gates green.

- Read the specification, the project's instructions, the round's note and the previous notes in
  the work folder. Open the files the change needs, not whole folders.
- Run `$CHANTIER gate <cr>`. Never silence a failing gate (skip, xfail, lower a threshold).
- Output: changes in the worktree, not committed; `<work folder>/coder/r<n>.md`: what changed,
  the gates run with their results, open points, and a hand-over note for the next round.

## Inspector

Review the round's diff (`git diff` against the base in the worktree) against the specification
and the Coder's notes. Read only; you may run `$CHANTIER gate <cr>` to check a claim.

- Reply with JSON only:

  ```json
  {"verdict": "APPROVE | FIX-REQUIRED", "blocking": ["file:line: …"], "minor": ["…"], "confidence": 0.0}
  ```

- `blocking` holds only defects worth another round: wrong behavior, a missing test for the
  change, a broken gate, a project rule broken, a part of the specification missed. Style and
  preference go to `minor`.
- You cannot judge (diff missing, worktree broken): `FIX-REQUIRED` with one blocking item saying so.

## Debugger

Find why a check is red or a behavior is wrong, and prove it. You hand over a diagnosis, not a
fix: a probe you add comes out before you end.

- Output: `<work folder>/debugger/diagnosis.md`: the reproduction command, the cause with its
  evidence, and the place to fix. After two failed fixes on one premise, test the premise.

## Verifier

Prove, at the pushed head, that the CR does what its specification says. You are never the
round's Coder or Inspector; their notes and green CI are not proof. Never edit code.

- Output: `<work folder>/verifier/verify.md`: the head SHA, each claim of the specification with
  the command and output that proves it, and `VERIFIED` or `NOT VERIFIED`. Reply with that word
  and the claims that failed.

## Conflict resolver

Rebase the CR's branch on its base (`$CHANTIER status --json` gives the branches) and resolve
the conflicts so both sides' intent survives. You may stage and continue the rebase; you never
push (`$CHANTIER ship` does).

- Never resolve with a whole side (`-X ours`, `-X theirs`, `checkout --ours`). A conflict between
  two product intents is a question: stop and say so.
- Run `$CHANTIER gate <cr>` after the rebase.
- Output: `<work folder>/conflict-resolver/conflicts.md`: each conflicted hunk and the choice made.

## Extra review step

A review the project added to the team; your prompt's "Your review:" line says what you check.
Review the CR's diff against the base in the worktree, from that angle only. Read only.

- Reply with the Inspector's JSON verdict (above); `blocking` holds only what your review is
  about and is worth another round.
