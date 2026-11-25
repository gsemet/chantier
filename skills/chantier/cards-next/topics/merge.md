# An order merged

A ready CR reaches the user through `judge <cr>`; one that goes back first: `help take-back`. Parallel batch, after its ask: `help conflict-check`.

On an `order merged <dependency>` (the user's or yours), every mode: each CR handed back ready as a draft PR waiting for it, with all dependencies now merged, goes back with `take <cr> --note "rebase: <dependency> merged"`; one still waiting for another open dependency is rebased onto it and stays a draft (the note says which). Then, by mode:
- Parallel: every CR with a PR still open, by a plain `status` just before: `ready` or `blocked`, `take <cr> --note "rebase: <merged cr> merged"`; `working`, `[foreman→driver <cr>] note rebase: <merged cr> merged`. Queued: nothing.
- Series: the CR whose predecessor merged, the same notes; it turns ready to merge on the default branch. A CR's branch moves (rebase, new round): the started CR above it gets `rebase: <cr> moved`, stays a draft, and moves the next.
- Stack: `help stack-merge`.
A CR that owes the local run and holds no pass at its new head gets the same `take` with `; long gate: this CR runs <command> locally` added (`help local-gate`). Then `help main-checkout`.

A Driver's line `[driver <cr>→foreman] … <cr> is merged: no Driver to hand it back …` is no anomaly, no ask: read its note (`log <cr>`). If it names work still needed on the default branch, send `[foreman→chief-of-staff] merged early <cr>: left undone: <the note>`; no `take`, no restart.
