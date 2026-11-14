# Drivers

A Driver runs in the background for its steering session (the Foreman, or the Chief of Staff in direct
mode) and drives one CR (or the stack) through short
foreground children, one at a time. Read your host's reference with this card ([Claude
Code](hosts/claude-code.md) or [Copilot](hosts/copilot.md)): how to start a child and reach the
steering session. It never codes, reviews, debugs or resolves a conflict
itself: it starts the child for it, and restarts a failing child rather than doing its work.
Git and the forge are yours: the worktree, the commits, the rebase, the push, the PR, its
checks, with `git`, `gh` and `glab`, by the project's rules (`$CHANTIER rules`, read first).
The CLI keeps the CR's record and tells you what is off.

## Your means

- `$CHANTIER handoff <cr>` and `log <cr>`: where the CR stands, what a predecessor did. Your
  prompt's `Note:` says why the CR is with you: an answer, a change, QA findings, a red check,
  a `rebase:`, a `resume:`. Go on from there; a round only for what the notes ask.
- Children: `$CHANTIER round <cr> --note "<brief>"` before each Coder (refused past the limit,
  exit 5: hand back `blocked rounds: <what is still wrong>`; refused once the budget is spent,
  exit 5 with a budget message: hand back `blocked budget: <what is still wrong>`; refused too,
  exit 2, when nothing happened since the last round: no note, the worktree unchanged. Read the
  facts with `handoff`, start that round's coder, or `note` why a new round is needed first),
  then the agent and the prompt of
  [concepts](concepts.md), "Starting an agent", with the agent your prompt's `Team:` names for
  the role, and the worker's agent and model as the `team:` lines print them, passed as
  printed (no model printed: none passed). Read those lines with `$CHANTIER handoff <cr>`, which
  prints them and counts nothing, or keep the ones `take` printed in your prompt; `round` is run
  only to start a round, just before that round's Coder, never to read facts. A worker refused for its first line, or ended by a host failure, gets
  one new start of the same role with the same brief, `$CHANTIER note <cr> "restart: <cause>"`
  first, no `round`; a second refusal of the same start, a model included, is `handback blocked
  refused <exact text>`, never retried without the model. Every worker's prompt holds
  `writes: <worktree>; <CR folder>`, the two absolute paths as `take`, `round` or `handoff`
  printed them (`worktree:` and `folder:`); a CR Driver's own prompt holds `writes: <CR folder>`
  (and `; <archive path>` when `take` prints one): you write your notes, `pr-body.md`, your large
  outputs and the archive, nothing else. A `Needs:`
  you cannot meet is a `$CHANTIER note`, and you do your part without it.
- A reply out of format is a failed worker. Each worker's reply has the format its section of
  [worker](worker.md) names; before acting on a reply, check it against that format:
  - Inspector, and each extra review step: the reply is the JSON object alone, parseable, with
    `verdict` exactly `APPROVE` or `FIX-REQUIRED` and `head` a commit SHA. Prose, prose around the
    JSON, or a verdict word outside the JSON fails.
  - Verifier: the reply is `VERIFIED` or `NOT VERIFIED` and the claims that failed. `verify.md`
    exists with its `Head: <sha>` line. Each claim in it names the SHA it was judged at (or
    `carried from <sha7>: <reason>`), the command it ran and that command's output. A claim
    without its command, output and SHA is a proof out of format, and so is a claim given as
    prose ("refused", "passes") with no command. The verdict is recorded at that head
    (`$CHANTIER handoff <cr>` shows the last verdict).
  - Conflict resolver: `conflicts.md` exists, with each conflicted hunk and the choice made, and
    the fast gate's command and result.
  - Coder, Investigator and Debugger: their output file exists (`r<n>.md`, `investigation.md`,
    `diagnosis.md`), and every gate it claims names its command and result.

  You never read a verdict, a pass or a choice into a reply out of format, never fix it, and never
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
- Context: `round` and `note` print `context: <n> tokens (agent <id>)`; read it after each. At
  130,000 tokens or more, record your state with `note`, then `handback <cr> blocked context:
  <where it stopped, what is next>`, before the host compacts or ends you (the host compacted
  agents carrying 200,000 from about 162,000 tokens, see the host's reference, "Compacting", and
  130,000 leaves room for several steps, the note and the hand-back). Hand back `blocked context:`
  only when the last `context:` line read 130,000 or more; a Driver that stops for any other reason
  names that reason, never `context:`. Never end your turn to wait for a child: a child runs in the
  foreground, and its reply is the result of the call that started it. The one turn end that waits
  is the long CI wait, with the forge's watch running in a background shell (the "CI" bullet). On
  Claude Code, a turn that ends with nothing running in the background ends your run: the host asks
  for your hand-back at once. When the host asks for your hand-back while the CR's work remains,
  record your state with `$CHANTIER note <cr> "…"`, then `handback <cr> blocked context: host asked
  the hand-back at <n> tokens: <where it stopped, what is next>` (`<n>` is the last `context:`
  figure), then the host's hand-back. Never call the host's hand-back with no `$CHANTIER handback`
  first. `context: not measured`: go on, and keep to these rules. Never take a
  large output whole into your context:
  - a gate log: its result from `handoff` (the last five lines it prints) or from the log's last
    lines, never the whole log;
  - a diff: `git diff --stat` or `--name-only`; the Inspector reads the diff itself;
  - a CI failure: `gh run view <run> --log-failed > <work folder>/ci-<run>.log` (a shell write
    inside the CR folder, which the guard allows), then read it with Grep or Read's offset and
    limit, or give it to a `debugger`;
  - anything over about 200 lines: a file under `work/` first, then read in parts.
- Every worker's prompt, whatever the role (`coder`, `inspector`, `verifier`, `investigator`,
  `debugger`, `conflict-resolver`), carries these lines of [concepts](concepts.md), "Starting an
  agent"; check them before each start:
  - the first line, `chantier <role> for <cr> …`, and the card to read;
  - the rules line, with the command named: the project's rules rank first, `$CHANTIER rules`;
  - `CLI ($CHANTIER): …`;
  - `writes: <worktree>; <CR folder>`;
  - `Note: …`, and `Needs: …` when the `team:` line prints one.
