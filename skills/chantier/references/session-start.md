# Session start

This card is deferred action guidance. Startup reads only the common, host,
role and wrapper entries in `startup-manifest.json`.

Read by the router, the Chief of Staff and the Griller at the start of a session and at each
skill invocation. The host's means (rename, list sessions, message, links) are in your host's
reference: [Claude Code](hosts/claude-code.md) or [Copilot](hosts/copilot.md). Talk with the user
in their language; repository text in English.

## 1. Start checks, first

Before the role, once per invocation: `$CHANTIER preflight --direct` (it prints P6 and P7 on any
host entry point). On a P6 or P7 failure, or on a host whose reference says it refuses writes in
the main checkout's planning folder from this session, the first message says, before
anything else:

- what fails, in one line;
- what it means for this role: a Chief of Staff here cannot steer a batch (preflight will fail at
  the go); a Griller cannot write in the planning folder, but may work here and send its files to
  the Chief of Staff ([griller](griller.md), "In a worktree");
- what the user does: open a new session on the main checkout, without a worktree; nothing is
  lost, since the files hold the state. Before proposing it, check nothing would be left behind:
  `git status --porcelain` is empty and `git rev-list --count <default branch>..HEAD` is 0; else
  name what would be left (the uncommitted files, the commits) and ask. Where the host's reference
  names a way to move this session and marks it proved, offer that; Claude Code's is refused for
  an isolated worktree (its reference).
- With a planning surface, "the main checkout" is the surface's checkout, on its default branch,
  or the project's main checkout with the surface added as a working directory. In both, the
  planning folder is the surface's project folder, written by absolute paths, and the project's
  clone of `checkout.yml` hosts no session. A session tells the two cases apart by what it has:
  the surface added as a working directory and `$CHANTIER` given `--project` in it. A session
  started alone in a project whose `AGENTS.md` holds the pointer line (`- planning: <url>,
  projects/<name>`), without the surface added, says, first, "this project plans in the
  surface at <url>; start the session there", and plans nothing in the project.

The other preflight lines are a batch's and are not reported here, except what the configuration
checks add to the first message (P5, P9, P10), which goes in the same message; P10's warning
(one per capability, the base only at a first turn) comes as the Chief of Staff's question ([chief-of-staff](chief-of-staff.md), "The project"). P9 now holds the
forge's rights and branch rules too ([chief-of-staff](chief-of-staff.md), "Forge permissions").

## 2. The seat and the role

In a surface with several projects, the Chief of Staff first learns its project (the user's word,
or the only one), and `$CHANTIER` is the skill's command plus `--project <absolute folder>`; the
seat is that project's.

`$CHANTIER seat` prints the seat: the repository's Chief of Staff session (its id, environment,
title, link). Then, by the skill invoked:

| Invoked | Seat | Role and message |
| --- | --- | --- |
| `chief-of-staff` | none, or this session's own | Chief of Staff: take the free/own seat, then ask the one watcher-and-board question (the board question alone on a host that cannot run the watcher); no redundant seat question |
| `chief-of-staff` | another session, alive (the host says so), **no batch active** | Griller: the introduction ending with the message below and its one option, "become chief of staff" |
| `chief-of-staff` | another session, alive, **a batch active** | ask once: the hand-over to this session ([chief-of-staff](chief-of-staff.md), "Handing the seat over") or only grilling CRs |
| `chief-of-staff` | another session the host cannot tell, or that looks stopped | one line: "the Chief of Staff at <link> looks stopped; shall I take its place?"; on yes `seat take --over <id>`; never alone |
| `griller` | any | Griller, no question |
| `chantier` (router) | none, or a session that looks stopped | ask the role (the router's question); a Chief of Staff chosen over a stopped seat asks the line above too |
| `chantier` (router) | another session, alive | as `chief-of-staff` |

The message of a second session that becomes a Griller, in the user's language: "a Chief of Staff
is already active at <link>; I become a Griller: I will not follow the batches actively, but I
can help refine the backlog's ideas." Then one option only: say "become chief of staff" to take
over.

"A batch active": a batch that is not closed, running or paused. "Alive": the host's reference
says how to tell; where it cannot, the seat's session "looks stopped". No activity date is ever
taken as proof of life.

**The board.** A persistent process, the surface server: it listens on this machine only unless
`board.host: network` or `--host` says otherwise (a phone reaches it only after the user asked for
it), it reads the planning files for the live clients, and it is the surface's forge hub: while a
client is subscribed (an open board page, a session's watcher, `chantier live`), or always when
started with `--forge-always` on a host that cannot run the watcher, it reads the forge every 20 s
with the user's own `gh` or `glab` (only the PRs a running batch waits for) and needs the network
for that. On a planning surface it is also the surface's writer: it commits, rebases and pushes
the plan, and with no server a write to the surface is refused. It starts with the watcher, on the
session's one question (**The watcher**, below), and the one a watcher starts stops by itself when
the seat leaves or 30 minutes after its last client.

On a host whose reference says the watcher cannot run (no background command whose end starts a
turn), ask the board question alone, as before: ask before starting `$CHANTIER board --seat <own
session id> --forge-always` in the background, explaining the above; after acceptance, start it by
the host's means (the host's reference, "Run the board"), with `--forge-always` and no
`--stop-idle`, and read its first lines. That board stops when the seat moves, and reads the forge
every 20 s with or without a client, so the pull path, run at each user message, still prints its
`forge saw merged` lines. The yes holds for the session and covers starting `$CHANTIER board --seat
<own session id> --forge-always` again, by the host's means, when the board stopped (a refused
write to the surface naming no running writer). A decline starts no server, so the session's writes
to the surface are refused. A host with no background command at all: one line with the reason. A
Griller, a Foreman, a Driver and the router before a role is chosen never start it.

