# Stack driver: an insertion, a drop, a hold, a park, a conflict, heavy CI

## Stack driver: changes to a stack on the forge

**Inserting into a stack ready to merge.** Taken with a note that names the new CR and its place
(`take stack --note "insert: <new cr> below <cr>"`):

1. Every PR that will sit above the new one goes back to draft first (`gh pr ready --undo`, then
   `$CHANTIER stack --draft <cr>…`),
   before any other step, so the user cannot merge the stack while it changes (the Chief of Staff
   may have done it already: check it on the forge).
2. Order the stack with the new CR at the place named (`$CHANTIER stack <cr>…`, bottom first; the
   release CR stays last), rebase the new PR on the one under it and each PR above on the one
   under it, push with `--force-with-lease`, `ship` each one moved, bottom up (`--conflict` by the rule of the
   long-gate bullet; fix the PR body lines `ship` names as stale, as above); the proofs a move touched are judged again as above (`verifier`,
   `inspector`), a clean restack carrying the verdict.
3. Update the stack on the forge: `$CHANTIER forge-stack rebuild` (it dissolves the stack,
   retargets the PRs, creates it again and reads it back).
4. The release PR: the insertion is a change of content under it, so it is stale: leave it a draft
   and hand back; the Foreman sends the release back (`take <release> --note "redo: <new cr>
   inserted"`) so that its notes name the new change, then takes the stack again.
5. Verify every PR of the stack again on the forge (the five checks), run the local gate at the
   mergeable top when its head carries no pass, and only then, after the chain check, turn the PRs
   above ready (`stack --out-of-draft <cr>…`), the release PR last; hand back with the stack's link.

**Removing a dropped CR.** Taken with a note, or sent one, that names `drop: <cr> to <destination>`
(`6-trash`, `3-ready` or `2-backlog/P<n>`; a `drop: <cr>` with no destination, from an older
Foreman, means the trash; a `1-inbox` from an older Foreman is the backlog's case: the PR to a
draft). Steps 1 to 4 apply to every destination:

1. Turn every PR above the dropped one back to a draft first (`gh pr ready --undo`, `glab mr
   update --draft`, then `$CHANTIER stack --draft <cr>…`): the user must not merge a stack that still holds the dropped commits.
2. Take the dropped commits out of each CR above that has no live Driver (handed back `ready`, or `blocked`),
   bottom up, in its own worktree. The first CR above sits on the dropped CR's branch: `git -C
   <worktree> rebase --onto <the branch now under it, or origin/<default branch>> <the dropped CR's
   branch>`. Each CR above that one: `git -C <worktree> rebase --onto <branch under it> <that branch's head before this take>`, the
   old head being the `head` that `$CHANTIER stack` printed for that CR before the take's first
   rebase. Skip a `working` CR: its Driver does it, on the Foreman's note. A conflict that only
   needs resolving goes to a `conflict-resolver`; one that needs code goes the way "A conflict
   that needs code" says.
3. Push each moved branch with `--force-with-lease`, one command per branch, and `ship` each one,
   bottom up (`--conflict` by the rule of the long-gate bullet). Judge again the proofs each move touched (a
   `verifier` given the move, and an `inspector` when the patch changed, always after a
   `conflict-resolver`); a drop carries when the CR's own commits are unchanged, as `ship` says
   (`carried:` or `off:`). Fix the PR body lines `ship` names as stale.
4. Heavy CI at the top. Then `$CHANTIER forge-stack rebuild`: it unstacks the stack that still
   holds the dropped CR's PR, and names that PR apart (`it also held #n of <cr>, dropped: close
   it` for a trashed CR; `it also held #n of <cr>, moved to <destination>: left out, on main` for
   one moved out, whose PR the rebuild retargets onto the default branch itself).
5. For a trashed CR, close its PR (`gh pr close <n>`, `glab mr close <n>`), with no
   `--delete-branch` and no comment; its branch and worktree stay until the user's word at
   `close`. For a CR moved to the backlog or the next batch (`3-ready`), turn its PR to a draft (`gh pr ready
   --undo`, `glab mr update --draft`): no close, no comment, no rebase of its branch, no retarget
   by hand; its branch and worktree stay.
6. Run the local gate at the mergeable top when its head carries no pass, then, after the chain check, turn the
   mergeable part ready (`stack --out-of-draft <cr>…`). A release above stays a draft, waiting for the Foreman's
   `redo:`. Hand back as for any take.

**A CR held out of the stack.** Taken with a note `hold: <cr>` (the CR's base is now the default
branch; the CRs above it no longer stand on it):

1. Turn every PR above the held CR to a draft first (`gh pr ready --undo`, `glab mr update
   --draft`, then `$CHANTIER stack --draft <cr>…`): the user must not merge a stack that still
   holds the held CR's commits.
