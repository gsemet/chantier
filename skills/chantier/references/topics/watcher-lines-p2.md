# The watcher's lines (part 2 of 2)

- `watch: no event for <name> in 2 h; ended ...` with no batch in flight: start it again at once, say nothing.
- It ends when the seat is another session's (`the seat of <project> is another session's now`: not started again). After a notification (last line `still watching`) there is no restart; after an end, run the printed command as is.
- `watch: not running: ...` prints after `open`, `seat`, `seat take`, a `take` or `order qa` that resumes a paused batch, a switch to direct, and in `status` (a session's start, a reload, any time): start it at once on the session's yes. Another session's watcher does not wake you. In Foreman mode the resuming `take` is the Foreman's: the line reaches you at your next `status`.
- Its events and what to do with them: `help watcher-events`, `help watcher-board`. The pull path: `help watcher-pull`.
