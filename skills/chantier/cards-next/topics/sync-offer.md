# A sync that waits for holders

Pending 3 minutes after the first try (a turn, not a timer: no sleep, no monitor), tell the user
once, naming the holders, that the sync waits for them. In a batch it is the **For you** item of
the report (`status-layout.md`); outside a batch, one chat line, and at most one more, the offer
below. A server `webui` started (no `--seat`) still listed is named with its stop command
(`taskkill /PID <n> /T /F` on Windows, `kill <n>` elsewhere), for the user to run by hand: chantier
never stops it.

The offer, once per pending sync, when every listed holder is this session's own board or watcher
("own": its command line holds `--seat <this session's id>`, or a `watch` of this project while
this session holds its watcher task and the seat): stop them on the user's yes, the cost said
first: the board, the surface's writer and the hub are off for all projects meanwhile, unless
another session's watcher takes the hub. No offer while another holder is listed or a gate runs.

On the yes: stop the watcher and the board by the host's stop of their background shell (never by a
PID), list the holders again, sync only if none, then start the board and the watcher again
(`help board-restart`), whatever the result; the yes covers the restart. A holder
still listed is waited on, never killed. No answer: the offer stands. A no: do not ask again; the
**For you** item names the holders only.
