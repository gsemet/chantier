# Drivers

A Driver runs in the background for its steering session (the Foreman, or the Chief of Staff in direct
mode) and drives one CR (or the stack) through short foreground children, one at a time. Read your
host's reference with this card ([Claude Code](hosts/claude-code.md) or [Copilot](hosts/copilot.md)):
how to start a child and reach the steering session. It never codes, reviews, debugs or resolves a
conflict itself: it starts the child, and restarts a failing child rather than do its work.
Git and the forge are yours (`git`, `gh`, `glab`), by the project's rules (`$CHANTIER rules`, read
first); the CLI keeps the CR's record and tells you what is off. You send every line to the steering
session by the `Steering:` line of your prompt; a prompt without it is a `Needs:`-like gap: `note` it
and use the host's reference row.

At startup read the startup core and the project's rules; defer the rest of this card by step.

- **Rules:** the instruction file `$CHANTIER rules` names first, whole; of the other files, only what
  touches a Driver's work (git, the branch, the gates, the PR, the forge, CI).
- **Specification**, whole or by part: its goal, scope, decisions, open points and evidence, to brief
  the workers, write `pr-body.md` and judge the proof. The detail of "What changes" is the Coder's and
  the Inspector's; you read its list of file edits and copy it into each Coder's prompt as a checklist
  ("CR driver").
- **A card:** Grep the heading, then Read with offset and limit; a section a link names in full, never
  printed with `cat`, `sed`, `awk` or `Get-Content`, never read twice.
- **Deferred:** a CR Driver's common path is the three lines of `startup-manifest.json`, each read when
  its step comes: before the first Coder `cr-driver`; before the first commit `cr-driver:ship`; at the
  pushed-head `VERIFIED` `cr-driver:closing`; a hand-back at any moment, "Means: your end". The other
  Drivers read their one line and their role section. A section no line
  lists is read when a link names it.
- **Concepts:** "Escalation" when a trigger arises; a rule or word of "Words" when a link names it.
- **A Driver started again** (a `resume:`, `rebase:`, `context:` or other `Note:`): read "Means: a Driver
  started again" first.
- Another Driver's section, another role's card and the users' docs are not opening reads.
- A rule you did not read still binds you: when a step is not in what you read, read its section
  before you act.

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
  <worktree> rebase <base>`; a conflict is a `conflict-resolver`. A rebase with no conflict that
  leaves the CR's patch unchanged needs no new long gate and no new `verifier`: the pass and the
  verdict carry over it ("Means: the long gate"). When the PR exists and the rebase needs a long
  gate (a conflict was resolved), push early, by the "Early push" rule below. Never `git stash`
  (shared): set work aside with a commit. Never stop a process by name or pattern (`pkill`,
  `killall`); stop only one you started, by its id (a running long gate: `gate <cr> --stop`, never
  by ending the `gate` command, which leaves its suite running). A command the host may refuse runs
  alone.
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
  not). A change of a PR's base or draft state on the forge is followed by `ship <cr> <link>`. What else `ship` prints (`base ?`, `off: no long gate
  passed`, a PR that carries another CR's head): "Means: carries, conflicts and the early push".

## Means: the long gate

- The long gate, the project's command, before the first push and the PR (with the `ci: beside
  the long gate` line: "Means: CI beside the long gate"): `$CHANTIER gate <cr> "<command>"
  ["<command>"...]` runs only the long gate the project's rules name, in the worktree, in order,
  as many at once as the project allows (`chantier.yaml`, one by default), the rest wait in a queue (its order: "Means: stopping a long gate"); a running gate is never stopped. A rebase with a conflict resolved takes `ship --conflict` and the early push ("Means: carries, conflicts and the early push"). The CLI reads no forge: you read CI at the new head, which must be green. A short gate (the fast gate, or the check that the rules ask of a CR they exempt from
  the long gate, such as a docs-only change) you run yourself in the worktree, never through
  `gate`: it would wait behind the long gates. A pipeline job named as the long gate: "Means: CI beside the long gate". A rule that asks the batch's or the stack's top for a local run: "Means: carries, conflicts and the early push".
  `gate` stops at the first failure, keeps the log and records the pass at that head. It is
  refused (exit 2) on a dirty tree: a gate binds to a commit, so commit first. The log's
  first line names the CR, the branch and the full SHA it ran at, its last line the result; a
  head that moved during the run (a gate command committed) is no pass at either head (exit 4).
  One command per argument, never a `;` or `&&` chain.
  Stopping a gate (`gate <cr> --stop`: only your own CR's, only when its result can no longer count) and a long wait in the queue: "Means: stopping a long gate". `cancel` is the steering session's, never a Driver's.
- A gate log is never taken whole: its result from `handoff` (the last five lines it prints) or from the log's last lines.

## Means: CI

- CI: while CI runs, do everything that does not need its result first: `pr-body.md` and the
  description as far as they can go, the archive's `delivery.md` when `take` printed an archive path, your notes. Then one long wait:
  the forge's watch in a background shell, `lease <cr> hold --lease <n> -- <the watch>` (`gh pr checks
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
  the long gate, and quotes that rule (a waived CR, or the stack's top: "Means: hand-backs out of the
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

## Means: a worker that fails

- A worker refused for its first line, or ended by a host failure, gets
  one new start of the same role with the same brief (a worker refused because its prompt names
  no card gets that one new start with the role's opening lines copied as printed; the rest of
  the brief stays the same), `$CHANTIER note <cr> "restart: <cause>"`
  first, no `round`; a second refusal of the same start, a model included, is `handback blocked
  refused <exact text>`, never retried without the model.
- You never read a verdict, a pass or a choice into a reply out of format, never fix it, and never
  ask the worker by message to fix it. Record `$CHANTIER note <cr> "restart: reply out of format:
  <what is missing>"` and start one new worker of the same role with the same brief, as for a
  refused first line (no `round`); its brief also says what the failed reply lacked. For a Coder,
  this new start is the restart of a failing coder of "CR driver": it counts as that round's one
  restart. A second reply out of format from the restarted worker: a Coder's is the next round
  (`$CHANTIER round`), as "CR driver" says of a second failed coder; any other role's is
  `handback <cr> blocked question: <role> replied out of format twice: <what is missing>`, and the
  stack driver sends `[stack→foreman] anomaly <cr> <role> replied out of format twice: <what is
  missing>`. A worker is never resumed by a message to its
  agent: only a new start continues its task, and a new round is always a new child, never the
  previous round's Coder resumed.
- After a coder that
failed, a dirty worktree goes to a new `coder` in the same round, with no `$CHANTIER round`; its
brief names what the failed attempt left and what to do with it: keep it, fix it, or discard it
back to the round's starting head (then the coder's own git). That is a restart of a failing
child, not a new round. The coder is restarted at most once per round: a second failed coder in
the same round is the next round (`$CHANTIER round`), whose brief carries both failures. A
worktree left dirty by a failed rebase goes to a `conflict-resolver`.
- A long reply is read, not restarted. A reply in format that only passes its cap (more than ten
  lines for a Coder or a Verifier; more than 3,000 characters for an Inspector or an extra review
  step) is acted on as any other reply, and you record `$CHANTIER note <cr> "long reply: <role>:
  <n> lines"` (`<n> characters` for the JSON). It is no cause of a restart and counts as no failed
  worker. The brief of the role's next start in this CR (the next round's Coder, the next Verifier)
  says that the last reply passed its cap and that the details go to the work file. An extra key
  alone in an otherwise correct Inspector JSON is read and noted the same way, not restarted.

## Means: escalation

- Escalation ([concepts](concepts.md), "Escalation"): only when one of its triggers arises, read
  the role's `escalation=` on the `team:` line first, then the `escalate:` line of
  `$CHANTIER playbook --batch <batch>`, as printed.
- Escalation applies to the CR driver as to any parent ([concepts](concepts.md), "Escalation"): a
`debugger` that explains no red check, or a `conflict-resolver` that settles no conflict, gets a
second one on the escalation model. A note `escalate: rounds` or `escalate: blocked twice: ...`
means each new round's `coder` starts on the coder's escalation model; you keep your own model.
You never escalate yourself.

## Means: a remote command fails

