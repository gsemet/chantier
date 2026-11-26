# Concepts

## Words

- **Ready** (the status): the stored status `ready` in `batch.json`, set by `handback <cr> ready <link>`. A token the rails and old records read, which the CLI turns into the three words below, used everywhere else; no person reads it alone, but in the stack rows of `take stack` and `stack` (`ready, PR draft (#<n>)`).
- **Ready to merge** (🟢): handed back ready, the PR out of draft on the forge as the record holds it (`ship`, `stack --out-of-draft`, never ahead of the forge); in a stack batch every CR under it ready to merge too (for a CR the stack driver placed, those below it in the stack's order; for one not placed, the CR whose branch is its PR's base, as `ship` last read it, none when that base is the default branch); outside a stack the PR's base is the default branch. The user may merge it at any moment, and the top of a stack ready to merge makes the whole stack mergeable. "Mergeable" names only these, never a draft, whatever the forge's field says. The mergeable part of a verified stack (`help stack-checks`) merges from its top PR in one action (GitHub) or one PR at a time from the bottom (GitLab: one MR at a time), the user's choice at each merge; a draft on top is not mergeable, and a PR below the top had heavy CI only at the top unless the user asked for it at its head.
- **PR in draft** (🟤): handed back ready, the PR open and a draft, or out of draft over a CR that is not; its hand-back line names its draft state and the CR it waits on (first the CR its PR's base branches from, else a CR below, its dependency, the release's top or its turn out of draft), and nobody merges it. Any other CR's PR (a series, a stack not yet made or being changed) is a draft on the forge too, and no one merges it.
- **Ready locally** (🟣): handed back ready with no PR yet (rare: `handback ready` needs a PR). A draft's icon is its CR's state, never "draft" by default: 🟡 rebasing or at a gate, 🟠 waiting for another CR's work, 🔴 blocked.
- A release PR is merged by the user, last of the batch (in a stack from its top PR with the rest; in a series after the rest, from the bottom up). The steering session merges only under the grant, never a stack that holds it; GitHub's asynchronous merge takes every open PR below, so it merges there only with nothing open below (`help merge-github`).
- **`3-ready`**: the folder of the CRs that wait for the next batch (never "the ready CRs"), specified or automatable (no specification: the Driver works from the request alone), moved there on the user's word. It is not "ready to merge": a CR handed back `ready` sits in `4-batch/2-actives/`, never in `3-ready`.
- **Lease**: a numbered 10-minute claim of a Driver, the stack driver or a QA driver on its unit (a CR, `stack`, a QA order `O-k`), started by `take` (or `order qa`) and renewed by the commands that carry `--lease <n>` and by `lease <unit> renew`.
- **Wait**: what a CR waits for (`answer`, the user's; `approval`, `pipeline`, `merge`, a forge's), recorded, cleared and listed with `wait`, kept in its `batch.json` entry (a backlog CR's `waits.json`); a CR with a wait is `blocked`, as any block is, and a wait is never called a gate.
- **Hold**: `order slots --note 0`, no new Driver. "Pause" names only the batch state.
- **Tracker issue**: an issue of the project's tracker (GitHub, GitLab, Jira…) a CR comes from, named by an `issue: <link>` line under the title of its `01-intent.md` and `03-change-spec.md`. The CR's PR names it in `## Issues References` ([PR template](pr-template.md)), in the project's form, else the template's default with a closing verb (`Closes #<n>`, `Closes <KEY>-<n>`); a project rule may differ. No agent closes or reopens an issue by hand. Only the Chief of Staff posts on an issue, only what the user approved for that ticket; a comment carries no CR number, batch, agent role or cost.
- **Host and default matrix**: the cases a CR proves one by one, because what it changes behaves differently per host (Claude Code, Copilot) or with a shipped default and a configured value: one cell per combination that applies, a host's refusal included. Each cell gives the result it must show and the real flow that proves it (the CLI's own commands from a real state, no user file for a shipped-default cell); a record or configuration built by hand proves no cell. The specification names the matrix in its evidence; a CR with neither dependency has none. The Inspector checks each cell has a test or a check in the diff; the Verifier proves each at the committed head.
- **Seat**: `seat.json`, kept by the CLI in the planning folder (one per project, local), naming the repository's Chief of Staff session (its session id, transcript, environment, title and link).
- **Steering session**: the Foreman, or the Chief of Staff in direct mode.
- **Order, ask, hand-back**: the user's word (`order`), what the Foreman needs heard (`asks`), a Driver's end (`handback`).

