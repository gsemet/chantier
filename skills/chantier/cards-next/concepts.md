# Concepts

## Words

- **Ready** (the status): the stored status `ready` in `batch.json`, set by `handback <cr> ready <link>`. A token the CLI turns into the three words below; no person reads it alone, but in the stack rows of `take stack` and `stack` (`ready, PR draft (#251)`).
- **Ready to merge** (🟢): handed back ready, the PR out of draft on the forge as the record holds it (`ship`, `stack --out-of-draft`, never ahead of the forge); in a stack batch every CR under it ready to merge too (for a CR the stack driver placed, those below it in the stack's order; for one not placed, the CR whose branch is its PR's base, as `ship` last read it, none when that base is the default branch); outside a stack the PR's base is the default branch. The user may merge it at any moment, and the top of a stack ready to merge makes the whole stack mergeable. "Mergeable" names only these, never a draft, whatever the forge's field says. The mergeable part of a verified stack (`help stack-checks`) merges from its top PR in one action (GitHub) or one PR at a time from the bottom (GitLab: one MR at a time), the user's choice at each merge; a draft on top is not mergeable, and a PR below the top had heavy CI only at the top unless the user asked for it at its head.
- **PR in draft** (🟤): handed back ready, the PR open and a draft, or out of draft over a CR that is not; its hand-back line names its draft state and the CR it waits on (first the CR its PR's base branches from, else a CR below, its dependency, the release's top or its turn out of draft), and nobody merges it. Any other CR's PR (a series, a stack not yet made or being changed) is a draft on the forge too, and no one merges it.
- **Ready locally** (🟣): handed back ready with no PR yet (rare). A draft's icon is its CR's state, never "draft" by default: 🟡 rebasing or at a gate, 🟠 waiting for another CR's work, 🔴 blocked.
- A release PR is merged by the user, last of the batch (in a stack from its top PR with the rest; in a series after the rest, from the bottom up). The steering session merges only under the grant, never a stack that holds it; GitHub's asynchronous merge takes every open PR below, so it merges there only with nothing open below (`help merge-github`).
- **`3-ready`**: the folder of the CRs that wait for the next batch (never "the ready CRs").
- **Lease**: a short claim on a unit (a CR, the stack, a QA folder), renewed by the Driver's commands.
- **Wait**: a typed wait of a CR (`answer`, `approval`, `pipeline`, `merge`), recorded and cleared with `wait`.
- **Hold**: `order slots --note 0`, no new Driver. "Pause" names only the batch state.
- **Tracker issue**: an issue of the project's tracker (GitHub, GitLab, Jira…) a CR comes from, named by an `issue: <link>` line under the title of its `01-intent.md` and `03-change-spec.md`. The CR's PR names it in `## Issues References` ([PR template](pr-template.md)), in the project's form, else the template's default with a closing verb (`Closes #<n>`, `Closes <KEY>-<n>`); a project rule may differ. No agent closes or reopens an issue by hand. Only the Chief of Staff posts on an issue, only what the user approved for that ticket; a comment carries no CR number, batch, agent role or cost.
- **Host and default matrix**: the cases a CR proves one by one, because what it changes behaves differently per host (Claude Code, Copilot) or with a shipped default and a configured value: one cell per combination that applies, a host's refusal included. Each cell gives the result it must show and the real flow that proves it (the CLI's own commands from a real state, no user file for a shipped-default cell); a record or configuration built by hand proves no cell. The specification names the matrix in its evidence; a CR with neither dependency has none. The Inspector checks each cell has a test or a check in the diff; the Verifier proves each at the committed head.
- **Seat**: `seat.json`, the repository's Chief of Staff session.
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

The folder moves, it is never copied: `1-inbox/`, `2-backlog/P1…P4/`, `3-ready/`, then in the running batch `4-batch/1-pending/`, `2-actives/` (taken by a Driver), `3-done/` (merged, until `close`), then `5-archives/<YYMMDD-HHMM>-<number>-<slug>/` or, after `order drop`, `6-trash/`. A CR taken out of the batch goes to the backlog or `3-ready`, never the inbox, with `formerly.json`; a release or fix CR leaves only to the trash. `triage <item> --inbox` sends an item back to the inbox; `restore` brings a trashed one back to the inbox, on the user's word only.

