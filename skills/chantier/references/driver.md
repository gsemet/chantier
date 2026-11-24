# Drivers

A Driver runs in the background for its steering session (the Foreman, or the Chief of Staff in direct
mode) and drives one CR (or the stack) through short foreground children, one at a time. Read your
host's reference with this card ([Claude Code](hosts/claude-code.md) or [Copilot](hosts/copilot.md)):
how to start a child and reach the steering session. It never codes, reviews, debugs or resolves a
conflict itself: it starts the child, and restarts a failing child rather than do its work.
Git and the forge are yours, by the project's rules (`$CHANTIER rules`, read
first); the CLI keeps the CR's record and tells you what is off. You send every line to the steering
session by the `Steering:` line of your prompt; a prompt without it is a `Needs:`-like gap: `note` it
and use the host's reference row.

At startup read the startup core and the project's rules; defer the rest of this card by step.

- **Rules:** the instruction file `$CHANTIER rules` names first, whole; of the other files, only what
  touches a Driver's work (git, the branch, the gates, the PR, the forge, CI).
- **A card:** Grep the heading, then Read with offset and limit; a section a link names in full, never
  printed with `cat`, `sed`, `awk` or `Get-Content`, never read twice.
- **The moments**, each an action of `startup-manifest.json`, read when its step comes; a section
  no action lists, when a link names it:
  - CR Driver: before the first Coder `cr-driver`; before the first commit `cr-driver:ship`; at
    the pushed-head `VERIFIED` `cr-driver:closing`.
  - Started again (a `resume:`, `rebase:`, `context:` or other `Note:`): `driver:restart` first.
  - Other Drivers' lines, shared lines, other moments: "Startup core".
  - **Concepts:** "Escalation" when a trigger arises; a rule or word of "Words" when a link names it.
  - After a compaction, read your entry action again, then the action of the moment you are in. "Startup core" too.
- Another Driver's section, another role's card and the users' docs are not opening reads.
- A rule you did not read still binds you: when a step is not in what you read, read its section
  before you act.

## Means: the specification

The specification, whole or by part: its goal, scope, decisions, open points and evidence, to brief
the workers, write `pr-body.md` and judge the proof. The detail of "What changes" is the Coder's and
the Inspector's; you read its list of file edits and copy it into each Coder's prompt as a checklist
("CR driver").

## Means: a Driver started again

A Driver started again (a `resume:`, `rebase:`, `context:` or other `Note:`) runs `$CHANTIER handoff
<cr>` and `log <cr>` first, then reads the sections of the steps still to do and never those of the
steps done. A `resume: closing` Driver reads the `cr-driver:closing` line only; a Driver resumed before
the first push reads `cr-driver:ship` and no part of `cr-driver` but "Means: the record and the
workers" when it starts a worker.