## Change Request (CR)

One change, from the request as it arrived to one pull request: a folder (numbered `<number>-<slug>/` in a batch) in a stage of the planning folder.

```text
<slug>/
  intake/                 the raw request as received; never edited
  01-intent.md            the request, summarised and analysed
  02-answers.md           every answer the user gave about the CR, whoever asked
  03-change-spec.md       the Change Specification
  summary.json            title, summary, origin, labels, group; through `$CHANTIER summary`, never by hand
  STATUS.md, STATUS.json  where the CR stands; the CLI writes them, never by hand
  formerly.json           where a CR taken out of a batch came from; written by `order drop` to the backlog or `3-ready`
  prototypes/NN-<idea>/   each version, with a README.md that says how to run it
  experiments/            scripts, tests, benchmarks, studies and research notes made for the CR
  evidence/               proof kept with the CR (screenshots kept on purpose, the Verifier's)
  work/                   written while it runs: notes, gate logs, the PR body
```

The folder moves, it is never copied: `1-inbox/`, `2-backlog/P1…P4/`, `3-ready/`, then in the running batch `4-batch/1-pending/` (a CR arrives by `open` or `order add`, the latter from the destination the user chose at "grilled enough?"), `2-actives/` (taken by a Driver), `3-done/` (merged, until `close`), then `5-archives/<YYMMDD-HHMM>-<number>-<slug>/` (after `close`, the merge's time) or, after `order drop`, `6-trash/`, always with its work. A CR taken out of the batch keeps its number and goes to the backlog or `3-ready`, never the inbox (`order drop` refuses it), with `formerly.json`; when that folder joins a batch it gets its number back, and its branch and PR while the branch exists, and `formerly.json` is deleted; a release or fix CR leaves only to the trash. `triage <item> --inbox` sends a backlog or `3-ready` item back to the inbox; `restore <6-trash/item> [--slug <name>]` brings a trashed one back to the inbox, on the user's word only, without its date or batch number, with a line `formerly CR-<n> of batch-<m>`.

**A CR's folder holds its work.** Whatever an agent makes for a CR (a prototype, a script, a test, a benchmark, a study, a research note, a screenshot it keeps, a plan) is written in that CR's folder, in the place the tree gives, never in the host's scratchpad or a temporary folder: this ranks above the host's own instruction to use its scratchpad, which stays the host's outside any CR's work. A sub-folder is created only when its first file is written. A new prototype version is a new folder (two digits and a kebab-case name) and the earlier ones stay; its README.md says what it tries, the command that runs it again (its server command, its port) and what it needs; its own scripts (a snapshot generator, a data builder) go in it, not in `experiments/`, whose files take numbered names (`01-benchmark.md`). Never in a CR's folder: secrets, personal data, large binaries that are not the retained prototype (name where they are), the batch's own files (gitignored), the agent's memory or the host's settings (`~/.claude/`). Raw logs stay in `work/gates/` or a `*.log`, a Verifier's scratch project in `work/scratch/`, a downloaded CI artifact in `work/scratch/artifacts-<run id>/`. What only the conversation holds (a subagent's reply, an inline visualization, a pasted image) is lost unless an agent writes it there: writing it is the agent's job.

A CR is named with its number and short slug together ("CR-<n> <slug>"); an item with no number is named by its slug. In a CR's PR the name appears only in the Internal references section, unless the project's rules say otherwise.

## A CR's summary

