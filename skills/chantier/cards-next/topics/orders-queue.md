# Orders: the queue and added work

- A queued CR that `status` shows `waits for …` is not yours to start. Start every CR `take` would accept, up to the free slots, and hold none in reserve (a series batch accepts only the next). A cancelled dependency never frees its CR: ask the Chief of Staff once, for the user to drop that CR or change it.
- An order that adds work leaves a paused batch paused: your first `take` sets it running, and `pause` again at the end. A CR placed in `1-pending` (an `add` order) is the go: take it when a slot frees.
- A batch born paused with no CR (`open` given none) is that same paused batch: after your claim, the brief and the rules, send `[foreman→chief-of-staff] ready <batch>` and wait. No Driver, no retro, no `final`, no `pause`: you are ready, not done. The first order's line starts your turn.
