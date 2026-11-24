# Drivers: carries, conflicts and the early push

## Means: carries, conflicts and the early push

- A `ship` refused `holds a merge commit`: rebase onto its base, push `--force-with-lease`, `ship`;
  gate and `verifier` run again. Refused `cannot check`: fetch, `ship`; again refused, `blocked`.
- The forge's rebase action: allowed, unproved; trial: on one CR's PR, on GitHub and GitLab, no
  merge commit is in `<base>..<head>` and `ship` records it with no refusal. The worktree then takes
  that head by fetch and rebase, never a merge; `ship` follows.
- Any change of a PR's base or draft state on the forge (`gh pr ready`, `gh pr ready --undo`,
  `glab mr update --ready`, `glab mr update --draft`, a retarget) is followed by `ship <cr>
  <link>`, so the record follows the forge (a `ship` refused `branch not based on` there: rebase
  first, as that refusal says, then `ship`).
- `ship`'s other lines: a failed read of the forge prints `base ? (not read from <link>: …)` and `draft
  not read`: the CR reads `PR in draft` until a `ship` reads the forge. With the `ci: beside the long
  gate` line `ship` runs before the gate passes, so `off: no long gate passed at <sha>` is expected
  there, as for a PR already recorded after a rebase that needs a long gate (the early push), and
  `handback ready` still refuses a head with no passed long gate, unless the pass carries over a clean
  rebase. `ship` also refuses a PR whose head carries another CR's (`… carries CR-x …`).
- A Conflict resolver's reply: `conflicts.md` exists, with each conflicted hunk and the choice made, and
  the fast gate's command and result.
- After a rebase with no conflict that leaves the
  CR's patch unchanged, run no long gate and no `verifier`: the pass and the Verifier's verdict
  at the head before the rebase carry, and `ship` checks both with git (the exact `git patch-id
  --verbatim` of each of the CR's own commits, oldest first, is the same on the base the judged
  head sat on and on the base the new head sits on, and no merge commit is among them; a base is
  the nearest branch under the head among the batch CRs' branches, local or remote, and the
  default branch, read by git, whatever the record or the PR names), logs a
  `carry` event with `gate_from` and `verdict_from`, and prints `carried:` (or `off:` with the
  reason, with both counts when the patch changed: unequal counts mean the CR's own commits
  were miscounted, an anomaly to report, not a reason to re-verify); `handback ready` reads that event and records the same keys. Any commit added or
  edited is gated again and gets a `verifier` given the move (the hand-back refuses with `does
  not carry: <why>`). **The `ship --conflict` rule, stated once:** any `ship` after a rebase
  during which a conflict was resolved takes `--conflict`, whoever resolved it (a
  `conflict-resolver`, or you) and whoever runs the `ship` (a CR's Driver, the stack driver, the
  release Driver), for a rebase of any reason (a `rebase:` note, `stacked on`, a mode switch, a
  restack, an insertion, a drop). `ship <cr> <link> --conflict` records `conflict: true` and
  voids every pass, verdict and carry recorded before it, at that head and any earlier one, so the
  CR is gated and verified again; the same head shipped again without the flag clears nothing. The CLI reads no CI: you read CI at the new head, which must be green.
- **Early push** (every batch, no `chantier.yaml` key): when a rebase of a CR
  whose PR exists needs a long gate (a `rebase:` note, a restack, a taken-back CR, with a
  conflict resolved), turn the PR to draft if it is not one (`gh pr ready --undo`, `glab mr
  update --draft`), push at once with `--force-with-lease`, `ship <cr> <link>`, then
  start the long gate and the CI watch side by side, by the outcomes of the "CI" bullet (a red
  CR job stops the gate, a failed gate stops the watch). The PR leaves draft (`gh pr ready`,
  `glab mr update --ready`, then `ship`) only once the gate has passed and
  CI is green at that same head. A PR that does not exist yet still waits for its gate before
  its first push, unless the project chose `ci: beside_gate: true`.
- A rule that asks a local run (by shape): a rule that names each shape (parallel, series, stack)
  is followed as written; a rule that names the stack's top alone is read by the batch's shape (the
  `shape` word of `$CHANTIER status`). In a stack, the stack's top owes the run, a top the rules
  exempt from the long gate (docs only) included ("The local gate at the mergeable top" is the
  stack driver's). In a parallel or series batch, each CR the long gate covers owes it, since each
  PR lands alone on the default branch: a CR the rules exempt from the long gate owes none, a fix
  CR counts, and a pipeline job named as the long gate is still checked (`driver-trouble.md` "Means: CI beside the
  long gate"), the local run being in addition to it. The CR's Driver meets it with `$CHANTIER
  gate` as any long gate, in your worktree, clean, at your pushed head, unless a pass or a carried
  pass is already there (`ship`'s `carried:` line), before the `ship` that precedes your ready
  hand-back, and so before you take the PR out of draft (the hand-back bullet's order: `ship`,
  `gh pr ready`, `ship` again, `handback`), and hands back with no `--no-gate`. A `take` note that
  says `long gate: this CR runs <command> locally` (in a stack, `long gate: the stack's top runs
  <command> locally`), alone or after `rebase: <cr> merged; ` in the same note, asks the same run
  at the head you push after that `take` (the rebased head). A failure there is a round, as for
  any long gate. A Release driver runs no local gate for this rule. No Windows run is asked on
  the merged result.
- `ship` refuses, and
  records nothing, a PR on the default branch and out of draft whose head carries the head of
  another CR of the batch not recorded merged and with a PR (`… carries CR-x (<link>): merging it
  would merge them too …`). The first step is always the same: draft, then `ship`. Put the PR
  back to draft (`gh pr ready --undo`, `glab mr update --draft`) and `ship` again, which records
  the PR in draft so the CR no longer reads mergeable; then, if the PR is to stay on the default
  branch, rebase it onto it without those commits, push, and `ship` again. If the CR named is
  already merged on the forge, `ship` again once `status` shows it merged. For the stack driver
  it means a PR moved without first going to draft, as the stack driver section asks.

## CR driver: moves and conflicts

A move is any change of the head after a judgment: a new round, a rebase, a restack, a conflict
resolution. A clean rebase that leaves the CR's patch unchanged is a move that touches no
judgment: no `verifier` and no `inspector` are due for it. Every `verifier` you start after the first is given the previous `verify.md`, the move
(`<old head>..<new head>`, with the old and new base for a rebase) and its kind, so it judges
again only what the move touched. A rebase during which a `conflict-resolver` ran is always a
change of the CR's patch: the `inspector` on that change is due without reading a range-diff to
decide it. It reviews that change alone, with no `$CHANTIER round` and no `coder`, as for a
body-only re-inspection; `FIX-REQUIRED` on the code is a round. Each such rebase gets its own
`inspector` before the next push, and its pass is recorded as `move <old7>..<new7> (conflict)
inspector approved at <head>`. Several rebases since the last push are inspected once, on the
patch as it stands after the last of them, against the head of the last pass. Before
`handback ready`, no proof in the PR is stale.
