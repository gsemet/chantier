# A rule that asks a local run

- A rule that names each shape (parallel, series, stack) is followed as written; one that names the stack's top alone is read by the batch's shape (the `shape` word of `$CHANTIER status`).
- In a stack, the stack's top owes the run, a docs-only top included (`help stack-make`). In a parallel or series batch each CR the long gate covers owes it, since each PR lands alone on the default branch; a CR the rules exempt owes none, a fix CR counts. A pipeline job named as the long gate is still checked (`help ci-beside-gate`); the local run is in addition.
- Run `$CHANTIER gate` as any long gate, in your worktree, clean, at your pushed head, unless a pass or a carried pass is there (`ship`'s `carried:` line), before the `ship` that precedes the ready hand-back, so before the PR leaves draft. Hand back with no `--no-gate`.
- A `take` note `long gate: this CR runs <command> locally` (stack: `the stack's top runs <command> locally`), alone or after `rebase: <cr> merged; `, asks the same run at the head you push after that `take`. A failure is a round.
- A release driver runs no local gate for this rule. No Windows run is asked on the merged result.
