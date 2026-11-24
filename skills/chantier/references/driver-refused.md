# Drivers: a refused force push or rebase

## Means: a force push the host refuses

- A force push the host refuses (any Driver that pushes; a rebase: "Means: a rebase the host
  refuses", below) climbs the ladder of
  [foreman](foreman-refused.md#a-drivers-refused-force-push), "A Driver's refused force push" (the
  steering session judges it and runs it; if the host refuses it there, the Chief of Staff judges
  it again and runs it; if the host refuses the Chief of Staff, the user is asked once), without
  the user's word in the normal case. In direct mode the steering session is the Chief of Staff,
  so the ladder is Driver, Chief of Staff, the user.
  This holds for a CR Driver and the Release driver (both hand back with `handback <cr>`); the
  stack driver keeps its own rule, below. With your work committed:
  1. Record the refusal first, in one note: `$CHANTIER note <cr> "refused: <the exact command> ->
     <the host's exact text>"`: the command as it ran (its `git -C <path>` form included, flags
     and refspec as typed), and the host's whole text as it came (with the classifier's label,
     such as "Git Destructive", when the host gives one). Never a summary such as "refused by
     host". It is what proves afterwards a missing allow rule or the classifier on a matching rule.
  2. Then one note with what is next: `$CHANTIER note <cr> "next after push: <the steps left, in
     order>"` (for instance: `ship`, the long gate already passed at `<sha7>`, read CI, the
     verifier given the move (unless the rebase was clean: the verdict carries), turn the PR
     ready, hand back ready), so a fresh Driver starts from it
     without reading the whole record again.
  3. `$CHANTIER handback <cr> blocked waits: push <branch> <expected remote sha> <local sha>`
     (the remote head you expect, from `git ls-remote`, and your head).
  4. Send `[driver <cr>→foreman] push <branch> <expected remote sha> <local sha>`, and end: no
     other push, no other way, and no wait in your turn. The CR waits, not you; the steering
     session restarts a fresh Driver on it when the push's answer comes back (the Foreman's, or the
     Chief of Staff's).

  The fresh Driver reads the answer in its `take` note (`push: <the answer>`) and acts on it, from
  your `next after push` note: `pushed <branch>`: `ship` and go on. `push failed`: look at why
  (`git fetch`, what the remote gained), never the same push again. `push refused <branch>: no
  long gate passed at <sha>`: run the long gate, send the push line again and hand back `waits:`
  again as above (with the `ci: beside the long gate` line, and for a branch whose PR is
  recorded (the early push), the steering session does not send it; one you get anyway goes to the
  steering session as printed). Any other `push refused` (the
  branch is not this batch's or not a chantier branch, the push was judged not legitimate and the
  user said no, or the host refused it at every step, the user's yes included) and a push the
  forge rejects as protected (`push failed`): `handback blocked
  refused <exact text>` at once; it goes to the user. Any other refused action stays `blocked
  refused` as above. The stack driver, which restacks several branches in one take, sends one
  push line per refused branch and waits for each result as a note (the result may now come from
  the Foreman's own push), no other push, no other way. The Release driver is covered by the same
  section, with no text of its own.

## Means: a rebase the host refuses

The ladder of [foreman](foreman-refused.md#a-drivers-refused-rebase), "A Driver's refused rebase", as for
a push: the steering session runs it, then the Chief of Staff, then the user. Work committed:

1. `$CHANTIER note <cr> "refused: <the exact command> -> <the host's exact text>"`, as for a push.
2. `$CHANTIER note <cr> "next after rebase: <the steps left, in order>"`, as for a push.
3. `$CHANTIER handback <cr> blocked waits: rebase <branch> <base>` (`base` as `take` printed it).
4. Send `[driver <cr>→foreman] rebase <branch> <base>` and end.

The fresh Driver reads the answer in its `take` note: `rebased <branch> onto <base> at <sha7>`:
push (`--force-with-lease`) and go on; `rebase conflict <branch> onto <base>`: the rebase is
stopped at the conflict in the worktree, start a `conflict-resolver` on it; `rebase refused
<branch>: <text>`: `handback blocked refused <text>`. The stack driver, which restacks several branches in one take,
sends one rebase line per refused branch, as for its pushes, and waits for each result as a note.
