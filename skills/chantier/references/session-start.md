# Session start

This card is deferred action guidance. Startup reads only the common, host,
role and wrapper entries in `startup-manifest.json`.

Read by the router, the Chief of Staff and the Griller at the start of a session and at each
skill invocation. Then read the file of the role the seat gives you, again when the role changes:
the Chief of Staff [session-start-chief-of-staff](session-start-chief-of-staff.md), the Griller
[session-start-griller](session-start-griller.md); both read [titles](titles.md). A sync reads
[sync-checkout](sync-checkout.md). The host's means (rename, list sessions, message, links) are in
your host's reference: [Claude Code](hosts/claude-code.md) or [Copilot](hosts/copilot.md). Talk
with the user in their language; repository text in English.

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
- With a planning surface, the session's folder is a main checkout, of the surface (on its default
  branch) or of the project (its clone, nested in the surface or beside it, as `checkout.yml`
  places it); the other folder is added to the session. P6 and P7 accept both and refuse a linked
  worktree of either.
- Finding the surface, once per session, before `$CHANTIER` runs: read the project's `AGENTS.md`
  pointer line (`- planning: <url>, projects/<name>`). With no pointer line and a
  `.agents/changes/` in the checkout, the project plans in itself (in-project layout): no
  `--project`. With one, the surface is the session folder (cwd or added working directory) whose
  `git remote get-url origin` names that url (compare without a trailing `.git`, and the same
  host and path over https or ssh) and that holds `projects/<name>/`; when the cwd is the surface
  itself, its own `projects/` names the project. `$CHANTIER` is then the skill's command plus
  `--project <absolute surface folder>/projects/<name>` for the whole session.
- Once found, the session keeps it: the plan's writes go through `$CHANTIER` (by absolute paths),
  and the session's own git reads run with `git -C <surface>` for the plan and `git -C <clone>`
  for the project's code, never with a bare `git` that reads whichever folder the cwd is.
- A session whose project `AGENTS.md` holds the pointer line and that has no folder matching it
  says, first, "this project plans in the surface at <url>; add its checkout to this session, or
  start the session there", and plans nothing in the project.
- The project's clone hosts the session when it is the cwd; its linked worktrees (the CRs') never
  do.

The other preflight lines are a batch's and are not reported here, except what the configuration
checks add to the first message (P5, P9, P10), which goes in the same message; P10's warning
(one per capability, the base only at a first turn) comes as the Chief of Staff's question ([chief-of-staff](chief-of-staff.md), "The project"). P9 now holds the
forge's rights and branch rules too ([chief-of-staff](chief-of-staff.md), "Forge permissions").

## 2. The seat and the role

In a surface with several projects, the Chief of Staff first learns its project (the user's word,
or the only one), and `$CHANTIER` is the skill's command plus `--project <absolute folder>`; the
seat is that project's.

A session's CRs are its own project's (the one its `--project` names; for the Chief of Staff, the
seat's). By default it does not grill, specify, triage, order or run a CR of another project of the
surface. It may file (relay) an item into another project's inbox on the user's word, then says in
one line that the CR waits for that project's own Chief of Staff or Griller, offers no grill,
specification, batch or order for it, and writes nothing more there. Only the user's explicit word
for that CR ("grill it here") lifts the default, for its grill, specification and triage, never for
a launch ([chief-of-staff](chief-of-staff.md), "Backlog and grill").

`$CHANTIER seat` prints the seat: the repository's Chief of Staff session (its id, environment,
title, link), then, when no watcher runs, the CRs that arrived in the planning folder from another
session or a pull since the last time they were told (`surface pull brought <folder> (...)`, `another
session wrote <folder> (...)`, at most ten, then the `watch --once` command for the rest): tell the user
each in one line, with no action. Then, by the skill invoked:

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

Only the Chief of Staff starts the board and the watcher
([session-start-chief-of-staff](session-start-chief-of-staff.md)); a Griller, a Foreman, a Driver
and the router before a role is chosen never start either.

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

Read the file of the role the seat gives you, again when the role changes.

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
  PR and reads its CI with `git` and the forge's own command-line tool (its reference in `forges/`). "Use my agent X as the coder" or "add a
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

After compaction, reload reads the manifest's common, host and role cores and this role's
startup sections only. In direct mode, a Chief of Staff whose `status` shows `shape stack` also reads
the manifest's `batch:stack` readings before its next act.

- **Trigger:** "chantier reload", the argument `reload` of a role skill or the router, or the
  host's auto reload. With no role, it starts the router.
- **Does:** read `$CHANTIER seat`, which names this session; the role is the Chief of Staff, else
  the Griller. If that is not the called skill's, load the other with `reload` (one hop; the
  router with no role reloads itself). No role question, introduction or batch change. Read only
  (`seat`, `status`): no order, `take`, heartbeat, Driver, message or `uv sync`. It repeats no grant and starts no service twice.
- **Says:** rules reloaded, batch status, a free seat.
