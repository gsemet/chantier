# A release CR: waiting, stale, a fix

- Handed back `blocked waits: …, then the user's word…`: once the others are merged, send `[foreman→chief-of-staff] release <cr>: the batch is merged; run the release procedure?` and take it back on `order confirm`.
- A CR under a prepared release changes: read `log <cr>`. A move with no change of content (a restack, a rebase) is the stack driver's. A change of content (a new round, a drop), or doubt, makes the release stale: `note` it, then `take <release> --note "redo: <cr> <why>"` once the stack under it is ready to merge again.
- A defect the release finds goes back to the CR that owns it (`note`, `take <cr> --note`), the release redone after. One that belongs to no CR is a fix CR.
- Its `blocked fix: <line>; <path>`: under the user's grant, `$CHANTIER order add --note "<path>" --fix-for <cr> --epoch <n>` starts the fix on the fast track (refused past three fixes or the budget); else, or refused, it is an ask.
