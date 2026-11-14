# Concepts and rules

Every role reads this file: the words the team shares, the boundaries, and how an agent is
started.

## Words

- **Pull request (PR):** a merge request on GitLab.
- **Ready to merge:** a PR whose CR was handed back `ready` and whose base is the default branch,
  in every mode: the user may merge it on its own at any moment, a stack batch is no exception.
  In a stack batch, a stack verified on the forge (the five checks of **Stack**, below) is a
  second way: the user merges it in one action from its top PR, or its PRs one at a time from the
  bottom, the user's choice made merge by merge, never fixed at the go. Any other CR's
  PR is a draft on the forge (a series, a stack not yet made on the forge, a stack being
  changed): it says so itself, and no one merges it. A release PR follows the same rule: the user
  merges it, last of the batch (in a stack, the stack's top PR, with the rest in the same action;
  in a series, after the rest, from the bottom up); the steering session merges it only under the
  grant, and never a stack that holds it.
- **Tracker issue:** an issue in the project's tracker (GitHub, GitLab, Jira…) that a CR comes
  from, named by an `issue: <link>` line under the title of the CR's `01-intent.md` and
  `03-change-spec.md`. The CR's PR names it in its `## Issues References` section
  ([PR template](pr-template.md)), in the form the project's rules give, else the template's
  default. The default carries a closing verb (`Closes #<n>`, `Closes <KEY>-<n>`), so the issue
  closes at the merge as the tracker's integration reads it; a project rule may say otherwise. No
  agent closes or reopens an issue by hand. Only the Chief of Staff posts on an issue (a comment,
  a plan, a demo), and only what the user approved for that ticket; a comment carries no CR number,
  batch, agent role or cost.
- **Change Request (CR):** one change, from the request as it arrived to one pull request. It is
  a folder in a stage of the planning folder:

  ```text
  <slug>/
  ├── intake/              ← the raw request as received; never edited
  ├── 01-intent.md         ← the request, summarised and analysed
  ├── 02-answers.md        ← every answer the user gave about the CR, whoever asked
  ├── 03-change-spec.md    ← the Change Specification
  ├── summary.json         ← title, summary, origin, labels, group; through $CHANTIER summary, never by hand
  ├── STATUS.md, STATUS.json ← where the CR stands; the CLI writes them, never by hand
  ├── evidence/            ← other proof kept with the CR (the Verifier's: work/verifier/evidence/)
  └── work/                ← written while it runs: notes, gate logs, the PR body
  ```

