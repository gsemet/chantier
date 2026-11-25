# The five checks of a stack

Read the stack on the forge with `$CHANTIER forge-stack show` (one line per failed check; exit 0 when all hold; on GitLab, the chain of MRs, unproved): the stack is open; it holds every PR of the stack as it stands, and no other; in the record's order, bottom first; no PR of a CR ready to merge is a draft, and every draft sits above the PRs ready to merge; the release PR, when it is in the stack, on top.
- One check fails: no ask. `take stack --note "<the check that failed>"` sends it back to a stack driver.
- A CR of the stack handed back, ready to merge or in draft: no ask. Record its gaps with `$CHANTIER note <cr> "gaps: …"` (`none` when it has none) and quote them after its link in the `stack-ready-to-merge`, partial or complete.
- The Chief of Staff's `order note` `insert: <new cr> below <cr>` makes this sequence: the PRs above the new place go to draft first (the Chief of Staff did it: check on the forge), the new CR's Driver, `take stack --note "insert: <new cr> below <cr>"` (the rebuild on the forge is `forge-stack rebuild`), the release redone (`take <release> --note "redo: <new cr> inserted"`), `take stack` again, the check, then `stack-ready-to-merge`. You edit no PR yourself.
- A PR ready to merge that stopped merging (`gh pr view --json mergeable`, `glab mr view`) is yours to notice: send it back with `--note "rebase: …"`.
