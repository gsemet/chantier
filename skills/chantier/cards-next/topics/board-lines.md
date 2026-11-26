# The board's lines

Pass each on once, in one line, as printed:
- `board on <URL> over ...`: the link and its key as announced, not a readiness proof (only a successful probe such as `GET /api/board` is; say none ran otherwise). A non-loopback binding (`board: listens on the local network (...)`): say LAN reach is untested. A second line `on this machine: http://127.0.0.1:...`: give both, the 127.0.0.1 one is where "Copy as image" works. `read-only: <link>` (or `on this machine, read-only:`) shows and acts on nothing, and can be shared; the private link acts.
- `board: no local network address found; on this machine only`: the board is local; once the network is back the user stops it by the host row, then it starts again.
- `board already running at <URL>`: the same lines if not given yet.
- `board: watches the planning files` or `no file notifications here; checks every 5 s` (a change shows up to 5 s late); `stops by itself after 30 min with no client`; `the running board reads the forge only while a client is subscribed`.
- `error: board not started: ... already serves this surface ...` or `does not answer`: one line with version, PID and the printed stop command. Never stop it yourself except by the restart (`help board-restart`).
- `board: writer not started: <reason>`: the board serves, writes to the surface are refused. Any other `error: board not started`: one line with the reason and the command, go on; the board never blocks a session, preflight, batch or report.