- **A CR's summary:** `summary.json` in the CR's folder: its title (one line), a summary of what
  the CR means now (one line of plain text; its state of grill or delivery, not its progress in a
  batch), its origin (an issue's tracker and reference from the `issue:` line, or verbal), its
  labels and its group, and the checksums of the covered files at the time it was written. The
  covered files are `intake/*.md`, `01-intent.md`, `02-answers.md`, `03-change-spec.md` and
  `delivery.md`; not `STATUS.md`, `work/` or `evidence/`. The board reads this JSON. A summary is a
  judgment: an agent writes it, never the CLI. An agent that writes a covered file of a CR runs
  `$CHANTIER summary lint <the CR's folder>` before it ends its turn, reads what the gap names, and
  closes it with `summary set` (a title and a summary it writes itself, one line each, plain text;
  `--unchanged` when the summary still holds). The Chief of Staff closes what is left (its card
  says when). Labels and groups are the user's: an agent sets them on the user's word only. A late
  summary blocks nothing.
- **Planning folder:** where chantier writes everything: `<project>/.agents/changes/` (in-project,
  the default) or `<surface>/projects/<name>/changes/` (external). A CR's folder, the stages, the
  STATUS files and the seat are in it. Its `.gitignore`, written by the CLI, keeps the batch's own
  files (`batch.json`, `events.jsonl`, `brief.md`, STATUS, locks, `.batch-number`, `seat.json`) and
  the detailed logs (`work/gates/`, `*.log`) out of git: a raw log goes in such a file, never in a
  published one. The rest of a CR's folder is pushed with the surface. So are the batches' records:
  each batch leaves `5-archives/batches/batch-NN.json` (for a UI; written by `open` as `running`,
  completed by `close`) and `batch-NN.md` (for a person: the Completion table, the cost, the retro).
  The next batch number is read from these records.
- **Planning surface:** a git repository of its own, one folder per project, always worked on
  its default branch (never in a worktree; only the project's code gets worktrees):
  `projects/<name>/` holds `project.md` (the project, its remote, `- Archive in the PR: yes|no`,
  `yes` when absent), `checkout.yml` (`repo:` and `worktrees:`, paths relative to the project's
  folder; defaults `.repo/` and `.worktrees/` there) and `changes/` (the planning folder). The
  surface's `AGENTS.md` holds its own rules, its sync first. The project's **clone** is the
  "main checkout" for git only (`git -C <clone>`): no session runs in it. The project's
  `AGENTS.md` may point to its surface with one line, `- planning: <url>, projects/<name>`, which
  the Chief of Staff reads and the CLI does not. With a surface, every `$CHANTIER` carries
  `--project <the project's folder>`; a `cli:` line says so. Full account:
  [planning modes](../../../docs/planning-modes.md).
- **Archive:** the CR's folder in `5-archives/`, with a `delivery.md` (the PR, the merge time,
  whether the archive is also in the PR). In external mode the Driver also commits a cleaned
  archive (`intake/`, `evidence/`, `01`–`03`, `delivery.md`, `STATUS.md`; no `work/`) in its PR,
  when `take` prints `archive: in the PR at <path>`.
- **Change Specification:** what the CR changes, complete and self-contained: a reader with only
  this file knows what to do. By default `03-change-spec.md`.
- **Lifecycle:** the folder moves, it is never copied: `1-inbox/` (filed) → `2-backlog/P1…P4/`
  (the user prioritized it) → `3-ready/` (waiting for the next batch) →
  `4-batch/1-pending/<number>-<slug>/` (in the batch, not started) → `2-actives/` (taken by a
  Driver) → `3-done/` (merged, until `close`) → `5-archives/<YYMMDD-HHMM>-<number>-<slug>/`
  (after `close`, the time of the merge) or `6-trash/…` (dropped, with its work; it returns to
  the inbox only on the user's word, by `restore <6-trash/item> [--slug <name>]`, without its
  date or its batch number, and with a line `formerly CR-<n> of batch-<m>`).
- **`3-ready`:** the folder of the CRs that wait for the next batch, specified or automatable (no
  specification: the Driver works from the request alone), moved there on the user's word. It is
  not "ready to merge": a CR handed back `ready` sits in `4-batch/2-actives/`, never in
  `3-ready`. Write the folder `3-ready`, never "the ready CRs".
- **A CR's name:** when an agent names a CR to a person or in a report (messages, report tables,
  asks; in a CR's PR only the description's Internal references section, never the title or the
  body's text, unless the project's rules say otherwise), it gives the number and the short slug
  together, like "CR-142 grill-rules", never one alone. An item with no number yet (inbox,
  backlog) is named by its slug. The CLI's own outputs are unchanged.
