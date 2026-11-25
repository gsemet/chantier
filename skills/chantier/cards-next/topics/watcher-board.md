# The board's writes

A `board wrote (...)` line that sets a CR's destination is written into its `02-answers.md` at once, in a folder that has one (none is created); the latest word wins:
- `board wrote (running-batch)`: `Destination: running batch <batch> (board, <HH:MM>)`, the line's own time in the user's local time.
- `board wrote (move)` to `3-ready` (with or without `running-batch mark cleared`): `Destination: next batch (board)`. A move of a marked CR to the inbox or a priority row: `Destination: back to the backlog (board)`.
- A `running-batch` line is the user's go for the running batch: read the CR's folder. In `3-ready`, or with its specification final (`03-change-spec.md` written, no `work/specifying`, its critic run and applied when due, no open question): `$CHANTIER order add --note <folder>` with no further question, handle the order as usual (Foreman mode: send its line to the Foreman; direct mode: take the CR when a slot frees), tell the user `<CR-id> added to <batch> from the board`. Otherwise one line: `<slug> marked for <batch> from the board: it joins once its specification is final`; `order add` when it is.
- An `order add` refused: say its text. Other `board wrote` lines: one line, no tool call.
