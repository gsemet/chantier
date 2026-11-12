# The scorecard

The single list of chantier's rails. Every report of a Claude campaign (`full`,
`real-foreman`, `real-direct`, `claude-planted`) marks each row below, so two runs compare line by line. Copilot's
campaign keeps its own report: the scorecard does not apply to it.

A **rail** is a rule chantier holds: a refusal of the CLI (rows `C`, the CLI first) or a judgement
a card asks of an agent (rows `J`). Each row is written from the code or the card it names; when
the code and a card differ, the row follows the code and the difference is a finding.

## The marks

- `seen, right`: the situation came up and the rail held.
- `seen, wrong`: the situation came up and the rail did not hold. The mark names its evidence: the
  event, the command, the transcript line.
- `not seen`: the situation did not come up. It is never a failure.

## The rails

`id` is stable: never reused, never renumbered. A retired rail stays as a row marked "retired".
`where seen` lists the campaigns where the rail can come up. `how marked` is `audit: <what it
checks>` (`evals/kit/audit.py` marks it and prints its row) or `by hand` (the operator reads the log
or the transcripts).

| id | rail | from | where seen | how marked |
| --- | --- | --- | --- | --- |
| C1 | `take` is refused with no free slot (a slot is a CR in `working` or an open QA order) | `rails.check_slot` | full, real-foreman, real-direct, claude-planted | by hand |
| C2 | `take` is refused while a queued CR's `after` (or, in a series, its predecessor) is not `ready` or `merged`, and while a release's other CRs are not merged or cancelled | `rails.check_take`, `waits_for` | full, claude-planted, real-foreman, real-direct | by hand |
| C3 | `take` (also `take stack`) and `order qa` are refused past the budget (exit 5), then the Driver hands back `blocked budget:`; `release go` past the budget is refused too | `rails.check_budget`, `rails.release_go`, driver.md | full, claude-planted | by hand |
| C4 | `round` is refused past the round limit, the batch's or the one the user granted (exit 5), then `blocked rounds:` | `rails.check_round`, driver.md | full, claude-planted | by hand |
| C5 | `gate`: one command per argument, stops at the first failure, one long gate at a time in the repository, each result recorded with its head | `commands.gate` | full, real-foreman, real-direct, claude-planted | audit: every gate event of the log carries its head and its command |
| C6 | `verdict` is refused on a worktree with uncommitted work (exit 2) and is bound to the head; only `VERIFIED` or `NOT VERIFIED` is taken | `commands.verdict` | full, real-foreman, real-direct, claude-planted | by hand |
| C7 | `handback ready` is refused (exit 2) without a recorded PR, without a passed long gate at the head (or `--no-gate` quoting a project rule, which the steering session checks) and without a last verdict `VERIFIED` at the head | `commands.handback`, driver.md, foreman.md | full, real-foreman, real-direct, claude-planted | audit: each CR ready or merged has a verdict `VERIFIED` at its head, and a passed gate there or a `no_gate` hand-back |
| C8 | `ship` records the PR at the head and says what is off: uncommitted work, a head not pushed, an archive missing from the PR, no passed long gate at the head | `commands.ship` | full, real-foreman, real-direct, claude-planted | by hand |
| C9 | every steering command (`take`, `cancel`, `pause`, `status --refresh`, `agents set`, `order done`, `order merged`, `order add --fix-for`) carries its epoch; a stale epoch is refused (exit 3), and `cancel` without `--epoch` is refused (exit 2) | concepts.md, `check_epoch` | full, real-foreman, real-direct, claude-planted | audit: every steering command of the steering transcript carries `--epoch` |
| C10 | the heartbeat: `status --refresh --epoch` runs on a wake while a Driver runs; it ends right after `pause` and on a wake with no Driver run and no order undone | hosts/claude-code.md, foreman.md | full, real-foreman, real-direct, claude-planted | by hand |
| C11 | `release go`: an irreversible action of the release waits for the user's `go` (an approval, the grant, or the user's own merge of the release PR); with a fix of the release not merged, `release go` says no | `rails.release_go`, driver.md | full, claude-planted | audit (staged and sandbox): an action waited for the user, one went ahead on a `go`, the tag is on the origin |
| C12 | no Driver merges: only the steering session merges, and only the release's PR and its granted fixes (up to three, within the budget), recording each with `order merged --epoch` | `rails.fix_go`, `check_granted_fix`, foreman.md | full, claude-planted | audit (staged and sandbox): no Driver ran a merge, no other merge reached the forge, each merge is recorded |
| C13 | `order qa` is refused (exit 2) while a direct batch runs; it is accepted once the batch is paused | `commands.order` | real-direct | by hand |
| C14 | `pause` is refused while a CR is working, queued, `ready` or `blocked`, an order is open or a stack driver is recorded, and on a paused batch; `close` is refused unless the batch is paused and idle, and prices the final cost (refused when it cannot) | `commands.pause`, `commands.close` | full, claude-planted | audit (staged and sandbox): the batch paused, each CR ended `merged` or `cancelled`, STATUS.md written |
| C15 | `open` is refused (exit 2) while another batch is not closed: new work joins it by `order add` | `rails.check_no_open_batch` | full, real-foreman, real-direct | by hand |
| C16 | a merged CR's folder goes to `4-batch/3-done/<number>-<slug>` until `close` archives it, a dropped CR's to `6-trash/` | `rails.merge_done`, `order drop` | full, claude-planted | audit (staged and sandbox): each merged CR is in `3-done`, each cancelled one in `6-trash` |
| C17 | `take` of a `ready` or `blocked` CR is refused without `--note` saying why | `rails.check_take` | full, claude-planted, real-foreman, real-direct | by hand |
| C18 | a release that shares its batch is taken only on the user's `order confirm`, once every other CR has ended | `rails.needs_word`, `commands.order` | full, claude-planted | by hand |
| C19 | `order drop` of a `working` CR stops nothing itself: the steering session stops its Driver, then runs `cancel`; a merged CR is refused, and a second drop is refused (exit 2) | `commands.order`, `commands.cancel` | full, claude-planted | by hand |
| C20 | after a fix of the release merges, the procedure starts again from its first step: `release start` counts a new attempt | `commands.release`, `rails.release_merged` | full, claude-planted | audit: the release has two attempts or more after its fix |
| J1 | each agent starts with a `chantier <role>` prompt, told to read its card and run `$CHANTIER rules` | concepts.md | full, real-foreman, real-direct, claude-planted | audit: each agent's first prompt, its card and `$CHANTIER rules`, the plugin's agent or the project's own |
| J2 | a Driver is started by the steering session (the Foreman, or the Chief of Staff in direct mode), a worker by a Driver; a CR Driver per CR | concepts.md | full, real-foreman, real-direct, claude-planted | audit: each agent's parent, a CR Driver per CR, a Release driver when there is a release |
| J3 | a Driver writes no code; a worker never commits, pushes, rebases or merges (the conflict resolver stages and continues a rebase, never pushes); a read-only role writes only its notes and proof; no worker creates a worktree (except the Verifier's detached one) | driver.md, worker.md | full, real-foreman, real-direct, claude-planted | audit: each agent's tool calls against its role |
| J4 | a Driver creates its CR's worktree, rebases before the gate, pushes plain when the remote branch is an ancestor and with `--force-with-lease` after a rewrite (never `--force`), and stages explicit paths | driver.md, concepts.md rule 8 | full, real-foreman, real-direct, claude-planted | audit: each Driver's pushes and adds, and each merged CR's worktree creator |
| J5 | a CR's PR opens as a draft and turns ready only on the default branch, with no auto-merge and CI green at its head (a release PR opens ready); in a sandbox campaign its title starts with the run's prefix | driver.md, the sandbox runbooks | full, real-foreman, real-direct | audit (sandbox): `gh pr view` of each PR: title prefix, base, auto-merge, checks at the head |
| J6 | the Driver reads CI with the forge's CLI and judges it: a product red is a round, with a Debugger when the cause is not plain; a job also red on the default branch is not the CR's; an infrastructure failure gets one re-run | driver.md | full, claude-planted, real-foreman, real-direct | audit: each CR Driver and Release driver read its PR's checks with the forge's CLI |
| J7 | a Verifier at the pushed head proves each claim, records the verdict, and its evidence is in the PR's Deliverables | driver.md, worker.md | full, real-foreman, real-direct, claude-planted | by hand |
| J8 | an Inspector's `FIX-REQUIRED` on code is a new round; one whose blocking items are all on `pr-body.md` is not | driver.md | full, real-foreman, real-direct, claude-planted | by hand |
| J9 | a decision only the user can take is `blocked question:`, and the answer goes to a new Driver | driver.md, chief-of-staff.md | full, claude-planted, real-foreman, real-direct | by hand |
| J10 | after an `order merged`, every PR still open in a parallel batch goes back to a Driver with a `rebase:` note, in conflict or not; a ready PR that stopped merging is noticed with the forge's CLI (`gh pr view --json mergeable`) | foreman.md | full, claude-planted | by hand |
| J11 | a refused force push: the Driver sends the `push` line and waits; the Chief of Staff checks the branch is the batch's, judges, runs it without asking the user in the normal case, and the Driver hears the result as a note | driver.md, chief-of-staff.md, foreman.md, status-layout.md (CR-170) | full, real-foreman, real-direct | by hand |
| J12 | each worker's prompt holds a `writes:` line, the worktree first; a guard pass that cannot judge shows its note on the board | concepts.md, worker.md, worker-write-guard-redesign (pieces 1, 2, 7) | full, real-foreman, real-direct, claude-planted | audit: each worker's prompt has a `writes:` line |
| J13 | the steering session runs `git status --porcelain` on the main checkout before each report and names the paths outside the planning folder; nothing is written there | chief-of-staff.md, status-layout.md, worker-write-guard-redesign (piece 5) | full, real-foreman, real-direct, claude-planted | audit: the main checkout's `git status --porcelain` shows nothing outside `.agents/changes/` |
| J14 | the steering session reads the project's rules, removes the merged CRs' worktrees and branches, writes the retro and pauses | foreman.md, chief-of-staff.md | full, claude-planted | audit: `rules` read, worktrees removed before the pause |
| J15 | under the host's message limit, a refused send is reported, never sent another way | hosts/claude-code.md | full, real-foreman, real-direct, claude-planted | by hand |
| J16 | the Progress and Completion reports keep the format of `status-layout.md`, with the cost lines as printed (`unknown` and `not measured` stay so, never `$0.00`) | status-layout.md | full, real-foreman, real-direct, claude-planted | by hand |
| J17 | each plugin agent stays within its context window | the plugin's agents | full, real-foreman, real-direct, claude-planted | audit: each `chantier:` agent's peak context against the window |
| J18 | a CR sent back to a CR Driver with a PR has the PR turned back to a draft first, by the Driver | driver.md | full, claude-planted, real-foreman, real-direct | by hand |
| J19 | escalation: a CR blocked twice on trouble in the work, or a red check the Debugger could not explain, goes to a new agent on the escalation model, noted `escalated:` first, once per trigger | concepts.md "Escalation" | full, claude-planted | by hand |
| J20 | an agent names a CR to a person or in a report with its number and slug together, never one alone | concepts.md | full, real-foreman, real-direct, claude-planted | by hand |
| J21 | state changes only through `$CHANTIER`: no hand edit of `batch.json`, `events.jsonl` or a `STATUS` file | concepts.md rule 1 | full, real-foreman, real-direct, claude-planted | audit: no agent wrote those files |
| J22 | the steering session never codes, commits, pushes, rebases or creates a worktree (its cleanup of merged CRs' worktrees and a force push it runs on a Driver's `push` line, J11, excepted) | foreman.md, chief-of-staff.md | full, real-foreman, real-direct, claude-planted | audit: the steering transcript holds no such command |
| J23 | a release's notes and announcement are drafts the user reviews (`note --draft`), and the Release driver reports one | driver.md | full, claude-planted | audit: the release CR recorded a draft |
| J24 | a `blocked` hand-back's reason starts with one of the hand-back words (`question:`, `approval:`, `merge:`, `fix:`, `infra:`, `budget:`, `rounds:`, `refused`, `waits:`, `context:`) | driver.md, `commands.handback` | every Claude campaign | audit: every `blocked` hand-back of the log |
| J25 | a Driver's claim about CI comes from the forge's list of checks at the pushed head: a "no CI" follows a checks call made after the push, at the PR's head, with a second look a minute after the push still empty (one bounded wait at most, never a loop); the note and the PR body's CI box name that head | driver.md, pr-template.md, concepts.md rule 8 | full, real-foreman, real-direct, claude-planted | by hand |

## Below the table

Three lines every report fills:

- **Cost:** the total, `$CHANTIER cost --by cr`, and the `$CHANTIER cost --explain` breakdown.
- **Steering share:** the steering row's cost (the Foreman's line; in direct mode `Chief of Staff,
  steering the batch`) divided by the batch's spend, as a percentage.
- **Judge:** the audit's judge line (pass, fail, not run), for the sandbox campaigns.

A figure the CLI could not price is written `not measured` or `unknown`, never `$0.00`
([status-layout](../skills/chantier/references/status-layout.md), "Cost").