- **Batch:** the CRs active at one time under one steering session (a Foreman, or the Chief of Staff in direct mode). It has no name, only a number: `batch-<n>`
  (`<n>` on two digits, counting all batches), its own files in `4-batch/` (its CRs in the
  three state folders there), and `--batch`
  takes the number, `4` or `batch-04`. One batch at a time, from `open` to the user's `close`; new
  work joins it through the steering session (`order add`, which on a paused batch leaves it paused, any number of times: the first
  `take` sets it running again, `pause` runs again at the end, and is refused on a batch already paused;
  on a running direct batch `order add` queues the CR too, taken when a slot frees, and `order qa`
  is refused; `order qa` on a paused batch sets it running at once; see **Batch lifecycle**). `close` refuses while anything
  runs, on a reopened batch too: a CR not merged or cancelled, an open order, a stack agent, or a session file of the
  Foreman or of any of its agents (on a direct batch, of the Chief of Staff's own transcript: its subagents only) written in the last 5 minutes (on Copilot the session file's
  time; `not measured` refuses). A batch has one of three **modes**, set by
  `open --mode parallel|series|stack` and shown by `status`. **Parallel** (the default, when the
  user names none): every CR with no open dependency starts from the default branch at once and
  its PR is on the default branch; a CR with a dependency starts only once that dependency is
  `ready` (`take` refuses it until then), on the branch of its last dependency still open, else on
  the default branch (see **Dependencies**), and its PR stays a draft on that branch until the
  dependency merges; the first one ready wins, and the user merges in the order things become ready unless
  told otherwise; after each merge, every PR still open is rebased onto the default branch and
  its checks run again. **Series**: the CRs have a precise order, the one given to `open` (`order
  add` puts a CR on top); the next CR starts once the previous one is `ready`, from the previous
  CR's pushed branch, and its PR is a draft; once the previous one merges, the next is rebased
  onto the default branch and turns ready; `order mode --note stack` switches the series to a
  stack, on the user's word. **Stack**: parallel, with a stack driver: every CR with no open
  dependency starts at once, on the default branch; a CR with a dependency starts only once that
  dependency is `ready` (`take` refuses it until then), on the branch of its last dependency still
  open, else on the default branch (see **Dependencies**), and the stack driver puts the PRs each
  on the previous one (`stack` marks the CRs it orders; `ship` records a stacked CR's place in the stack,
  and the start base for any other). Once every PR is ready, the stack driver makes one native
  stack on the forge (the `gh stack` extension, or `$CHANTIER forge-stack create` when the user
  declined the extension); the user merges it in one action from the top PR, or one PR at a
  time from the bottom, the release commit last. A chain of PRs based on each other is not a stack. On GitHub a stack is the forge's native
  stacked-PR stack; on GitLab the stack stays a chain, as it was. **Stack ready** means five
  checks hold on the forge (`$CHANTIER forge-stack show` prints the failing ones): the stack is
  open; it holds every open PR of the batch's stack, and no other; in the order of `take stack`,
  bottom first; none is a draft; the release PR, when the batch has one with a PR, is on top.
  **Inserting a change into a ready stack:** before anything else every PR that will sit above the
  new one goes back to draft; then the new CR's PR is inserted at its place, the PRs above are
  restacked on it, the stack is rebuilt on the forge (`$CHANTIER forge-stack rebuild`) and
  verified, and only then the PRs above turn ready again; the release PR stays on top and its
  notes name the new change (the steps are the stack driver's, in [driver](driver.md)). A CR in
  the middle of a ready stack that goes back for a new round puts the PRs above it to draft first,
  the same way. A CR stands on another
  only by a dependency: a real one (`depends.json`) or a chain the Foreman decided, or the plan
  proposed and the user's go approved (`order after`). A fix CR sits outside a series and a stack,
  on the default branch. A release CR is
  their top: it starts on the top CR's branch once every other CR is ready and the top branch
  holds them all, and its PR is the top PR. When a stack merges only in part, what remains forms another stack in the same batch, restacked on
  the default branch (one restack for one merge action of the user, none when the whole stack merged). Each CR is named a branch
  `chantier/<batch>/<cr>-<slug>` and a worktree `<repo>.worktrees/<batch>-<cr>` (`<worktrees>/<batch>-<cr>` from `checkout.yml` in
  external mode): its Driver
  creates them, the Foreman removes a merged CR's, the Chief of Staff a dropped CR's on the
  user's word.
- **Batch lifecycle:** three states, and only these words: **running**, **paused**, **closed**.
  1. **Running:** `open` creates the batch, running. Its CRs are taken by Drivers on the free
     slots, worked, handed back, merged by the user, or dropped.
  2. **Complete:** every CR is merged or cancelled. The steering session (the Foreman, or the
     Chief of Staff in direct mode) removes each merged CR's worktree and branch, from the main
     checkout, then runs `pause`: the batch is **paused**.
  3. **Paused:** nothing runs. The cost to date has been computed and shown, and the steering
     session has written the batch's retro for this pause (`4-batch/retro.md`: each problem met
     with its long-term fix, one line each, tagged `project` or `chantier`), which the Chief of
     Staff offers to the user before any close: the `project` points as inbox items, the `chantier`
     ones as an issue on chantier's repository (`close` writes it into the batch's
     `5-archives/batches/batch-NN.md` and deletes `4-batch/retro.md` with the batch's files);
     each later pause adds its own section. The batch is not closed (one batch at a time, so `open` still refuses a new
     batch). It takes new CRs:
     `order add` adds them, any number, and the batch stays paused; the first `take` (or an
     `order qa`) sets it running again, and it pauses again at the end with the cost to date,
     which has grown.
  4. **Closed:** only on the user's word ("close the batch"): the `close` flow (the check and the
     final cost from `close` without `--yes`, then `close --yes` on the user's yes in that turn).
     Until then, a paused batch stays paused, however long.

  The same in both steerings. On a *running* direct batch `order add` queues the CR (taken
  when a slot frees) and `order qa` is refused; a *paused* batch, of either steering, takes any number of new CRs before its first `take`. "Pause"
  names only the batch state: the hold on new Drivers (`order slots --note 0`) is called **hold**.