`summary.json` in the CR's folder: its title (one line, at most 72 characters), a summary of what the CR means now (one line of plain text: its state of grill or delivery, not its progress in a batch), its origin (an issue's tracker and reference from the `issue:` line, or verbal), its labels and group, and the checksums of the covered files (`intake/*.md`, `01-intent.md`, `02-answers.md`, `03-change-spec.md`, `delivery.md`; not `STATUS.md`, `work/` or `evidence/`). The board reads it. A summary is a judgment: an agent writes it, never the CLI. An agent that writes a covered file runs `$CHANTIER summary lint <the CR's folder>` before it ends its turn, reads the gap, and closes it with `summary set` (a title and a summary it writes itself; `--unchanged` when the summary still holds). The Chief of Staff closes what is left. Labels and groups are the user's: set on the user's word only. A late summary blocks nothing.

## Planning

The **planning folder** is where chantier writes everything: `<project>/.agents/changes/` (in-project, the default) or `<surface>/projects/<name>/changes/`. The **planning surface**, when the plan is not in the code repository, is a git repository of its own, one folder per project (`projects/<name>/`: `project.md`, with the project, its remote and `- Archive in the PR: yes|no`, `no` when absent; `checkout.yml`, with `repo:` and `worktrees:`, paths relative to that folder, `.repo/` and `.worktrees/` there by default; `changes/`), always worked on its default branch, never in a worktree (only the code gets worktrees); its `AGENTS.md` holds its own rules. The **archive** is the CR's folder in `5-archives/`, with a `delivery.md` (the PR, the merge time, whether the archive is also in the PR); when the project asks, a cleaned copy also goes in its PR. The **Change Specification** (`03-change-spec.md` by default) says what the CR must do, how it is proved and what it leaves out, complete and self-contained: a reader with only this file knows what to do.

## Batch

The CRs active at one time under one steering session. It has a number only, `batch-<n>`; `--batch` takes `<n>` or `batch-<n>`. One batch at a time, from `open` to the user's `close`. Modes: parallel, series, stack (each CR on the previous one's branch, the top PR validates) and direct (`open --direct`: the Chief of Staff steers).

States, and only these words: **running**, **paused**, **closed**. `open` creates it running (paused when it holds no CR, with no cost, retro or close offer at that pause): its CRs are taken by Drivers on the free slots, worked, handed back, merged by the user, or dropped. When every CR is merged or cancelled the CLI removes the merged CRs' worktrees and branches and pauses it; the steering session writes the retro, the Chief of Staff offers it, and `close --yes` runs only on the user's yes. A paused batch takes `order add`; the first `take` (or `order qa`) runs it again, and it pauses again at its end with the cost to date. It stays paused, however long, until the user's close.

