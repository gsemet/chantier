# The board (part 1 of 2)

The surface server: it serves the web board, the planning files to live clients, the surface's writer and the forge hub. It listens on this machine only unless `board.host: network` or `--host` says otherwise. One board serves a surface, on whatever port; a second session's `serve --seat <id>` registers on it. With no server, a write to the planning surface is refused.
- It starts with the watcher, on the session's one yes (`help watcher`). On a host that cannot run a watcher, ask first, then run `$CHANTIER serve --seat <own session id> --forge-always` in the background by the host row, no `--stop-idle`; the yes covers a later restart of it. A host with no background command: one line with the reason. A Griller, a Foreman, a Driver and the router never start it.
- The forge is read every 20 s while a client is subscribed (always with `--forge-always`), only for the PRs a running batch waits for; it needs the network.
- A watcher's board stops by itself when the seat leaves or 30 minutes after its last client. To stop it sooner, on the user's word only, run the stop command with the PID of the watcher's start line or `status`'s `forge hub:` line (`taskkill /PID <pid> /T /F` on Windows, else `kill <pid>`).
- A reload starts nothing; the board survives a compaction.
