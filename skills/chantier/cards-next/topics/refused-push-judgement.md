# A refused force push: the judgement

Read-only (`git fetch <remote>`, then the main checkout or `git -C <worktree>`), on what it looks at, not a fixed list:
- the local sha is the worktree's committed head (`rev-parse HEAD`, a clean `git status`);
- the local head holds the remote head's work rebased onto the CR's `base` (as `handoff` prints it): the base is an ancestor of the local head and the remote head's commits are in it (`git range-diff`, `git cherry`); a patch changed by a resolved conflict is not by itself a doubt;
- the long gate passed at the local head: the last `gate` at the local full sha in the batch's `events.jsonl` passed every command (its events share a `run`), or the Driver's notes and last gate log in `handoff`. No pass is the Driver's slip: push nothing; it runs the gate and sends the line again.
A push that would drop work the remote has and the local head does not, or that you cannot tie to the CR, is not legitimate.
The skips of the gate check and the two refusals: `help refused-push-gate`.
