# CR driver: re-takes

## CR driver: re-takes

A CR whose first `take` shows a `PR:` link came back to a
batch: use the branch and worktree `take` printed, never a new branch. Read its PR first (`gh pr
view <n> --json state`, `glab mr view <n>`): open, go on; closed, `gh pr reopen <n>` / `glab mr
reopen <n>` before any push, and if refused hand back `handback <cr> blocked question: its PR
<link> is closed and the forge refuses to reopen it: <exact text>`; merged, hand back `handback
<cr> blocked question: its PR <link> is already merged` (the Chief of Staff records `order merged
<cr>`). Then rebase on the base `take` names, ship to that PR: never open a second PR.

A CR taken with the note `rebase: <cr> merged` and no open dependency or predecessor left (also
a CR with no dependency at all, in a parallel batch): fetch, rebase onto `origin/<default
branch>` (a `conflict-resolver` for a conflict that needs only resolving; one that needs code is
a round), retarget the PR to the default branch if it was elsewhere (`gh pr edit --base`, `glab mr
update --target-branch`), push with `--force-with-lease` (a refused one goes up as written
above), `ship`, read CI (red is a round). After a clean rebase (no conflict, the patch
unchanged), run no long gate and no `verifier`: the pass and the verdict carry, which `ship`
records (`carried:`). Mark each proof of
`pr-body.md` whose SHA left the head's history (the Test plan items, the `Verified at` box, the
evidence captions) as `at <new head7> (carried from <sha7>)`, as `ship`'s `off: pr-body.md line <n> names …`
lines guide, and attach the image files `ship` names as the evidence bullet says (no long gate, no
Verifier: the rule above stands), run the pre-post audit and post the file. With a conflict resolved, run the long
gate at the new head (`ship --conflict`, `driver:conflicts`) with the early push: the PR goes to draft and is pushed at once, the long
gate and the CI watch run side by side by the rules of the "CI" bullet, and the PR leaves draft
once both passed at that head. The `verifier`, given the move, judges again what it touched
before `handback ready`: only after a resolved conflict or a refused carry. Green, no conflict, on
the default branch: turn the PR ready and `handback ready <link>`. A clean rebase and
green CI start no new `coder` round and no new `verifier`. If the note names another open dependency instead, or is
`rebase: <cr> moved`, or `take` prints the base as another CR's branch (the base `take` prints is the CR's place in the
stack, as the record orders it; `; PR on <ref>` after it says the PR's base on the forge is still
another branch: the place wins, rebase onto the place, and the PR's base is the stack driver's to set
(`forge-stack rebuild`), or yours on a `note rebase: stacked on …`, as the next paragraph says;
`; PR base ? (not read from <link>: …)` says the read failed and changes nothing for the rebase),
rebase onto that branch,
keep the PR a draft and `handback ready <link> draft on <base>: waits for <cr>`. A CR taken back
`blocked` for a rebase, after the rebase, is handed back blocked with the same reason it had. A
`note rebase: …` received while working: rebase before the next push, however many `rebase:`
notes came since your last push: one rebase, onto the latest default branch (for the default
branch's notes only; see the next paragraph for `stacked on`). With a long gate of
the CR running, stop it (`gate <cr> --stop`) before that rebase. After a clean rebase run no
new long gate and no new `verifier` (the pass and the verdict carry, recorded at `ship`); after one with a conflict
resolved (`ship --conflict`, `driver:conflicts`), run the long gate at the new head with the early push (the "Early push" rule, `driver:conflicts`);
CI runs at the new head either way. A note `rebase: stacked on <cr below>, without <dropped cr>`
changes the rebase command only: `git -C <worktree> rebase --onto <base> <the dropped CR's branch>`, so the
dropped commits leave the branch; the rest is the rule above. A series CR's PR opens, as a draft,
on the base `take` printed: a Driver still retargets nothing but on a `rebase:` note.

In a stack batch the `base` that `take` prints may be another CR's branch (after a reorder it follows the new order, not the branch the worktree started on): the nearest earlier CR
of the batch that has a PR, handed back `ready`, that the forge does not show merged, or, for a CR with an open `after`, its highest open dependency's branch. Create the worktree on that base and no other, never on a branch with
no PR (the PR's base is the `base` that `take` printed, never another), and open the PR on it as a
draft; that branch is the stack driver's, never rebased by you but on a note or on a `ship` refused `branch not based on`. A `base:` line after
the `worktree:` line says the CLI left a CR out of the base because the forge shows its PR merged (not
recorded yet): it only explains the base; the worktree goes on the base the `worktree:` line names. A `note rebase: stacked on
<cr below>` received while working: rebase onto that CR's branch (not the default branch), retarget
your PR to it (`gh pr edit --base`, `glab mr update --target-branch`) while it is in no native
stack, push with `--force-with-lease`, `ship` (`--conflict` by the rule above).

A `ship` refused in a stack or series batch (a CR placed on another CR's branch, the CR below it in
a series batch its predecessor):
- `branch not based on <cr>'s head` (your first `ship` included, on a branch taken onto another CR's
  branch that has shipped a new head since) means the CR below moved under you. You own your
  branch: rebase onto the branch the refusal names at once, without waiting for a `rebase:` note,
  as for a `rebase: stacked on <cr below>` note (in a series batch, the predecessor's branch), push
  with `--force-with-lease`, and `ship` again. This is a move: `driver-conflicts.md` "CR driver: moves and conflicts"
  applies.
- `<cr>'s branch moved since its last ship (<rec7> -> <tip7>)` means you are already on its branch,
  and that CR has not shipped its new head: do not rebase again; wait for its `ship` (its Driver's,
  or the stack driver's, bottom up), then `ship` again.
- If the forge shows the CR the refusal names already merged, the record does not hold that merge
  yet: once the journal or the record holds the merge (`status` shows it merged), `ship` again.

A CR taken with the note `unhold: <O-m>` (the user's `order unhold` released a CR held while it was
working): resume it as a `resume:` does (`handoff <cr>` for where it stands, the worktree as the
stopped Driver left it); no round is counted. In a stack, rebase onto the branch its `start` line
names before the next `ship`.

A CR taken (or a `note`) with `rebase: <cr> dropped` (a held or parked CR this CR waited with was
dropped out of the batch, in a series or parallel batch): rebase the branch onto the base `take` or
`handoff` names, leaving out the dropped CR's commits (those of its branch that are not on that
base), retarget the PR to that base if it was elsewhere, push with `--force-with-lease`, `ship`,
and go on with the CR's work as before; a conflict is a `conflict-resolver` as for any rebase.
Taken back ready, it is the path of a `rebase:` note, a conflict resolved bringing the long gate
again. The `rebase:` line of `driver.md` "Means: a Driver started again" already sends a Driver there.

A CR taken (or a `note`) with `rebase: mode <mode>` (the batch switched mode with `order mode`; a
stack was dissolved first by `forge-stack unstack` where it applied): put the PR to draft first
on the forge (`gh pr ready --undo`, `glab mr update --draft`), rebase onto the base `take`
printed (parallel: the default branch, or the branch of its open dependency; series: its
predecessor's branch, the bottom CR on the default branch), retarget the PR to it, push with
`--force-with-lease`, then `ship` (`--conflict` by the rule above): that one `ship` records the
draft state and the new base (a `ship` before the rebase is refused, `branch not based on`, when
the new mode puts the CR on another CR's branch), read CI at the new head (the long gate and a `verifier` only when
the carry does not hold: `ship`'s `off: … does not carry` line), and hand back `ready`;
the PR leaves draft once it is ready to merge, as any CR of that mode (a series PR above the bottom
stays a draft). A clean rebase and green CI start no new `coder` round and no new `verifier`.

A CR taken with the note `folded: <k> merged into its branch` (GitLab only: the user merged CR
k's MR, which targeted this CR's branch, so k's change now rides in this CR's MR): bring the
forge's branch into the worktree (`git -C <worktree> fetch`, `git -C <worktree> rebase
origin/<branch>`), then `git -C <worktree> rebase <base>` (the one `take` printed), which
linearizes the fold (a conflict is a `conflict-resolver`'s; never `git reset --hard`), push with
`--force-with-lease`, `ship`; add to
`pr-body.md` one line naming the folded CR's change and its merged MR (Deliverables, and the
Internal references), post the file, then treat it as a move that changed the CR's patch:
`verifier` given the move, `inspector` on it (its `APPROVE` recorded first), the long gate and CI
at the new head, the description pass, and hand back as before. Unproved; trial: one run on a
GitLab project.