- `resume: closing` (the CR's earlier Driver stopped in its closing): after `handoff <cr>` and
  `log <cr>`, read `pr-body.md`, `work/verify.md` and the evidence files it names, by name and
  caption, not opened (except a text file a body line needs); read
  [pr-template.md](pr-template.md) only before the first body edit, and only the sections that
  edit needs. Do not open the specification, `investigation.md`, the `r<n>.md` notes or the
  diff, nor a section of this card beyond the Startup core, "CR driver: the closing" and the
  `Means:` section of a step you carry out. Start at the first closing step with no `closing:` note
  in the log ("CR driver: the closing" names the steps and their notes). A step outside the closing
  (a red check, a move, a review item on the code, a `rebase:` note) brings back the card's usual
  rules and reads.
- `stop hold: <O-n>` (a Foreman's note: the user held your CR): commit nothing new, leave the
  worktree as it is, and answer the Foreman `stopped: held; worktree clean|dirty: <files>`; your
  next leased command is `claim lost`.
- `rebase:`, `restack`, `folded:` or another re-take note: read "CR driver: re-takes".

## Means: the record and the workers

- `$CHANTIER handoff <cr>` and `log <cr>`: where the CR stands, what a predecessor did. Your
  prompt's `Note:` says why the CR is with you: an answer, a change, QA findings, a red check,
  a `rebase:`, a `resume:`. Go on from there; a round only for what the notes ask.
- Children: `$CHANTIER round <cr> --note "<brief>"` before each Coder (refused past the limit,
  exit 5: hand back `blocked rounds: <what is still wrong>`; refused once the budget is spent,
  exit 5 with a budget message: hand back `blocked budget: <what is still wrong>`; refused, exit 2,
  when nothing happened since the last round: read the facts with `handoff`, start that round's
  coder, or `note` why a new round is needed first), then the agent and the prompt of
  [concepts](concepts.md), "Starting an agent" (read "The agent and the model" and "The prompt"
  before the first worker's start), with the agent your prompt's `Team:` names for the role, and the worker's agent and model as the `team:` lines print them, passed as
  printed (no model printed: none passed; `agent=(generic)`: the generic agent with the printed
  contract lines, "The agent and the model"). Read those lines with `$CHANTIER handoff <cr>` (it counts nothing) or
  keep the ones `take` printed; `round` only starts a round, just before its Coder. A worker refused for its first line, or ended by a host failure: "Means: a worker that fails" (and "An agent that ends before its part is done" of concepts). A CR Driver's own prompt holds `writes: <CR folder>`
  (and `; <absolute archive path>` when `take` prints one; [concepts](concepts.md), "A Driver's prompt"): you write your notes, `pr-body.md`, your large
  outputs and, when `take` prints an archive path, the archive, nothing else. The repository's git folder, a file to ignore: "Means: a git command in the wrong place". A `Needs:`
  you cannot meet is a `$CHANTIER note`, and you do your part without it (never `$CHANTIER`: a CLI that cannot run is a stop, `startup-core.md`).
- A reply out of format is a failed worker. Each worker's reply has the format its own card names; before acting on a reply, check it against that format:
  - Inspector, and each extra review step: the reply is the JSON object alone, parseable, with
    `verdict` exactly `APPROVE` or `FIX-REQUIRED` and `head` a commit SHA. Prose, prose around the
    JSON, or a verdict word outside the JSON fails.
  - Coder, Investigator and Debugger: their output file exists (`r<n>.md`, `investigation.md`,
    `diagnosis.md`), and every gate it claims names its command and result. A Coder's reply also
    has its `Notes:` line naming the `r<n>.md` that exists.
  - Verifier: "CR driver: ship and proof". Conflict resolver: "Means: carries, conflicts and the early push".
- A reply out of format, a failed worker, a long reply: "Means: a worker that fails".
- Every worker's prompt, whatever the role, carries these lines of [concepts](concepts.md), "The
  prompt"; check them before each start: the role's opening lines, as `take`, `round` or `handoff`
  printed them under `<role> prompt, opening lines:`, copied unchanged at the top (the first line, the
  card's `Read` line, the rules line), never retyped, shortened or rephrased, a follow-up start (a new
  head, a rebase, a description pass) included; `CLI ($CHANTIER): …`; the `writes:` line of the `worker
  writes line` that `take`, `round` or `handoff` printed, copied unchanged (never put together from
  `worktree:` or `folder:`, whose values carry text after the path); `Note: …`, and `Needs: …` when the
  `team:` line prints one.
- `$CHANTIER phase <cr> <phase> [detail]` before each step, as it starts, so the board and the pane show
  it: `investigator`, `inspector` (the round's), `review <name>` (each review step of `Team:`), `rebase`,
  `gate <name>` (before `gate`), `pr` (before the push and the PR), `ci` (while CI runs), `verifier` (each),
  `debugger`, `conflict-resolver`. `round` records `coder` itself; `take` and `handback` clear the step.
  A step is one call, not chained with another command; a step left unrecorded shows the last one: record
  each. The Stack driver and the QA driver record none.
- `$CHANTIER note <cr> "<one sentence>"` after each step worth knowing; `note <cr> --draft
  <path>` for a file the user reviews and edits in place.
- The host's reference: "Tools" before the first start, "Auto mode" when the host refuses a command, "The write
  guard" when a write is refused; its Configuration, sessions and Heartbeat parts are the steering
  sessions'. A worker's own card (`<role>.md`): only when its reply needs checking beyond this section.
- Escalation: "Means: escalation". A `[foreman→driver <cr>]` message: "Means: the steering session's messages".
- Logs: a raw log goes in `work/gates/` or a `*.log` file, never in a file that is published with
  the CR. A CI artifact you download (`gh run download`, `glab job artifact`, or the forge's
  equivalent) goes under `<CR folder>/work/scratch/artifacts-<run id>/`, never elsewhere in the CR's
  folder: it stays on this machine, never published. What proves a claim is copied from it, small,
  into `evidence/`. A brief that asks a `debugger` or a `verifier` to read an artifact names that
  folder.

## Means: context and your folder

- Context: `round` and `note` print `context: <n> tokens (agent <id>)`; read it after each. At
  130,000 tokens or more, record your state with `note`, then `handback <cr> blocked context:
  <where it stopped, what is next>`, before the host compacts or ends you (the host compacted
  agents carrying 200,000 from about 162,000 tokens, see the host's reference, "Compacting", and
  130,000 leaves room for several steps, the note and the hand-back). Hand back `blocked context:`
  only when the last `context:` line read 130,000 or more, or for the closing hand-off of "CR
  driver: the closing" (`context: closing: …`: at 115,000 or more at `VERIFIED`, or at 130,000 or
  more during the closing); a Driver that stops for any other reason names that reason, never
  `context:`. Never end your turn to wait for a child: a child runs in the foreground, and its reply
  is the result of the call that started it. Ending the turn while your own long gate or CI watch
  runs in a background shell is allowed and needs no message (the host tells the steering session
  that you wait on your own work). The one turn end that waits is the long CI wait ("Means: CI", "Means: CI beside the long gate").
  On Claude Code, a turn that ends with nothing running in the background ends your run: the host asks for
  your hand-back at once. The host asking for your hand-back while the CR's work remains: "Means: hand-backs out of the ordinary". `context: not measured`: go on, and keep to these rules. Never take a
  large output whole into your context: a diff by `git diff --stat` or `--name-only` (the Inspector
  reads the diff itself); anything over about 200 lines as a file under `work/` first, then read in
  parts; a gate log: "Means: the long gate"; a CI failure: "Means: CI".
- Every git command a Driver runs names its worktree: `git -C <worktree> <command>` (the CR's
  worktree as `take`/`handoff` printed it; for the stack driver, the worktree of the CR it moves;
  for the QA and Release drivers, their own). A bare `git <command>` relies on the shell's current
  folder, which the host may reset between calls, and lands in the main checkout. The main checkout
  is read-only for a Driver: no `checkout`, `switch`, `rebase`, `merge`, `reset`, `commit`, `stash`
  or `pull` there; only the worktree's creation names it ("Means: the worktree"). Its one move is
  the steering session's post-merge fast-forward ("Means: a git command in the wrong place").
- Your folder and your background tasks ([concepts](concepts.md), rule 8). On Claude Code a CR
  Driver starts in its worktree, or, before the worktree exists, in the project's root (the main
  checkout, or the project's clone); never in its CR folder. Read and write the CR folder's files
  by the absolute paths your prompt names (`folder:`, `specification:`): a relative path lands
  where you run. Change no shell's folder into a CR folder, and name targets (`git -C <worktree>`,
  absolute paths, `gh … --repo`, `glab … -R`). Keep the id of each background task you start (the
  long gate's shell, the CI watch, a host monitor) and stop each by that id, with the host's stop
  of a background task (your host's reference, "Tools"), as soon as its result is read or no
  longer counts. Before every `$CHANTIER handback`, ready or blocked, whatever the reason
  (`context:` and `waits: push` included), stop every one still running, except the shell that
  runs `$CHANTIER gate` (a long gate still running: "Means: stopping a long gate"). A task left
  running wakes you after your hand-back, and a re-sent hand-back wakes the steering session for
  nothing.

## Means: the worktree

- The worktree is your first step: `git -C <main checkout> fetch <remote> <default branch>`, then
  `git -C <main checkout> worktree add -b <branch> <path> <base>` (with a planning surface, from
  the clone that `take` names: `git -C <clone>`), with the names your prompt gives. An
  earlier Driver's worktree is there: use it (its branch alone: `git -C <main checkout> worktree
  add <path> <branch>`). Workers never create one, except the Verifier's detached worktree of the
  base, which it removes at its end. A CR whose first `take` shows a `PR:` link came back to a batch: "CR driver: re-takes".
- Never run `git branch -a` or `git branch --list` with no pattern, nor `git status` outside your
  worktree: name your branch or your worktree.

## Means: rebase and push

- Rebase first, so the long gate passes on the head you push: `git -C <worktree> fetch`, `git -C
  <worktree> rebase <base>`; a conflict is a `conflict-resolver`. Rebase only (rule 8). A
  conflict-free rebase that leaves the CR's patch unchanged needs no new long gate or `verifier`:
  pass and verdict carry over ("Means: the long gate"). When the PR exists and a resolved conflict
  needs a long gate, push early ("Early push", below). Never `git stash` (shared): commit work
  aside. Never stop a process by name or pattern (`pkill`, `killall`); stop only yours, by id (a
  long gate: `gate <cr> --stop`, never by ending `gate`, which leaves its suite running). A
  command the host may refuse runs alone. Outside your prompt's `Rewrites:` line, a rebase or push
  is not yours.
- **Before the first push:** run the project's fast gate again, in the worktree, at the rebased
  committed head you are about to push, with any extra pre-push check the project's rules name
  (`$CHANTIER rules`) for the kind of change the CR is. The rebase may have changed what the Coder's
  run on the round's base checked. You run these short gates yourself, one
  command per call, never through `gate`. A failure is a round: a `coder` with the failing lines, the reviews, then these checks
  again at the new head before the push. Record each
  result with `$CHANTIER note <cr> "before first push at <sha7>: <command>: pass"` (one note per command, or one note naming each). When the rules name no fast gate and no pre-push check, there is
  nothing to run and no note. It holds whichever way the first push happens (before `gate`, before
  a pipeline job's push, with the `ci: beside the long gate` line); it is not a third gate.
- Push and the PR. A remote command that fails with a forge server error or a network failure:
  "Means: a remote command fails". A force push the host refuses: "Means: a force push the host
  refuses". `take` printing `archive: in the PR at <path>`: "Means: the archive in the PR". Push: a
  plain `git -C <worktree> push -u <remote> <branch>` when the remote branch is an ancestor of your
  head, `git -C <worktree> push --force-with-lease -u <remote> <branch>` only for a rewrite (a
  rebase). `<branch>` is your own CR's branch, the one your `take` / `handoff` prints, never another
  CR's. Open the PR yourself: a CR Driver as a draft (`gh pr create --draft --body-file <work
  folder>/pr-body.md`, `glab mr create --draft`), a Release driver as the base says (ready on the
  default branch, a draft on another base). A CR Driver writes the title
  and `<work folder>/pr-body.md` from the project's PR template and rules, else
  [pr-template](pr-template.md), and keeps the body and the PR's description current with the scope
  (`gh pr edit --body-file`, `glab mr update`, GitLab: "Means: GitLab forms"). The body is a file,
  written with the Write tool, changed with the Edit tool and posted from that file
  ([concepts](concepts.md), rule 9), never as text in the command. The body carries the `## Issues
  References` section for the specification's `issue:` lines ([pr-template](pr-template.md)), left
  out when there is none; a Driver never comments on, closes or reopens an issue. Before each post
  of the body, a CR Driver reads `pr-body.md` once against the audit list of the template in use,
  the items on internal references (role names included) and on Known gaps first, and fixes
  `pr-body.md` itself before posting. This is not a round or a review: it replaces neither the
  Inspector's audit nor the Verifier's description pass. Then `$CHANTIER ship <cr> <pr link>` (it
  reads the PR's base and draft state from the forge, records the PR at this head (the full SHA) and
  says what is off: uncommitted changes, a head not pushed, no long gate passed at it). The PR's
  base is the `base` that `take` printed, never another (the stack driver retargets, a Driver does
  not). A change of a PR's base or draft state on the forge is followed by `ship <cr> <link>` (a `ship` refused `branch not based on` there: rebase first, as that
  refusal says, then `ship`). What else `ship` prints (`base ?`, `off: no long gate
  passed`, a PR that carries another CR's head): "Means: carries, conflicts and the early push".

## Means: the long gate

- The long gate, the project's command, before the first push and the PR (with the `ci: beside
  the long gate` line: "Means: CI beside the long gate"): `$CHANTIER gate <cr> <name>
  [<name>...]` runs only the long gates `chantier.yaml` names (`$CHANTIER playbook` prints them), in the worktree, in order,
  as many at once as the project allows (`chantier.yaml`, one by default), the rest wait in a queue (its order: "Means: stopping a long gate"); a running gate is never stopped. A rebase with a conflict resolved takes `ship --conflict` and the early push ("Means: carries, conflicts and the early push"). The CLI reads no CI: you read CI at the new head, which must be green. A short gate (the fast gate, or the check that the rules ask of a CR they exempt from
  the long gate, such as a docs-only change) you run yourself in the worktree, never through
  `gate`: it would wait behind the long gates. A pipeline job named as the long gate: "Means: CI beside the long gate". A rule that asks a local run (by shape): "Means: carries, conflicts and the early push".
  `gate` stops at the first failure, keeps the log and records the pass at that head. It is
  refused (exit 2) on a dirty tree: a gate binds to a commit, so commit first. The log's
  first line names the CR, the branch and the full SHA it ran at, its last line the result; a
  head that moved during the run (a gate command committed) is no pass at either head (exit 4).
  One name per argument, never a `;` or `&&` chain. A refused name is a `blocked` line, never a free command.
  Stopping a gate (`gate <cr> --stop`: only your own CR's, only when its result can no longer count) and a long wait in the queue: "Means: stopping a long gate". `cancel` is the steering session's, never a Driver's.
- A gate log is never taken whole: its result from `handoff` (the last five lines it prints) or from the log's last lines.

## Means: CI

- CI: while CI runs, do everything that does not need its result first: `pr-body.md` and the
  description as far as they can go, the archive's `delivery.md` when `take` printed an archive path, your notes. Then one long wait:
  the forge's watch in a background shell, start it, then `lease <cr> hold --lease <n>` (45 min, up to 90) (`gh pr checks
  <pr> --watch`, `glab ci status --live`), end your turn, and let its end wake you; no `gh pr checks` or `glab ci` look in
  between (the two looks of the "no CI" rule below come before the long wait, or instead of it
  when no check is listed). Read the result yourself (`gh pr checks`, `glab ci list`) and judge it by the project's rules: a skipped job is never a green
  one; a job also red on the default branch is not the CR's (note it); an infrastructure
  failure, a flake or a CI still running after 3 hours: "Means: a remote command fails"; the rest is a round, with a `debugger` first when the cause is not
  plain. Say what CI showed in a `note`. What you say about CI follows these rules, for every
  Driver that pushes:
    - With the `ci: beside the long gate` line, or an early push: "Means: CI beside the long gate".
  - The only source: any claim about CI (running, green, red or none) comes from the forge's list
    of checks for the PR at the pushed head: `gh pr checks <pr>`, `glab ci list`, or the forge's
    equivalent. The project's files (a workflow folder or its absence), its rules, an earlier
    Driver's note and a guess are not a source.
  - The head first: before you read the checks, confirm the PR's head on the forge is the head you
    pushed (`gh pr view <pr> --json headRefOid`, or the forge's equivalent). Checks listed for an
    older commit prove nothing about the pushed head.
    - "No CI" needs two looks a minute apart, and a list that contradicts the rules is noted: "Means: when CI lists no check".
  - What the note says: the `note` that says what CI showed names the command you ran and the head
    (seven characters) you read at, e.g. `CI: gh pr checks 12 at abc1234: test pass`
    (the form for no check: "Means: when CI lists no check"). The PR body's CI box says the same in the
    template's words ([pr-template](pr-template.md)).
- A CI failure is never taken whole: `gh run view <run> --log-failed > <work folder>/ci-<run>.log` (a shell
  write inside the CR folder, which the guard allows), then read it with Grep or Read's offset and
  limit, or give it to a `debugger`.

## Means: commits, the PR's state and the evidence

- [pr-template](pr-template.md): read it when you write `pr-body.md` (at the first push and the PR).
- Commits: a PR merges by rebase with every commit of its branch, so each commit you make is a
  commit of the default branch. Every one, a round's commit or a checkpoint (work set aside, a commit
  before a gate or after a `FIX-REQUIRED` round), has a message in the project's commit style (its rules; where they give none, a Conventional Commit
  subject, as for the PR title in [pr-template](pr-template.md)) that says what the commit holds.
  Never a `wip` type, never "pending", "checkpoint", a round or a review state, never a CR
  number, a batch or a role. A checkpoint that is your head before the first push may be folded: "Means: checkpoint commits". A commit a procedure names (a release's `release: vX.Y.Z`) keeps its
  message.
- A CR's PR says on the forge when it is not [ready to merge](concepts.md), "Words" (a PR in draft). When a CR with a PR is sent
  back to a CR Driver (handed back ready or blocked, whatever the note), it turns the PR back to
  a draft first (`gh pr ready --undo`, `glab mr update --draft`): the Foreman never edits a PR.
  A release PR, a project that shows a draft otherwise, a forge that refuses a draft: "Means:
  hand-backs out of the ordinary".
- The evidence: once the Verifier has left it, you put it in the PR's description, in its
  Deliverables section, before and after side by side, as the forge's own CLI uploads images and
  videos (`gh pr edit --attach` on GitHub, `gh` 2.103 and later); read the CLI's help for any
  other forge. A file its CLI cannot upload stays in `work/`, and the description names it in
  its Internal references section. A taken-back note `evidence: <path>`, an image
  linked into a commit of the CR's branch, an image found after a move, and the look every image
  is given before it is kept or uploaded: "Means: images and the look".

## Means: your end

- Your end comes in this order: first your background tasks stopped (the "Your folder and your
  background tasks" bullet of "Means: context and your folder"), then `$CHANTIER handback <cr> …`;
  once the CLI accepted it, the host's hand-back, whose first line is the line `handback` printed
  (`[driver <cr>→foreman] hand-back …`), unchanged. Never call the host's hand-back until a
  `$CHANTIER handback` (ready or blocked) is accepted (a refused one counts for none): a report sent
  with no recorded hand-back leaves the CR `working`, and the steering session resumes you to record
  it.
- `$CHANTIER handback <cr> ready <link>` is refused, one line per cause, without a PR recorded, without
  a passed long gate and a last verdict `VERIFIED` at the PR's head, when the worktree's head is not the
  one `ship` recorded, and when the tree is dirty or the branch not pushed at that head: fix the cause,
  `ship` again, run the missing gate or start a new `verifier`, then hand back again. `--no-gate "<the
  project's rule>"` replaces the long gate check only, never the head, clean, pushed and verdict
  checks, and only where the project's rules declare none, exempt this CR, or name a pipeline job as
  the long gate, and quotes that rule (a waived CR that owes the local run: "Means: hand-backs out of the
  ordinary").
- Just before it, a CR Driver turns the PR ready (`gh pr ready`, `glab mr update --ready`) if its base
  is the default branch, then runs `ship <cr> <link>` again (as after any change of draft state); on
  another base it stays a draft (PR in draft) and the text after the link says so and what it waits
  for: `handback <cr> ready <link> draft on <base>: waits for <what>`. When the body's Known gaps is
  not "None", the text ends with `gaps: <gap>; <gap>`, each gap the first sentence of its bullet as
  written in the posted body, in the body's order, none the body does not name and none missing:
  `handback <cr> ready <link> gaps: …`, or `… draft on <base>: waits for <what>; gaps: …`; with
  `--no-gate`: `handback <cr> ready <link> gaps: <gap> --no-gate "<rule>"`, which prints `no long gate:
  <rule> gaps: <gap>`. The CLI prints which state the CR is (ready to merge, PR in draft or ready
  locally): "Means: hand-backs out of the ordinary".
- `handback <cr> blocked <reason>` (`question:`, `approval:`, `merge:`, `fix:`, `infra:`, `budget:`, `rounds:`,
  `refused`, `waits: <what>`, `context: …`): it writes the state and prints the line to send the Foreman
  (your host's reference says how it reaches the steering session); record your state with `$CHANTIER note
  <cr> "…"` first when your context is ending. The closing hand-off, `context: closing: …`, is made at
  the pushed-head `VERIFIED` at 115,000 tokens or more, or at the context rule during the closing ("CR
  driver: the closing"). Then end: ending frees your slot. The forms of each reason: "Means:
  hand-backs out of the ordinary".
- A wait of a known type (`--wait`), a `budget:` hand-back, a hand-back refused (`is ready`, `is blocked`,
  `is merged`, a head `ship` did not record), a Driver still recorded on a CR it handed back `blocked`,
  and `blocked waits: <what>` (a thing already on its way that no one decides: the CR shows 🟠, and the
  steering session takes it back when that thing lands): "Means: hand-backs out of the ordinary".

## CR driver

Take one CR from its specification to a green PR, then hand it back. A CR Driver edits no code,
card, doc or other project file itself, not even one line, and not through the shell either (a
redirection, `Set-Content`, `sed -i`, an interpreter's inline code): the guard refuses what it
sees, and the rule holds for what it does not. Every change the CR makes goes
through a `coder`. It writes only its notes, `pr-body.md` and, when `take` prints an archive path, the CR's archive.

A CR that touches the board's write paths: "CR driver: the board's write paths".

Lease: `take` prints `lease: <n>`; pass `--lease <n>` on `round`, `ship` and `handback`. `claim lost`:
stop at once, record nothing more, tell the Foreman. A wait over 3 minutes, a renewal, a lease "not
confirmed", a reclaim: "Means: the lease".

You never discard the worktree's work: no `git reset --hard`, `git checkout -- <path>`,
`git restore`, `git clean`, and no deletion of a file in the worktree. `git rebase --abort` is
allowed: it returns to the head before the rebase, and no work is lost. After a failed coder or a failed rebase: "Means: a worker that fails". Before round 1 and between
rounds, your own reading of the code is an `investigator` or a `debugger`, not you.

Before round 1,
when the code is unfamiliar, an `investigator`. You answer for the CR's evidence plan (the end of the
investigator's report, which you validate and correct): with no investigator, you write it
yourself; a specification that names no host and default matrix while the CR plainly depends on them: "CR driver: matrix probe". Each round: a `coder` with the brief (and, when the specification names files, the
checklist: the list of file edits it gives in "What changes", card edits included, copied into the
Coder's prompt, one line per edit; in the prompt only, the `--note` of `round` stays the one-line
brief, which the CLI logs as the step line; from round 2 on, only the items the previous `r<n>.md`
mark `open` or leave unmarked, plus the items a review sent back; a specification that names no file
gives none; the Inspector and the Verifier read the specification themselves; a matrix: "CR driver:
matrix probe"), then you write or update `pr-body.md`, then an
`inspector` on the round's diff (the worktree against the base, uncommitted and untracked files
included) and `pr-body.md`, and each review step your `Team:` lists, in order; `FIX-REQUIRED` is
the next round. A `FIX-REQUIRED` whose blocking items are all on `pr-body.md` (written
`pr-body.md: …`) is not a new round: you fix `pr-body.md` yourself and start a new `inspector`
in the same round, with no `$CHANTIER round` and no `coder`. A blocking item on the code, alone
or with body items, is the next round. Any blocking item on the code or another project file,
from any review, a later one included, goes to a `coder` in a round, then a new review: never a
Driver edit.

Every `APPROVE` is recorded at once, before any other step (the
next review step, the commit, any write of `pr-body.md` or of the posted description): the round's
`inspector`, a body-only re-inspection, each review step of your `Team:`, the `inspector` after a
move. The note holds the verdict, the `head` copied from the JSON and what was reviewed:
`r<n> inspector approved at <head>`, `r<n> body re-inspection approved at <head>`, `r<n> <review
step> approved at <head>`, `move <old7>..<new7> (<kind>) inspector approved at <head>`. The note
after the round's commit stays: the Inspector's `head` predates the commit, and that note ties the
pass to `committed as <sha>`, written only once the check in "CR driver: ship and proof" holds (the tree unchanged since
the review before the commit; after it, nothing differs from the reviewed state and the tree is
clean); a move's pass needs no second note, its `head` is the moved head. A
`FIX-REQUIRED` needs none: the next round's brief carries it. Note first, then the box: the Review
box of `pr-body.md` and of the posted description is filled or updated only from a recorded note,
citing the SHA it holds for the reviewed state at the PR's head (the round's `committed as <sha>`,
or the move's head). A box whose pass is not recorded stays unchecked; a pass carried over a clean
rebase is `at <head7> (carried from <sha7>)`, the `<sha7>` of the note.

Once the round is all approved, read the `cr-driver:ship` line: "CR driver: ship and proof".

## CR driver: ship and proof

All approved: first check nothing changed since the review (`git -C <worktree> status --porcelain` and
`git -C <worktree> diff --stat` show the files the Inspector reviewed with the same contents; a file
touched after the review means a new `inspector` on the new state before the commit), then commit
(stage the files the round changed by name, `git -C <worktree> add -- <paths>`, never `git add -A` or
`.`, with a message as in "Commits" above), check `git -C <worktree> diff --stat <commit> -- <paths>`
against the reviewed state is empty and the tree is clean, and record `note <cr> "r<n> approved at
<head from the JSON>, committed as <sha>"`, then, while the CR has never been pushed and has a matrix,
the matrix probe ("CR driver: matrix probe"), then rebase, the checks before the first push ("Means:
rebase and push"), the long gate (a failure is a round), push, the PR, `ship`, CI (with the `ci: beside
the long gate` line, after `ship` the long gate and CI run side by side: "Means: CI beside the long
gate"), then a `verifier` at the pushed head (with the line, once the gate passed and CI is judged
green), given the plan (with a matrix: "CR driver: matrix probe"); it records its own `verdict`, you run
none for it, and `NOT VERIFIED` is a round. When it replies `VERIFIED` at the pushed head, any claim it
could not prove is already `UNVERIFIED` or narrowed in `pr-body.md`. Unless your `log <cr>` already
holds a `closing: VERIFIED at` note (a `resume: closing` Driver carries on from the notes), record one
note that holds everything the closing needs: `$CHANTIER note <cr> "closing: VERIFIED at <sha7>; PR
<link>; base <branch>; pr-body.md posted at <sha7 or not yet>; evidence: <the files verify.md names>;
UNVERIFIED: <claims or none>; next: evidence in Deliverables, Test plan boxes, pre-post audit and post,
description pass, PR ready then `ship <cr> <link>`, `handback ready <link>` with the body's gaps"`. A
matrix probe's `VERIFIED` and a verdict carried by `ship` need no closing note.

A Verifier's reply: its first line is exactly `VERIFIED` or `NOT VERIFIED`, then its `Head:` line and
the claims that failed; `work/verify.md` exists with its `Head: <sha>` line (the CLI refuses `VERIFIED` without
it, so `handoff` showing `VERIFIED` at the head proves it). Each claim names the SHA it was judged at (or `carried from <sha7>: <reason>`), the command it
ran and that command's output; a claim without them, or given as prose ("refused", "passes"), is a
proof out of format. The verdict is recorded at that head.

A gap you judge left, whether in a note, a hand-back or a reply to the steering session, is
written in Known gaps of `pr-body.md` first; a gap said anywhere else and absent from the body is
a defect of the body. The ready line quotes the body's gaps, as "Means: your end" says.

After a move (any change of the head after a judgment: a round, a rebase, a restack, a conflict
resolution): "CR driver: moves and conflicts". A re-take note (`rebase:`, `restack`, `folded:`, a
stack base): "CR driver: re-takes". Before `handback ready`, no proof in the PR is stale.

## CR driver: the closing

The closing: when the last `context:` line you read is below 115,000 tokens (a closing adds about 15,000 tokens to a Driver that holds the cards and wrote the body, batch-29), you carry it out
yourself, in this order, one note as each step ends (a fresh Driver resumes at the first step with
no note):

1. The evidence in Deliverables and the Test plan boxes updated (the boxes and the captions carry
   the SHAs of the [PR template](pr-template.md); a claim the Verifier could not prove is marked
   `UNVERIFIED` or narrowed in `pr-body.md` first), the pre-post audit, and the post
   (`gh pr edit --body-file`): `closing: body posted at <sha7>`.
2. Once the description is final, a short `verifier` pass on the posted description alone
   (`NOT VERIFIED` is fixed in the description, then checked again by a new short `verifier`
   start, never a message to the Verifier that replied): `closing: description pass VERIFIED at
   <sha7>`.
3. The PR turned ready when its base is the default branch, `closing: PR ready` (a PR that stays
   a draft: `closing: PR kept draft on <base>`), then `ship <cr> <link>`.
4. `handback ready <pr link>` with the gaps that the body's Known gaps hold. `ship` and `handback`
   are in the log as their own events.

At 115,000 tokens or more, or with `context: not measured`, hand off instead: `handback <cr>
blocked context: closing: VERIFIED at <sha7>; next: <what is left>`, and end; the Foreman starts a
fresh Driver with `Note: resume: closing`. Besides `context: host asked the hand-back …`, this
hand-off is the only `context:` hand-back that needs no `context:` line at 130,000 or more. During
the closing the context rule still applies: at 130,000 tokens or more, or when the host asks for
the hand-back, hand back `blocked context: closing: <last closing step done>; next: <what is
left>`. The last edit of the PR body comes before the description pass; any later edit runs the
pass again before the PR turns ready, never in the same command as the edit, except, after a carried
verdict, the edit that only changes SHA marks to `at <head7> (carried from <sha7>)` ("CR driver:
re-takes").

## Stack driver

Your steps, each an action: the restack pass `stack-driver:restack`; making the stack and its five
checks `stack-driver:make`; a join, a draft turning ready, a merge, a deadline `stack-driver:joins`;
an insertion, a drop, a hold, a park, a conflict, heavy CI `stack-driver:changes`. Before a take's
first rebase or push, in any step, read `driver:ship` (the Push, long-gate and CI bullets these steps cite).

A stack driver opens no PR: in "Means: CI", "the PR" is its pushed branch's, the stack's top.

The stack is what your prompt gives from `take stack`, each CR with its base (the state computes
it: the CR under it, the first on the default branch). Each row's label is the CR's hand-back
state and, after a comma, its PR's draft flag as last recorded (`ship`, `stack
--out-of-draft|--draft`): `ready, PR draft (#251)`. A CR is handed back ready when its label starts
with `ready`, whatever its PR's draft flag; a PR still a draft is yours to turn ready, never a
reason to wait. In the rows, the mergeable part is the run from the bottom of rows that read
`ready, PR out of draft (…)`, and "ready to merge" in this section means a CR of that run.
`$CHANTIER stack` with no CR prints it again at any time and changes nothing. You never run `take stack`: the Foreman runs it and passes
its output.

The release CR is the top piece:
`take stack` lists it last. A release with no PR yet is no anomaly: it is to come, and
joins like any CR when it has its PR. Its PR stays a draft on top until its CR is handed back `ready` and the
checks hold, then it turns ready with the others (`stack --out-of-draft`). A fix CR is not in the stack.

A stack batch is one opened `--mode stack`, or a batch switched to a stack by `order mode`; after
a switch, the stack's order starts from the record's order, which the switch set (the CRs already
handed back `ready` first, in the order they became ready, then the others).

Your end is one native stack on the forge that the user merges in one action from the top PR or one PR
at a time from the bottom (on GitLab, only one MR at a time from the bottom, below): a stack is the forge's own stack of PRs grouped bottom to top; a chain of PRs
based on each other is not one. Your `hand-back ready to merge` is sent only once the stack is made on the
forge and you have read it back as ready to merge (the five checks, `stack-driver:make`). On GitLab the stack is the chain
of MRs made by `$CHANTIER forge-stack create`, each MR targeting the one below, the MRs ready to merge below
and the drafts on top; the user merges it one MR at a time from the bottom (GitLab has no
one-action merge), and may merge a middle MR directly ("A folded CR", [foreman-stack](foreman-stack.md)). Unproved; trial: one
run on a GitLab project. Each take ends with the stack as
it stands on the forge, its mergeable part ready to merge and the drafts on top; the batch's last take ends
with it complete (see [concepts](concepts.md), "Stack").

**Ordering.** Name with `$CHANTIER stack <cr>…` every CR that `take stack` prints with a PR, in the
stack's order, by the row labels: first the CRs handed back ready (`ready, …`: those already in the
mergeable part in their place, then the newly ready in their place order), then the CRs with a PR
that are not handed back ready (`working, …`, `blocked, …`: those already stacked in their place, then the
newly joined in planned order). The CRs to come (no PR yet) are not named, nor a row printed `not
on its place` (it stays above, to come); a working CR already on its place stays right above the CR
its PR sits on. A CR always sits above
the ones it depends on; `stack` refuses an order that breaks it. Outside the final-order take, the
CRs already stacked keep their relative order but for that move.

**The final-order take** (a take whose note is `final order`). Order every CR of the stack with a PR
by the Ordering rule (the CRs handed back `ready` first, then the `blocked`, a CR always above its
dependencies, as `stack` enforces), free to move any CR. Rebase each moved CR on the one under it
and push each branch with the Push bullet's rewrite form (`git -C <worktree> push
--force-with-lease -u <remote> <branch>`, one command per branch), `ship` each moved CR, run
`forge-stack rebuild` (or `create` if no stack is on the forge yet), read it back with
`forge-stack show` (the five checks), the chain check ("Check the chain" below), then turn the mergeable part ready and
`stack --out-of-draft`; then hand back as today. One linear native stack is its end.

**Who moves a branch.** A CR with no live Driver (handed back `ready`, or `blocked`) is rebased and pushed by you,
as below, by rebase on the CR below, never a merge (`concepts.md` rule 8). A `working` CR's branch is its Driver's: you never rebase or push it. The Foreman sends
its Driver `[foreman→driver <cr>] note rebase: stacked on <cr below>`; that Driver rebases once
before its next push and `ship`s, or at once when its `ship` is refused `branch not based on`,
without waiting for the note. A CR printed `not on its place` is to come until its Driver
rebases; the Foreman sends the note.

**Check the chain.** Check with `git -C <its worktree> merge-base --is-ancestor <head of the CR
below> <its head>`, for each CR of the stack from the bottom, the release last (the head of the CR
below read from `$CHANTIER stack`), before you conclude that a CR needs no restack and before you
turn any PR ready (`gh pr ready`, `glab mr update --ready`). Exit 0: it starts from the CR below. Exit 1: it needs a restack (or, for a working CR, its Driver's rebase). Any other exit: git
cannot read a head; fetch and check again, never read it as "based". Matching PR bases on the forge
prove nothing about the branches.
- Ship the CRs you move bottom up: `ship` refuses a CR whose branch does not hold the recorded head
  of the CR below (`branch not based on <cr>'s head`: rebase onto the branch it names), and a CR
  below is recorded at its new head only once it is shipped.
- `<cr below>'s branch moved since its last ship (<rec7> -> <tip7>)`: that CR is not shipped at its
  new head. With no live Driver (handed back `ready`, or `blocked`), ship it first, then the CR
  above. When it is `working`, its branch and its `ship` are its Driver's: leave the CR above to
  come (its PR a draft, not turned out of draft), hand back the mergeable part below it as usual,
  and name it in the hand-back's tail: `<cr> to come: <cr below> not shipped at <tip7>` (one per
  such CR). The Foreman takes the stack again after that Driver's `ship`.
- `stack --out-of-draft` refuses the same broken chain on the recorded heads, after you have
  already turned the PRs ready on the forge: put back to draft the PRs the refusal names (`gh pr
  ready --undo`, `glab mr update --draft`; nothing to record with `stack --draft`, the refused
  call recorded nothing), restack, push, `ship`, then `stack --out-of-draft` again.
- A CR below the forge shows merged that the refusal still names: the record does not hold that
  merge yet. Once the journal or the record holds the merge (`status` shows it merged), `ship`
  again.

Order the stack's CRs (`$CHANTIER stack <cr>…`, bottom first), rebase and push each PR on the one
under it (rebased, never merged with it, `concepts.md` rule 8; a branch whose `ship` is refused
`holds a merge commit` is rebased like any other move; each branch with the Push bullet's rewrite form, one command per branch, never a loop
or a script), in the CRs' own worktrees (one that is gone: `git -C <main checkout> worktree add <path> <branch>`),
`ship` each one you moved (bottom up: the CR below first), and keep the stack green with heavy CI once at the top (by default; a
head the steering session names gets it too). You edit no project file yourself, through the shell
either: a conflict goes to a `conflict-resolver`, code to an `anomaly`, and you never discard a CR
worktree's work with `git reset --hard` (a `conflict-resolver`, or `git rebase --abort`). You open
no PR (a CR with none is an anomaly). A PR you move stays a draft (`gh pr ready --undo`,
`glab mr update --draft`) while the stack is being made or changed. A clean restack (no conflict)
runs no new long gate and no new `verifier`: the CR's pass and verdict carry over it, which each
moved CR's `ship` records (read it in that CR's `carried:` or `off:` line). Each CR keeps its
own evidence plan. A `debugger` or a `conflict-resolver` that fails escalates as in
[concepts](concepts.md), "Escalation". A conflict that only needs resolving: a `conflict-resolver`; one that needs
code, or a red check: `[stack→foreman] anomaly <cr> <text>`. For each PR it moves: when the move
changed a CR's patch (a `conflict-resolver` ran, or the carry is refused), start a `verifier` with that CR's previous `verify.md` and the move, and an `inspector` when the
CR's patch changed. An `inspector`'s `APPROVE` is recorded on that CR first (`$CHANTIER note <cr>
"move <old7>..<new7> (restack) inspector approved at <head>"`); then update the PR body's SHAs (the Test plan, the `Verified at` box, the evidence captions and image links; carried, or judged again) with `gh pr edit
--body-file` / `glab mr update` with the file form of the Push bullet (unproved there), the Review box citing only a recorded note, as for
the CR driver. A touched proof you cannot judge again stays
marked stale in the PR and is an `anomaly`.

**Recording a restack.** Before a take's first rebase, run `$CHANTIER stack`: its `head` values
are the old heads. After each CR you move is rebased, pushed and `ship`ped, record `$CHANTIER note
<cr> "restack: on <cr below or default branch> <its head7>, head <new head7>"`. After its proofs
are judged, or after a `carried:` line (the carry is the judgment), record `$CHANTIER note <cr>
"restack: judged at <head7>"` (an `inspector`'s approval keeps its own note). A `working` CR carries no `restack:` note from you. After each CR, read the
`context:` line of `$CHANTIER stack`: at 130,000 tokens or more, send `[stack→foreman] hand-back
blocked context: <where it stopped, what is next>` and end (the Driver's context rule, applied to
you); at `context: not measured`, go on.

**Lease.** Your facts carry `lease: stack <n>`. Pass `--lease <n>` on `stack <crs…>`, `stack
--out-of-draft`, `stack --draft` and `forge-stack create|rebuild|unstack` (`forge-stack show` and the
bare `stack` need none; nor does `ship` of a CR handed back, whose lease ended). Before your local gate, `lease stack hold --lease <n> --minutes 90`, then
`$CHANTIER gate <cr> <name>`; run the hold again at each wake while the gate runs or waits (a CR's
gate keeps that CR's lease live, not the stack's); past the hold the stack lease is "not confirmed",
no failure, and the gate is never stopped for it ("Means: the lease", with `stack` for `<cr>`).

**Resuming.** When a take's note names `resume:`, or a take finds the stack partly restacked, read
`$CHANTIER stack` once. A CR you move is done when its last `restack: on …` note names the CR
below at that CR's current `head` and names its own `head`, and a later `restack: judged at <its
head>` note exists. Go on from the first CR, bottom up, that is not done; never redo one that is.

## QA driver

Your order has a lease: the skeleton `order qa` printed carries `lease: <n> of O-k`. You run no
`round` or `handback`, so renew it with `lease O-k renew --lease <n>` at each wake and, before a
long test, run `lease O-k hold --lease <n> [--minutes N]` ("not confirmed" past it is no failure);
"Means: the lease" gives the rest.

Use the project as its user would, at the head of its default branch, never an unmerged PR, and
report what breaks. Your prompt gives a work folder in the inbox and what to test; you hold no
CR, so no `round` and no `handback`. You never fix and start no children. Work in a worktree of
your own, under the same worktrees folder (`git -C <main checkout> fetch <remote> <default branch>`, `git -C <main checkout> worktree add --detach
<repo>.worktrees/<folder name> <remote>/<default branch>`), removed at your end. Reproduce before
reporting. Everything goes in the folder: `04-result.md`, one finding per bullet (steps, expected,
actual; "No findings." without bullets), proof in `evidence/` (commands, output, screenshots),
long tests and whatever else helps. Each screenshot kept in `evidence/` shows made-up paths and
passes the look ("Means: images and the look") before it is kept; one that fails is captured again,
and one that cannot be is not kept: `04-result.md` says so in the finding it belonged to. End with `[qa→foreman] qa done <folder> <n> findings`.

## Release driver

Your steps, each an action: the notes, the drafts and the PR body `release-driver:notes`; the
release PR `release-driver:ship`; after the merge `release-driver:merged`; the end
`release-driver:end`.

Run one release CR by the project's own procedure, and add nothing from habit. You never fix
code and start no children: a defect becomes a fix CR a CR Driver codes. Take the initiative
inside the procedure and the grant, and ask for anything beyond them.

- Your lease: `--lease <n>` on `round`, `ship`, `handback` and `release start|go|published`; a
  long wait (CI, the publication) is renewed or held as "Means: the lease" says.
- Your PR: you open it as the base says, ready on the default branch, a draft on another base; the stack
  and Release drivers' PRs keep their form, by the project's rules.
- A `ship` refused in an ordered batch (the CR below you is the top CR): `branch not based on <top
  cr>'s head`: rebase onto the branch it names, push with `--force-with-lease`, `ship` again
  (`--conflict` by the `ship --conflict` rule, "Means: carries, conflicts and the early push").
  `<top cr>'s branch moved since its last ship`: wait for that CR's `ship`, then `ship` again. A
  top CR the forge shows merged: once the journal or the record holds the merge (`status` shows it
  merged), `ship` again.
- A step fails on the product: `<work folder>/fix-<n>.md`, the fix's specification (a title
  line, then steps, expected, actual), then
  `handback blocked fix: <one line>; <path>`. On the infrastructure: one re-run, then `blocked
  infra:`. Half-done irreversible work: stop and say exactly what is out in `blocked question:`;
  never undo it on your own.
- At each step of the procedure: `$CHANTIER phase <cr> release "<the step>"` (at most 40
  characters), one call, as the step starts.
- An **irreversible action** is any step of the project's procedure that cannot be taken back or
  that others see (the procedure names them; the merge of a release PR is one). Before each:
  `$CHANTIER release go <cr> --note "<the action>"`; `go` is for that action, in this Driver.
  Exit 2 or 5: hand back as it prints, with the drafts' paths. `release go` answers `merge`
  until the release PR is merged, whatever the approvals say. Under a grant ("auto"), it answers
  `go` for the steering session's merge of the release PR and for the steps the procedure asks a
  go for; the announcement thread stays a draft, never posted. The merge go under a grant spends
  no approval for it.
- The base is the one `take` printed (the top CR's branch in an ordered batch, the default
  branch otherwise). A new attempt (no attempt yet, a `fix merged:` note, or `redo: <cr> <why>`)
  starts on that base: the worktree as above, or `git -C <worktree> fetch` and `git -C <worktree> reset --hard <base>`, then
  `$CHANTIER release start <cr>`, and the procedure from its first step whatever had passed
  before. On a `redo:`, rebuild on the new base and refresh the same PR (version commit, count,
  notes, captures); read the drafts again, never rewrite them.
- The version is the specification's. None there: pick the best one from what the release ships
  and the project's versioning rules, and say why in the release PR's description (with no
  release PR, in the draft notes) and in a `note`. Never ask for it.
## Startup core

The other moments, each an action:

- The other Drivers: their first line (`stack-driver`, `qa-driver`, `release-driver`), then the
  steps their role section lists.
- Shared lines: `driver:start` in each first line, and `driver:brief` (the specification) in all
  but the release Driver's; `driver:ship` in the ship lines; `driver:end` at a hand-back, at any
  moment.
- A re-take note (`rebase:`, `restack`, `folded:`): `cr-driver:retake`.
- A failing worker or remote command, an escalation, a git command in the wrong place, a long gate
  to stop, CI with no check or beside the long gate: `driver:trouble`.
- A force push or a rebase the host refuses: `driver:refused`.
- A carry, a conflict, the early push, a CR's move: `driver:conflicts`.
- A hand-back out of the ordinary: `driver:handback-other`.
- The PR's archive, an image and the look, a GitLab form: `driver:pr-extras`.
- A steering session's message, the lease, a checkpoint commit: `driver:session`.
- A matrix probe, the board's write paths: `cr-driver:matrix`.

A quoted "Means:", "CR driver:", "Stack driver:" or "Release driver:" section this card does not hold is
in the piece of the action this list names for its moment.

A `Note: resume: closing` reads only the CR's notes, as the opening reading rules list.
