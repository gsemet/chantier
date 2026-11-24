# Stack driver: making the stack and the checks

## Stack driver: making the stack

**Making the stack.** Once two CRs are handed back ready with their PRs (the rows' `ready`, whatever the draft flag), the moment the stack can form (ordered,
restacked, pushed, `ship`ped, CI green at the top), create the native stack on the forge with the
means your prompt names: the `gh stack` extension, or `$CHANTIER forge-stack create` when the
user declined the extension (it retargets the PRs of the stack as it stands whose base is not the
record's, then creates the stack, in one command; never a retarget by hand); the PRs bottom to top, the CRs not handed back ready on top, as drafts; the CRs handed back ready form the mergeable part, turned ready after the stack is made. The first take ends with the stack made, whatever a working CR is doing. Then, after the chain check, turn every PR of
the mergeable part ready (`gh pr ready`), not only the bottom one, and record them right after
the forge command: `$CHANTIER stack --out-of-draft <cr>…` (refused for a CR not handed back `ready`
for one with a draft under it, and for one whose recorded head does not hold its CR below's). A means that is not available as the prompt names it
(the extension not installed, the command refused by the forge, the API missing) is an `anomaly`
with the exact text: no other means without the user's word (no fallback). On GitLab the means is always
`$CHANTIER forge-stack create` (no extension): the MRs of the mergeable part are turned ready
(`glab mr update <iid> --ready`, then `stack --out-of-draft <cr>…`), the drafts on top left drafts (unproved; trial: one run on a
GitLab project). Any later change to a stack already on the forge (an
insertion, a restack after a merge, a reorder) is `$CHANTIER forge-stack rebuild`, after the
rebases and pushes: it dissolves the stack, retargets each PR whose base is not the record's,
creates the stack again and reads it back (the drafts are a line to act on, not a failure); on
GitLab it only retargets, there is nothing to unstack. Never retarget a PR by hand: a PR's base
cannot change while it is stacked, and on GitLab `forge-stack` retargets, though GitLab would
allow it by hand. A `rebuild` refused (by the forge or the permission check) is an `anomaly` with
the exact text, as above; no other means, except one: when its error ends with the line `stack #<n>
is dissolved and no stack replaces it yet: run `forge-stack create``, run `$CHANTIER forge-stack
create` yourself and go on as after a `rebuild` (a `create` refused is an `anomaly` with the exact
text). The line `… the stack's state is unknown: run `forge-stack show`` gets no exception: it
stays an `anomaly` with the exact text; before you raise it you may run `forge-stack show` (a read)
and quote its output in the anomaly, without carrying on from it.

**The local gate at the mergeable top.** When the project's rules ask the stack's top for a
local run and the stack has drafts on top or CRs to come (a partial stack), the top of the
mergeable part must have passed that local gate at its pushed head. Run it there when it has
not: `$CHANTIER gate <cr> <name>…` in that CR's worktree (clean, at the head
you shipped), as any long gate (its queue, its lock, never stopped for slowness). A head with a
pass is not run again: a `gate` that passed there, or that CR's `ship` printed `carried:` for the
gate at that head (a clean restack). This holds at the first stack made and at each new top of
the mergeable part, in any take: a draft that turns ready to merge, a restack after a partial
merge, an insertion, a drop. Every hand-back that leaves a partial stack names the result for the
mergeable top as it stands: `[stack→foreman] hand-back ready to merge <stack link> <cr>=<link>…
local gate <cr> at <head7>: passed|failed`. A failed run is also `[stack→foreman] anomaly <cr>
local gate failed at <head7>: <the log's path>`, sent before the hand-back; you change nothing
for it (no round of your own: you edit no project file). A PR that would become the new mergeable
top turns out of draft only once its local gate passed at its head; until then it stays a draft
on top. When its gate fails, it stays a draft, the mergeable part keeps its previous top (whose
pass still holds), and the anomaly above goes up.
A top the project's rules exempt from the long gate (docs only) still runs this gate.

## Stack driver: the five checks

**The five checks,** read on the forge with `$CHANTIER forge-stack show` (one line per failed
check, exit 0 when all hold), on the stack as it stands (the bottom CRs with a PR; drafts on top
and the `to come:` line are no failure; a working CR not placed yet is in `to come:`): the stack is open; it holds every PR of the stack as it
stands, and no other; in the order of `take stack`, bottom first; no PR of a CR ready to merge is a draft
and every draft sits above the PRs ready to merge; the release PR, when it is in the stack, is on top. On
GitLab the checks read the chain (each MR's target is the branch below, the first on the default
branch; no other MR on a branch of the stack but drafts of CRs to come; drafts only on top; the
release on top; unproved; trial: one run on a GitLab project).
Green and checked: `[stack→foreman] hand-back ready to merge <stack
link> <cr>=<link>…[ local gate <cr> at <head7>: passed|failed|not run][ <cr> to come: <cr below> not shipped at <tip7>]…`,
the local gate tail present under the rule on every hand-back that leaves a partial stack, a
`to come` clause for each CR left to come ("Check the chain").
