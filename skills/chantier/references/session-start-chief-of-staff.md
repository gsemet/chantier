# Session start: the Chief of Staff

Read by the Chief of Staff at the start of a session, after [session-start](session-start.md), and
again when the role changes to it.

## The board

**The board.** A persistent process, the surface server: it listens on this machine only unless
`board.host: network` or `--host` says otherwise (a phone reaches it only after the user asked for
it), it reads the planning files for the live clients, and it is the surface's forge hub: while a
client is subscribed (an open board page, a session's watcher, `chantier live`), or always when
started with `--forge-always` on a host that cannot run the watcher, it reads the forge every 20 s
with the user's own command-line tool for the project's forge (its reference in `forges/`) (only the PRs a running batch waits for) and needs the network
for that. On a planning surface it is also the surface's writer: it commits, rebases and pushes
the plan, and with no server a write to the surface is refused. It starts with the watcher, on the
session's one question (**The watcher**, below), and the one a watcher starts stops by itself when
the seat leaves or 30 minutes after its last client.

On a host whose reference says the watcher cannot run (no background command whose end starts a
turn), ask the board question alone, as before: ask before starting `$CHANTIER serve --seat <own
session id> --forge-always` in the background, explaining the above; after acceptance, start it by
the host's means (the host's reference, "Run the board"), with `--forge-always` and no
`--stop-idle`, and read its first lines. That board stops when the seat moves, and reads the forge
every 20 s with or without a client, so the pull path, run at each user message, still prints its
`forge saw merged` lines. The yes holds for the session and covers starting `$CHANTIER serve --seat
<own session id> --forge-always` again, by the host's means, when the board stopped (a refused
write to the surface naming no running writer). A decline starts no server, so the session's writes
to the surface are refused. A host with no background command at all: one line with the reason. A
Griller, a Foreman, a Driver and the router before a role is chosen never start it.

Another project runs chantier from its checkout in plugin mode, a build uv caches by version: it
changes at each version bump. The board server, its writer and the forge hub, started from
another project's session, run that build and serve every project of the surface, chantier
included, with no notice while the version is equal, until the next version bump or until
stopped by hand and started again from a chantier session; but a chantier session in the dev
mode is told, on `status`, the watcher's start line and `serve`, when the board runs another
build than its checkout's, even at the same version string (`server.json` records each entry's
`source`). (The dev mode runs only in chantier's
own checkout, when the session's project is chantier: the launch paragraph of the SKILL.md.) The
watcher that is the hub (below) runs the same build.

- `board on <URL> over ...`: report the server-announced binding (the link and its key), not
  verified local readiness. Local readiness is verified only by a successful probe such as
  `GET /api/board` with the key; if no probe was run, say so. If the server announces a
  non-loopback binding (the `board: listens on the local network (...)` line), pass that line on and say that LAN reachability is untested; do not claim that it opens
  remotely. The link is theirs only. When the board prints a second line, `on this machine:
  http://127.0.0.1:<port>/?k=...`, give the user both links, the 127.0.0.1 one named as the one
  where the Costs page's "Copy as image" works (a browser allows an image copy on a secure origin
  only; the LAN link is plain http). The `read-only: <link>` line (and, when it differs, `on this machine, read-only: <link>`) is passed on with them: that link shows the board and acts on nothing, so it can be shared; the private link acts.