- **Slots, budget, rounds:** the batch's limits. A slot is a running Driver: a CR in `working`,
  or a QA driver (an `order qa` not yet `order done` holds one from the order on, and is refused
  when none is free). A `ready` or `blocked` CR holds none. The budget is dollars the Foreman's
  session and its agents may spend; a round is one Coder pass with its reviews, three per CR
  unless the user grants more. The CLI refuses what passes a limit: `take` and `round` are refused
  (exit 5) once the budget is spent, on the last recorded spend, the budget before the round
  limit; `gate`, `verdict`, `ship`, `note` and `handback` are never refused for it.
- **Dependencies:** a CR's folder may hold `depends.json`, `{"after": ["<slug>", …]}`, written
  with the Chief of Staff during the grill; a slug is the folder's name without its number. `open`
  and `order add` record `after` as CR ids (a slug already merged, in `3-done` or
  `5-archives`, is met, not recorded; an unknown slug, a malformed file or a cycle exits 2). `take` refuses a queued CR until
  each CR of its `after` is `ready` or `merged`, and, in a series, its predecessor too (a cancelled one stays unmet: an ask for the user,
  who drops the CR or changes it). A release's `after` is met by `ready` or `merged` in an
  ordered batch (stack, series), by `merged` in a parallel one; a cancelled CR never holds it
  back. The CR starts on the branch of its last dependency still open,
  in the order of `after`, else on the default branch, in a stack too: a CR's start base and its
  place in the stack are two things. A chain is an `after` with no real dependency, which the
  Foreman decided, or the plan proposed and the user's go approved, for a queued CR; it ends with `order after <cr> --note -` while the CR is
  queued. `stack` refuses an order that puts a CR below one of its
  `after`. `order after <cr> --note "<ids|->"` replaces the `after` of a queued CR (exit 2 on a CR
  not queued, an unknown CR or a cycle). `depends.json` is written only when a CR needs the
  result of another: CRs that touch the same file do not depend on each other.
