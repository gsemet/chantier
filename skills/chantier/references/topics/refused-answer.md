# A refused push or rebase: the answer's way back

The answer never goes to a live Driver as a note: it handed back `blocked waits: push <branch> …` (or `rebase <branch> <base>`) and ended.
- The CR `blocked` with that `waits:`: take it back at once by the restart path's steps (`agents set <cr> - --epoch <n>` first) and `take <cr> --note "push: <the answer, as it came>"` (`rebase: …` for a rebase), then a new CR Driver (or Release driver) before any queued CR: a blocked CR holds no slot, so it takes the next free one. No round is counted.
- An answer that comes before the hand-back has landed (the CR still `working`): wait for the hand-back, then take it back as above. A Driver that ended without its hand-back takes the lost-Driver path, with the answer in its `resume:` note.
- A Driver of a CR handed back `waits: push` is never pinged, and the CR is not a lost Driver. The stack driver, which waits for the result, still gets `[foreman→driver stack] note push <branch>: <the answer>`.
