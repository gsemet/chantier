# After a merge, in a stack

A choice you make per recorded merge (or group of merges recorded in one message), never fixed at the go:
- A restack, whenever a native stack of the batch is on the forge (on GitLab a chain made by `forge-stack create` or `rebuild` and read back by `show`): once every CR one action of the user merged is recorded, one `take stack` for what remains and one stack driver, or the note `merged: <cr>…` to the one that runs. `order merged` prints `restack owed: …` when one is owed.
- A folded CR (GitLab, unproved): on the Chief of Staff's `order merged <k>` with the note `folded: <k> into <k-1>`, the CR below goes back first, `take <k-1> --note "folded: <k> merged into its branch"` (a slot, or it waits); the restack (`take stack`) comes after its hand-back.
- Rebase notes only before the first stack is made, the parallel rules scoped to the CRs whose base the merge changed: a `working` CR based on the merged CR's branch or the default branch gets `[foreman→driver <cr>] note rebase: <merged cr> merged`; a CR `ready` or `blocked` with a PR that no longer merges (`gh pr view --json mergeable`, `glab mr view`) or whose base was the merged CR's branch gets `take <cr> --note "rebase: <merged cr> merged"`. A PR ready to merge on the default branch that still merges cleanly is left alone.
- Nothing of the stack left open: neither.
Say in your next line to the Chief of Staff which you chose and why, in one clause.