2. Take the held CR's commits out of each CR above it that has no live Driver (handed back
   `ready`, or `blocked`), bottom up, as steps 2 and 3 of "Removing a dropped CR" say (`rebase
   --onto`, push with `--force-with-lease`, `ship`); a `working` CR above is skipped: its Driver
   does it, on the Foreman's rebase note, as for a drop.
3. Rebase the held CR's own branch on `origin/<default branch>` (`git -C <worktree> rebase
   origin/<default branch>`), push it with the Push bullet's rewrite form
   (`--force-with-lease`), and `ship` it. A held CR at the top of the stack has nothing above it:
   only this step, step 4 and the rebuild.
4. Turn the held CR's PR to a draft (`gh pr ready --undo`, `glab mr update --draft`, then
   `$CHANTIER stack --draft <cr>`). A held CR is never turned out of draft: `stack --out-of-draft`
   refuses it.
5. `$CHANTIER stack <cr>…` orders the rest (the CRs of `chain`, held ones apart), then
   `$CHANTIER forge-stack rebuild`: it dissolves the stack, moves the held PR to the default
   branch (`held out of the stack`) and makes the stack without it.
6. Read it back (the five checks), run the local gate at the mergeable top when its head carries
   no pass, and, after the chain check, turn the mergeable part ready again (`stack --out-of-draft <cr>…`, the held CR
   never named).

A clean rebase carries the CR's gate and verdict as any clean restack. A conflict that only needs
resolving goes to a `conflict-resolver`, and the proofs a move touched are judged again by the
rule above (a `verifier` given the move, an `inspector` when the patch changed, always after a
`conflict-resolver`); one that needs code goes the way "A conflict that needs code" says.

**A CR parked.** Taken with a note `park: <cr>` (the CR left the stack for an outside wait, as a
held one: its base is the default branch, and the CRs that wait with it, its dependents, stay
out of the stack too): the steps of "A CR held out of the stack", for the parked CR and its
dependents; its PR is turned to a draft and left out by `forge-stack rebuild` (`parked out of the
stack`), and a dependent's PR with it (`waits with`). When it comes back, it is a working CR
that joins on top, as for `unhold`.

For a CR held while working (`order hold <cr>` of a live CR; `blocked`, its Driver ended by
`claim lost`), the same take differs in two steps. Step 2 skips each CR above that depends on the
held CR (an `after`, or a series start on it): it is out of the stack with it and keeps the held
CR's commits. Step 3 is skipped whatever its worktree: the stack driver never rebases a CR held
from live; its worktree may hold its stopped Driver's work, and its next Driver rebases it at its
return. Its PR goes to a draft and, by the rebuild, to the default branch, its branch as it stands.

With `unhold: <cr>` for a CR held from ready, the CR comes back on top: it is a ready CR that
joins, handled as "A draft that turns ready to merge" (ordered below the drafts, rebased,
`forge-stack rebuild`, turned ready, `stack --out-of-draft <cr>`). A CR held from live comes back
as a working CR does: the next `take stack` prints it `not on its place`, the Foreman sends its
Driver `note rebase: stacked on <cr below>`, and it is ordered on top as it hands back. The
final-order take orders only the CRs of `chain` (held CRs apart).

A note `rebase: <cr> dropped` (a parked or held CR with dependents was dropped, in a series or
parallel batch): rebase onto the default branch, or onto the branch the `worktree:` line names,
without the dropped CR's commits, as for `rebase: <cr> moved`.

A dropped CR with an open PR and nothing on its branch needs only steps 4 and 5; one with no PR
and nothing on its branch needs nothing from you.

**A conflict that needs code,** at the join or the move of a CR with no live Driver: `git -C <worktree> rebase
--abort` and push nothing for it; turn its PR to a draft; place it on top among the
drafts with `stack` (above the CRs it does not depend on, the release last), where it stays in the
stack as it stands (its PR retargeted by the rebuild, its branch not rebased); go on with the rest
of the take, the `rebuild` included; before the hand-back, send `[stack→foreman] anomaly <cr>
conflict: stacked on <cr below>: <files>`.

**Heavy CI on a head.** A note `heavy CI: <cr>` (the user asked for it): run the project's heavy
CI at that PR's pushed head by the means the project's rules give (a re-run, a label, a workflow
dispatch); when the forge already ran it at that head, only read the result. Judge it as the CI
bullet says (the head first, a skipped job is never green, the `timing:` line's re-runs for an
infrastructure failure), note it in that form (`CI: gh pr checks <n> at <head7>: …`), and name it in your
hand-back as `heavy CI <cr> at <head7>: green|red <checks>`. A red result changes nothing by
itself.