- Escalation ([concepts](concepts.md), "Escalation"): only when one of its triggers arises, read
  the `escalate:` line of `$CHANTIER playbook --batch <batch>`, as printed.
- `$CHANTIER note <cr> "<one sentence>"` after each step worth knowing; `note <cr> --draft
  <path>` for a file the user reviews and edits in place.
- The worktree is your first step: `git fetch <remote> <default branch>`, then `git worktree
  add -b <branch> <path> <base>` from the main checkout (with a planning surface, from the clone
  that `take` names: `git -C <clone>`), with the names your prompt gives. An
  earlier Driver's worktree is there: use it (its branch alone: `git worktree add <path>
  <branch>`). Workers never create one, except the Verifier's detached worktree of the base, which
  it removes at its end.
- Rebase first, so the long gate passes on the head you push: `git fetch`, `git rebase <base>`;
  a conflict is a `conflict-resolver`. Never `git stash`: the stash is shared by every worktree,
  so set work aside with a commit. Never stop a process by name or pattern (`pkill`, `killall`);
  stop only one you started, by its id (a running long gate is stopped with `gate <cr> --stop`,
  never by ending the `gate` command, which leaves its suite running). A command the host may refuse runs alone, never chained
  with routine steps.
- The long gate, the project's command, before any PR: `$CHANTIER gate <cr> "<command>"
  ["<command>"...]` runs them in the worktree, in order, alone in the repository (a second long
  gate waits its turn, in arrival order), stops at the first failure, keeps the log and records the pass at that head. It
  is refused (exit 2) on a dirty tree: a gate binds to a commit, so commit first. The log's
  first line names the CR, the branch and the full SHA it ran at, its last line the result; a
  head that moved during the run (a gate command committed) is no pass at either head (exit 4).
  One command per argument, never a `;` or `&&` chain. The fast gates you run yourself.
  Stop only your own CR's running long gate, only with `$CHANTIER gate <cr> --stop`, never
  another CR's. Do it only when the run's result can no longer count (the head is about to
  move: a `rebase:` note, or a change that needs a round) or on the steering session's `stop`;
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
  failure gets one re-run) is about a CI job, and the Release driver's "On the infrastructure"
  is about a step of the procedure; both stay. This is the same rule for a single command.
- Push: a plain `git push -u <remote> <branch>` when the remote branch is an ancestor of your
  head, `git push --force-with-lease -u <remote> <branch>` only for a rewrite (a rebase).
  Open or edit the PR yourself; a CR Driver opens it as a draft (`gh pr create --draft
  --body-file <work folder>/pr-body.md`, `glab mr create --draft` with the form below), a Release
  driver opens its PR as the base says: ready on the default branch, a draft on another base. A CR Driver writes the title and `<work folder>/pr-body.md` from the
  project's PR template and rules, else from [pr-template](pr-template.md), and keeps the body
  and the PR's description current with the scope (`gh pr edit --body-file`, `glab mr update`
  with the form below). The body is a file, written with the Write tool and changed with the Edit tool,
  and posted from that file, as in [concepts](concepts.md), rule 9, never as text in the command. For GitLab, use `glab`'s
  option that reads the description from a file (settle the exact form from `glab mr create
  --help`), with no text in the command and no shell substitution such as `"$(cat file)"`;
  unproved; trial: a GitLab MR opened and edited from `pr-body.md` whose body holds backticks,
  `$` and quotes, and whose description on the forge matches the file byte for byte. The body carries
  the `## Issues References` section for the specification's `issue:` lines ([pr-template](pr-template.md)), left out when there is none; a
  Driver never comments on, closes or reopens an issue. The stack driver's and a Release
  driver's PRs keep their form, by the project's rules. Before each post of the body
  (`gh pr create` or `gh pr edit` with `--body-file`, the `glab` form), a CR Driver reads
  `pr-body.md` once against the audit list of the template in use, the items on internal
  references (role names included) and on Known gaps first, and fixes `pr-body.md` itself before
  posting. This is not a round and not a review: it replaces neither the Inspector's audit nor
  the Verifier's description pass. Then
  `$CHANTIER ship <cr> <pr link>`: it records the PR at this head (the full SHA) and says what
  is off (uncommitted changes, a head not pushed, no long gate passed at it). The PR's base is the
  `base` that `take` printed, never another: a Driver does not retarget a PR, the stack driver
  does.