**A CR's folder holds its work.** Whatever an agent makes for a CR (a prototype, a script, a test, a benchmark, a study, a research note, a screenshot it keeps, a plan) is written in that CR's folder, in the place the tree gives, never in the host's scratchpad or a temporary folder: this ranks above the host's own instruction to use its scratchpad, which stays the host's outside any CR's work. A sub-folder is created only when its first file is written. A new prototype version is a new folder (two digits and a kebab-case name) and the earlier ones stay; its README.md says what it tries, the command that runs it again and what it needs; its own scripts go in it, not in `experiments/`, whose files take numbered names (`01-benchmark.md`). Never in a CR's folder: secrets, personal data, large binaries that are not the retained prototype (name where they are), the agent's memory or the host's settings (`~/.claude/`). Raw logs stay in `work/gates/` or a `*.log`, a Verifier's scratch project in `work/scratch/`, a downloaded CI artifact in `work/scratch/artifacts-<run id>/`. What only the conversation holds (a subagent's reply, a pasted image) is lost unless an agent writes it there.

A CR is named with its number and short slug together ("CR-142 grill-rules"); an item with no number is named by its slug. In a CR's PR the name appears only in the Internal references section, unless the project's rules say otherwise.

## A CR's summary

`summary.json` in the CR's folder: its title (one line, at most 72 characters), a summary of what the CR means now (one line of plain text: its state of grill or delivery, not its progress in a batch), its origin (an issue's tracker and reference from the `issue:` line, or verbal), its labels and group, and the checksums of the covered files (`intake/*.md`, `01-intent.md`, `02-answers.md`, `03-change-spec.md`, `delivery.md`; not `STATUS.md`, `work/` or `evidence/`). The board reads it. A summary is a judgment: an agent writes it, never the CLI. An agent that writes a covered file runs `$CHANTIER summary lint <the CR's folder>` before it ends its turn, reads the gap, and closes it with `summary set` (a title and a summary it writes itself; `--unchanged` when the summary still holds). The Chief of Staff closes what is left. Labels and groups are the user's: set on the user's word only. A late summary blocks nothing.

## Planning

The **planning folder** holds the changes (`.agents/changes/`, or the project's folder in an external planning surface); the **planning surface** is the repository that holds it when it is not the code repository. The **archive** is a CR's cleaned folder, in its PR when the project asks for it, else in `5-archives/`. The **Change Specification** (`03-change-spec.md`) says what the CR must do, how it is proved and what it leaves out.

## Batch

The CRs active at one time under one steering session. It has a number only, `batch-<n>`; `--batch` takes `4` or `batch-04`. One batch at a time, from `open` to the user's `close`. Modes: parallel, series, stack (each CR on the previous one's branch, the top PR validates) and direct (`open --direct`: the Chief of Staff steers).

States, and only these words: **running**, **paused**, **closed**. `open` creates it running (paused when it holds no CR). When every CR is merged or cancelled the CLI removes the merged CRs' worktrees and branches and pauses it; the steering session writes the retro, the Chief of Staff offers it, and `close --yes` runs only on the user's yes. A paused batch takes `order add`; the first `take` runs it again.

Slots (`batch.slots`, 4 by default) bound the Drivers at once; the budget is dollars; a round is one Coder pass with its reviews, three per CR unless the user grants more. The CLI refuses what passes a limit (exit 5).

A CR's `depends.json` (`{"after": ["<slug>"]}`) is written only when a CR needs the result of another, never for a shared file; `order after` changes it.

A **release CR** releases the batch's work by the project's own procedure and waits for every other CR; the merge of its PR is the go for the irreversible steps. A **fix CR** is one the release found it needs.

The **Griller** keeps the inbox and the backlog with the user: it opens no batch and steers nothing. A session's title is `[<code>] 💬 Project · <role>`, the Foreman's `[<code>] ⚙️ Project · Foreman (Batch <nn>)` (`help titles`). To the user a claim's number is the Foreman's number in its batch, never the word epoch; the flag stays `--epoch`.

`STATUS.md` and `STATUS.json` (the planning folder, `4-batch/`, each CR) are written by the CLI alone, with `batch.json` and `events.jsonl`. A Driver's `phase <cr> <phase>` records its step.

## `$CHANTIER`

The CLI, as your prompt gives it. It runs no git command that changes anything and no forge command beyond `forge-stack` and the reads of `ship`, `take`, `round` and `handoff`. The agents create worktrees, commit, rebase, push and open and merge PRs with `git`, `gh` and `glab`. Exit codes: 0 ok, 1 usage, 2 precondition, 3 stale Foreman, 4 external (git, a gate), 5 budget or rounds. A CR argument takes its bare number (`165`, `CR-165`). Heads are full 40-character SHAs. The long gate is `gate <cr> <name>`: one name per argument, from `long_gate.commands`; it has passed at a head when the last run there passed and the head did not move. `handback <cr> ready` needs a passed gate and a `VERIFIED` verdict at the PR's head, committed, clean and pushed; `--no-gate "<the rule>"` waives the gate check only, for a project whose rules name none or name a pipeline job. Output is ten lines at most, except `status`, `take`, `round`, `handoff`, `rules`, `log`, `cost`, `asks`, `pause`, `close`, `playbook`, `preflight` and `order qa`.

## Starting an agent

