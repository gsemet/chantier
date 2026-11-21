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
| `chief-of-staff` | none, or this session's own | Chief of Staff: take the free/own seat, then ask before starting the board; no redundant seat question |
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

**The board.** Ask before starting `$CHANTIER board --seat <own session id>` in the background,
explaining its persistent process, that it listens on this machine only unless `board.host: network` or `--host` says otherwise (a phone reaches it only after the user asked for it), and that it is also the
surface's forge hub: it reads the forge every 20 s with the user's own `gh` or `glab` (only the
PRs a running batch waits for) and needs the network for that. On a planning surface it is also the
surface's writer: it commits, rebases and pushes the plan, and with no server a write to the surface
is refused. A decline starts no server, so the session's writes to the surface are refused.
After acceptance, use the host's means (the host's reference, "Run the board"),
and reads its first lines. A Griller, a Foreman, a Driver and the router before a role is chosen
never start it.

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
- `error: board not started: chantier board <v> (PID <n>) already serves this surface ...` or
  `... holds this surface at <host>:<port> and does not answer ...`: one line to the user with the
  version, the PID and the stop command as printed. Never stop it yourself and never start one on
  another port to get round it: the user decides, then you run `board --seat <id>` again on the
  user's word.
- `board: writer not started: <reason>`: one line with the reason; the board serves anyway, and
  writes to the surface are refused until a writer runs. The board's other start line is the
  writer's own, `writer: <state>`.
- `error: board not started: ...`, or a host that cannot run a background command: one line with
  the reason, then go on. The board never blocks the session, a preflight, a batch or a report.

On a surface, `$CHANTIER board --seat <id>` keeps the `--project` that `$CHANTIER` holds.

**The watcher.** A Chief of Staff (never a Griller, a Foreman, a Driver or the router before a
role), whatever its project's batch (running, paused or none), asks the user once per session, as
for the board, before starting the watcher in the background, on the `watch: not running` line of
`seat take` (or of any output later): it runs on in the background and tells the Chief of Staff,
within about 20 s, what the user does in the board; its hub reads the forge of every project of
the surface every 20 s with the user's own `gh` or `glab`, and needs the network. A yes holds for
the session (every later start, restart, resume and switch to direct mode goes on without asking
again); a no starts nothing for the session, merges go back to the user's word and the `forge saw
merged` lines of `status`, and the pull path (the line's `after the user's no` command) runs at
each user message. Start it by the host's means (the host's reference, "Run the watcher"). Its
start is the `watch: not running` line of `seat take` (or of any output later): with the session's
yes, start it at once; run the printed command as is: no flag added. On a host whose reference says
a watcher's end does not wake the session, or is not proved to (Copilot today), say once, in the
user's language: "This host may not wake me: what you do in the board reaches me at your next
message." A host that cannot run a background command: one line with
the reason, then go on, no workaround. A watcher started while the board runs is not the hub (its
start line has no `, the hub`): the board reads the forge. The start line's `hub is chantier <v>`: tell the user once,
in one line, and go on. When it starts and stops: [chief-of-staff](chief-of-staff.md).

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

## 6. Sync the checkout

Read before the first sync of a dev-mode session (`$CHANTIER`'s mode is set in `SKILL.md`). A sync runs at the session's start, at a batch's start and after a merge that changes `uv.lock`. Six steps:

1. Check, writing nothing: run `uv sync --locked --check --project "<plugin root>"` (the command inside the rule P10 prints for it) and read its exit: 0 is in sync, nothing to sync, stop here; 1 with uv's text "The environment is outdated" goes to step 2; any other exit is an ordinary sync failure, handled as below, never `sync pending` (a stale `uv.lock` also gives 1 with that text, and the real sync of step 3 then fails with its lock error, handled the same way).

2. Name the holders before syncing, on every system: list the processes that hold `<plugin root>/.venv` by the host's means (its reference, row "Name the holders of the checkout's environment").

3. With none, run `uv sync --locked --project "<plugin root>"`.

4. With any holder (a gate, a watcher, the board or hub, of any project or surface, this session's own included), or when the sync fails with os error 32 (a holder the listing missed, or one that started in between), never stop or kill a process and ask no one to: go on unsynced, saying `sync pending: held by <holders>` (each holder as `PID <n> <subcommand> <project>`, or `an unlisted process` when the listing found none), and try again from step 1 at each next turn but a reload (`session-start.md`, "5. Reload": a reload runs no `uv sync`).

5. Still pending 3 minutes after its first try, tell the user once, naming the holders, that the sync waits for them (in a batch as the **For you** item of `status-layout.md`; outside a batch one chat line, and at most one more, step 6's offer), then go on as in step 4.

6. Your own board and watcher, on your yes: at the first try, at or after those 3 minutes, where every listed holder is this session's own board or watcher, offer once per pending sync to stop them, stating the cost: the board and the surface's writer are off for all projects meanwhile, the hub too, unless another session's watcher takes it (off a planning surface there is no writer, and the cost names the board and the hub only, with the same "unless"). When that holds at the 3-minute message, the offer is in that message; when it first holds later (a gate held `.venv` at 3 minutes and has ended since), the offer is, in a batch, the **For you** item's new state, and outside a batch one more chat line, the only one after step 5's. No third line: if a gate or another holder appears after the offer, say nothing more; the offer stands for a later yes while the conditions hold. "First try" is a turn, not a timer: no sleep, no monitor, no wake for it. "Own" is the host row's evidence: own board, its command line holds `--seat <this session's id>` and this session's `board --seat` did not print `board already running`; own watcher, a `watch` process with this project's `--project` while this session holds a running watcher task and the project's seat; anything else is not own (another session's board included). An own process is stopped by the host's stop of the background shell that holds it, never by `Stop-Process`, `taskkill`, `kill` or a PID. On the user's yes: stop the watcher and the board, list the holders again, sync only if none, then start the board and the watcher again whatever the result (`session-start.md`'s board start, and the watcher's printed command, as is); a holder still listed after the stop is no longer own (its shell is gone): it is waited on as in step 4, never killed, and the board's restart then meets `board already running`, passed on as is. The yes covers the restart: no second question. A failed sync is one line with uv's text. No offer while another holder is listed or a gate runs (listed, or shown by `$CHANTIER status`). No answer: the offer stands. A no: keep waiting as in step 4, do not ask again; in a batch the **For you** item then names the holders only, plus "a later yes still counts". An ordinary sync failure is, at the session's start, `startup-core.md`'s; at a batch's start or after a merge, one line to the user with uv's text, and you go on.
