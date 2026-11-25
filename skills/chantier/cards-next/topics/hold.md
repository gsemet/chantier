# A held CR

`order hold <cr>` or `order unhold <cr>` (the user's word): a held CR is out of the slots and the order, in every mode.
- Held while ready (stack): `take stack --note "hold <cr>"` (or `unhold <cr>`), then `order done <O-n>`.
- Held while working: send its Driver `[foreman→driver <cr>] stop hold: <O-n>`; it answers `stopped: held; worktree clean|dirty: <files>`. Then `agents set <cr> - --epoch <n>`, in a stack `take stack --note "hold <cr>"`, `order done <O-n>`; the slot is free only then. Worktree and branch stay.
- Dependents (`after` it; in a series, those started on it) wait with it until `order unhold` or `order drop`.
- `order unhold` of a CR held while working: it comes back `blocked`; before any queued CR, `take <cr> --note "unhold: <O-n>" --epoch <n>`, a new Driver, no round (no free slot: wait). In a stack it joins as a working CR (`not on its place`: its Driver gets `note rebase: stacked on <cr below>`) with no `take stack --note "unhold <cr>"`.
- A release working when a CR is held: let it hand back, `note` it stale, `take <release> --note "redo: <cr> held"`.
- Never take a held CR. A held or parked CR and its dependents are out of the final-order take; neither it nor `take <release>` starts while one is held or parked: one ask `the release waits: <cr> is held (order O-n)` (`… is parked (<what it waits for>)`). A CR parked while the release works or is ready: once back and handed back ready, `take <release> --note "redo: <cr> back from park"`.