The parent starts an agent by its host's means (the host's file gives the tool and the agent's name). Agent and model come from the playbook, which only the CLI resolves.

- Pass the agent and the model exactly as `$CHANTIER` printed them (`playbook`, `playbook --batch`, or the `team:` lines of `take`, `round`, `handoff`): never typed from memory, completed or "corrected", never an effort. No model printed: pass none.
- `agent=(generic)` printed: start the host's generic agent, pass the model as printed, and put the printed contract lines after the opening lines. A parent never chooses it.
- The Chief of Staff reads `playbook` for its subagents, the Foreman (or the Chief of Staff, direct) `playbook --batch <batch>` for a Driver, a Driver the `team:` lines for a worker.
- A start the host refuses with a model is reported with its exact text: never retried without the model or with another.
- A `Needs:` line is copied as printed; an agent lacking a skill or tool says so in a note and works without it, never without `$CHANTIER`.
- An extra review step (a review of the project's `AGENTS.md` `chantier` section) gets no printed opening lines: the Driver writes its prompt (`help cr-review-step`), with `Read <skill>/references/review-step.md;` and a `Your review:` line.

The prompt is the whole brief:

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

`writes:` holds bare absolute paths: a worker's is copied from the `worker writes line` printed, a Driver's follows the table below. On Claude Code the plugin refuses a Write or Edit outside the folders named, and a prompt without the line is not guarded. `Steering:` holds the means of the host's row "A Driver messages its steering session" (`hosts/claude-code.md` or `hosts/copilot.md`), with the session id for the record; workers get none.

A Driver's prompt (the table below):

- Every one holds the opening lines, `CLI ($CHANTIER):`, the lines its command printed, `Steering:`, `Needs:` when the playbook gives the role some, and `Note:`; `writes:`, `Team:` and `Rewrites:` only where the table says so, and `writes: none` means no line (the guard would refuse the Driver's worktree writes).
- `Rewrites:` sits between `writes:` and `Steering:`; the CLI prints its text, copied as it is.
- `take`, `take stack` and `order qa` print this skeleton: copy it whole, fill each `<...>` left, add no line and drop none.

An agent whose prompt does not start with its role's first line answers "I run inside a chantier batch only. My prompt must start with `<its first line>`; a message to me gets this same answer: start a new agent with that line." and stops; it answers every later message so. The parent starts one new agent with that line, never a message to the refused one.

| Role | First line |
| --- | --- |
| Drivers and workers (CR driver, coder, verifier, inspector, debugger, conflict-resolver, release-driver, investigator) | `chantier <role> for <cr> "<title>" of batch <batch>, in the project <root>.` |
| QA driver | `chantier qa-driver for <folder> of batch <batch>, in the project <root>.` |
| Stack driver | `chantier stack-driver for the stack of batch <batch>, in the project <root>.` |
| Demo explorer, and the Chief of Staff's other subagents | `chantier <role> for the Chief of Staff of batch <batch>, in the project <root>.` |
| Spec-writer | `chantier spec-writer for the Chief of Staff, in the project <root>.` |
| Spec critic | `chantier spec-critic for the Chief of Staff, in the project <root>.` |
| Retro critic | `chantier retro-critic for the Chief of Staff, in the project <root>.` |

A subagent of the Chief of Staff writes its files in a CR's folder (or a folder its brief names) with a number prefix (`04-report.md`), except the names a card fixes; the host refuses some unprefixed names (`report`, `summary`, `findings`, `analysis`). It never implements: no commit, push or PR. The Spec-writer and the Spec critic run outside any batch and take no slot; the Retro critic writes nothing and takes no slot.

An agent that ends before its part is done is restarted once from the recorded state, after the parent records the cause (`note <cr> "restart: <cause>"`): `stopped from outside`, `host failure: <text>`, `refused first line`, `reply out of format: <what>`, a mode switch, or a cause the Foreman's card names. One exception: a Driver stopped from outside is restarted at each such stop, which counts toward nothing (`help lost-outside`); other agents and other causes keep "once". A restart is one way, a message that resumes the agent where a card names it or a new start, never both; the parent starts nothing while the agent may still run. A worker ended by a host failure gets one new worker with the same brief and no new `round`.

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

- Only `coder`, `debugger` and `conflict-resolver` escalate; Drivers and judging agents never do.
- Triggers: a `blocked rounds:` hand-back (the next rounds' Coder); two `blocked` hand-backs of one CR that show trouble in the work; a red check the Debugger could not explain; a conflict the resolver could not settle.
- Said, never silent: before it starts, record `note <cr> "escalated: <trigger>; <role> on <model as printed>"`.
- Once per CR, then the user: a CR with an `escalated:` note that fails again stays `blocked` and goes up as a question (one more round, drop it, another approach).
- No escalation printed: the trigger takes its usual route, and the note says `no escalation on this host`.