Slots (`batch.slots`, 4 by default, set in a `chantier.yaml` or on the board's Configuration page; `--slots` wins at `open`) bound the Drivers at once; the budget is the dollars the Foreman's session and its agents may spend; a round is one Coder pass with its reviews, three per CR unless the user grants more. The CLI refuses what passes a limit (exit 5).

A CR stands on another only by a dependency: a real one (`depends.json`), or a chain the Foreman decided or the plan proposed and the user's go approved (`order after`). A CR's `depends.json` (`{"after": ["<slug>"]}`, a slug being a folder's name without its number) is written with the Chief of Staff during the grill, only when a CR needs the result of another, never for a shared file. `open` and `order add` record `after` as CR ids (a slug already merged is met, not recorded; an unknown slug, a malformed file or a cycle exits 2); `order after` changes it.

A **release CR** releases the batch's work by the project's own procedure and waits for every other CR; the merge of its PR is the go for the irreversible steps (with no release PR, the user's `order confirm`, once the others are merged). A **fix CR** is one the release found it needs, its `fix-<n>.md` its specification.

The **Griller** keeps the inbox and the backlog with the user (file, triage, grill, answers, specification) and may prepare work for the Chief of Staff: it opens no batch and steers nothing. It is usually short; the board can start one, headless, on one CR. A session's title is `[<code>] 💬 Project · <role>`, the Foreman's `[<code>] ⚙️ Project · Foreman (Batch <nn>)` (`help titles`). To the user a claim's number is the Foreman's number in its batch, never the word epoch; the flag stays `--epoch`.

`STATUS.md` and `STATUS.json` (the planning folder, `4-batch/`, each CR) are written by the CLI alone, with `batch.json` and `events.jsonl`. A Driver's `phase <cr> <phase> [detail]` records what it is doing (`coder r2`, `gate scenario`, `CI`); a working CR's `STATUS.json` holds it as `phase`, shown by the board, `status` and the pane.

## `$CHANTIER`

The CLI, as your prompt gives it. It runs no git command that changes anything (it reads the head, the remote and the status to say what is off) and no forge command beyond `forge-stack` and the reads of `ship`, `take`, `round` and `handoff`. The agents create worktrees, commit, rebase, push, open, watch and merge PRs, clean up and fast-forward the main checkout after a recorded merge, with `git`, `gh` and `glab`. Exit codes: 0 ok, 1 usage, 2 precondition (the message says which), 3 a stale Foreman (a later one claimed the batch), 4 external (git, a gate; a head that moved), 5 the budget (`take`, `round`) or the round limit (`round`). A CR argument takes its bare number (`<n>`, `CR-<n>`, `cr-<n>`). Heads are full 40-character SHAs (7 only for display; an older short record matches by prefix). The long gate is `gate <cr> <name>`: one name per argument, never a `;` or `&&` chain, from `long_gate.commands` in the code repository's root `chantier.yaml` (a surface's are ignored); it stops at the first failure and has passed at a head when the last run there passed every command and the head did not move; its log's first line names the CR, branch and full SHA, its last the result. The Verifier's `verdict <cr> VERIFIED` or `verdict <cr> "NOT VERIFIED"` is recorded at the head it verified; the last at a head decides. `handback <cr> ready` needs a passed gate and a `VERIFIED` verdict at the PR's head (or carried over a clean rebase), committed, clean and pushed; `--no-gate "<the rule>"` waives the gate check only, for a project whose rules declare none, exempt this CR, or name a pipeline job as the long gate, and the steering session checks it. Output is ten lines at most, except `status`, `take`, `round`, `handoff`, `rules`, `log`, `cost`, `asks`, `pause`, `close`, `playbook`, `preflight` and `order qa`.

## Starting an agent

The parent starts an agent by its host's means (the host's file gives the tool and the agent's name). Agent and model come from the playbook, which only the CLI reads, merges, validates and resolves: the plugin's defaults, then optional `chantier.yaml` files (which may also carry `prices:` for models the built-in table lacks, `ci:` with `beside_gate: true`, and `hosts.<host>.timing`, printed as `ci:` and `timing:` lines). Permissions are scoped to session, project and effect: a started agent inherits only its role's, never merge or publication permission.

- Pass the agent and the model exactly as `$CHANTIER` printed them (`playbook`, `playbook --batch`, or the `team:` lines of `take`, `round`, `handoff`): never typed from memory, completed or "corrected", never an effort. No model printed: pass none.
- `agent=(generic)` printed: start the host's generic agent, pass the model as printed, and put the printed contract lines after the opening lines. A parent never chooses it.
- The Chief of Staff reads `playbook` for its subagents, the Foreman (or the Chief of Staff, direct) `playbook --batch <batch>` for a Driver, a Driver the `team:` lines for a worker. The project's rules (`$CHANTIER rules`) rank above every card: follow them as written for commits, PRs, tests, CI, evidence and releases; where they are silent, your card holds.
- A start the host refuses with a model is reported with its exact text: never retried without the model or with another.
- A `Needs:` line is copied as printed; an agent lacking a skill or tool says so in a note and works without it, never without `$CHANTIER`.
- An extra review step (a review of the project's `AGENTS.md` `chantier` section) gets no printed opening lines: the Driver writes its prompt (`help cr-review-step`), with `Read <skill>/references/review-step.md;` and a `Your review:` line.

The prompt is the whole brief; it names the card the role reads:

```text
chantier <role> for <cr> "<title>" of batch <batch>, in the project <root>.
<the lines take, round or handoff print under "opening lines", copied unchanged>
CLI ($CHANTIER): <the `cli:` line of take, round or handoff>
<the other lines they printed: the specification, the folder, the worktree and its base, the PR, the rounds, the grant, the notes>
writes: <worktree>; <CR folder>
Rewrites: <the scope>
Steering: <who steers> <how to reach it>
Team: <the `team:` lines, as printed, then the review steps>
Needs: skills <…>; tools <…>
Note: <why the CR is with it, or the round's brief>
```

`writes:` holds bare absolute paths: a worker's is copied from the `worker writes line` printed, a Driver's follows the table below. A Driver's names the CR folder as `folder:` prints it and the archive as `<worktree>/<archive path>`. On Claude Code the plugin starts such an agent in its first folder (a CR Driver in its worktree, or the project's root while the worktree does not exist yet) and refuses its Write, Edit, NotebookEdit and a shell write it can see outside the folders named; a prompt without the line is not guarded. `Steering:` holds the means of the host's row "A Driver messages its steering session" (`hosts/claude-code.md` or `hosts/copilot.md`), with the session id for the record; workers get none.

A Driver's prompt (the table below):

- Every one holds the opening lines, `CLI ($CHANTIER):`, the lines its command printed, `Steering:`, `Needs:` when the playbook gives the role some, and `Note:`; `writes:`, `Team:` and `Rewrites:` only where the table says so, and `writes: none` means no line (the guard would refuse the Driver's worktree writes).
- `Rewrites:` sits between `writes:` and `Steering:`: the rebase and the push the Driver may run, and their scope; the CLI prints its text, copied as it is.
- `take`, `take stack` and `order qa` print this skeleton: copy it whole, fill each `<...>` left, add no line and drop none.

An agent whose prompt does not start with its role's first line answers "I run inside a chantier batch only. My prompt must start with `<its first line>`; a message to me gets this same answer: start a new agent with that line." and stops; it answers every later message so and does nothing else, even when a message resumes it (a `killed` task is never resumed). The parent starts one new agent with that line, never a message to the refused one and never a variant.

| Role | First line |
| --- | --- |
| Drivers and workers (CR driver, coder, verifier, inspector, debugger, conflict-resolver, release-driver, investigator) | `chantier <role> for <cr> "<title>" of batch <batch>, in the project <root>.` |
| QA driver | `chantier qa-driver for <folder> of batch <batch>, in the project <root>.` |
| Stack driver | `chantier stack-driver for the stack of batch <batch>, in the project <root>.` |
| Demo explorer, and the Chief of Staff's other subagents | `chantier <role> for the Chief of Staff of batch <batch>, in the project <root>.` |
| Spec-writer | `chantier spec-writer for the Chief of Staff, in the project <root>.` |
| Spec critic | `chantier spec-critic for the Chief of Staff, in the project <root>.` |
| Retro critic | `chantier retro-critic for the Chief of Staff, in the project <root>.` |

A subagent of the Chief of Staff writes its files in a CR's folder (or a folder its brief names) with a number prefix (`04-report.md`), except the names a card fixes (`03-change-spec.md`, `delivery.md`, `STATUS.md`, `retro.md`, the `work/` files the cards name); the host refuses some unprefixed names (`report`, `summary`, `findings`, `analysis`) on the name alone, and no allow rule fixes it. It never implements: no commit, push or PR. The Spec-writer and the Spec critic are subagents of the Chief of Staff or a Griller, outside any batch: each reads its own card, never `driver.md`, its brief gives the CR folder, and it takes no slot or budget (the Spec-writer writes `03-change-spec.md` there; the critic writes nothing). The Retro critic is a subagent of the Foreman or the Chief of Staff: its brief gives the points and their evidence files; it writes nothing and takes no slot, and its cost counts in the batch when a batch's steering session starts it.

An agent that ends before its part is done (any agent, any parent) is restarted once from the recorded state (`handoff`, `log`, the CR's notes, the worktree's commits, the folder's files), after the parent records the cause (`note <cr> "restart: <cause>"`; for a spec-writer or critic, its `work/specifying` line; for a retro critic, in the parent's own words in its turn): `stopped from outside: <text>`, `host failure: <exact text>`, `refused first line`, `reply out of format: <what>`, `switch to Foreman mode`, `switch to direct mode`, or a cause `help lost-restart` names (`context`, a proven death, a new epoch, a silent end). One exception: a Driver stopped from outside is restarted at each such stop, which counts toward nothing (`help lost-outside`); other agents and other causes keep "once". A restart is one way, a message that resumes the agent where a card names it or a new start, never both; the parent starts nothing while the agent may still run. A worker ended by a host failure gets one new worker with the same brief and no new `round`.

### A Driver's prompt

This table is the only source of which template lines each Driver's prompt holds. The CLI reads it.

| Driver | Started after | Card | `writes:` | `Team:` | `Rewrites:` |
| --- | --- | --- | --- | --- | --- |
| `cr-driver` | `take <cr>`, a CR of kind `change` or `fix` | `driver.md` | the CR folder, then the absolute archive path when `take` prints one | yes | own branch |
| `release-driver` | `take <cr>`, a CR of kind `release` | `driver.md` | none | none | own branch |
| `stack-driver` | `take stack` | `driver.md` | none | yes | batch branches |
| `qa-driver` | `order qa` | `driver.md` | none | none | none |

## Escalation

An agent's model is fixed at its start. Escalation is a new agent for the same task on the model the role's `escalation` names, as `playbook` prints it (`escalate:` line, or `escalation=` on a `team:` line), passed as printed.

- Only `coder`, `debugger` and `conflict-resolver` escalate. Drivers never do (a failed restack escalates the stack driver's `conflict-resolver`; the stack driver keeps the batch's model); nor do the judging agents (`inspector`, `verifier`, `investigator`, `spec-writer`, `spec-critic`, `retro-critic`, `demo-explorer`): a new one runs on its own model.
- The only four triggers, and who acts:
  - a `blocked rounds:` hand-back, any failure: once the user grants rounds, the CR's next Driver is told `escalate: rounds` and starts each new round's Coder on the escalation model (a grant with a `rounds exception:` note keeps the model); escalation never grants a round.
  - two `blocked` hand-backs of one CR that show trouble in the work (`refused`, `infra:` after its re-runs, `driver ended twice`, `stopped`, `rounds:` not under the exception, `fix:`; never `question:`, `approval:`, `merge:`, `waits:`, `budget:` or a stop from outside), when the row above did not escalate: the Foreman (direct: the Chief of Staff), from `log <cr>`, runs `take <cr> --note "escalate: blocked twice: <reasons>"`; a CR with no rounds (release, QA order, `fix:`) goes to the user's question.
  - a red check the Debugger could not explain (its `diagnosis.md` names no cause with evidence): its Driver starts a new `debugger` given that file.
  - a conflict the resolver could not settle (two product intents stay a user question): its Driver starts a new `conflict-resolver` given `conflicts.md`.
  - a Debugger fix that fails again, or a stack driver's red check needing code (`anomaly`), ends in CR hand-backs.
- Said, never silent: before it starts, record `note <cr> "escalated: <trigger>; <role> on <model as printed>"`.
- Once per CR, then the user: a CR with an `escalated:` note made for that CR (not a stack-wide one written on each CR) never escalates again nor swaps back; if it fails again it stays `blocked`, is not taken again, and goes up as a question (one more round, drop it, another approach), with no further round without the answer; so does a CR with no rounds blocked twice.
- No escalation printed (`escalate: (none on this host)`, or no `escalation=`): the trigger takes its usual route, the note says `no escalation on this host`; no stop, no look-alike.
