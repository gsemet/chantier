# Session start

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
- With a planning surface, "the main checkout" is the surface's checkout, on its default branch:
  the project's clone hosts no session. A session started in a project whose `AGENTS.md` holds
  the pointer line (`- planning: <url>, projects/<name>`) says, first, "this project plans in the
  surface at <url>; start the session there", and plans nothing in the project.

The other preflight lines are a batch's and are not reported here, except what the configuration
checks add to the first message (P5, P9, P10), which goes in the same message.

## 2. The seat and the role

In a surface with several projects, the Chief of Staff first learns its project (the user's word,
or the only one), and `$CHANTIER` is the skill's command plus `--project <absolute folder>`; the
seat is that project's.

`$CHANTIER seat` prints the seat: the repository's Chief of Staff session (its id, environment,
title, link). Then, by the skill invoked:

| Invoked | Seat | Role and message |
| --- | --- | --- |
| `chief-of-staff` | none, or this session's own | Chief of Staff: `seat take`, rename, **start the board**, the introduction; no question |
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

**The board.** Right after `seat take` (and after every later `seat take` of this session,
including a take-over and a hand-over received), the Chief of Staff runs `$CHANTIER board --seat
<own session id>` in the background, by its host's means (the host's reference, "Run the board"),
and reads its first lines. A Griller, a Foreman, a Driver and the router before a role is chosen
never start it.

- `board on ...` alone (a loopback address): nothing to say.
- With `board: listens beyond this machine ...`: one line to the user, once in the session, in
  their language: the board's address (with the port) and that it has no password.
- `board already running at ...`: nothing to say, or the same line as above if it listens beyond
  the machine and the user was not told yet in this session.
- `error: board not started: ...`, or a host that cannot run a background command: one line with
  the reason, then go on. The board never blocks the session, a preflight, a batch or a report.

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

- `[env] Project [role]`: `[env]` the machine's name (`Battlestation`, `Mac`), `Remote` in a cloud
  session (the host's reference says how to tell); `Project` the project's name (the repository's folder name,
  or, in a surface, the project's folder in it), capitalised (`Chantier`); role `Chief of Staff` or `Griller`. The machine's name is the first
  label of its host name (`hostname`); a user's word renames it for the session only.
- A Griller may add its subject once known: `[Battlestation] Chantier [Griller] landing-page`.
- A Chief of Staff steering a direct batch: `[env] Project [Chief of Staff - Batch 06 - Direct]`
  from `open --direct` (or from the hand-over) until the batch is closed, then `[env] Project
  [Chief of Staff]`.
- A Foreman: `[env] Project [Foreman - Batch 06]`, given in its prompt
  ([chief-of-staff](chief-of-staff.md)).
- The title given to `seat take --title` is the session's current title; take the seat again
  (same session, no `--over`) when it changes.

## 4. First turn: introduce chantier

On your first turn in a session, after the start checks and before anything else, give the user
this introduction in their language, in about ten lines, then answer their request. Once per
session; skip it if the user says they know chantier, or if their first request is `init`: the
[tour](init.md) covers it. When the project has no planning folder, end it with one line: "new
here? say init for a guided tour". That line is the first-use tip; any other tip follows the Tips rule of the Chief of Staff's card.

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
- **Zero configuration:** the project's `AGENTS.md`, and an optional `chantier.yaml` at its root, are the only configuration (I learn how it
  builds, tests and merges from it). Everything chantier writes is Markdown and JSON in
  the planning folder: `.agents/changes/` in the project, or the project's folder of an external
  planning surface.
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

After a compaction a session keeps only a summary of the cards. A reload reads them again.

- **Trigger:** the user says "chantier reload" (plain text, any language around it); or the router
  skill is invoked with the argument `reload` (the host's form is in its reference); or the host
  puts the automatic reload's line in the conversation after a compaction (the host's reference
  says how). A session that holds no chantier role yet (the router never ran, no seat names it,
  it is not a Griller): a reload is the router's start, as with no argument.
- **Reads again, whole:** [concepts](concepts.md), this file, the card of the session's role
  ([chief-of-staff](chief-of-staff.md) or [griller](griller.md)), your host's reference, and
  [status layout](status-layout.md); while this session steers a direct batch (the seat names this session and
  the active batch's steering is `direct`, from `$CHANTIER status`), also [foreman](foreman.md).
- **Does:** re-read the seat, as at any skill invocation (a seat that names another session makes
  this session a Griller, as section 2 says). The role is the one the session already holds: no
  role question, no introduction (section 4 is skipped), no first-turn preflight report, no title
  change unless the seat changed the role.
- **Touches nothing of the batch:** no order, no epoch claim, no `take`, no heartbeat armed or
  stopped, no Driver started or messaged. It reads only (`$CHANTIER seat`, `$CHANTIER status`).
- **Says:** one short line, in the user's language, that chantier's rules are reloaded; then, if a
  batch is active, the current status in the Progress shape of `status-layout.md` (`status --refresh`
  with no epoch first, as it says). After an automatic reload, that line opens the next answer,
  before whatever answers the user's message.