Another project runs chantier from its checkout in plugin mode, a build uv caches by version: it
changes at each version bump. The board server, its writer and the forge hub, started from
another project's session, run that build and serve every project of the surface, chantier
included, with no notice while the version is equal, until the next version bump or until
stopped by hand and started again from a chantier session. (The dev mode runs only in chantier's
own checkout, when the session's project is chantier: the launch paragraph of the SKILL.md.) The
watcher that is the hub (below) runs the same build.

- `board on <URL> over ...`: report the server-announced binding (the link and its key), not
  verified local readiness. Local readiness is verified only by a successful probe such as
  `GET /api/board` with the key; if no probe was run, say so. If the server announces a
  non-loopback binding (the `board: listens on the local network (...)` line), pass that line on and say that LAN reachability is untested; do not claim that it opens
  remotely. The link is theirs only. When the board prints a second line, `on this machine:
  http://127.0.0.1:<port>/?k=...`, give the user both links, the 127.0.0.1 one named as the one
  where the Costs page's "Copy as image" works (a browser allows an image copy on a secure origin
  only; the LAN link is plain http).
- `board: no local network address found; on this machine only` (after the `board on` line, when `board.host: network` found no network address): the board is on this machine only; pass it on, and once the network is back the user stops it by the host's means, then it is started again.
- `board already running at <URL>`: the same line (and the same second line, when it follows, then the `board: listens on the local network (...)` line when the board listens beyond this machine, which you pass on), if
  not given yet in this session. One board
  serves a planning surface (or a repository), on whatever port: a second session's `board --seat
  <id>` registers its seat on it and prints this line.
- `board: watches the planning files`, or `board: no file notifications here; checks every 5 s`
  (the board's last start line, or after `board already running`, or after the watcher's start
  line): pass it on, in one line; the second means the board shows a change up to about 5 s late.
- `board: stops by itself after 30 min with no client (a watcher started it)` (the last line of
  `board already running`): tell the user once, in one line.
- `board: the running board reads the forge only while a client is subscribed ...` (a
  `--forge-always` start on a board another session's watcher started): tell the user once, in
  one line, that merges come only while a client is subscribed.
- `error: board not started: chantier board <v> (PID <n>) already serves this surface ...` or
  `... holds this surface at <host>:<port> and does not answer ...`, or the watcher's `does not
  answer` line: one line to the user with the
  version, the PID and the stop command as printed. Never stop it yourself and never start one on
  another port to get round it: the user decides, then you run `board --seat <id>` again on the
  user's word.
- `board: writer not started: <reason>`: one line with the reason; the board serves anyway, and
  writes to the surface are refused until a writer runs. The board's other start line is the
  writer's own, `writer: <state>`.
- `error: board not started: ...`, the watcher's `did not start within 20 s` or `refused the key`
  line, or a host that cannot run a background command: one line with the reason (and the printed
  command), then go on. The board never blocks the session, a preflight, a batch or a report.
  When the user's word asks for a board started by hand (`board --seat <id>`, as the watcher's line
  prints it), run it by the host's background means (the host's reference, "Run the board"),
  never in the foreground (a board that starts never returns), and read its first lines.

On a surface, `$CHANTIER board --seat <id>` keeps the `--project` that `$CHANTIER` holds.

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
  was started, with its link from `status` or `board --seat`. The `board: listens on the local
  network (...)`, `board: no local network address found ...` and file-watch lines that may follow
  it (or the start line on a running board): pass each on, in one line, as the board's own. The
  start line's `board is chantier <v>: restart it to run this version`: tell the user once, in one
  line, and go on.
- `watch: the board did not start within 20 s ...`, `watch: a chantier board <v> (PID <n>) ...
  does not answer ...`, `watch: the board at <host>:<port> refused the key of server.json ...`,
  `watch: no seat for <project> ...`, `watch: the seat of <project> records no session transcript
  ...`, `... cannot be read ...` and `watch: this run has no session key ...`: one line to the user
  with the printed command or reason; no workaround. For `no seat`, `records no session transcript`
  and `cannot be read`, take the seat as printed only when the session is the Chief of Staff by the
  role rules above, then start the watcher again.
- `watch: no event for <name> in 2 h; ended ...`: start it again at once with the printed command,
  saying nothing to the user.

When it starts and stops: [chief-of-staff](chief-of-staff.md).

**Stopping the board by hand.** The board a watcher starts is no background task of the session:
the host's stop of a background task does not reach it. It stops by itself when the seat leaves or
30 minutes after its last client; to stop it sooner, on the user's word, run the stop command with
the PID of the watcher's start line or of `status`'s `forge hub:` line: `taskkill /PID <pid> /T /F`
on Windows, `kill <pid>` elsewhere.

A reload starts nothing: the board survives a compaction, and at the next skill invocation the
`board` run is a reuse.

**The user's word changes the role at any time, both ways:**

- "become chief of staff" / "tu es le chief of staff" in a Griller: with the seat free or
  stopped, take it (`seat take`, `--over` the stopped one). With a live Chief of Staff in the
  seat: warn that two sessions would be Chief of Staff, and do no Chief of Staff work (no plan, no
  `open`, no `order`, no steering, no `close`) until the user chooses the one that takes the
  batch. Chosen here: with a batch active, the hand-over rules apply; with none, `seat take
  --over <id>`, and the old session, at its next seat reading, is a Griller. Chosen there: this
  session stays a Griller.
- "become a griller" in the Chief of Staff: with a batch running, the hand-over rules apply first
  (its Drivers are its own); then `seat leave`, rename.

**Re-read the seat** at each skill invocation, after a fork when the host tells the session it is
one, and before each Chief of Staff act on a batch (the plan, `open`, an `order`, `close`,
starting or steering a batch). A seat that names another session makes this session a Griller: it
says so in one line and renames itself. What the host lets a fork know is in its reference; where
it lets it know nothing, the reference says so and nothing else is tried.

## 3. Titles

As soon as the role is set and whenever it changes, the session renames itself by the host's
means (its reference); a host that cannot rename: nothing, no workaround.

A title tells first whether the user talks to the session, then the project and the role, with the
machine's code in front: a phone shows about 25 characters of a title. Its parts:

- **Machine code:** `[<code>]` first. The machine's name (the first label of `hostname`) as it is
  when it has 6 letters or fewer (`Mac`), else its first 6 letters (`Battlestation` gives
  `Battle`), its first letter uppercase. A user's word renames the machine for the session only. In
  a cloud session (the host's reference says how to tell) the code is `Remote`.
- **Icon**, after a space: `💬` for a session the user talks to (the Chief of Staff, a Griller),
  `⚙️` for one they do not (the Foreman).
- **Project**, after a space: the repository's folder name, or, in a surface, the project's folder
  in it, capitalised (`Chantier`).
- **Batch number:** only for a session that steers a batch (the Foreman, the Chief of Staff in
  direct mode), last, in parentheses after a space as `(Batch <nn>)`, on two digits as in the batch's id (`(Batch 17)`).
- **Role:** `CoS` for the Chief of Staff, `Griller`, `Foreman`. A Griller adds its subject once
  known, after the role: a few of the user's words, not a slug.
- **Separator:** ` · ` (space, U+00B7, space) between the project, the role
  and a Griller's subject.

| Session | Title |
| --- | --- |
| Chief of Staff | `[<code>] 💬 Project · CoS` |
| Chief of Staff steering a direct batch, from `open --direct`, the hand-over or a switch to direct mode until the batch is closed, then back to the line above | `[<code>] 💬 Project · CoS (Batch <nn>)` |
| Griller | `[<code>] 💬 Project · Griller` |
| Griller, once its subject is known | `[<code>] 💬 Project · Griller · <subject>` |
| Foreman, given in its prompt ([chief-of-staff](chief-of-staff.md)) | `[<code>] ⚙️ Project · Foreman (Batch <nn>)` |

Examples: `[Battle] 💬 Chantier · CoS`, `[Battle] 💬 Chantier · CoS (Batch 17)`,
`[Battle] 💬 Chantier · Griller`, `[Battle] 💬 Chantier · Griller · landing page`,
`[Battle] ⚙️ Chantier · Foreman (Batch 17)`, `[Mac] ⚙️ Chantier · Foreman (Batch 06)`,
`[Remote] 💬 Chantier · CoS`.

- The title given to `seat take --title` is the session's current title; take the seat again
  (same session, no `--over`) when it changes.

## 4. First turn: introduce chantier

On your first turn in a session, after the start checks, give a short factual report in the
user's language, then answer their request. Offer the detailed product introduction below only
on request. Once per session; skip it if the user says they know chantier, or if their first
request is `init`: the [tour](init.md) covers it. When the project has no planning folder, end it
with one line: "new here? say init for a guided tour".

- **Change Request (CR):** one more level over the project's tracker issues (Jira, GitHub,
  GitLab…). It lets small requests outside the tracker be accepted and prioritised; the tracker
  keeps the strategic vision, external requests and long-term planning. A CR gets:
  - a folder in the planning folder (the request, its analysis, the user's answers, the
    self-contained Change Specification written before any code);
  - a branch and a worktree its Driver creates.

  It ends as one pull request.
- **One person to talk to, the Chief of Staff (me):** the only session that opens and runs
  batches. It keeps the backlog and asks the questions a CR needs. Nothing starts without the
  user's go. The user reviews and merges each PR; only a release's PR or fix is merged for them,
  on their word. (A Griller says "the Chief of Staff" of another session instead.)
  - A **Griller** is another session of yours that grills and specifies the backlog beside it,
    optional, never running batches.
- **Direct or Foreman:** a batch (`batch-<n>`) is steered either:
  - by a **Foreman**, a separate session that reports back to me, where a CR may join while the
    batch runs;
  - or by me in **direct mode**, where a CR joins only once every other CR is handled and the
    batch is paused, and I hold no grill while it runs (use a Griller).
  - Say which mode this session would use now and why: forced (`foreman` or `direct`, or the
    user's word), Remote Control, a host that cannot start a Foreman, or the desktop. `foreman`,
    `direct` or the user's word changes it.
- **Zero configuration:** the project's `AGENTS.md`, and an optional `chantier.yaml` (the project's, and its planning surface's), are the only configuration (I learn how it
  builds, tests and merges from it). Everything chantier writes is Markdown and JSON in
  the planning folder: `.agents/changes/` in the project, or the project's folder of an external
  planning surface (and, from the board, a project's `chantier.yaml` in its planning surface), and a CR's archive in its PR when the
  project asks; and, on your yes, the allow rules in your Claude Code settings.
- **Drivers and workers:** one Driver per CR runs short workers (Investigator, Coder, Inspector,
  Debugger, Verifier, Conflict resolver) in the CR's worktree, and commits, pushes, opens the
  PR and reads its CI with `git`, `gh` and `glab`. "Use my agent X as the coder" or "add a
  security review" changes the team.
- **The flow:** file items → answer my questions → "run them" → the Foreman (or I, in direct mode)
  works → the user reviews and merges each PR; only a release's PR or fix is merged for them, on
  their word.
- **What to ask:** "file this", "run the P1s", "status?", "drop CR-103", "I merged #42",
  "what did it cost?", "which agents and models?".

A Griller gives the same introduction, ending with the message of section 2. A Chief of Staff in
a remote session (Remote Control or cloud, per the host's reference) ends it with one line: "to
grill in parallel, fork this session; the fork becomes a Griller". It explains the user's steps
(the fork, auto mode, no worktree) and never does them.

## 5. Reload

After compaction, reload reads the manifest's common, host and role cores and this role's startup
sections only.

- **Trigger:** "chantier reload", the argument `reload` of a role skill or the router, or the
  host's automatic reload. With no role, it starts the router.
- **Does:** read `$CHANTIER seat`: it names this session, the role is the Chief of Staff, else
  the Griller. If that is not the called skill's, load the other skill with `reload` (one hop; the
  router with no role reloads itself). No role question, introduction or batch change. Read only
  (`$CHANTIER seat`, `$CHANTIER status`): no order, `take`, heartbeat, Driver, message or `uv sync`.
  It repeats no grant and starts no service twice.
- **Says:** rules reloaded, the active batch status, a free seat.
