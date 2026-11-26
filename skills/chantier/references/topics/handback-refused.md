# A hand-back that is refused

- `<cr> is ready` or `<cr> is blocked` (a refusal naming `take <cr> --note`): the CR was not taken back after its earlier hand-back. Keep the commits, the gate and the verdict, which bind to the head. Pass the refused line as printed to the steering session (`[driver <cr>→foreman] …`, by the host's means), wait for its `taken back:` note, then hand back again.
- `the worktree's head … is not the head ship recorded`: `ship` at this head, then the long gate and a new `verifier` given the move (unless the move was a clean rebase, whose pass and verdict carry), then hand back again.
- `<cr> is merged: no Driver to hand it back`: the user merged the PR while you finished. Push nothing, edit nothing, retarget nothing, turn nothing ready or draft. `note <cr> "merged before the hand-back; left undone: <what>"` (`none` when nothing), pass the refused line as printed to the steering session, and end.
- Any other refusal is passed as printed, never worked around.
