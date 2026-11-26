# A sync that waits for holders (part 1 of 2)

Pending 3 minutes after the first try (a turn, not a timer: no sleep, no monitor, no wake for it),
tell the user once, naming the holders, that the sync waits for them. In a batch it is the
**For you** item of the report (`status-layout.md`); outside a batch, one chat line, and at most
one more, the offer. A server `webui` started (no `--seat`) still listed is named with its stop
command (`taskkill /PID <n> /T /F` on Windows, `kill <n>` elsewhere), for the user to run by hand:
chantier neither stops it nor offers to.

The offer, once per pending sync, at the first try at or after those 3 minutes with every listed holder this session's own board or watcher:
stop them on the user's yes, the cost said first: the board, the surface's writer and the hub are
off for all projects meanwhile, unless another session's watcher takes the hub (off a planning
surface there is no writer: name the board and the hub only). Own board: its command line holds
`--seat <this session's id>` and this session's `serve --seat` did not print
`board already running`. Own watcher: a `watch` of this project while this session holds its
watcher task and the seat. Anything else is not own.
