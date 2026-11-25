# A mode switch

The Chief of Staff's `order mode --note <mode>`, any mode to any other; the record is already changed, in `status`. No CR already started is stopped, a merged CR is never touched, a fix CR stays outside every shape. By target:
- To a stack: `help stack` before the first `take stack`. With two CRs or more `ready` with a PR, the first `take stack` forms it; a `working` CR's Driver gets `[foreman→driver <cr>] note rebase: stacked on <cr below>`; CRs not started join on top as they get their PR.
- To parallel, from a stack: first `$CHANTIER forge-stack unstack` (a refusal is an `anomaly` or ask with the forge's exact text). Then each open CR with a PR gets its rebase: `ready` or `blocked`, `take <cr> --note "rebase: mode parallel"`; `working`, `[foreman→driver <cr>] note rebase: mode parallel`. Queued CRs start as slots free, on the default branch.
- To a series, from a stack: first `forge-stack unstack`; the same notes with `rebase: mode series`, bottom CR first (on the default branch, each above on the one below); a PR above the bottom is a draft.
- A stack driver running when the batch leaves a stack: `[foreman→stack] note mode: <mode>`; it stops after the branch it is pushing (no rebase, no `rebuild`) and hands back; then `forge-stack unstack` and the rebase notes.
- A release CR already started when an ordered batch goes parallel: `take <release> --note "redo: mode parallel"` once the others are merged.
Then `order done`.
