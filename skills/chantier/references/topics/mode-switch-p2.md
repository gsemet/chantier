# A mode switch (part 2 of 2)

- To parallel, from a stack: first `$CHANTIER forge-stack unstack` (a refusal is an `anomaly` or ask with the forge's exact text, no other means). Then each open CR with a PR gets its rebase: `ready` or `blocked`, `take <cr> --note "rebase: mode parallel"`; a `working` CR's Driver, `[foreman→driver <cr>] note rebase: mode parallel`. Queued CRs start as slots free, on the default branch.
- To a series, from a stack: first `forge-stack unstack`; then the same rebase notes with `rebase: mode series`, bottom CR first: the bottom one is rebased on the default branch, each one above on the one below, and a PR above the bottom is a draft (a stack's mergeable part shrinks to the bottom PR).
- A stack driver running when the batch leaves a stack: `[foreman→stack] note mode: <mode>`; it stops after the branch it is pushing (no further rebase, no `rebuild`) and hands back; then `forge-stack unstack` and the rebase notes.
- A release CR already started when an ordered batch goes parallel: `take <release> --note "redo: mode parallel"` once the others are merged (its PR closed meanwhile, branch kept).

Then `order done`.