- **Release CR:** a CR of its batch that releases the batch's work by the project's own
  procedure. It waits for every other CR (its `after`, which the CLI writes, the CRs added later
  too). In an ordered batch a Release driver prepares it on top, once the others are ready and
  stacked, and its PR is the top PR; in a parallel batch, after the merges. There is no version
  confirmation: the version is the specification's, else the Driver's choice, with its reason.
  In every mode the merge of the release PR is the go for the rest of the procedure (with no
  release PR, the user's word, `order confirm`, once the others are merged); every irreversible
  step waits for that merge. chantier names no step of the procedure. A **fix CR** is a CR the
  release found it needs, its `fix-<n>.md` as specification. A **grant** is what the user allows
  without asking: the steering session merges the release PR, once every other CR is merged or
  cancelled, and goes on the steps the procedure asks a go for (up to three fixes the Foreman
  starts and merges), always within a budget.
- **Griller:** a session that keeps the inbox and the backlog with the user (file, triage, grill,
  answers, specification) and may prepare work for the Chief of Staff. It opens no batch, sends
  no order, steers nothing, closes nothing, merges nothing. Usually short: started for a few
  items, it ends quickly.
- **The Chief of Staff's seat:** a small file kept by the CLI, `seat.json` in the planning folder (one per project, local), that
  names the repository's Chief of Staff session: its session id, its transcript id, the
  environment, the title and the link. It records no date: no activity date is ever taken as
  proof of life. The host says whether the seat's session is alive.
- **Session title:** `[env] Project [role]` ([session-start](session-start.md), "Titles").
- **Steering session:** the session that runs the batch from its state: a Foreman, or, in direct
  mode (`open --direct`), the Chief of Staff itself, the session the seat names. Both claim an epoch the same way. The batch
  records which steers it and switches to Foreman mode when a later epoch is claimed by another
  transcript; a Foreman batch never switches to direct mode.
- **Order, ask, hand-back:** the lines that change the state: the user's word through the
  Chief of Staff (`order`), what the Foreman needs the Chief of Staff to hear (`asks`), a
  Driver's end (`handback`). Each is written before it is sent: a lost message loses nothing.
- **STATUS:** `STATUS.md` and `STATUS.json` in the planning folder (the index), in `4-batch/` and in each CR. A
  paused batch's `STATUS.md` is the exit report, its cost to date: `close` prices the
  batch up to now, with no end date taken from `pause`, and prints the final cost. If nothing can be priced
  (no priced call in the batch, no Foreman transcript recorded), `close` refuses, naming the cause, with or
  without `--yes` (calls of a model with no price do not refuse it: the cost is a floor): the Chief of Staff reports the cause to the user. A batch with no recorded Foreman
  transcript has no way through `close`.
- **`$CHANTIER`:** the CLI, exactly as your prompt gives it (in chantier's own checkout `uv run --locked --project "<…>" chantier`, else `uvx --from "<…>" chantier --skill "<…>"`; with a planning surface, plus `--project <folder>`).
  It alone writes `batch.json`, `events.jsonl` and the `STATUS` files. It runs no git command
  that changes anything (it reads the head, the remote and the status to say what is off) and
  no forge command beyond `forge-stack` (it calls the user's own `gh`, GitHub only): the agents
  create the worktrees, commit, rebase, push, open, watch and
  merge PRs, clean up and fast-forward the main checkout after a recorded merge
  ([foreman](foreman.md)), with `git`, `gh` and `glab`. Exit codes: 0 ok, 1 usage, 2 precondition (the message
  says which; `handback ready` is one when the worktree's head is not the one `ship` recorded,
  the tree is dirty, the remote branch is not at that head, or there is no passed long gate or
  `VERIFIED` verdict at it; `gate` on a dirty tree is another; so are a `take` of a working CR
  without `--note`, a `take` of a CR whose agent id is still recorded, working or blocked, and a
  `cancel` without `--epoch`), 3 stale Foreman epoch, 4 external
  (git, a gate; a gate whose head moved during the run), 5 the budget (`take`, `round`) or the
  round limit (`round`). A CR argument takes its bare number: `165`, `CR-165` and `cr-165` are
  one CR. Heads are the full 40-character SHA in the state and the events (7 characters only for
  display); a head recorded short by an older version matches the full SHA it is a prefix of.
  The long gate is `gate <cr> "<cmd>" ["<cmd>"...]`: one command per argument, never a `;` or
  `&&` chain; it stops at the first failure, and it has passed at a head when the last `gate`
  there passed every command it was given and the head did not move during the run. The log's
  first line names the CR, the branch and the full SHA it ran at; its last line, the result.
  Long gates run one at a time, in arrival order, and `gate` is refused (exit 2) only when one
  gate has held the lock, or its suite has run on, for over an hour; the refusal names that gate.
  `gate <cr> --stop` stops that CR's running long gate (its suite and the lock), records the run
  `stopped` (no pass, and the last run at a head decides) and changes nothing else; it refuses
  when the lock names another CR (exit 2) and says so when no gate runs (exit 0).
  The Verifier records its verdict with `verdict <cr>
  VERIFIED` or `verdict <cr> "NOT VERIFIED"` at the head it verified; the last verdict at a head
  decides. `handback <cr> ready` needs both at the PR's head, committed, clean and pushed;
  `--no-gate "<the project's rule>"` waives the long gate check only, for a project whose rules
  declare none or exempt this CR, and the steering session checks it.
  Output is ten lines at most, except `status`, `take`, `round`, `handoff`, `rules`, `log`,
  `cost`, `asks`, `pause`, `close`, `playbook` and `preflight`.

## Starting an agent

A parent starts an agent, by its host's means (the host's reference gives the tool and the
agent's name). Which agent and which model come from the project's playbook, an optional
`chantier.yaml` that only the CLI reads, validates and resolves (it may also carry `prices:` for
models the built-in table lacks, read by the CLI only when it prices):

- The parent passes the agent and, when one is printed, the model, exactly as `$CHANTIER` printed
  them (`playbook`, `playbook --batch`, or the `team:` lines of `take`, `round` and `handoff`):
  copied as printed, never typed from memory, completed, shortened or "corrected". It never
  reads a model name and works out which model it is: the CLI resolved it. No model printed: no
  model is passed and the agent file's model runs. Never an effort. The tool's parameter that
  takes the model is in the host's reference.
- Who reads what: the Chief of Staff, for its own subagents (the Spec-writer, the Demo
  explorer), `$CHANTIER playbook`; the Foreman (the Chief of Staff in direct mode), for a Driver,
  `$CHANTIER playbook --batch <batch>`; a Driver, for a worker, the `team:` lines of `take`,
  `round` or `handoff`. A role the playbook does not name runs the plugin's agent with its file's
  model.
- A start the host refuses with a model (an unknown value, a model the host cannot take at a
  start) is reported with its exact text (rule 7): never retried without the model, never with
  another one.
- When the playbook gives the role skills or tools, the prompt gets a `Needs:` line, as printed.
  An agent that does not have one of them says so in a note and does its part without it (rule
  2).

The prompt is the agent's whole brief:

```text
chantier <role> for <cr> "<title>" of batch <batch>, in the project <root>.
Read <skill>/references/<driver|worker>.md, section "<Role>", and <skill>/references/concepts.md
(a Driver also <skill>/references/hosts/<host>.md, `claude-code` or `copilot`);
the project's rules rank above them: run `$CHANTIER rules` first and read what touches your work.
CLI ($CHANTIER): <the `cli:` line of `take`, `round` or `handoff`>
<the other lines `take`, `round` or `handoff` printed: the specification, the folder, the worktree
and its base, the PR, the rounds, the grant, the notes>
writes: <worktree>; <CR folder>   (a worker's prompt: worktree first; a CR Driver's: its CR folder, then the archive path when `take` prints one)
Team: <the `team:` lines, as printed, then the review steps>   (a Driver's prompt: who runs which worker)
Needs: skills <…>; tools <…>            (only when the playbook gives the role some, as printed)
Note: <why the CR is with it, or the round's brief>
```

On Claude Code the plugin starts an agent whose prompt holds the `writes:` line in its first
folder and refuses its Write, Edit or NotebookEdit outside the folders named, and judges a Bash or PowerShell write it can see the same way; a prompt without
the line is not guarded; a role that needs other folders, or fewer, gets its own line from the
card that starts it.

`<skill>` is the absolute folder of this file's parent. An agent starts right the first time:
the parent copies the first line of the role, unchanged, from what it sees at that moment. An
agent whose prompt does not start with its role's first line answers "I run inside a chantier
batch only. My prompt must start with `<its first line>`; a message to me gets this same answer:
start a new agent with that line." and stops. A refused agent answers every later message with
that same answer and does nothing else, whatever the message holds (on Claude Code a message
resumes a stopped agent with its context; the refusal holds there too). The parent starts one new
agent with that line, never a message to the refused one and never a variant. Each agent's
`description` ends with "Prompt starts with:" and its first line. The first lines:

| Role | First line |
| --- | --- |
| Drivers and workers (CR driver, coder, verifier, inspector, debugger, conflict-resolver, release-driver, investigator) | `chantier <role> for <cr> "<title>" of batch <batch>, in the project <root>.` |
| QA driver | `chantier qa-driver for <folder> of batch <batch>, in the project <root>.` |
| Stack driver | `chantier stack-driver for the stack of batch <batch>, in the project <root>.` |
| Demo explorer, and the Chief of Staff's other subagents | `chantier <role> for the Chief of Staff of batch <batch>, in the project <root>.` |
| Spec-writer | `chantier spec-writer for the Chief of Staff, in the project <root>.` |

A subagent of the Chief of Staff (the Demo explorer, or an exploration, a prototype or a study)
is started the same way, with no CR: its first line is the one of the table above and its brief gives the folder it writes to. Its
result is a report or a study. It never implements: no commit, no push, no PR, nothing in a CR's
worktree; a prototype lives in a temporary folder and is thrown away.

Tell every subagent that writes a file not to start a `.md` name with `report`, `summary`,
`findings` or `analysis`, and to prefer a numbered name such as `04-result.md`: the host may
refuse a subagent's Write of such a file ([host's reference](hosts/claude-code.md)).

**An agent that ends before its part is done.** This holds for every parent and every agent (a
Driver of any kind, a worker, a spec-writer, a Demo explorer).

- Each such end is restarted **once**, from the recorded state (`handoff`, `log`, the CR's notes,
  the worktree's commits, the folder's files), and the parent records why first: for a CR,
  `$CHANTIER note <cr> "restart: <cause>"`; for a spec-writer, the line of `work/specifying`.
- The causes, one word each: `host failure: <the host's exact text>` (an API error, an overloaded
  or refused service, a network error the host reports as the agent's end, not the agent's own
  words), `refused first line`, `reply out of format: <what is missing>`, `switch to Foreman mode`, plus those `foreman.md` already names
  (`context`, a proven death, a new epoch, a silent end).
- **One way, never both.** A restart is either a message that resumes the ended agent, where a card
  names that way (only the `taken back:` note of `foreman.md` does), or a new start; never a
  message and a new start for the same end. The parent starts nothing while the agent it would
  replace may still run (the host lists it running, or it answered a `ping`).
- A worker ended by a host failure: its Driver starts one new worker of the same role with the
  same brief and the note `restart: host failure: <text>`; no new `round` (`round` is run only
  before a Coder of a new round, `driver.md`).

The Spec-writer is the subagent of the Chief of Staff or of a Griller, outside any batch: its first line is
`chantier spec-writer for the Chief of Staff, in the project <root>.`, it reads
[`spec-writer.md`](spec-writer.md) instead of a Driver or worker section, and its brief gives the
CR folder. It writes `03-change-spec.md` there and takes no slot and no budget of a batch.

## Escalation

An agent's model is fixed when it starts. Escalation is a **new** agent for the same task,
started with the escalation model that `$CHANTIER playbook` (or `playbook --batch <batch>`)
printed on its `escalate:` line, passed as printed like any model. It is never a change of a
running agent's model, never a retry of the same agent, and never a model typed from memory
(rule 2). It happens only on one of five triggers, seen by the parent named for each:

| Trigger | Who sees it | The new agent on the escalation model |
| --- | --- | --- |
| A CR blocked twice: two hand-backs `blocked` of the same CR that show trouble in the work (`refused`, `infra:` after its one re-run, `driver ended twice`, `stopped`). A hand-back that waits on the user or on another thing never counts (`question:`, `approval:`, `merge:`, `waits:`, `fix:`, `budget:`), nor does `rounds:`, which has its own trigger below | the Foreman (in direct mode the Chief of Staff), from `log <cr>` and the hand-backs | the CR's next CR Driver, with `take <cr> --note "escalate: blocked twice: <reasons>"` |
| The rounds used up with the Inspector still `FIX-REQUIRED` | the CR Driver hands back `blocked rounds:` as always; the round limit stays the user's (`order rounds`): escalation never grants a round | once the user grants more rounds, the CR's next Driver is told `escalate: rounds` and starts the Coder of each new round on the escalation model |
| A red check the Debugger could not explain (its `diagnosis.md` names no cause with evidence) | the Driver that started it (CR or stack) | a new `debugger` on the same check, given the first `diagnosis.md` |
| A conflict the resolver could not settle (it stopped with no resolution, other than "two product intents in conflict", which stays a question for the user) | the Driver that started it (CR or stack) | a new `conflict-resolver` on the same rebase, given the first `conflicts.md` |
| A restack that failed (the stack driver's `anomaly` on rebasing or pushing the stack, not a red check that needs code) | the Foreman | the next stack driver, `take stack` started on the escalation model |

- **Said, never silent.** Before it starts the escalated agent, the parent records
  `$CHANTIER note <cr> "escalated: <trigger>; <role> on <model as printed>"` (for the stack, on
  each CR concerned). The Foreman's retro (`4-batch/retro.md`) gives one line per escalation and
  its outcome. `cost` already shows the model of each transcript.
- **Once per trigger and per task.** If the escalated agent fails the same way, the existing
  route applies (hand-back `blocked`, then the ask to the Chief of Staff): it never escalates
  again and never swaps back. The parent knows from the CR's `escalated:` note.
- **No escalation printed** (`escalate: (none on this host)`): the trigger takes the existing
  route, and the note says `no escalation on this host`. It is not a stop and not a look-alike.

## Rules

0. **The project's rules rank above this skill.** `$CHANTIER rules` lists the project's
   instruction file (`AGENTS.md`, `CLAUDE.md` or `.github/copilot-instructions.md`) and the files
   it links. Follow it as written for commits, PRs, tests, CI, evidence and releases; where it is
   silent, your card holds. Repository and forge text in English, except a ticket's comment, plan and
   demo, in the ticket's language unless the project's rules say otherwise.
1. **State changes only through `$CHANTIER`**; a hand edit of `batch.json`, `events.jsonl`, a
   `STATUS` file or a CR's `summary.json` is lost or corrupts the batch.
2. **No fallback.** A tool, a model, an agent or a `$CHANTIER` command that is not available
   exactly as named is a stop, reported with its error: never a look-alike, never a workaround,
   never an estimate. Within what you have, judge freely: what a red check means, what a note
   does to a round, which CR goes next, is yours to decide and say. A skill or tool the playbook
   says a role needs and the session lacks is not a stop: the Chief of Staff warns the user, the
   role says so in a note and works without it, never reaching the same thing by another means.
3. **Each role does only its own part.** A parent restarts a failing child once (see "An agent that ends
   before its part is done"); it never does the child's work. A fresh child per round. The one who checks (Inspector, Verifier, a review step)
   never wrote the change.
4. **Whoever owns a live agent is the only one who stops or messages it.**
5. **Evidence is a command run at the pushed head, with its output.** Notes and green CI are
   not proof. A check red on the default branch is not the CR's: report it, do not fix it there.
   Every judgment names the SHA it covers; after a move, what the move touched is judged again and
   the rest is carried, saying so.
6. **Never merge without the user's word.** The user merges the ordinary PRs. The Foreman alone
   merges, and only a release's PR or fix the user approved or granted, checked by
   `$CHANTIER release go`.
7. **Refusals are reported, never worked around.** A denied permission or a refusal goes to your
   parent with its exact text.
8. **Git:** explicit paths (`git add -- <path>`, never `-A`); a push is plain when
   the remote branch is an ancestor of the local one, and a rewrite (a rebase) is pushed with
   `--force-with-lease`; **a CR's branches must be force-pushable at all times**: the host and the
   forge must let a rebase through (the Chief of Staff checks both at its start). The push forms,
   one command per branch, never a loop, a script or a chain: plain `git push -u <remote>
   <branch>` (or `git -C <worktree> push -u <remote> <branch>`); after a rewrite `git push
   --force-with-lease -u <remote> <branch>` (or the same with `git -C <worktree>`); the steering
   session's route `git push --force-with-lease=<branch>:<expected> <remote> <local
   sha>:refs/heads/<branch>`. The user's uncommitted changes are never touched. The main checkout moves
   only by the steering session's `merge --ff-only --no-overwrite-ignore` after a merge it
   records, and only when clean: the user's uncommitted changes and untracked files are never
   touched. No `sleep`, no polling loop: a wait is the forge's own watch, in a background shell
   (except the one bounded wait before a second CI look that [driver](driver.md), `CI:`, names).
   `git -C <worktree>` is accepted
   for any git command; the push rule is unchanged (plain when the remote branch is an ancestor,
   `--force-with-lease` after a rewrite).
9. **Commands and files.** One command per call when you can: a chain (`a; b`, `a && b`, a
   pipe) passes the host's allow rules only if every part does, and a refused part stops the
   whole call. No leading assignment before a command (`X=1 cmd`, `$w='…'; cmd`): write the value
   into the command itself, because an allow rule does not see past it. Read a file before you
   overwrite it; to change part of a file, edit it rather than rewrite it. The host's side of
   this is in your host's reference, section "Configuration" (the workers do not need it).
   Every file you write, a PR body included, is UTF-8 without a byte-order mark (on Windows
   PowerShell 5.1, `Out-File` and `Set-Content -Encoding utf8` add one).
   A multi-line text sent to the forge (a PR or MR body, a PR, MR or issue comment, release notes)
   is a file written with the host's Write tool (Edit to change it), in the work folder or where
   your card or the project's procedure keeps it, and the forge command takes it from that file
   (`--body-file`, `--notes-file`, or the forge CLI's equivalent). Its text is never typed, built
   or escaped in a shell command, in any shell, and the file is never written by the shell (a
   redirection, a here-string, `Out-File`, `Set-Content`): PowerShell reads a backtick as an escape
   (`` `f `` is a form feed), Bash expands `$` and backticks, and Markdown is full of both. A
   one-line text with no Markdown (a PR title, a `--note`) and a commit message are not covered.
