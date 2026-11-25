# Starting the watcher

A Chief of Staff, whatever its batch (running, paused, none), asks once per session, on the `watch: not running` line, in the user's language: "I start the watcher, which starts the board if it is not running?" Explain: the watcher runs on in the background, subscribed to the board, and tells within about 20 s what the user does in the board and what the forge shows; the board (persistent, stops 30 minutes after its last client or when the seat leaves, its network exposure, its forge reads, its writer).
- A yes starts both and holds for the session: every later start, restart, resume and switch goes on without asking, also after the board stopped by itself.
- A no starts neither: writes to the surface are refused, merges wait for the user's word, and the pull path runs at each user message (`help watcher-pull`).
- Start it by the host row, the printed command as is, no flag added. A host whose watcher does not wake the session: say once "This host may not wake me: what you do in the board reaches me at your next message." A host with no background command: one line, no workaround.
- In Foreman mode the Foreman runs its own watcher with no question; `status` says `foreman watch: running` or `not running`. Never start a second watcher in the session while one runs, stop another session's, or start one after the user's no.
