# Stack driver: a join, a draft turning ready, a merge, a deadline

## Stack driver: a join, a draft turning ready, a merge, a deadline

**A CR that joins** (it has a PR, a draft): order it on top (`stack`), have it rebased (see "Who
moves a branch"), then `$CHANTIER forge-stack rebuild` (unstack, retarget, create; on GitLab, retarget). The PRs below
are not moved and stay ready to merge: the user may merge them meanwhile. The same holds on GitLab for a
draft that turns ready, an insertion and a restack after a merge, each ending with `rebuild`.

**A draft that turns ready to merge** (its CR handed back `ready`) moves into the mergeable part. When it
is the lowest draft, nothing moves: no `rebuild`; read the stack back and turn its PR ready once
the five checks hold, the chain check passes and, under the rule, its local gate passed at its head, then `stack --out-of-draft <cr>`. When drafts sit under it, order it below them (`stack`), rebase it and the
drafts above (theirs by their Drivers' notes when working), `rebuild`, then, after the chain check, turn it ready and `stack --out-of-draft <cr>`.

**A merge during a take.** On `[foreman→stack] note merged: <cr>…`, read the stack again
(`$CHANTIER stack`), restack what remains on `origin/<default branch>` with the CRs being added
(one restack pass, as "After a partial merge", the siblings pushed at once), then `rebuild`. A `rebuild` refused because a PR of the
plan merged meanwhile is an `anomaly` with the exact text, as any refused `rebuild`.

**Deliver by a time.** A take whose note names `deliver by <time>` keeps the stack on the forge
mergeable at that time. Turn ready only what is restacked, judged and green at the top before the
time; leave the rest a draft on top. Never leave, at the time, the stack unstacked or a rebuild
half done: a `rebuild` that cannot finish before the time is not started. Hand back with the stack
as it stands. With the rule above, a local gate that has not passed by the time does not hold
the hand-back: hand back at the time with `local gate <cr> at <head7>: not run` (or `failed`); a
gate still running is not stopped and records its result as any gate.