- `board: no local network address found; on this machine only` (after the `board on` line, when `board.host: network` found no network address): the board is on this machine only; pass it on, and once the network is back the user stops it by the host's means, then it is started again.
- `board already running at <URL>`: the same line (and the same second line, when it follows, then the `board: listens on the local network (...)` line when the board listens beyond this machine, which you pass on, and an added `board runs another build` line: say it once to the user as printed, never stop or restart the board), if
  not given yet in this session. One board
  serves a planning surface (or a repository), on whatever port: a second session's `serve --seat
  <id>` registers its seat on it and prints this line.
- `board: watches the planning files`, or `board: no file notifications here; checks every 5 s`
  (the board's last start line, or after `board already running`, or after the watcher's start
  line): pass it on, in one line; the second means the board shows a change up to about 5 s late.
- `board: stops by itself after 30 min with no client (a watcher started it)` (the last line of
  `board already running`): tell the user once, in one line.
- `board: the running board reads the forge only while a client is subscribed ...` (a
  `--forge-always` start on a board another session's watcher started): tell the user once, in
  one line, that merges come only while a client is subscribed.
- `error: board not started: chantier serve <v> (PID <n>) already serves this surface ...` or
  `... holds this surface at <host>:<port> and does not answer ...`, or the watcher's `does not
  answer` line: one line to the user with the
  version, the PID and the stop command as printed. Never stop it yourself and never start one on
  another port to get round it: the user decides, then you run `serve --seat <id>` again on the
  user's word.
- `board: writer not started: <reason>`: one line with the reason; the board serves anyway, and
  writes to the surface are refused until a writer runs. The board's other start line is the
  writer's own, `writer: <state>`.
- `error: board not started: ...`, the watcher's `did not start within 20 s` or `refused the key`
  line, or a host that cannot run a background command: one line with the reason (and the printed
  command), then go on. The board never blocks the session, a preflight, a batch or a report.
  When the user's word asks for a board started by hand (`serve --seat <id>`, as the watcher's line
  prints it), run it by the host's background means (the host's reference, "Run the board"),
  never in the foreground (a board that starts never returns), and read its first lines.

On a surface, `$CHANTIER serve --seat <id>` keeps the `--project` that `$CHANTIER` holds.

## The watcher

**The watcher.** A Chief of Staff (never a Griller, a Foreman, a Driver or the router before a
role), whatever its project's batch (running, paused or none), asks the user one question once per
session, on the `watch: not running` line of `seat take` (or of any output later), in the user's
language, in substance "I start the watcher, which starts the board if it is not running?",
explaining both: the watcher runs on in the background, subscribed to the board, and tells the
Chief of Staff, within about 20 s, what the user does in the board and what the forge shows (the
board reads the forge while the watcher is subscribed); the board as above (its persistent
process, which stops by itself 30 minutes after its last client or when the seat leaves, its
configured network exposure, its forge reads while a client is subscribed, its writer). A yes
starts both (the watcher starts the board, detached, when none runs and the seat is this
session's) and holds for the session: every later start, restart, resume and switch to direct mode
goes on without asking again, and so does starting the watcher again after the board stopped by
itself (a refused write to the surface naming no running writer, or a `watch: not running` line:
start the watcher, which starts the board). A no starts neither: the session's writes to the
surface are refused, merges go back to the user's word (nothing reads the forge, so no `forge saw
merged` line comes), and the pull path (the line's `after the user's no` command) runs at each user
message. Start it by the host's means (the host's reference, "Run the watcher"): with the session's
yes, at once on that line; run the printed command as is: no flag added. On a host whose reference
says a watcher's end does not wake the session, or is not proved to (Copilot today), say once, in
the user's language: "This host may not wake me: what you do in the board reaches me at your next
message." A host that cannot run a background command: one line with the reason, then go on, no
workaround. Its lines:

- `watch: <project> from cursor <n> for ...; started the board (PID <n>)`: say once that the board
  was started, with its link from `status` or `serve --seat`. The `board: listens on the local
  network (...)`, `board: no local network address found ...` and file-watch lines that may follow
  it (or the start line on a running board): pass each on, in one line, as the board's own. The
  start line's `board is chantier <v>: restart it to run this version`: tell the user once, in one
  line, and go on.
- `watch: the board did not start within 20 s ...`, `watch: a chantier serve <v> (PID <n>) ...
  does not answer ...`, `watch: the board at <host>:<port> refused the key of server.json ...`,
  `watch: no seat for <project> ...`, `watch: the seat of <project> records no session transcript
  ...`, `... cannot be read ...` and `watch: this run has no session key ...`: one line to the user
  with the printed command or reason; no workaround. For `no seat`, `records no session transcript`
  and `cannot be read`, take the seat as printed only when the session is the Chief of Staff by the
  seat table of [session-start](session-start.md), "2. The seat and the role", then start the watcher again.
- `watch: no event for <name> in 2 h; ended ...` (only with no batch in flight): start it again at
  once with the printed command, saying nothing to the user.

When it starts and stops: [chief-of-staff-steering](chief-of-staff-steering.md) (`chief-of-staff:steering`).

## Stopping the board by hand

**Stopping the board by hand.** The board a watcher starts is no background task of the session:
the host's stop of a background task does not reach it. It stops by itself when the seat leaves or
30 minutes after its last client; to stop it sooner, on the user's word, run the stop command with
the PID of the watcher's start line or of `status`'s `forge hub:` line: `taskkill /PID <pid> /T /F`
on Windows, `kill <pid>` elsewhere.

A reload starts nothing: the board survives a compaction, and at the next skill invocation the
`serve` run is a reuse.