- CI's `timing:` line is, on Claude Code, the `subagent` one; on Copilot, the line of your model's family,
  else `other models`. An infrastructure failure of a CI job gets at most the CI re-runs of that line (1 by
  default; 0: none), each at the same head, and a failure the CR does not touch that passes on a re-run is
  a flake: a `note` names the test, the run and the symptom, for the Chief of Staff to file. Once the
  re-runs are used up and the job is still red on the infrastructure, end with
  `handback <cr> blocked infra: CI <job> red on the infrastructure after <n> re-runs` (the stack
  driver: `[stack→foreman] anomaly <cr> infra: …`). With no result after 3 hours on one head, stop waiting
  and end with `handback <cr> blocked infra: CI still running after 3 hours` (a longer CI in the
  project's rules gives its own limit).
- A remote command (`git fetch`, `git push`, `gh`, `glab`) that fails with a forge server error
  (an HTTP 5xx) or a network failure (no route, a reset or timed-out connection, a name that does
  not resolve) runs the same command once more, at once and with no `sleep`. Before re-running a
  command that creates or moves something (`git push`, `gh pr create`, `glab mr create`, `gh pr
  edit`), first check whether the first attempt took effect (`git ls-remote <remote> <branch>`,
  `gh pr list --head <branch>`, or the forge's equivalent) and do not run it again if it did.
  Note it: `$CHANTIER note <cr> "infra re-run: <command>: <exact error>"`. If the second attempt
  fails the same way, the CR Driver and the Release driver end with `handback <cr> blocked infra:
  <command>: <exact error>`; the stack driver sends `[stack→foreman] anomaly <cr> infra:
  <command>: <exact error>`. A refusal (an HTTP 4xx, a denied permission, a protected branch, a
  failed lease) is not an infrastructure failure: it keeps its own routes (`blocked refused`, the
  force-push route, a failed lease examined), with no re-run. The CI rule (an infrastructure
  failure gets at most the CI re-runs of your `timing:` line) is about a CI job, and the Release
  driver's "On the infrastructure" is about a step of the procedure; both stay, and the remote
  command's one re-run above is not the `timing:` line's. This is the same rule for a single command.

## Means: a force push the host refuses

- A force push the host refuses (any Driver that pushes): it climbs the ladder of
  [foreman](foreman.md#a-drivers-refused-force-push), "A Driver's refused force push" (the
  steering session judges it and runs it; if the host refuses it there, the Chief of Staff judges
  it again and runs it; if the host refuses the Chief of Staff, the user is asked once), without
  the user's word in the normal case. In direct mode the steering session is the Chief of Staff,
  so the ladder is Driver, Chief of Staff, the user.
  This holds for a CR Driver and the Release driver (both hand back with `handback <cr>`); the
  stack driver keeps its own rule, below. With your work committed:
  1. Record the refusal first, in one note: `$CHANTIER note <cr> "refused: <the exact command> ->
     <the host's exact text>"`: the command as it ran (its `git -C <path>` form included, flags
     and refspec as typed), and the host's whole text as it came (with the classifier's label,
     such as "Git Destructive", when the host gives one). Never a summary such as "refused by
     host". It is what proves afterwards a missing allow rule or the classifier on a matching rule.
  2. Then one note with what is next: `$CHANTIER note <cr> "next after push: <the steps left, in
     order>"` (for instance: `ship`, the long gate already passed at `<sha7>`, read CI, the
     verifier given the move (unless the rebase was clean: the verdict carries), turn the PR
     ready, hand back ready), so a fresh Driver starts from it
     without reading the whole record again.
  3. `$CHANTIER handback <cr> blocked waits: push <branch> <expected remote sha> <local sha>`
     (the remote head you expect, from `git ls-remote`, and your head).
  4. Send `[driver <cr>→foreman] push <branch> <expected remote sha> <local sha>`, and end: no
     other push, no other way, and no wait in your turn. The CR waits, not you; the steering
     session restarts a fresh Driver on it when the push's answer comes back (the Foreman's, or the
     Chief of Staff's).

  The fresh Driver reads the answer in its `take` note (`push: <the answer>`) and acts on it, from
  your `next after push` note: `pushed <branch>`: `ship` and go on. `push failed`: look at why
  (`git fetch`, what the remote gained), never the same push again. `push refused <branch>: no
  long gate passed at <sha>`: run the long gate, send the push line again and hand back `waits:`
  again as above (with the `ci: beside the long gate` line, and for a branch whose PR is
  recorded (the early push), the steering session does not send it; one you get anyway goes to the
  steering session as printed). Any other `push refused` (the
  branch is not this batch's, the push was judged not legitimate and the user said no, or the host
  refused it at every step, the user's yes included): `handback blocked
  refused <exact text>` at once; it goes to the user. Any other refused action stays `blocked
  refused` as above. The stack driver, which restacks several branches in one take, sends one
  push line per refused branch and waits for each result as a note (the result may now come from
  the Foreman's own push), no other push, no other way. The Release driver is covered by the same
  section, with no text of its own.

## Means: the archive in the PR

- The archive in the PR: when `take` or `handoff` prints `archive: in the PR at <path>`, before
  each `handback <cr> ready` write the cleaned archive in your worktree at that path and commit
  it with the change: `intake/`, `evidence/`, `01-intent.md`, `02-answers.md`,
  `03-change-spec.md`, `delivery.md` (what the PR delivers, from the PR body's summary, with the PR
  link once known) and `STATUS.md` as it stands; no `work/`, no log. Keep it current at each later
  round. The retained prototype goes in too: the version `02-answers.md` (or the specification)
  names as retained, copied as `prototypes/NN-<idea>/`, or zipped as `prototypes/NN-<idea>.zip`
  when it is above 1 MB (up to 10 MB); when `02-answers.md` records a decision on a very big
  folder, follow it. No other version and no `experiments/` go in the PR's archive (they stay in
  the planning folder's `5-archives/`); with no retained prototype named, nothing from
  `prototypes/` goes in. Each image added or changed in the archive passes the look (The
  evidence, above) before the commit; one that fails stays out until it passes. A retained prototype above 10 MB with no recorded decision stays out of
  the archive: say it in a `note`, and name it in the PR's Known gaps ("retained prototype not in
  the archive: too big, no decision recorded"), so the ready line quotes it and the Chief of Staff
  asks the user. The same Known gap names a folder that grew very big during the batch. `ship`
  says `archive missing from the PR at <path>` when it is off. When the project
  ignores `.agents/changes/`, say it in a `note` and hand back with the PR as it is: the Chief of
  Staff asks the user (no `git add -f`). `archive: not in the PR` means no archive in the worktree, no `.agents/changes/` path in the diff,
  and no `delivery.md` to write for the PR; that is the default with a planning surface.

## Means: images and the look

- A taken-back note `evidence: <path>` is an image to attach the same way: remove the matching bullet from
  Known gaps, run the description pass, hand back ready. An image linked into a commit of the CR's branch
  is not an upload; one found after a move (`ship`'s `off: pr-body.md line <n> shows an image from …`) is
  attached by you with the forge's CLI, using the same image file (from `work/`, or from `git show
  <old>:<path>` while the commit is still local), before the PR turns ready; it is captured again only
  when a Verifier is due anyway (a conflict, a refused carry). Every image is given the look before it
  is kept or uploaded, below.
- A Driver never opens an image file (`.png`, `.jpg`, `.gif`, `.webp`): it attaches the images the Verifier
  or the Demo explorer names, by path and caption, and judges them from their reply.
- No image shows the user's username or home folder; every image you keep or upload shows made-up
  paths. Terms: the *user's username* is both the login name of the machine you run on
  (`$env:USERNAME` on Windows, `$USER` on Linux and macOS) and the last part of the home folder's
  path (they can differ; check both). The *home folder* is its full path (`C:\Users\<name>`,
  `/Users/<name>`, `/home/<name>`) in any form on screen (either slash, `~` expanded, inside a
  longer path such as a temporary folder under it). A *made-up path* holds neither, wherever the
  image shows a local path (planning folder, worktree, file, prompt, window title); how you get it
  is yours (a made-up folder name, `~`, `user`; a scratch project under `work/scratch` sits under
  the user's home folder, so rewrite its paths in the capture, or do not keep it). *The
  look*: open the image as an image (not its file name) and look for both; it passes once neither
  shows. *Keeping* an image is writing it anywhere in the planning folder (a CR's `evidence/` or
  `work/`, a QA work folder's `evidence/`), which is pushed with the surface. An *upload* is any
  way an image leaves the machine for the forge: `gh pr edit --attach` or another forge CLI's
  attach, a release asset, a push of a commit that adds or changes an image. Give each image the
  look before you keep it and again before each upload; keep or upload it only once it passes. An
  image of yours that fails is captured again with made-up paths; the Verifier's that fails is
  asked again of the Verifier; none is kept or uploaded meanwhile. The user's own screenshot (the
  taken-back `evidence: <path>`) gets the look before the upload: when it fails, do not upload it
  or copy it into the planning folder, keep its Known gap (the PR's Known gaps still quotes it),
  and say why (it shows the username or the home folder) in a `note` and in your hand-back
  report. A leak found after an upload (your description pass, or the Verifier's `NOT VERIFIED`
  on it): replace the image in the description with a clean capture (made-up paths, given the
  look) and say in a `note` and in your hand-back report that the old one was uploaded (the PR,
  which image, at which SHA); a removed attachment can stay reachable on the forge, so the user
  is told. When the leaked image is the user's own screenshot, remove it from the description,
  put the Known gap back, and say so in the same `note` and report. Nothing about the leak goes
  in the public PR.

## Means: carries, conflicts and the early push

- Any change of a PR's base or draft state on the forge (`gh pr ready`, `gh pr ready --undo`,
  `glab mr update --ready`, `glab mr update --draft`, a retarget) is followed by `ship <cr>
  <link>`, so the record follows the forge.
- `ship`'s other lines: a failed read of the forge prints `base ? (not read from <link>: …)` and `draft
  not read`: the CR reads `PR in draft` until a `ship` reads the forge. With the `ci: beside the long
  gate` line `ship` runs before the gate passes, so `off: no long gate passed at <sha>` is expected
  there, as for a PR already recorded after a rebase that needs a long gate (the early push), and
  `handback ready` still refuses a head with no passed long gate, unless the pass carries over a clean
  rebase. `ship` also refuses a PR whose head carries another CR's (`… carries CR-x …`).
- A Conflict resolver's reply: `conflicts.md` exists, with each conflicted hunk and the choice made, and
  the fast gate's command and result.
- After a rebase with no conflict that leaves the
  CR's patch unchanged, run no long gate and no `verifier`: the pass and the Verifier's verdict
  at the head before the rebase carry, and `ship` checks both with git (the exact `git patch-id
  --verbatim` of each of the CR's own commits, oldest first, is the same on the base the judged
  head sat on and on the base the new head sits on, and no merge commit is among them; a base is
  the nearest branch under the head among the batch CRs' branches, local or remote, and the
  default branch, read by git, whatever the record or the PR names), logs a
  `carry` event with `gate_from` and `verdict_from`, and prints `carried:` (or `off:` with the
  reason, with both counts when the patch changed: unequal counts mean the CR's own commits
  were miscounted, an anomaly to report, not a reason to re-verify); `handback ready` reads that event and records the same keys. Any commit added or
  edited is gated again and gets a `verifier` given the move (the hand-back refuses with `does
  not carry: <why>`). **The `ship --conflict` rule, stated once:** any `ship` after a rebase
  during which a conflict was resolved takes `--conflict`, whoever resolved it (a
  `conflict-resolver`, or you) and whoever runs the `ship` (a CR's Driver, the stack driver, the
  release Driver), for a rebase of any reason (a `rebase:` note, `stacked on`, a mode switch, a
  restack, an insertion, a drop). `ship <cr> <link> --conflict` records `conflict: true` and
  voids every pass, verdict and carry recorded before it, at that head and any earlier one, so the
  CR is gated and verified again; the same head shipped again without the flag clears nothing. The CLI reads no forge: you read CI at the new head, which must be green.
- **Early push** (every batch, no `chantier.yaml` key): when a rebase of a CR
  whose PR exists needs a long gate (a `rebase:` note, a restack, a taken-back CR, with a
  conflict resolved), turn the PR to draft if it is not one (`gh pr ready --undo`, `glab mr
  update --draft`), push at once with `--force-with-lease`, `ship <cr> <link>`, then
  start the long gate and the CI watch side by side, by the outcomes of the "CI" bullet (a red
  CR job stops the gate, a failed gate stops the watch). The PR leaves draft (`gh pr ready`,
  `glab mr update --ready`, then `ship`) only once the gate has passed and
  CI is green at that same head. A PR that does not exist yet still waits for its gate before
  its first push, unless the project chose `ci: beside_gate: true`.
- A rule that also asks the stack's
  top for a local run is met by that CR's Driver with `$CHANTIER gate` as any long gate, and that
  CR hands back with no `--no-gate`.
  In a batch with no stack on the forge, the top is the batch's last open CR other than a release
  CR (every other non-release CR merged or cancelled; a fix CR counts; a one-CR batch's CR from
  the start), or, when the last open non-release CRs are all handed back ready and no other CR is
  working or queued, the last of them in `status`'s order: before the `ship` that precedes your
  ready hand-back, and so before you take the PR out of draft (the hand-back bullet's order:
  `ship`, `gh pr ready`, `ship` again, `handback`), read a plain `$CHANTIER status` (no
  `--refresh`, no `--epoch`); when your CR is that top once it is handed back, run the local gate
  at your pushed head unless a pass or a carried pass is already there (`ship`'s `carried:` line),
  in your worktree, clean, before the PR turns out of draft, and hand back with no `--no-gate`. A
  `take` note that says `long gate: the batch's top runs <command> locally` (alone, or after
  `rebase: <cr> merged; ` in the same note) asks the same run at the head you push after that
  `take` (the rebased head). A failure there is a round, as for any long gate. When your CR is not
  the top, hand back as the project's rules say (`--no-gate "<the rule>"` for a pipeline job); if
  it becomes the top later, the steering session sends it back for the run. A Release driver is
  never the top and runs no local gate for this rule.
- `ship` refuses, and
  records nothing, a PR on the default branch and out of draft whose head carries the head of
  another CR of the batch not recorded merged and with a PR (`… carries CR-x (<link>): merging it
  would merge them too …`). The first step is always the same: draft, then `ship`. Put the PR
  back to draft (`gh pr ready --undo`, `glab mr update --draft`) and `ship` again, which records
  the PR in draft so the CR no longer reads mergeable; then, if the PR is to stay on the default
  branch, rebase it onto it without those commits, push, and `ship` again. If the CR named is
  already merged on the forge, `ship` again once `status` shows it merged. For the stack driver
  it means a PR moved without first going to draft, as the stack driver section asks.

## Means: CI beside the long gate

- When the project's rules name a pipeline job as the long gate
  ([concepts](concepts.md)), run no `gate`: push and open the PR after the approved round (the
  first push starts the gate, so no wait before it; `ship`'s `off: no long gate passed at <sha>`
  is then expected), read CI as the "CI" bullet says, and once that job is green at the PR's head
  with the `VERIFIED` verdict there, hand back `ready <link> … --no-gate "<the rule>"`, quoting
  the rule; a red run of that job is a red CI job, a round. A rebase needs no gate carry: the job
  runs again at the pushed head. (GitLab and Copilot: unproved.)
- With the `ci: beside the long gate` line (a CR Driver only), after the approved round,
    the commit and the rebase: push, open the PR as a draft or update it (the audit pass on
    `pr-body.md` first), `ship`, then start the long gate (`$CHANTIER gate <cr> "<command>"…`)
    and the CI watch (`gh pr checks <pr> --watch --fail-fast`; on GitLab `glab ci status
    --live`, unproved; trial: a red job of a GitLab pipeline ends the watch or shows in its
    output before the pipeline's end), each in its own background shell by the host's means
    (Claude Code `Bash` with `run_in_background: true`, Copilot's background shell). Do
    everything that needs neither result, end your turn, and the first shell to end wakes you.
    Unproved; trial: a CR Driver of a batch with the line pushes at the approved round, runs its
    gate while CI runs, and on a red CI job stops its gate and starts a debugger before the gate
    ends. The outcomes:
    - A red job that is the CR's (not an infrastructure failure, not a job also red on the
      default branch, judged as above): at once, without waiting for the gate or the other jobs,
      `$CHANTIER gate <cr> --stop` (recorded `stopped`: no pass, not a round), a `note` naming
      the job and the head, `gh run view <run> --log-failed > <work folder>/ci-<run>.log`, a
      `debugger` on it, the next round.
    - An infrastructure failure, or a job also red on the default branch: its rule above (the
      `timing:` line's re-runs, or a note). The gate is not stopped, its result still counts.
    - The gate fails first: a round, as today. Stop the CI watch's shell you started, by its
      id; CI at that head no longer counts.
    - The gate passes first: go on waiting for CI. CI is green first: go on waiting for the
      gate.
    - Both done, the gate passed and CI green or judged by the rules: the `verifier` at the
      pushed head, as today.
    - The early push of a PR that exists (every batch, no line needed) uses these same
      outcomes after a rebase that needs a long gate: the PR is a draft, pushed at once, and
      leaves draft only once the gate has passed and CI is green at that same head.
    The 3-hour limit, the "no CI" looks, the head check and the CI note's form stay.
- With the `ci: beside the long gate` line, a CR Driver reads the systems CI covers from the
forge's list of checks at the pushed head (job names such as `just check (ubuntu-latest)` name
their system) and compares them with the system the long gate ran on. In Known gaps it writes one
bullet naming the systems only CI covers and which commands of the long gate ran only there, for
example "The long gate ran on Windows only; Linux and macOS are covered by CI alone." A forge
that lists no check gives no such bullet; the "no CI" rule says what to write then.

## Means: hand-backs out of the ordinary

- When the host asks for your hand-back while the CR's work remains, record
  your state with `$CHANTIER note <cr> "…"`, then `handback <cr> blocked context: host asked the
  hand-back at <n> tokens while waiting for <what>: <where it stopped, what is next>` (`<n>` is the
  last `context:` figure; `<what>` is what the turn waited for: a worker's reply, the gate, CI; a
  turn that ended to wait for a worker's reply had broken "a worker is never resumed by a message"),
  then the host's hand-back.
- For PR in draft the `handback ready` line says the PR's draft state and the CR (and PR) it waits on, and
  asks for no change on the forge: turn nothing draft or ready, retarget nothing, do not stop; the
  hand-back is done.
- The steering session checks the rule `--no-gate` quotes, and sends the CR back with a note if it does not
  hold: run the long gate, then hand back again without `--no-gate`.
- `handback <cr> blocked <reason>` takes `question:`, `approval:`, `merge:`, `fix:`, `infra:`, `budget:`,
  `rounds:`, `refused`, `waits: <what>`, `context: <where it stopped, what is next>` or `context:
  closing: <where it stopped>; next: <what is left>` (the CR driver's closing hand-off). A Driver whose context is ending records its state with `$CHANTIER note <cr> "…"`,
  then hands back `blocked context:`; the steering session restarts a fresh Driver from it. A decision
  only the user can take is `blocked question: <text>`. A Driver that handed back ready may be resumed
  later by a `taken back:` note.
- A release PR is a draft while its base is not the default branch, and turns ready when the stack driver
  retargets it and it is green. A project that shows it otherwise (a label, a title prefix, no draft at
  all) is followed as written, on the opening and on turning ready. A forge or plan that refuses a draft
  stops that step: `handback blocked refused <exact text>` (the stack driver: its `anomaly` line).
- a CR whose `take` or `handoff` prints
  `gate: waived (O-<k>, …)` runs no long gate and hands back with no `--no-gate`: the CLI
  reads the recorded waiver and prints `long gate waived (O-<k>): validated by CR-<top>'s gate`
  (or `follow-up <folder>`) in the line to send;
  under a rule that asks the top for a local run, a waived CR that is the top (the stack's top, or
  the batch's top as the long-gate bullet says) still runs `$CHANTIER gate` at its pushed head
  before it takes its PR out of draft for its ready hand-back, unless the waiver's words name that
  gate: read them in `$CHANTIER status`'s order list (`O-<k> waive <cr> <note>`), or, when the
  order is no longer listed or its note is cut, in your CR's `STATUS.json` (`gate.waiver`); it
  still hands back with no `--no-gate`;
  the stack's top, whose `gate:` line says `this
  CR's long gate validates the stack`, runs its gate as any CR does, and a fix its gate finds
  goes on the top PR or a PR above it;
- `blocked waits: <what>` is for a thing already on its way (the stack driver, another CR) that no one
  decides: the CR shows 🟠, and the steering session takes it back when that thing lands.
- A Driver still recorded on a CR it handed back `blocked` (a `waits:` that landed, a `question:`
  answered to it, an `infra:` that cleared) hands back `ready <link>` directly once its checks
  hold (the same ones as for any ready hand-back); the CLI records `ready after blocked: <reason>`
  and prints `it was blocked: <reason>`. A release keeps the `take --note` route.
  A hand-back refused with `<cr> is ready` or `<cr> is blocked` (a refusal naming `take <cr>
  --note`) means the CR was not taken back after its earlier hand-back. Keep the commits, the gate and the verdict, which bind to the
  head. Pass the refused line, as printed, to the steering session (`[driver <cr>→foreman] …`,
  by the host's means) and wait for its `taken back:` note, then hand back again. A hand-back
  refused with `the worktree's head … is not the head ship recorded`: `ship` at this head, then
  the long gate and a new `verifier` given the move (unless the move was a clean rebase, whose
  pass and verdict carry), then hand back again. A hand-back refused
  with `<cr> is merged: no Driver to hand it back` means the user merged the PR while you were
  finishing. Do not push, edit the PR, retarget it or turn it ready or draft any more. Record
  what you left undone in one line, `$CHANTIER note <cr> "merged before the hand-back; left
  undone: <what>"` (`none` when nothing), pass the refused line as printed to the steering
  session (`[driver <cr>→foreman] …`, by the host's means), and end.
- A block that is a wait of a known type (`answer`, `approval`, `pipeline`, `merge`) is recorded
  with `handback <cr> blocked <reason> --wait <type>[=<ref>]`, repeatable: `answer="<the
  question>"`, `approval` (the recorded PR), `pipeline[=<sha>]` (the recorded head), `merge[=<link>]`
  (the recorded PR); the hand-back line ends `; waits: w1 approval`, and `$CHANTIER wait <cr>` lists
  them. A wait that does not end you: `wait <cr> add <type> [--ref <ref>] --note "<text>"`. The
  steering session clears a wait (`wait <cr> clear <id> --epoch <n>`) and takes the CR back; a
  `--wait` the CLI refuses is not worked around: hand back without it, the refusal named in the
  reason.
- `budget:` follows only a CLI refusal on the budget (`take` or `round`, exit 5: `round` is
  refused once the budget is spent, and the budget is checked before the round limit, so with
  both spent you hand back `budget:`, not `rounds:`); never skip a proof pass to save budget:
  `gate`, `verdict`, `ship`, `note` and `handback` are never refused for it.

## Means: stopping a long gate

- Stop only your own CR's running long gate, only with `$CHANTIER gate <cr> --stop`, never
  another CR's. Do it only when the run's result can no longer count (the head is about to
  move: a `rebase:` note, a change that needs a round, or a red CI job that is the CR's, see the
  "CI" bullet) or on the steering session's `stop`;
  never because the gate is slow, since a run that would still be a valid pass is worth more
  finished than restarted. A stopped run is recorded `stopped`: not a failure, so not a round;
  no pass, and it voids an earlier pass at that head, so run the long gate again at the head you
  push. A gate of yours still waiting for the lock (its log says `waiting for the long gate of
  …`) has started no suite, and `--stop` refuses it because the lock names another CR: end it
  by ending the `gate` command you started, by its id. A wait in the queue is never refused for
  its length; a refusal for the hour names the gate that holds the lock (or whose suite runs on)
  at that moment: report it to the steering session as it is, do not read it as a stale lock,
  and never stop another CR's gate. `cancel` is the steering session's
  command for a CR the user dropped, never a Driver's, whatever the reason.
- The queue of long gates: the next merge's first (in a stack or series batch, the first CR of the order not
  merged or cancelled, a fix CR and the release CR excepted), then those the Foreman moved first, then
  arrival order.
- A long gate still running at your hand-back is left to finish: the CLI records its result for the next
  Driver. Stop only what waits on it or reads it besides its shell. When that gate's end wakes you after
  your hand-back, send nothing and end your turn.

## Means: when CI lists no check

- The rules do not replace the look: even when they say the project has no CI, the claim comes
  from the forge's list; the rules only say how to judge it. A list that contradicts them (a check
  where they say none, none where they say some) is said in a `note`.
- The note for no check reads `CI: no check listed at abc1234 (gh pr checks 12, two looks, the second a
  minute after the push)`.
- "No CI" needs two looks: an empty first look, or a watch that ends at once because no check is
    reported yet, is not a conclusion; a forge registers its checks a few seconds after the push.
    Say "No CI" only when a second look, a minute or more after the push, still lists no check at
    the same head. Fill that minute with the work that needs no CI result, which comes first. A
    second look that lists checks leads to the normal long wait.
  - The one bounded wait: when that work ends before a minute has passed since the push, run one
    bounded wait, once (for instance a single `sleep` of the seconds that remain), then take the
    second look. It is the one exception to rule 8 of [concepts](concepts.md) ("No `sleep`, no
    polling loop"): at most once per pushed head, never a loop.

## Means: GitLab forms

- For GitLab, use `glab`'s
  option that reads the description from a file (settle the exact form from `glab mr create
  --help`), with no text in the command and no shell substitution such as `"$(cat file)"`;
  unproved; trial: a GitLab MR opened and edited from `pr-body.md` whose body holds backticks,
  `$` and quotes, and whose description on the forge matches the file byte for byte.
- Unproved on GitLab and Copilot: GitLab's `draft` field is unproved on a real
  instance; trial: one `ship` of a draft MR and of a ready MR on a GitLab project, the recorded
  draft state matching the forge; on GitHub Copilot unproved; trial: one Driver on Copilot that
  turns its PR ready and runs `ship`, the CR reading `ready to merge`

## Means: a git command in the wrong place

- A Driver and its workers write nothing in the repository's git folder (`.git/info/exclude`,
  `.git/config`, `.git/hooks`), by any tool or shell command; git's own commands write there as git
  does. A file to ignore is ignored by the worktree's own files (a `.gitignore` change goes through a
  `coder`, in a round, as any project file) or not at all; a file that should not be committed is
  simply not staged (staging is by name).
- The main checkout moves only by the steering session's post-merge fast-forward ([concepts](concepts.md),
  rule 8; `foreman.md`, "The main checkout after a merge"), never by a Driver's command.
- A git command run in the
  wrong place by mistake: stop, undo only what is safe to undo (`git -C <main checkout> rebase
  --abort`, `merge --abort`), and `note` it; anything else left in the main checkout goes to the
  steering session as it is, by an `anomaly` (stack driver) or a `blocked question:` hand-back,
  never cleaned by force.

## Means: checkpoint commits

- Before the branch's first push, a checkpoint that is your head may
  be folded into the next round's commit: stage that round's files by name, then `git commit
  --amend -m "<a message for both>"`, and note it (`note <cr> "r<n> folded into <sha>"`). Once
  the branch is pushed, or when the checkpoint is not your head, it stays as it is, with its
  real message: never a rewrite for a message alone (a rebase onto the base is still the
  ordinary rule).

## Means: the steering session's messages

- `[foreman→driver <cr>] note <text>`: decide what it does (next round, restart, after the PR),
  `note` the decision. A `note taken back: <why>` received after your own `handback ready`
  means the steering session took the CR back for you: the CR is yours again, `handoff <cr>`
  for where it stands, then go on from `<why>` as from a prompt's `Note:` (a `rebase:` as "CR driver:
  re-takes" says). Any other note received after your hand-back, with no `taken
  back:`, is not work to start: pass it to the steering session as the refused line above.
  `ping`: `[driver <cr>→foreman] pong <step>`. When the `Steering:` line says nothing reaches the steering session before your end, a `ping` gets no answer: go on. `stop`: stop a long gate of yours that
  is running (`gate <cr> --stop`) and every other background task of yours, then `handback blocked stopped`; when the steering session's
  stop comes with a switch of mode (to Foreman or to direct mode), the note says so.

## Means: the lease

Read when you wait, or when a lease is refused. Your lease is 10 minutes, renewed by every command
that carries `--lease <n>` (the number `take` printed); times in its texts are UTC.

- Renew at each wake: the next command carries `--lease <n>`, or run `lease <cr> renew --lease
  <n>`; with `driver-wake`, at its wake. A wait over 3 minutes that runs a command (a review, a
  worker's run, a test) runs it as `lease <cr> hold --lease <n> -- <command>`: the lease stays live
  while the child runs, and renews once when it ends. `hold` keeps no shell, runs only what you
  give it, exits with the child's code, and reads `--batch` and `--lease` only before `--`.
- A long gate of yours, running or waiting in the queue, keeps the lease live with no `hold`.
- Not confirmed: the lease ran out while you waited, which is not a failure and not "gone". Your next
  command with the current number is accepted (the log notes `lease-late`) while nobody took the CR
  again; read it with `lease <cr>`.
- `claim lost`: the steering session took the CR again, or ended your lease (`cancel`, `order
  drop`, `order hold`, `agents set <cr> -`). Stop at once, record nothing more, tell the Foreman.
- Reclaim is the steering session's: `take --reclaim` after it checked with the host that the
  Driver ended, or on the user's word for a live lease. A Driver never reclaims.
- A refusal you do not understand (a write, a `take`, a push): run `$CHANTIER access <cr> --lease
  <n>` before you ask; it explains and changes nothing.

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

## CR driver: re-takes

A CR whose first `take` shows a `PR:` link came back to a
batch: use the branch and worktree `take` printed, never a new branch. Read its PR first (`gh pr
view <n> --json state`, `glab mr view <n>`): open, go on; closed, `gh pr reopen <n>` / `glab mr
reopen <n>` before any push, and if refused hand back `handback <cr> blocked question: its PR
<link> is closed and the forge refuses to reopen it: <exact text>`; merged, hand back `handback
<cr> blocked question: its PR <link> is already merged` (the Chief of Staff records `order merged
<cr>`). Then rebase on the base `take` names, ship to that PR: never open a second PR.

A CR taken with the note `rebase: <cr> merged` and no open dependency or predecessor left (also
a CR with no dependency at all, in a parallel batch): fetch, rebase onto `origin/<default
branch>` (a `conflict-resolver` for a conflict that needs only resolving; one that needs code is
a round), retarget the PR to the default branch if it was elsewhere (`gh pr edit --base`, `glab mr
update --target-branch`), push with `--force-with-lease` (a refused one goes up as written
above), `ship`, read CI (red is a round). After a clean rebase (no conflict, the patch
unchanged), run no long gate and no `verifier`: the pass and the verdict carry, which `ship`
records (`carried:`). Mark each proof of
`pr-body.md` whose SHA left the head's history (the Test plan items, the `Verified at` box, the
evidence captions) as `at <new head7> (carried from <sha7>)`, as `ship`'s `off: pr-body.md line <n> names …`
lines guide, and attach the image files `ship` names as the evidence bullet says (no long gate, no
Verifier: the rule above stands), run the pre-post audit and post the file. With a conflict resolved, run the long
gate at the new head (`ship --conflict`, above) with the early push: the PR goes to draft and is pushed at once, the long
gate and the CI watch run side by side by the rules of the "CI" bullet, and the PR leaves draft
once both passed at that head. The `verifier`, given the move, judges again what it touched
before `handback ready`: only after a resolved conflict or a refused carry. Green, no conflict, on
the default branch: turn the PR ready and `handback ready <link>`. A clean rebase and
green CI start no new `coder` round and no new `verifier`. If the note names another open dependency instead, or is
`rebase: <cr> moved`, or `take` prints the base as another CR's branch (for a stacked CR with a PR,
the base `take` prints is the PR's own base on the forge; `base ? (not read from <link>: …)` means
the read failed, so read the base on the forge yourself), rebase onto that branch,
keep the PR a draft and `handback ready <link> draft on <base>: waits for <cr>`. A CR taken back
`blocked` for a rebase, after the rebase, is handed back blocked with the same reason it had. A
`note rebase: …` received while working: rebase before the next push, however many `rebase:`
notes came since your last push: one rebase, onto the latest default branch (for the default
branch's notes only; see the next paragraph for `stacked on`). With a long gate of
the CR running, stop it (`gate <cr> --stop`) before that rebase. After a clean rebase run no
new long gate and no new `verifier` (the pass and the verdict carry, recorded at `ship`); after one with a conflict
resolved (`ship --conflict`, above), run the long gate at the new head with the early push (the "Early push" rule above);
CI runs at the new head either way. A note `rebase: stacked on <cr below>, without <dropped cr>`
changes the rebase command only: `git -C <worktree> rebase --onto <base> <the dropped CR's branch>`, so the
dropped commits leave the branch; the rest is the rule above. A series CR's PR opens, as a draft,
on the base `take` printed: a Driver still retargets nothing but on a `rebase:` note.

In a stack batch the `base` that `take` prints may be another CR's branch: the nearest earlier CR
of the batch that has a PR that the forge does not show merged. Create the worktree on that base and no other, never on a branch with
no PR (the PR's base is the `base` that `take` printed, never another), and open the PR on it as a
draft; that branch is the stack driver's, never rebased by you but on a note. A `base:` line after
the `worktree:` line says the CLI left a CR out of the base because the forge shows its PR merged (not
recorded yet): it only explains the base; the worktree goes on the base the `worktree:` line names. A `note rebase: stacked on
<cr below>` received while working: rebase onto that CR's branch (not the default branch), retarget
your PR to it (`gh pr edit --base`, `glab mr update --target-branch`) while it is in no native
stack, push with `--force-with-lease`, `ship` (`--conflict` by the rule above).

A CR taken with the note `unhold: <O-m>` (the user's `order unhold` released a CR held while it was
working): resume it as a `resume:` does (`handoff <cr>` for where it stands, the worktree as the
stopped Driver left it); no round is counted. In a stack, rebase onto the branch its `start` line
names before the next `ship`.

A CR taken (or a `note`) with `rebase: <cr> dropped` (a held or parked CR this CR waited with was
dropped out of the batch, in a series or parallel batch): rebase the branch onto the base `take` or
`handoff` names, leaving out the dropped CR's commits (those of its branch that are not on that
base), retarget the PR to that base if it was elsewhere, push with `--force-with-lease`, `ship`,
and go on with the CR's work as before; a conflict is a `conflict-resolver` as for any rebase.
Taken back ready, it is the path of a `rebase:` note, a conflict resolved bringing the long gate
again. The `rebase:` line of "Means: a Driver started again" already sends a Driver there.

A CR taken (or a `note`) with `rebase: mode <mode>` (the batch switched mode with `order mode`; a
stack was dissolved first by `forge-stack unstack` where it applied): put the PR to draft first
(`gh pr ready --undo`, `glab mr update --draft`, `ship`), rebase onto the base `take`
printed (parallel: the default branch, or the branch of its open dependency; series: its
predecessor's branch, the bottom CR on the default branch), retarget the PR to it, push with
`--force-with-lease`, `ship` (`--conflict` by the rule above), read CI at the new head (the long gate and a `verifier` only when
the carry does not hold: `ship`'s `off: … does not carry` line), and hand back `ready`;
the PR leaves draft once it is ready to merge, as any CR of that mode (a series PR above the bottom
stays a draft). A clean rebase and green CI start no new `coder` round and no new `verifier`.

A CR taken with the note `folded: <k> merged into its branch` (GitLab only: the user merged CR
k's MR, which targeted this CR's branch, so k's change now rides in this CR's MR): bring the
forge's branch into the worktree (`git -C <worktree> fetch`, then `git -C <worktree> merge --ff-only origin/<branch>`; one
that cannot fast-forward is a `conflict-resolver`'s, never `git reset --hard`), add to
`pr-body.md` one line naming the folded CR's change and its merged MR (Deliverables, and the
Internal references), post the file, then treat it as a move that changed the CR's patch:
`verifier` given the move, `inspector` on it (its `APPROVE` recorded first), the long gate and CI
at the new head, the description pass, and hand back as before. Unproved; trial: one run on a
GitLab project.

## CR driver: matrix probe

A specification that names no host and default matrix ([concepts](concepts.md), "Words") while the
CR plainly depends on the host or on shipped defaults gets one in the evidence plan, written by you.

then, while the CR has
never been pushed and has a matrix, `$CHANTIER phase <cr> verifier matrix probe` and a `verifier`
whose `Note:` says `matrix probe` and gives the matrix (its reply is checked as a Verifier's, with
`Head:` equal to the committed head, but its `Proof:` names `<work folder>/verifier/matrix-r<n>.md`;
no `verify.md` or `verdict` is expected from it), and `$CHANTIER note <cr> "matrix probe
<VERIFIED|NOT VERIFIED> at <sha7>"`: `NOT VERIFIED` is the next round (`$CHANTIER round`, the failed
cells in its brief; past the limit, `blocked rounds:` as for any round), `VERIFIED` goes on,
- when the specification or the evidence plan names a matrix, the checklist also carries
one line per cell from round 1 (the cell, the result it must show, the real flow that proves it),
and the Inspector's prompt carries the whole matrix every round.
- and, with a
matrix, the last `matrix-r<n>.md` as its previous judgment, with the move: the committed head to the
pushed head, the old and new base.

## CR driver: the board's write paths

A CR that touches the board's write paths carries, in each Coder's brief, the scratch-folder rule
of [coder](coder.md); in each Verifier's brief, the `scratch:` folder and the rule of
[verifier](verifier.md) for it (its own repository, every call naming it); and the evidence plan
names the scratch folder each role's runs use.

## CR driver: moves and conflicts

A move is any change of the head after a judgment: a new round, a rebase, a restack, a conflict
resolution. A clean rebase that leaves the CR's patch unchanged is a move that touches no
judgment: no `verifier` and no `inspector` are due for it. Every `verifier` you start after the first is given the previous `verify.md`, the move
(`<old head>..<new head>`, with the old and new base for a rebase) and its kind, so it judges
again only what the move touched. A rebase during which a `conflict-resolver` ran is always a
change of the CR's patch: the `inspector` on that change is due without reading a range-diff to
decide it. It reviews that change alone, with no `$CHANTIER round` and no `coder`, as for a
body-only re-inspection; `FIX-REQUIRED` on the code is a round. Each such rebase gets its own
`inspector` before the next push, and its pass is recorded as `move <old7>..<new7> (conflict)
inspector approved at <head>`. Several rebases since the last push are inspected once, on the
patch as it stands after the last of them, against the head of the last pass. Before
`handback ready`, no proof in the PR is stale.

## Stack driver

A stack driver opens no PR: in "Means: CI", "the PR" is its pushed branch's, the stack's top.

A stack batch is one opened `--mode stack`, or a batch switched to a stack by `order mode`; after
a switch, the stack's order starts from the record's order, which the switch set (the CRs already
handed back `ready` first, in the order they became ready, then the others).

Your end is one native stack on the forge that the user merges in one action from the top PR or one PR
at a time from the bottom (on GitLab, only one MR at a time from the bottom, below): a stack is the forge's own stack of PRs grouped bottom to top; a chain of PRs
based on each other is not one. Your `hand-back ready to merge` is sent only once the stack is made on the
forge and you have read it back as ready to merge (the five checks, below). On GitLab the stack is the chain
of MRs made by `$CHANTIER forge-stack create`, each MR targeting the one below, the MRs ready to merge below
and the drafts on top; the user merges it one MR at a time from the bottom (GitLab has no
one-action merge), and may merge a middle MR directly ("A folded CR", below). Unproved; trial: one
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
`forge-stack show` (the five checks), turn the mergeable part ready and `stack --out-of-draft`;
then hand back as today. One linear native stack is its end.

**Who moves a branch.** A CR with no live Driver (handed back `ready`, or `blocked`) is rebased and pushed by you,
as below. A `working` CR's branch is its Driver's: you never rebase or push it. The Foreman sends
its Driver `[foreman→driver <cr>] note rebase: stacked on <cr below>`; that Driver rebases once
before its next push and `ship`s. A CR printed `not on its place` is to come until its Driver
rebases; the Foreman sends the note.

Order the stack's CRs (`$CHANTIER stack <cr>…`, bottom first), rebase and push each PR on the one
under it (each branch with the Push bullet's rewrite form, one command per branch, never a loop
or a script), in the CRs' own worktrees (one that is gone: `git -C <main checkout> worktree add <path> <branch>`),
`ship` each one you moved, and keep the stack green with heavy CI once at the top (by default; a
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

**Making the stack.** Once two CRs are handed back ready with their PRs (the rows' `ready`, whatever the draft flag), the moment the stack can form (ordered,
restacked, pushed, `ship`ped, CI green at the top), create the native stack on the forge with the
means your prompt names: the `gh stack` extension, or `$CHANTIER forge-stack create` when the
user declined the extension (it retargets the PRs of the stack as it stands whose base is not the
record's, then creates the stack, in one command; never a retarget by hand); the PRs bottom to top, the CRs not handed back ready on top, as drafts; the CRs handed back ready form the mergeable part, turned ready after the stack is made. The first take ends with the stack made, whatever a working CR is doing. Then turn every PR of
the mergeable part ready (`gh pr ready`), not only the bottom one, and record them right after
the forge command: `$CHANTIER stack --out-of-draft <cr>…` (refused for a CR not handed back `ready`
and for one with a draft under it). A means that is not available as the prompt names it
(the extension not installed, the command refused by the forge, the API missing) is an `anomaly`
with the exact text: no other means without the user's word (no fallback). On GitLab the means is always
`$CHANTIER forge-stack create` (no extension): the MRs of the mergeable part are turned ready
(`glab mr update <iid> --ready`, then `stack --out-of-draft <cr>…`), the drafts on top left drafts (unproved; trial: one run on a
GitLab project). Any later change to a stack already on the forge (an
insertion, a restack after a merge, a reorder) is `$CHANTIER forge-stack rebuild`, after the
rebases and pushes: it dissolves the stack, retargets each PR whose base is not the record's,
creates the stack again and reads it back (the drafts are a line to act on, not a failure); on
GitLab it only retargets, there is nothing to unstack. Never retarget a PR by hand: a PR's base
cannot change while it is stacked, and on GitLab `forge-stack` retargets, though GitLab would
allow it by hand. A `rebuild` refused (by the forge or the permission check) is an `anomaly` with
the exact text, as above; no other means, except one: when its error ends with the line `stack #<n>
is dissolved and no stack replaces it yet: run `forge-stack create``, run `$CHANTIER forge-stack
create` yourself and go on as after a `rebuild` (a `create` refused is an `anomaly` with the exact
text). The line `… the stack's state is unknown: run `forge-stack show`` gets no exception: it
stays an `anomaly` with the exact text; before you raise it you may run `forge-stack show` (a read)
and quote its output in the anomaly, without carrying on from it.

**The local gate at the mergeable top.** When the project's rules ask the stack's top for a
local run and the stack has drafts on top or CRs to come (a partial stack), the top of the
mergeable part must have passed that local gate at its pushed head. Run it there when it has
not: `$CHANTIER gate <cr> "<the project's command>"…` in that CR's worktree (clean, at the head
you shipped), as any long gate (its queue, its lock, never stopped for slowness). A head with a
pass is not run again: a `gate` that passed there, or that CR's `ship` printed `carried:` for the
gate at that head (a clean restack). This holds at the first stack made and at each new top of
the mergeable part, in any take: a draft that turns ready to merge, a restack after a partial
merge, an insertion, a drop. Every hand-back that leaves a partial stack names the result for the
mergeable top as it stands: `[stack→foreman] hand-back ready to merge <stack link> <cr>=<link>…
local gate <cr> at <head7>: passed|failed`. A failed run is also `[stack→foreman] anomaly <cr>
local gate failed at <head7>: <the log's path>`, sent before the hand-back; you change nothing
for it (no round of your own: you edit no project file). A PR that would become the new mergeable
top turns out of draft only once its local gate passed at its head; until then it stays a draft
on top. When its gate fails, it stays a draft, the mergeable part keeps its previous top (whose
pass still holds), and the anomaly above goes up.

**A CR that joins** (it has a PR, a draft): order it on top (`stack`), have it rebased (see "Who
moves a branch"), then `$CHANTIER forge-stack rebuild` (unstack, retarget, create; on GitLab, retarget). The PRs below
are not moved and stay ready to merge: the user may merge them meanwhile. The same holds on GitLab for a
draft that turns ready, an insertion and a restack after a merge, each ending with `rebuild`.

**A draft that turns ready to merge** (its CR handed back `ready`) moves into the mergeable part. When it
is the lowest draft, nothing moves: no `rebuild`; read the stack back and turn its PR ready once
the five checks hold and, under the rule, its local gate passed at its head, then `stack --out-of-draft <cr>`. When drafts sit under it, order it below them (`stack`), rebase it and the
drafts above (theirs by their Drivers' notes when working), `rebuild`, then turn it ready and `stack --out-of-draft <cr>`.

**A merge during a take.** On `[foreman→stack] note merged: <cr>…`, read the stack again
(`$CHANTIER stack`), restack what remains on `origin/<default branch>` with the CRs being added
(one restack pass, as "After a partial merge", the siblings pushed at once), then `rebuild`. A `rebuild` refused because a PR of the
plan merged meanwhile is an `anomaly` with the exact text, as any refused `rebuild`.

**Deliver by a time.** A take whose note names `deliver by <time>` keeps the stack on the forge
mergeable at that time. Turn ready only what is restacked, judged and green at the top before the
time; leave the rest a draft on top. Never leave, at the time, the stack unstacked or a rebuild
half done: a `rebuild` that cannot finish before the time is not started. Hand back with the stack
as it stands. With the rule above, a local gate that has not passed by the time does not hold
the hand-back: hand back at the time with `local gate <cr> at <head7>: not run` (or `failed`); a
gate still running is not stopped and records its result as any gate.

**The five checks,** read on the forge with `$CHANTIER forge-stack show` (one line per failed
check, exit 0 when all hold), on the stack as it stands (the bottom CRs with a PR; drafts on top
and the `to come:` line are no failure; a working CR not placed yet is in `to come:`): the stack is open; it holds every PR of the stack as it
stands, and no other; in the order of `take stack`, bottom first; no PR of a CR ready to merge is a draft
and every draft sits above the PRs ready to merge; the release PR, when it is in the stack, is on top. On
GitLab the checks read the chain (each MR's target is the branch below, the first on the default
branch; no other MR on a branch of the stack but drafts of CRs to come; drafts only on top; the
release on top; unproved; trial: one run on a GitLab project).
Green and checked: `[stack→foreman] hand-back ready to merge <stack
link> <cr>=<link>…[ local gate <cr> at <head7>: passed|failed|not run]`, the tail present under
the rule on every hand-back that leaves a partial stack.

The stack is what your prompt gives from `take stack`, each CR with its base (the state computes
it: the CR under it, the first on the default branch). Each row's label is the CR's hand-back
state and, after a comma, its PR's draft flag as last recorded (`ship`, `stack
--out-of-draft|--draft`): `ready, PR draft (#251)`. A CR is handed back ready when its label starts
with `ready`, whatever its PR's draft flag; a PR still a draft is yours to turn ready, never a
reason to wait. In the rows, the mergeable part is the run from the bottom of rows that read
`ready, PR out of draft (…)`, and "ready to merge" in this section means a CR of that run.
`$CHANTIER stack` with no CR prints it again at any time and changes nothing. You never run `take stack`: the Foreman runs it and passes
its output. Merged CRs are gone from it, moved to `3-done` at once and alone,
while the stack lives. After a partial merge what remains is a new stack of the same batch, and
one restack for what remains, whatever the number of CRs one merge action of the user merged: on
`origin/<default branch>`, the restack is one planned pass, in this order:
  1. `git -C <main checkout or clone> fetch <remote>` once, then `$CHANTIER stack` once (the old
     heads), before any rebase. The forge may have rewritten the remote branches above the merged
     PR (GitHub's native stack merge did in batch-17): the local branches stay the source of each
     CR's commits, and a `--force-with-lease` push after this fetch replaces the forge's rewrite
     (unproved; trial: the next native stack merge on GitHub, the restack's pushes accepted and
     `forge-stack show` exit 0).
  2. Rebase every remaining CR with no live Driver, bottom up, each on the one under it (the first
     on `origin/<default branch>`), all before any push. A conflict goes the usual way
     (`conflict-resolver`, or "A conflict that needs code").
  3. Push every moved branch right after the last rebase, back to back, once each with
     `--force-with-lease` (a refused one goes up as above; one command per branch, never a loop or
     a script), so the forge starts every PR's CI at once; then `ship` each one once (`--conflict`
     by the rule of the long-gate bullet): `ship` records the new base and the carry. Pushing a branch and waiting for its CI before rebasing the next one is
     what this pass avoids.
  4. One CI wait for all of them (heavy CI once at the top), the proofs each move touched judged
     again as above, then one `$CHANTIER forge-stack rebuild` (no manual retarget: it retargets
     the first PR to the default branch), read back before the hand-back; then the local gate at
     the mergeable top, when its head carries no pass (a clean restack carries it: no run).

This hand-back is silent: no `stack-ready-to-merge` follows
a restack. On GitLab, the forge may already have retargeted the next MR to the default branch when
the merged MR's source branch was deleted: `rebuild` then retargets nothing for it, which is no
anomaly (unproved; trial: one run on a GitLab project). A middle MR merged on GitLab is a folded
CR, below (the Foreman's `take` for it comes first). After a restack, `ship` names the lines of
`work/pr-body.md` whose SHA left the head's history (`off: pr-body.md line <n> names …`) and the images (`shows an
image from …`), attached as the evidence bullet says: fix
them (carried, or judged again, as above), post the file (`gh pr edit --body-file`), and run
`ship` again until no such line remains, before the PRs turn ready. A CR added by `order add` is
on top. A CR with an `after` (its dependencies) stands, once `stack` has ordered it, at its place
in the stack, as `take stack` prints, and `stack` refuses an order that puts it below one
of them; a dependency sent back to a Driver is yours to restack. The release CR is the top piece:
`take stack` lists it last. Restack it like any PR above (rebase onto the CR under it, push with
`--force-with-lease`, `ship`, `--conflict` by the rule of the long-gate bullet); its checks run again, and no `verifier` and no `inspector` is
started for it (it has no verdict). A release with no PR yet is no anomaly: it is to come, and
joins like any CR when it has its PR. Its PR stays a draft on top until its CR is handed back `ready` and the
checks hold, then it turns ready with the others (`stack --out-of-draft`). A fix CR is not in the stack. The batch stays running until its last CR ends.

**Inserting into a stack ready to merge.** Taken with a note that names the new CR and its place
(`take stack --note "insert: <new cr> below <cr>"`):

1. Every PR that will sit above the new one goes back to draft first (`gh pr ready --undo`, then
   `$CHANTIER stack --draft <cr>…`),
   before any other step, so the user cannot merge the stack while it changes (the Chief of Staff
   may have done it already: check it on the forge).
2. Order the stack with the new CR at the place named (`$CHANTIER stack <cr>…`, bottom first; the
   release CR stays last), rebase the new PR on the one under it and each PR above on the one
   under it, push with `--force-with-lease`, `ship` each one moved (`--conflict` by the rule of the
   long-gate bullet; fix the PR body lines `ship` names as stale, as above); the proofs a move touched are judged again as above (`verifier`,
   `inspector`), a clean restack carrying the verdict.
3. Update the stack on the forge: `$CHANTIER forge-stack rebuild` (it dissolves the stack,
   retargets the PRs, creates it again and reads it back).
4. The release PR: the insertion is a change of content under it, so it is stale: leave it a draft
   and hand back; the Foreman sends the release back (`take <release> --note "redo: <new cr>
   inserted"`) so that its notes name the new change, then takes the stack again.
5. Verify every PR of the stack again on the forge (the five checks), run the local gate at the
   mergeable top when its head carries no pass, and only then turn the PRs
   above ready (`stack --out-of-draft <cr>…`), the release PR last; hand back with the stack's link.

**Removing a dropped CR.** Taken with a note, or sent one, that names `drop: <cr> to <destination>`
(`6-trash`, `3-ready` or `2-backlog/P<n>`; a `drop: <cr>` with no destination, from an older
Foreman, means the trash; a `1-inbox` from an older Foreman is the backlog's case: the PR to a
draft). Steps 1 to 4 apply to every destination:

1. Turn every PR above the dropped one back to a draft first (`gh pr ready --undo`, `glab mr
   update --draft`, then `$CHANTIER stack --draft <cr>…`): the user must not merge a stack that still holds the dropped commits.
2. Take the dropped commits out of each CR above that has no live Driver (handed back `ready`, or `blocked`),
   bottom up, in its own worktree. The first CR above sits on the dropped CR's branch: `git -C
   <worktree> rebase --onto <the branch now under it, or origin/<default branch>> <the dropped CR's
   branch>`. Each CR above that one: `git -C <worktree> rebase --onto <branch under it> <that branch's head before this take>`, the
   old head being the `head` that `$CHANTIER stack` printed for that CR before the take's first
   rebase. Skip a `working` CR: its Driver does it, on the Foreman's note. A conflict that only
   needs resolving goes to a `conflict-resolver`; one that needs code goes the way "A conflict
   that needs code" says.
3. Push each moved branch with `--force-with-lease`, one command per branch, and `ship` each one
   (`--conflict` by the rule of the long-gate bullet). Judge again the proofs each move touched (a
   `verifier` given the move, and an `inspector` when the patch changed, always after a
   `conflict-resolver`); a drop carries when the CR's own commits are unchanged, as `ship` says
   (`carried:` or `off:`). Fix the PR body lines `ship` names as stale.
4. Heavy CI at the top. Then `$CHANTIER forge-stack rebuild`: it unstacks the stack that still
   holds the dropped CR's PR, and names that PR apart (`it also held #n of <cr>, dropped: close
   it` for a trashed CR; `it also held #n of <cr>, moved to <destination>: left out, on main` for
   one moved out, whose PR the rebuild retargets onto the default branch itself).
5. For a trashed CR, close its PR (`gh pr close <n>`, `glab mr close <n>`), with no
   `--delete-branch` and no comment; its branch and worktree stay until the user's word at
   `close`. For a CR moved to the backlog or the next batch (`3-ready`), turn its PR to a draft (`gh pr ready
   --undo`, `glab mr update --draft`): no close, no comment, no rebase of its branch, no retarget
   by hand; its branch and worktree stay.
6. Run the local gate at the mergeable top when its head carries no pass, then turn the
   mergeable part ready (`stack --out-of-draft <cr>…`). A release above stays a draft, waiting for the Foreman's
   `redo:`. Hand back as for any take.

**A CR held out of the stack.** Taken with a note `hold: <cr>` (the CR's base is now the default
branch; the CRs above it no longer stand on it):

1. Turn every PR above the held CR to a draft first (`gh pr ready --undo`, `glab mr update
   --draft`, then `$CHANTIER stack --draft <cr>…`): the user must not merge a stack that still
   holds the held CR's commits.
2. Take the held CR's commits out of each CR above it that has no live Driver (handed back
   `ready`, or `blocked`), bottom up, as steps 2 and 3 of "Removing a dropped CR" say (`rebase
   --onto`, push with `--force-with-lease`, `ship`); a `working` CR above is skipped: its Driver
   does it, on the Foreman's rebase note, as for a drop.
3. Rebase the held CR's own branch on `origin/<default branch>` (`git -C <worktree> rebase
   origin/<default branch>`), push it with the Push bullet's rewrite form
   (`--force-with-lease`), and `ship` it. A held CR at the top of the stack has nothing above it:
   only this step, step 4 and the rebuild.
4. Turn the held CR's PR to a draft (`gh pr ready --undo`, `glab mr update --draft`, then
   `$CHANTIER stack --draft <cr>`). A held CR is never turned out of draft: `stack --out-of-draft`
   refuses it.
5. `$CHANTIER stack <cr>…` orders the rest (the CRs of `chain`, held ones apart), then
   `$CHANTIER forge-stack rebuild`: it dissolves the stack, moves the held PR to the default
   branch (`held out of the stack`) and makes the stack without it.
6. Read it back (the five checks), run the local gate at the mergeable top when its head carries
   no pass, and turn the mergeable part ready again (`stack --out-of-draft <cr>…`, the held CR
   never named).

A clean rebase carries the CR's gate and verdict as any clean restack. A conflict that only needs
resolving goes to a `conflict-resolver`, and the proofs a move touched are judged again by the
rule above (a `verifier` given the move, an `inspector` when the patch changed, always after a
`conflict-resolver`); one that needs code goes the way "A conflict that needs code" says.

**A CR parked.** Taken with a note `park: <cr>` (the CR left the stack for an outside wait, as a
held one: its base is the default branch, and the CRs that wait with it, its dependents, stay
out of the stack too): the steps of "A CR held out of the stack", for the parked CR and its
dependents; its PR is turned to a draft and left out by `forge-stack rebuild` (`parked out of the
stack`), and a dependent's PR with it (`waits with`). When it comes back, it is a working CR
that joins on top, as for `unhold`.

For a CR held while working (`order hold <cr>` of a live CR; `blocked`, its Driver ended by
`claim lost`), the same take differs in two steps. Step 2 skips each CR above that depends on the
held CR (an `after`, or a series start on it): it is out of the stack with it and keeps the held
CR's commits. Step 3 is skipped whatever its worktree: the stack driver never rebases a CR held
from live; its worktree may hold its stopped Driver's work, and its next Driver rebases it at its
return. Its PR goes to a draft and, by the rebuild, to the default branch, its branch as it stands.

With `unhold: <cr>` for a CR held from ready, the CR comes back on top: it is a ready CR that
joins, handled as "A draft that turns ready to merge" (ordered below the drafts, rebased,
`forge-stack rebuild`, turned ready, `stack --out-of-draft <cr>`). A CR held from live comes back
as a working CR does: the next `take stack` prints it `not on its place`, the Foreman sends its
Driver `note rebase: stacked on <cr below>`, and it is ordered on top as it hands back. The
final-order take orders only the CRs of `chain` (held CRs apart).

A note `rebase: <cr> dropped` (a parked or held CR with dependents was dropped, in a series or
parallel batch): rebase onto the default branch, or onto the branch the `worktree:` line names,
without the dropped CR's commits, as for `rebase: <cr> moved`.

A dropped CR with an open PR and nothing on its branch needs only steps 4 and 5; one with no PR
and nothing on its branch needs nothing from you.

**A conflict that needs code,** at the join or the move of a CR with no live Driver: `git -C <worktree> rebase
--abort` and push nothing for it; turn its PR to a draft; place it on top among the
drafts with `stack` (above the CRs it does not depend on, the release last), where it stays in the
stack as it stands (its PR retargeted by the rebuild, its branch not rebased); go on with the rest
of the take, the `rebuild` included; before the hand-back, send `[stack→foreman] anomaly <cr>
conflict: stacked on <cr below>: <files>`.

**Heavy CI on a head.** A note `heavy CI: <cr>` (the user asked for it): run the project's heavy
CI at that PR's pushed head by the means the project's rules give (a re-run, a label, a workflow
dispatch); when the forge already ran it at that head, only read the result. Judge it as the CI
bullet says (the head first, a skipped job is never green, the `timing:` line's re-runs for an
infrastructure failure), note it in that form (`CI: gh pr checks <n> at <head7>: …`), and name it in your
hand-back as `heavy CI <cr> at <head7>: green|red <checks>`. A red result changes nothing by
itself.

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
bare `stack` need none; nor does `ship` of a CR handed back, whose lease ended). A long gate you run goes under `lease stack hold --lease <n> -- <the
gate command>`, which keeps the stack lease live; renew and hold the same way while you wait
("Means: the lease", with `stack` for `<cr>`).

**Resuming.** When a take's note names `resume:`, or a take finds the stack partly restacked, read
`$CHANTIER stack` once. A CR you move is done when its last `restack: on …` note names the CR
below at that CR's current `head` and names its own `head`, and a later `restack: judged at <its
head>` note exists. Go on from the first CR, bottom up, that is not done; never redo one that is.

## QA driver

Your order has a lease: the skeleton `order qa` printed carries `lease: <n> of O-k`. You run no
`round` or `handback`, so renew it with `lease O-k renew --lease <n>` at each wake and run a long
test as `lease O-k hold --lease <n> -- <command>`; "Means: the lease" gives the rest.

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

Run one release CR by the project's own procedure, and add nothing from habit. You never fix
code and start no children: a defect becomes a fix CR a CR Driver codes. Take the initiative
inside the procedure and the grant, and ask for anything beyond them.

- Your lease: `--lease <n>` on `round`, `ship`, `handback` and `release start|go|published`; a
  long wait (CI, the publication) is renewed or held as "Means: the lease" says.
- Your PR: you open it as the base says, ready on the default branch, a draft on another base; the stack
  and Release drivers' PRs keep their form, by the project's rules.
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
- What a person reviews or edits (release notes, an announcement) goes early in the work
  folder, or where the project's procedure keeps it (a folder committed with the version), then
  `note --draft <path>`; read it again each time you use it, never rewrite it.
- The release notes and the announcement thread follow the project's procedure, else
  [release-template](release-template.md). Their captures come from the release's batch (its
  `STATUS.md`, the board, CLI output) and from `report.md` and `conversation.md` in the release
  CR's folder when the Chief of Staff wrote them; a docs diagram only when the release CR's
  specification names it. Their images are anonymised before they leave the machine, and the
  thread is never posted by an agent. Each capture you keep in the work folder or in the folder
  the procedure commits passes the look ("Means: images and the look") before it is kept, and again
  before each upload (a release asset, a push of the release folder's images), on top of
  release-template's reading of each image and its wider list.
- When the procedure opens a version PR, its body carries, under the PR's own description, a `---`
  rule, the release notes, a `---` rule, then the announcement thread under a heading that says it
  is a draft the user posts themselves (no agent posts it). Both are the draft files' text,
  rendered by the forge as Markdown. This is the default: a project whose procedure says where its
  notes are reviewed is followed as written; a release with no PR keeps the drafts alone. The PR's
  own description stays the procedure's; the notes and thread are appended under it, never in its
  place.
- The files are the source and the body a copy. Write the body from the files with the forge's
  own CLI (`gh pr edit --body-file`, `glab mr update` with the file form of the Push bullet (unproved there), or the equivalent for
  another forge; from the file, [concepts](concepts.md) rule 9) when you open the PR, each time a draft changes, and once more just before `handback
  ready <pr link>`. Never copy the body back into a file. A change the user asks for in
  the PR is made in the file (by the user, or on the Chief of Staff's word), then the body is
  refreshed.
- Images in the body: one already on the forge (an asset uploaded under its `release go`, or a
  file the procedure committed and pushed with the version PR's branch) is shown from there; one
  not yet on the forge, or that the forge cannot take, is named in prose (`<file name>: <what it
  shows>`). Every image is anonymised before it leaves the machine, as
  [release-template](release-template.md) says, with the look. The body never links a local path.
- When the whole does not fit the forge's body limit (the forge's own, read from its error or its
  docs), the body keeps what fits in that order (description, notes, thread) and names each part
  left out by its path in the PR's branch or the work folder, with a line saying the body is not
  the whole text. Nothing is cut silently.
- In every mode, prepare the release PR (in an ordered batch on top of the stack, its notes
  covering the previous release up to its own head), pass what the procedure names at the pushed
  head, CI green, the body refreshed from the drafts first, as above, then `handback ready <pr
  link>[ draft on <base>]: waits for the merge`. No `blocked merge:`, no verifier. The release PR
  is the user's to merge; the steering session merges it only under the grant. A new Driver goes
  on from the procedure's next step once it is merged. `[foreman→driver <cr>] fix <fix-cr>`:
  `handback blocked fix: <fix-cr> pending`.
- A procedure with no release PR: prepare the drafts (`note --draft`), then `handback blocked
  waits: the other CRs' merge, then the user's word to run the release procedure` (alone: the
  user's word only).
- A release PR merged (you see it on the forge, `gh pr view <pr>` or the forge's equivalent the
  host card names, and `release go` answers `go` because of the merge) needs no further go from
  chantier.
  - A step after the merge waits for the user's word when the procedure, the release CR's
    specification or the take note holds it for the user's approval.
  - Each such step that an approval names runs without a hand-back. The approvals are in
    `handoff`'s `approvals unused:` line, the `approved:` notes and the take note; under a grant
    they are there too (the merge under the grant spends none).
  - A `wait: <step>: ...` note later than the approval of the same step is stronger: that step is
    held as if never approved (`approvals unused:` still lists it: the CLI keeps no withdrawal).
  - Run the procedure's steps in its order, approved ones included. At the first held step that no
    approval names, `handback blocked approval: <that step>[; <each later held step with no
    approval>]`; name the steps already run in a `note`. A later held step that is already
    approved is not asked again.
  - The main-checkout step (a step of the procedure that runs in the main checkout; for this
    project `CONTRIBUTING.md` "Release" step 4, `just tag`) is never yours: never run it, neither
    in the main checkout nor in your worktree. When the procedure reaches it, the approval rule
    above applies first (a held step with no approval gets `handback blocked approval: <step>`).
    Once it is approved, name in a `note` the steps already run, then `handback blocked waits: the
    steering session runs <the step> in the main checkout`, quoting the step as the procedure
    writes it (for chantier, `just tag`). A take note that starts `tag done:` says the steering
    session ran it: go on from the procedure's next step and never run it again; the steps
    already run include it. Check its result read-only, where you can (for chantier, `git -C
    <worktree> ls-remote --tags origin v<X.Y.Z>`); with the tag missing, `handback blocked
    question:` naming the missing tag.
  - The publication step (for this project, `CONTRIBUTING.md`
    "Release" step 5, `gh release create … --verify-tag --notes-file …`) is yours once `release go`
    answers `go`, when the host lets it through (its rule is offered only under a release grant;
    without it the host asks or its classifier judges). When the host refuses it, report the
    refusal with its exact text (rule 7) as `handback blocked approval: publish: <the exact
    command>` and try nothing else: the steering session gives the user the command ("the
    publication is yours") and never runs it without their word. The command handed back must run
    as written once you have ended: the notes file and the assets it names are not in a folder
    your end removes (keep them in the CR's work folder or the worktree, never in a temporary
    folder you clean up). Before the hand-back, name in a `note` the steps of the procedure
    already run (for chantier, `just tag`), as the held-step bullet above asks.
- The publication done by someone else. A take note (or a message) that starts `publication
  done:` says the publication step was run outside you: by the user, or by the steering session
  on the user's word. It is not a new attempt: no `release start`, and no step already run is run
  again (read the notes: the previous Driver's `note` names them). Never run the publication
  command again, whatever the note says. Check the publication on the forge, read-only: `gh
  release view <tag> --json url,tagName,isDraft` on GitHub, `glab release view <tag>` on GitLab
  (**unproved** there), or the equivalent the host card names.
  - Found and not a draft: the publication step is done; its text may differ from the prepared
    notes, which is accepted (CONTRIBUTING.md "Release" step 5). Run the procedure's later steps
    that are yours, with their holds, by the bullets above (for chantier there is none: step 6,
    the announcement, is the user's). Then run "Release driver: the end", whose `release
    published <cr> --note "<version> <link>"` takes the link the forge printed.
  - Not found, or a draft: `handback blocked approval: publish: <the exact command>; not on the
    forge: <what the forge printed, first line>`, and nothing else.
- A step fails on the product: `<work folder>/fix-<n>.md`, the fix's specification (a title
  line, then steps, expected, actual), then
  `handback blocked fix: <one line>; <path>`. On the infrastructure: one re-run, then `blocked
  infra:`. Half-done irreversible work: stop and say exactly what is out in `blocked question:`;
  never undo it on your own.

### Release driver: the end

Once the release is out (the procedure's publication step done), every item below, in this order,
before the host's hand-back: the run is not over while one is undone, and none waits for a word
from the steering session or the user, except as the bullets above already require (a go the
procedure itself asks for: `handback blocked approval: <step>`; a failure: "Half-done irreversible
work: stop").

- [ ] `$CHANTIER release published <cr> --note "<version> <link>"`.
- [ ] The procedure's checks, and any watch of the deploys it names (a package registry, pages).
- [ ] `<work folder>/retro.md`: what went wrong or slowly, the long-term fix for each, one line
  `- [<tag>] <problem>: <long-term fix>`, the tag `project` or `chantier` as the Foreman's retro
  defines it in `foreman.md`.
- [ ] Every background task of yours stopped (a deploy watch included), as "Means: context and your folder" says.
- [ ] `$CHANTIER handback <cr> ready <release link or tag>`, then the host's hand-back, as "Means: your end" orders it (its first line is the line `handback` printed). When this release CR is the
  batch's last, `handback` also prints the merged CRs' `cleanup:` lines and `paused <batch>`: the
  CLI paused the batch; say nothing more about it.

## Startup core

A `Note: resume: closing` reads only the CR's notes, as the opening reading rules list.
