# The watcher's lines

Its start lines:
- `watch: <project> from cursor <n> ...; started the board (PID <n>)`: say once, with the link from `status`. Pass on its `board:` lines. `board is chantier <v>: restart it ...`: say once with the offer (`help board-restart`). `; no board started: a chantier dev session holds its seat ...`: pass on once; it links by itself.
- `did not start within 20 s`, `does not answer`, `refused the key`, `no seat`, `records no session transcript`, `cannot be read`, `no session key`: one line with the printed command or reason, no workaround. For the seat ones take the seat as printed only when this session is the Chief of Staff (`help seat`), then start it again.
- `watch: no event for <name> in 2 h; ended ...` with no batch in flight: start it again at once, say nothing.
- It ends when the seat is another session's (`the seat of <project> is another session's now`: not started again). After a notification (last line `still watching`) there is no restart; after an end, run the printed command as is.
- `status` prints `watch: not running: ...` after `open`, `seat take`, a `take` or `order qa` that resumes a paused batch, a switch to direct, a reload: start it at once on the session's yes. Another session's watcher does not wake you.
- Its events and what to do with them: `help watcher-events`, `help watcher-board`. The pull path: `help watcher-pull`.