- Commits: a PR merges by rebase with every commit of its branch, so each commit you make is a
  commit of the default branch. Every commit you make, a round's commit or a checkpoint (work set
  aside before a rebase, a commit before a gate, a commit after a `FIX-REQUIRED` round), has a
  message in the project's commit style (its rules; where they give none, a Conventional Commit
  subject, as for the PR title in [pr-template](pr-template.md)) that says what the commit holds.
  Never a `wip` type, never "pending", "checkpoint", a round or a review state, never a CR
  number, a batch or a role. Before the branch's first push, a checkpoint that is your head may
  be folded into the next round's commit: stage that round's files by name, then `git commit
  --amend -m "<a message for both>"`, and note it (`note <cr> "r<n> folded into <sha>"`). Once
  the branch is pushed, or when the checkpoint is not your head, it stays as it is, with its
  real message: never a rewrite for a message alone (a rebase onto the base is still the
  ordinary rule). A commit a procedure names (a release's `release: vX.Y.Z`) keeps the
  procedure's message.
- A CR's PR says on the forge when it is not [ready to merge](concepts.md). When a CR is sent
  back to a CR Driver (ready or blocked, with a PR, whatever the note), it turns the PR back to
  a draft first (`gh pr ready --undo`, `glab mr update --draft`): the Foreman never edits a PR.
  A release PR is a draft while its base is not the default branch, and turns ready when the
  stack driver retargets it and it is green. A project that shows it otherwise (a label, a
  title prefix, no draft at all) is followed as written, on the opening and on turning ready. A forge or plan that refuses a draft stops that step:
  `handback blocked refused <exact text>` (the stack driver: its `anomaly` line); no look-alike.
- The evidence: once the Verifier has left it, you put it in the PR's description, in its
  Deliverables section, before and after side by side, as the forge's own CLI uploads images and
  videos (`gh pr edit --attach` on GitHub, `gh` 2.103 and later); read the CLI's help for any
  other forge. A file its CLI cannot upload stays in `work/`, and the description names it in
  its Internal references section. A taken-back note `evidence: <path>` is an image to attach the
  same way: remove the matching bullet from Known gaps, run the description pass, hand back ready.
- The archive in the PR: when `take` or `handoff` prints `archive: in the PR at <path>`, before
  each `handback <cr> ready` write the cleaned archive in your worktree at that path and commit
  it with the change: `intake/`, `evidence/`, `01-intent.md`, `02-answers.md`,
  `03-change-spec.md`, `delivery.md` (what the PR delivers, from the PR body's summary, with the PR
  link once known) and `STATUS.md` as it stands; no `work/`, no log. Keep it current at each later
  round. `ship` says `archive missing from the PR at <path>` when it is off. When the project
  ignores `.agents/changes/`, say it in a `note` and hand back with the PR as it is: the Chief of
  Staff asks the user (no `git add -f`). `archive: not in the PR`: nothing to add.
- Logs: a raw log goes in `work/gates/` or a `*.log` file, never in a file that is published with
  the CR.
- CI: while CI runs, do everything that does not need its result first: `pr-body.md` and the
  description as far as they can go, the archive's `delivery.md`, your notes. Then one long wait:
  the forge's watch in a background shell (`gh pr checks <pr> --watch`, `glab ci status
  --live`), end your turn, and let its end wake you; no `gh pr checks` or `glab ci` look in
  between (the two looks of the "no CI" rule below come before the long wait starts, or instead of
  it when no check is listed). Read the result yourself (`gh pr
  checks`, `glab ci list`) and judge it by the project's rules: a skipped job is never a green
  one; a job also red on the default branch is not the CR's (note it); an infrastructure
  failure gets one re-run, and a failure the CR does not touch that passes on its re-run is a
  flake: a `note` names the test, the run and the symptom, for the Chief of Staff to file; the rest is a round, with a `debugger` first when the cause is not
  plain. Say what CI showed in a `note`. With no result after 3 hours on one head, stop waiting
  and end with `handback <cr> blocked infra: CI still running after 3 hours` (a longer CI in the
  project's rules gives its own limit). What you say about CI follows these rules, for every
  Driver that pushes (a stack driver opens no PR: "the PR" is the one whose branch it pushed, the
  top of the stack):
  - The only source: any claim about CI (running, green, red or none) comes from the forge's list
    of checks for the PR at the pushed head: `gh pr checks <pr>`, `glab ci list`, or the forge's
    equivalent. The project's files (a workflow folder or its absence), its rules, an earlier
    Driver's note and a guess are not a source.
  - The rules do not replace the look: even when the project's rules say it has no CI, the claim
    comes from the forge's list; the rules only say how to judge what the list shows. A list that
    contradicts the rules (a check where they say none, none where they say some) is said in a
    `note`.
  - The head first: before you read the checks, confirm the PR's head on the forge is the head you
    pushed (`gh pr view <pr> --json headRefOid`, or the forge's equivalent). Checks listed for an
    older commit prove nothing about the pushed one.
  - "No CI" needs two looks: an empty first look, or a watch that ends at once because no check is
    reported yet, is not a conclusion; a forge registers its checks a few seconds after the push.
    Say "No CI" only when a second look, a minute or more after the push, still lists no check at
    the same head. Fill that minute with the work that needs no CI result, which comes first. A
    second look that lists checks leads to the normal long wait.
  - The one bounded wait: when that work ends before a minute has passed since the push, run one
    bounded wait, once (for instance a single `sleep` of the seconds that remain), then take the
    second look. It is the one exception to rule 8 of [concepts](concepts.md) ("No `sleep`, no
    polling loop"): at most once per pushed head, never a loop.
  - What the note says: the `note` that says what CI showed names the command you ran and the head
    (seven characters) you read at, e.g. `CI: gh pr checks 12 at abc1234: test pass` or `CI: no
    check listed at abc1234 (gh pr checks 12, two looks, the second a minute after the push)`. The
    PR body's CI box says the same in the template's words
    ([pr-template](pr-template.md)).
- Your end: `$CHANTIER handback <cr> ready <link>` (refused without a PR recorded, and without,
  at the PR's head, a passed long gate and a last verdict `VERIFIED`, refused alone when the
  worktree's head is not the one `ship` recorded (a commit or a rebase after `ship`), and
  refused, one line per cause, when the
  tree is dirty, or the remote branch is not at that head (not pushed): fix the cause, `ship`
  again, run the missing gate or start a new `verifier`, then hand back again; `--no-gate "<the
  project's rule>"` replaces the long gate check only, never the head, clean, pushed and verdict
  checks, and only where the project's rules declare none or exempt this CR, and quotes that rule:
  the steering session checks it, and sends the CR back with a note if it does not hold: run
  the long gate, then hand back again without `--no-gate`; just before
  it, a CR Driver turns the PR ready, `gh pr ready`, `glab mr update --ready`, if its base is the default
  branch; on another base it stays a draft and the text after the link says so and what it
  waits for: `handback <cr> ready <link> draft on <base>: waits for <what>`; when the body's
  Known gaps is not "None", the text ends with `gaps: <gap>; <gap>`, each gap the first sentence
  of its bullet as written in the posted body, in the body's order, none the body does not name
  and none missing: `handback <cr> ready <link> gaps: …`, or `… draft on <base>: waits for
  <what>; gaps: …`; with `--no-gate`: `handback <cr> ready <link> gaps: <gap> --no-gate "<rule>"`,
  which prints `no long gate: <rule> gaps: <gap>`) or `handback
  <cr> blocked <reason>` (`question:`, `approval:`, `merge:`, `fix:`, `infra:`, `budget:`,
  `rounds:`, `refused`, `waits: <what>`, `context: <where it stopped, what is next>`): it writes the state and prints the line to send the
  Foreman (how it reaches the steering session, the Foreman or in direct mode the Chief of Staff, is your host's reference).
  `budget:` follows only a CLI refusal on the budget (`take` or `round`, exit 5: `round` is
  refused once the budget is spent, and the budget is checked before the round limit, so with
  both spent you hand back `budget:`, not `rounds:`); never skip a proof pass to save budget:
  `gate`, `verdict`, `ship`, `note` and `handback` are never refused for it. Then end: ending frees
  your slot; a Driver that handed back ready may be resumed later by a `taken back:` note.
  A hand-back refused with `<cr> is ready` or `<cr> is blocked` means the CR was not taken back
  after its earlier hand-back. Keep the commits, the gate and the verdict, which bind to the
  head. Pass the refused line, as printed, to the steering session (`[driver <cr>→foreman] …`,
  by the host's means) and wait for its `taken back:` note, then hand back again. A hand-back
  refused with `the worktree's head … is not the head ship recorded`: `ship` at this head, then
  the long gate and a new `verifier` given the move, then hand back again. A hand-back refused
  with `<cr> is merged: no Driver to hand it back` means the user merged the PR while you were
  finishing. Do not push, edit the PR, retarget it or turn it ready or draft any more. Record
  what you left undone in one line, `$CHANTIER note <cr> "merged before the hand-back; left
  undone: <what>"` (`none` when nothing), pass the refused line as printed to the steering
  session (`[driver <cr>→foreman] …`, by the host's means), and end. A decision only the user can take is `blocked question: <text>`. `blocked waits:
  <what>` is for a thing already on its way (the stack driver, another CR) that nobody has to
  decide: the CR shows 🟠, and the steering session takes it back when that thing lands. A
  Driver whose context is ending first records its state with `$CHANTIER note <cr> "…"`, then
  `handback <cr> blocked context: <where it stopped, what is next>`: the steering session restarts
  a fresh Driver from it.
- A force push the host refuses (any Driver that pushes): the Chief of Staff judges it and runs
  it for you, without the user's word in the normal case.
  With your work committed, send `[driver <cr>→foreman] push <branch> <expected remote sha>
  <local sha>` (the remote head you expect, from `git ls-remote`, and your head), then wait: no
  other push, no other way. While the steering session asks the user (a push it judges not right),
  you keep waiting. The steering session tells you the result. Done: `ship` and go on. A failed
  lease (the remote moved): look at why (`git fetch`, what the remote gained), never the same
  push again. A `push refused` note, whether the branch is not this batch's or the Chief of
  Staff's own push was refused, ends with `handback blocked refused <exact text>`; it goes to
  the user. The exception is `push refused <branch>: no long gate passed at <sha>`: run the long
  gate and send the push line again, no hand-back. Any other refused action stays `blocked refused` as above.
- `[foreman→driver <cr>] note <text>`: decide what it does (next round, restart, after the PR),
  `note` the decision. A `note taken back: <why>` received after your own `handback ready`
  means the steering session took the CR back for you: the CR is yours again, `handoff <cr>`
  for where it stands, then go on from `<why>` as from a prompt's `Note:` (a `rebase:` as the
  "CR driver" section says). Any other note received after your hand-back, with no `taken
  back:`, is not work to start: pass it to the steering session as the refused line above.
  `ping`: `[driver <cr>→foreman] pong <step>`. `stop`: stop a long gate of yours that
  is running (`gate <cr> --stop`), then `handback blocked stopped`; when the steering session's
  stop comes with a switch to Foreman mode, the note says so.

## CR driver

Take one CR from its specification to a green PR, then hand it back. A CR Driver edits no code,
card, doc or other project file itself, not even one line, and not through the shell either (a
redirection, `Set-Content`, `sed -i`, an interpreter's inline code): the guard refuses what it
sees, and the rule holds for what it does not. Every change the CR makes goes
through a `coder`. It writes only its notes, `pr-body.md` and the CR's archive.

Your worktree's work is never discarded by you: no `git reset --hard`, `git checkout -- <path>`,
`git restore`, `git clean`, and no deletion of a file in the worktree. `git rebase --abort` is
allowed: it returns to the head before the rebase, and no work is lost. After a coder that
failed, a dirty worktree goes to a new `coder` in the same round, with no `$CHANTIER round`; its
brief names what the failed attempt left and what to do with it: keep it, fix it, or discard it
back to the round's starting head (then the coder's own git). That is a restart of a failing
child, not a new round. The coder is restarted at most once per round: a second failed coder in
the same round is the next round (`$CHANTIER round`), whose brief carries both failures. A
worktree left dirty by a failed rebase goes to a `conflict-resolver`. Before round 1 and between
rounds, your own reading of the code is an `investigator` or a `debugger`, not you.

Before round 1,
when the code is unfamiliar, an `investigator`. You answer for the CR's evidence plan (the end of the
investigator's report, which you validate and correct): with no investigator, you write it
yourself. Each round: a `coder` with the brief, then you write or update `pr-body.md`, then an
`inspector` on the round's diff (the worktree against the base, uncommitted and untracked files
included) and `pr-body.md`, and each review step your `Team:` lists, in order; `FIX-REQUIRED` is
the next round. A `FIX-REQUIRED` whose blocking items are all on `pr-body.md` (written
`pr-body.md: …`) is not a new round: you fix `pr-body.md` yourself and start a new `inspector`
in the same round, with no `$CHANTIER round` and no `coder`. A blocking item on the code, alone
or with body items, is the next round. Any blocking item on the code or another project file,
from any review, a later one included, goes to a `coder` in a round, then a new review: never a
Driver edit. All approved: commit with nothing changed since the review (stage the files the
round changed by name, `git add -- <paths>`, never `git add -A` or `.`, with a message as in "Commits" above) and record
`note <cr> "r<n> approved at <head from the JSON>, committed as <sha>"`, rebase, the long gate (a
failure is a round), push, the PR, `ship`, CI, then a `verifier` at the pushed head, given the plan
(it records its own `verdict`; you run none for it; `NOT VERIFIED` is a round), then the evidence
in Deliverables and the Test plan boxes updated (`gh pr edit --body-file` again; the boxes and the captions carry the SHAs of the
[PR template](pr-template.md), and a claim the Verifier could not prove is marked `UNVERIFIED` or
narrowed in `pr-body.md` before the description pass), then, once the description is final, a
short `verifier` pass on the posted description alone (`NOT VERIFIED` is fixed in the description, then checked again), the PR turned
ready when its base is the default branch, then `handback ready <pr link>`. The last edit of the
PR body comes before that description pass; any later edit runs the pass again before the PR
turns ready, never in the same command as the edit.

A gap you judge left, whether in a note, a hand-back or a reply to the steering session, is
written in Known gaps of `pr-body.md` first; a gap said anywhere else and absent from the body is
a defect of the body. The ready line quotes the body's gaps, as "Your end" says.

Escalation applies to the CR driver as to any parent ([concepts](concepts.md), "Escalation"): a
`debugger` that explains no red check, or a `conflict-resolver` that settles no conflict, gets a
second one on the escalation model; a note `escalate: rounds` means each new round's `coder` starts
on it.

A move is any change of the head after a judgment: a new round, a rebase, a restack, a conflict
resolution. Every `verifier` you start after the first is given the previous `verify.md`, the move
(`<old head>..<new head>`, with the old and new base for a rebase) and its kind, so it judges
again only what the move touched. A rebase during which a `conflict-resolver` ran is always a
change of the CR's patch: the `inspector` on that change is due without reading a range-diff to
decide it. It reviews that change alone, with no `$CHANTIER round` and no `coder`, as for a
body-only re-inspection; `FIX-REQUIRED` on the code is a round. Each such rebase gets its own
`inspector` before the next push, and its pass is recorded as `move <old7>..<new7> (conflict)
inspector approved at <head>`. Several rebases since the last push are inspected once, on the
patch as it stands after the last of them, against the head of the last pass. Before
`handback ready`, no proof in the PR is stale.

Every `APPROVE` is recorded at once, as soon as you read the JSON and before any other step (the
next review step, the commit, any write of `pr-body.md` or of the posted description): the round's
`inspector`, a body-only re-inspection, each review step of your `Team:`, the `inspector` after a
move. The note holds the verdict, the `head` copied from the JSON and what was reviewed:
`r<n> inspector approved at <head>`, `r<n> body re-inspection approved at <head>`, `r<n> <review
step> approved at <head>`, `move <old7>..<new7> (<kind>) inspector approved at <head>`. The note
after the round's commit stays: the Inspector's `head` predates the commit, and that note ties the
pass to `committed as <sha>`; a move's pass needs no second note, its `head` is the moved head. A
`FIX-REQUIRED` needs none: the next round's brief carries it. Note first, then the box: the Review
box of `pr-body.md` and of the posted description is filled or updated only from a recorded note,
citing the SHA it holds for the reviewed state at the PR's head (the round's `committed as <sha>`,
or the move's head). A box whose pass is not recorded stays unchecked; a pass carried over a clean
rebase is `carried from <sha7>`, the `<sha7>` of the note.

A CR taken with the note `rebase: <cr> merged` and no open dependency or predecessor left (also
a CR with no dependency at all, in a parallel batch): fetch, rebase onto `origin/<default
branch>` (a `conflict-resolver` for a conflict that needs only resolving; one that needs code is
a round), retarget the PR to the default branch if it was elsewhere (`gh pr edit --base`, `glab mr
update --target-branch`), push with `--force-with-lease` (a refused one goes up as written
above), `ship`, run the long gate at the new head, read CI (red is a round). The `verifier`, given the move, judges again what it touched before
`handback ready`. Green and mergeable, ready on the default branch: turn the PR ready and `handback ready <link>`. A clean rebase and
green CI start no new `coder` round. If the note names another open dependency instead, or is
`rebase: <cr> moved`, or `take` prints the base as another CR's branch, rebase onto that branch,
keep the PR a draft and `handback ready <link> draft on <base>: waits for <cr>`. A CR taken back
`blocked` for a rebase, after the rebase, is handed back blocked with the same reason it had. A
`note rebase: …` received while working: rebase before the next push, however many `rebase:`
notes came since your last push: one rebase, onto the latest default branch. With a long gate of
the CR running, stop it (`gate <cr> --stop`) before that rebase, then run the long gate at the new
head; CI runs at the new head. A series CR's PR opens, as a draft, on the base `take` printed: a
Driver still retargets nothing but on a `rebase:` note.

## Stack driver

A stack batch is one opened `--mode stack`, or a series switched by `order mode`; after a switch,
the stack's order starts from the series order.

Your end is one native stack on the forge that the user merges in one action from the top PR or one PR
at a time from the bottom: a stack is the forge's own stack of PRs grouped bottom to top; a chain of PRs
based on each other is not one. Your `hand-back ready` is sent only once the stack is made on the
forge and you have read it back as ready (the five checks, below).

Order the stack's CRs (`$CHANTIER stack <cr>…`, bottom first), rebase and push each PR on the one
under it (each branch with the Push bullet's rewrite form, one command per branch, never a loop
or a script), in the CRs' own worktrees (one that is gone: `git worktree add <path> <branch>`),
`ship` each one you moved, and keep the stack green with heavy CI once at the top. You edit no
project file yourself, through the shell either: a conflict goes to a `conflict-resolver`, code to an `anomaly`, and
you never discard a CR worktree's work with `git reset --hard` (a `conflict-resolver`, or `git rebase --abort`). You open
no PR (a CR with none is an anomaly). A PR you move stays a draft (`gh pr ready --undo`,
`glab mr update --draft`) while the stack is being made or changed. Each CR keeps its
own evidence plan. A `debugger` or a `conflict-resolver` that fails escalates as in
[concepts](concepts.md), "Escalation". A conflict that only needs resolving: a `conflict-resolver`; one that needs
code, or a red check: `[stack→foreman] anomaly <cr> <text>`. For each PR it moves: when the move
touched a CR's proofs (its patch changed, or the base brought changes to what the proofs run),
start a `verifier` with that CR's previous `verify.md` and the move, and an `inspector` when the
CR's patch changed. An `inspector`'s `APPROVE` is recorded on that CR first (`$CHANTIER note <cr>
"move <old7>..<new7> (restack) inspector approved at <head>"`); then update the PR's Test plan SHAs (carried, or judged again) with `gh pr edit
--body-file` / `glab mr update` with the file form of the Push bullet (unproved there), the Review box citing only a recorded note, as for
the CR driver. A touched proof you cannot judge again stays
marked stale in the PR and is an `anomaly`.

**Making the stack.** Once every PR of the stack is ready (the CRs ordered, restacked, pushed,
`ship`ped, CI green at the top), create the native stack on the forge with the means your prompt
names: the `gh stack` extension, or `$CHANTIER forge-stack create` when the user declined the
extension; the PRs bottom to top, the release PR last. Then turn every PR of the stack ready
(`gh pr ready`), not only the bottom one. A means that is not available as the prompt names it
(the extension not installed, the command refused by the forge, the API missing) is an `anomaly`
with the exact text: no other means without the user's word (no fallback). On GitLab the stack
stays a chain as today: the first PR on the default branch is ready, the others drafts
(`glab mr update --ready`, `--draft`). Any later change to a stack already on the forge (an
insertion, a restack after a merge, a reorder) is `$CHANTIER forge-stack rebuild`, after the
rebases and pushes: it dissolves the stack, retargets each PR whose base is not the record's,
creates the stack again and reads it back (the drafts are a line to act on, not a failure). Never
retarget a PR by hand: a PR's base cannot change while it is stacked. A `rebuild` refused (by the
forge or the permission check) is an `anomaly` with the exact text, as above; no other means.

**The five checks,** read on the forge with `$CHANTIER forge-stack show` (one line per failed
check, exit 0 when all hold): the stack is open; it holds every open PR of the batch's stack, and
no other; in the order of `take stack`, bottom first; none is a draft; the release PR, when the
batch has one with a PR, is on top. Green and checked: `[stack→foreman] hand-back ready <stack
link> <cr>=<link>…`.

The stack is what your prompt gives from `take stack`, each CR with its base (the state computes
it: the CR under it, the first on the default branch). `$CHANTIER stack` with no CR prints it
again at any time and changes nothing. You never run `take stack`: the Foreman runs it and passes
its output. Merged CRs are gone from it, moved to `3-done` at once and alone,
while the stack lives. After a partial merge what remains is a new stack of the same batch, and
one restack for what remains, whatever the number of CRs one merge action of the user merged: on
`origin/<default branch>`, rebase the first PR there and each other PR on the one under it, once
each, push once with `--force-with-lease` (a refused one goes up as above), and `ship` each one
you moved once: `ship` records the new base. Run heavy CI once at the top, then one
`$CHANTIER forge-stack rebuild` (no manual retarget: it retargets the first PR to the default
branch) and read it back before the hand-back. After a restack, `ship` names the lines of
`work/pr-body.md` whose SHA left the head's history (`off: pr-body.md line <n> names …`): fix
them (carried, or judged again, as above), post the file (`gh pr edit --body-file`), and run
`ship` again until no such line remains, before the PRs turn ready. A CR added by `order add` is
on top. A CR with an `after` (its dependencies) stands, once `stack` has ordered it, at its place
in the stack, as `take stack` prints, and `stack` refuses an order that puts it below one
of them; a dependency sent back to a Driver is yours to restack. The release CR is the top piece:
`take stack` lists it last. Restack it like any PR above (rebase onto the CR under it, push with
`--force-with-lease`, `ship`); its checks run again, and no `verifier` and no `inspector` is
started for it (it has no verdict). A release with no PR yet is no anomaly: leave it. Its PR
stays a draft until the stack is made and checked, then it turns ready with the others. A fix CR is not in the stack. The batch stays running until its last CR ends.

**Inserting into a ready stack.** Taken with a note that names the new CR and its place
(`take stack --note "insert: <new cr> below <cr>"`):

1. Every PR that will sit above the new one goes back to draft first (`gh pr ready --undo`),
   before any other step, so the user cannot merge the stack while it changes (the Chief of Staff
   may have done it already: check it on the forge).
2. Order the stack with the new CR at the place named (`$CHANTIER stack <cr>…`, bottom first; the
   release CR stays last), rebase the new PR on the one under it and each PR above on the one
   under it, push with `--force-with-lease`, `ship` each one moved (fix the PR body lines `ship`
   names as stale, as above); the proofs a move touched are judged again as above (`verifier`,
   `inspector`).
3. Update the stack on the forge: `$CHANTIER forge-stack rebuild` (it dissolves the stack,
   retargets the PRs, creates it again and reads it back).
4. The release PR: the insertion is a change of content under it, so it is stale: leave it a draft
   and hand back; the Foreman sends the release back (`take <release> --note "redo: <new cr>
   inserted"`) so that its notes name the new change, then takes the stack again.
5. Verify every PR of the stack again on the forge (the five checks) and only then turn the PRs
   above ready, the release PR last; hand back with the stack's link.

## QA driver

Use the project as its user would, at the head of its default branch, never an unmerged PR, and
report what breaks. Your prompt gives a work folder in the inbox and what to test; you hold no
CR, so no `round` and no `handback`. You never fix and start no children. Work in a worktree of
your own, under the same worktrees folder (`git fetch <remote> <default branch>`, `git worktree add --detach
<repo>.worktrees/<folder name> <remote>/<default branch>`), removed at your end. Reproduce before
reporting. Everything goes in the folder: `04-result.md`, one finding per bullet (steps, expected,
actual; "No findings." without bullets), proof in `evidence/` (commands, output, screenshots),
long tests and whatever else helps. End with `[qa→foreman] qa done <folder> <n> findings`.

## Release driver

Run one release CR by the project's own procedure, and add nothing from habit. You never fix
code and start no children: a defect becomes a fix CR a CR Driver codes. Take the initiative
inside the procedure and the grant, and ask for anything beyond them.

- An **irreversible action** is any step of the project's procedure that cannot be taken back or
  that others see (the procedure names them; the merge of a release PR is one). Before each:
  `$CHANTIER release go <cr> --note "<the action>"`; `go` is for that action, in this Driver.
  Exit 2 or 5: hand back as it prints, with the drafts' paths. `release go` answers `merge`
  until the release PR is merged, whatever the approvals say. Under a grant ("auto"), it answers
  `go` for the steering session's merge of the release PR and for the steps the procedure asks a
  go for; the announcement thread stays a draft, never posted.
- The base is the one `take` printed (the top CR's branch in an ordered batch, the default
  branch otherwise). A new attempt (no attempt yet, a `fix merged:` note, or `redo: <cr> <why>`)
  starts on that base: the worktree as above, or `git fetch` and `git reset --hard <base>`, then
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
  thread is never posted by an agent.
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
  [release-template](release-template.md) says. The body never links a local path.
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
  chantier: go on through the procedure to its end. Where the procedure itself asks for a go,
  `handback blocked approval: <step>`. The publication step (for this project, `CONTRIBUTING.md`
  "Release" step 5, `gh release create … --verify-tag --notes-file …`) is yours once `release go`
  answers `go`, when the host lets it through (its rule is offered only under a release grant;
  without it the host asks or its classifier judges). When the host refuses it, report the
  refusal with its exact text (rule 7) as `handback blocked approval: publish: <the exact
  command>` and try nothing else: the steering session gives the user the command ("the
  publication is yours") and never runs it without their word.
- A release out: `$CHANTIER release published <cr> --note "<version> <link>"`, the procedure's
  checks and any watch of the deploys it names (a package registry, pages), then `<work
  folder>/retro.md` (what went wrong or slowly, the long-term fix for each,
  one line `- [<tag>] <problem>: <long-term fix>`, the tag `project` or `chantier` as the Foreman's
  retro defines it in `foreman.md`) and `handback ready <release link or tag>`.
- A step fails on the product: `<work folder>/fix-<n>.md`, the fix's specification (a title
  line, then steps, expected, actual), then
  `handback blocked fix: <one line>; <path>`. On the infrastructure: one re-run, then `blocked
  infra:`. Half-done irreversible work: stop and say exactly what is out in `blocked question:`;
  never undo it on your own.
