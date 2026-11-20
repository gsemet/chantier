# Concepts and rules

The steering sessions and the Drivers read this file: the words the team shares, the boundaries,
and how an agent is started. Each worker reads its own card, which restates the rules it uses.

## Startup core

At startup, identify the role, batch, project and parent session.

## Words

- **Pull request (PR):** a merge request on GitLab.
- **Connector:** the module that reads one forge, read-only (GitHub and GitLab ship).
- **Interest:** a PR or MR, or a tracker issue a CR's `issue:` line names, that someone waits
  for; `chantier interests` lists them; the forge hub reads only the PRs and MRs, an outside
  poller (the user's own program) the issues, and writes their events with `chantier journal
  add`.
- **Ready (the status):** the CR's stored status `ready` in `batch.json`: its Driver handed it back
  (`handback <cr> ready <link>`). It is a token the rails and old records read; the CLI derives
  from it the three words below, and no person reads `ready` alone, but in one place: the stack rows of `take stack` and `stack`
  show it with the PR's draft flag (`ready, PR draft (#251)`), for the stack driver, which makes the
  stack from it. The three derived words stay everywhere else.
- **Ready to merge** (🟢): a CR handed back `ready` whose PR is out of draft on the forge (the CLI
  records it: `ship` reads it from the forge, `stack --out-of-draft`, never ahead of the forge) and, in a
  stack batch, with every CR under it ready to merge too; outside a stack its PR's base on the
  forge, as `ship` last read it, is the default branch. The user may merge it on its own at any moment, a stack batch is no exception;
  the top of a stack ready to merge means the whole stack is mergeable. "Mergeable" names only PRs
  ready to merge, never a draft, whatever the forge's `mergeable` field says.
  In a stack batch, a PR of the mergeable part of a verified stack (the five checks of **Stack**,
  below) is a second way: the user merges it with those under it, in one action from its top PR,
  or its PRs one at a time from the bottom, the user's choice made merge by merge, never fixed at
  the go (one action from the top is GitHub's; on GitLab, one MR at a time from the bottom); a
  draft on top is not mergeable. A PR of the mergeable part below the top had heavy CI
  only at the top, unless the user asked for it at its head.
- **PR in draft** (🟤): a CR handed back `ready` whose PR is open and a draft, or out of draft over a CR that is not (a
  stack, a PR on another CR's branch); its hand-back line names its own draft state and the CR it
  waits on; it waits for what is
  under it: first the CR whose branch its PR's base is on the forge, as `ship` last read it, else
  a CR below, its dependency, the release's top, or for its turn out of draft, and
  nobody merges it (do not merge). **Ready locally** (🟣): a CR handed back `ready` with no PR yet
  (rare: `handback ready` needs a PR). A draft's icon is its CR's state, never "draft" by
  default: 🟡 while it rebases or runs a gate, 🟠 waiting for another CR's work, 🔴 blocked.
  Any other CR's PR is a draft on the forge (a series, a stack not yet made on the forge, a stack being
  changed): it says so itself, and no one merges it. A release PR follows the same rule: the user
  merges it, last of the batch (in a stack, the stack's top PR, with the rest in the same action;
  in a series, after the rest, from the bottom up); the steering session merges it only under the
  grant, and never a stack that holds it. On GitHub a PR in a native stack is merged through the
  asynchronous merge, which takes every open PR below it, so the steering session merges it only when
  nothing open sits below it ([foreman](foreman.md), Your means, "Merging on GitHub").
- **Lease:** a numbered hold of a Driver, the stack driver or a QA driver on its unit (a CR, `stack`
  or a QA order `O-k`), started by `take` (or `order qa`), lasting 10 minutes and renewed by the
  commands that carry `--lease <n>`, by `lease <unit> renew` and by a `lease <unit> hold` child
  that runs. It is local to the machine that runs the batch. **Live** while it has not ended and
  it is within its 10 minutes, a long gate of the CR runs or waits, or a hold runs. **Not
  confirmed** when it ran out with none of these: its holder may only be waiting for its worker, so
  it is not gone, and its holder's next command with the current number is accepted while nobody
  took the unit again. Only the steering session, once it checked with the host that the Driver
  ended, takes the unit again (`take --reclaim`); a live lease is taken only on the user's word.
  **Ended** by the hand-back, the order's end, `agents set <unit> -` on a live lease, a `--reclaim`,
  `cancel` or `order drop`; the old holder's next command gets `claim lost`.
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
  ├── formerly.json        ← where a CR taken out of a batch came from (batch, branch, worktree, PR); written by `order drop` to the inbox or the backlog
  ├── prototypes/NN-<idea>/ ← each prototype version, with a README.md that says how to run it; only once there is one
  ├── experiments/         ← scripts, tests, benchmarks, studies and research notes (sources, quotes) made for the CR; only once there is one
  ├── evidence/            ← proof kept with the CR: screenshots kept on purpose, the Verifier's (work/verifier/evidence/); only once there is one
  └── work/                ← written while it runs: notes, gate logs, the PR body
  ```

  **A CR's folder holds its work.** Whatever an agent makes for a CR (a prototype, a script, a
  test, a benchmark, a study, a research note, a screenshot it keeps, a plan) is written in that
  CR's folder, in the place the tree gives, never in the host's scratchpad or a temporary folder.
  This rule ranks above the host's own instruction to use its scratchpad; outside any CR's work the
  scratchpad stays the host's. A sub-folder is created only when its first file is written: neither
  the CLI nor an agent creates `prototypes/`, `experiments/` or `evidence/` ahead of use.
  Prototypes come in versions, `prototypes/01-<idea>/`, `prototypes/02-<idea>/`, … (two digits, then
  a short kebab-case name of the idea); a new version is a new folder and the earlier ones stay.
  Each holds a `README.md` of a few lines: what the version tries, the command that runs it again
  (its server command, its port) and what it needs. A script that belongs to one version (its
  snapshot generator, its data builder) goes in that version's folder, not in `experiments/`. Names
  in `experiments/` follow the rule for subagent files below (a numbered name such as
  `01-benchmark.md`). `prototypes/` and `experiments/` are not covered files of a summary, like
  `evidence/` and `work/`. Kept out by design: secrets, personal data, and large binaries that are
  not the retained prototype (a dataset, a video above the forge's limits: the folder names where
  it is); the batch's own files and raw logs (already gitignored; a raw log stays in `work/gates/`
  or a `*.log` file; a Verifier's scratch project stays in `work/scratch/`); the agent's memory and the host's settings (`~/.claude/`), never a CR's
  place. What only the conversation holds (a subagent's reply, an inline visualization, a pasted
  image) is lost unless an agent writes it in the folder: writing it is the agent's job.

- **A CR's summary:** `summary.json` in the CR's folder: its title (one line, at most 72 characters), a summary of what
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
  the detailed logs (`work/gates/`, `*.log`) and the Verifier's scratch folder (`work/scratch/`)
  out of git: a raw log goes in such a file, never in a
  published one. The rest of a CR's folder is pushed with the surface. So are the batches' records:
  each batch leaves `5-archives/batches/batch-NN.json` (for a UI; written by `open` as `running`,
  completed by `close`) and `batch-NN.md` (for a person: the Completion table, the cost, the retro).
  The next batch number is read from these records. `$CHANTIER validate` checks the whole planning
  folder (stages, CR folders, `summary.json`'s format, missing or late summaries, broken links
  between its Markdown files), writes nothing, exits 0 when it finds only gaps (their count on its
  first line), 3 on errors and 1 when it cannot run; a surface's own validation calls it; it
  blocks no other command.
- **Planning surface:** a git repository of its own, one folder per project, always worked on
  its default branch (never in a worktree; only the project's code gets worktrees):
  `projects/<name>/` holds `project.md` (the project, its remote, `- Archive in the PR: yes|no`,
  `no` when absent), `checkout.yml` (`repo:` and `worktrees:`, paths relative to the project's
  folder; defaults `.repo/` and `.worktrees/` there) and `changes/` (the planning folder). The
  surface's `AGENTS.md` holds its own rules, its sync first. The project's **clone** is the
  "main checkout" for git only (`git -C <clone>`): no session runs in it. The project's
  `AGENTS.md` may point to its surface with one line, `- planning: <url>, projects/<name>`, which
  the Chief of Staff reads and the CLI does not. With a surface, every `$CHANTIER` carries
  `--project <the project's folder>`; a `cli:` line says so. A surface whose rules name
  `.agents/guidelines/autosync.guidelines.md` and that holds `scripts/ai-autosync-git.py` has an
  **autosync**: its own tool keeps the surface pushed. Preflight's P13 and a line of `status` report
  its state (active, stopped, blocked, or waiting for the user's approval); chantier only reads its
  files in `<surface git dir>/ai-autosync/` and never deletes one. chantier owns no autosync: the
  Chief of Staff, the Foreman and a Griller in the surface's checkout may join its group only after
  an explicit session-start opt-in, with `--session-id <their session id>`, and follow its
  guidelines. Drivers, and a Griller in a surface worktree, never join. While the group is enabled,
  no session commits or pushes the surface by hand. The board server does not join it implicitly;
  board permission and autosync participation are independent, and autosync is explicit opt-in.
  Several sessions may work one surface on one machine: each stages only its own project's folder,
  one board serves the surface, and `preflight` (P14) and `status` list the other batches.
  Full account:
  [planning modes](../../../docs/planning-modes.md).
- **Archive:** the CR's folder in `5-archives/`, with a `delivery.md` (the PR, the merge time,
  whether the archive is also in the PR). In external mode the Driver also commits a cleaned
  archive (`intake/`, `evidence/`, `01`–`03`, `delivery.md`, `STATUS.md`, and the retained
  prototype `prototypes/NN-<idea>/`, zipped if needed, as the grill decided; no `work/`, no
  `experiments/`) in its PR, when `take` prints `archive: in the PR at <path>`. Size: as is up to
  1 MB, zipped from 1 to 10 MB, very big above 10 MB; no retained version named, nothing from
  `prototypes/` ([driver](driver.md)).
- **Change Specification:** what the CR changes, complete and self-contained: a reader with only
  this file knows what to do. By default `03-change-spec.md`.
- **Host and default matrix:** the cases a CR must prove one by one, because what it changes
  behaves differently on each host (Claude Code, Copilot) or with a shipped default and with a
  value the user configured. There is one cell per combination that applies, including a host's
  refusal where one exists. Each cell gives the result it must show and the real flow that proves
  it: the CLI's own commands from a real state, with no user file for a shipped-default cell. A
  record or configuration shape built by hand, which the real flow does not produce, proves no
  cell. The specification names the matrix in its evidence. A CR with neither dependency has none.
- **Lifecycle:** the folder moves, it is never copied: `1-inbox/` (filed) → `2-backlog/P1…P4/`
  (the user prioritized it) → `3-ready/` (waiting for the next batch) →
  `4-batch/1-pending/<number>-<slug>/` (in the batch, not started) → `2-actives/` (taken by a
  Driver) → `3-done/` (merged, until `close`) → `5-archives/<YYMMDD-HHMM>-<number>-<slug>/`
  (after `close`, the time of the merge) or, on `order drop`, `6-trash/…` (cancelled; it returns
  to the inbox only on the user's word, by `restore <6-trash/item> [--slug <name>]`, without its
  date or its batch number, and with a line `formerly CR-<n> of batch-<m>`), or
  `1-inbox/<number>-<slug>/` or `2-backlog/P<n>/<number>-<slug>/` (taken out of the batch, keeping
  its number, with `formerly.json`; when that folder joins a batch, it gets its number back, and its branch and PR while its branch exists; `formerly.json` is then deleted), always with its work; a release or fix CR leaves only to the
  trash. A CR in the backlog
  or in `3-ready` goes back to the inbox with `triage <item> --inbox`.
- **`3-ready`:** the folder of the CRs that wait for the next batch, specified or automatable (no
  specification: the Driver works from the request alone), moved there on the user's word. It is
  not "ready to merge": a CR handed back `ready` sits in `4-batch/2-actives/`, never in
  `3-ready`. Write the folder `3-ready`, never "the ready CRs". From the web board the user may
  say "the next batch is ready": the board writes `next-batch.json` in the planning folder (the
  time and the slugs then in `3-ready`). It is the user's word and decides nothing: the Chief of
  Staff reads it and still asks before opening a batch.
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
  runs, on a reopened batch too: a CR not merged or cancelled, an open order, a stack agent, or an
  agent the batch holds (one `agents set` recorded and `-` did not clear, or the current Foreman),
  whose transcript shows it still runs (a tool call with no result, or a step under way; on a
  direct batch the Chief of Staff's own transcript is not read, its subagents are), or cannot be
  read (a held id with no transcript cannot be read: the way out is `agents set <cr> - --epoch
  <n>`; on Copilot, until `copilot-close-end-event` lands, a held agent whose lease is live, the
  Foreman's heartbeat under 10 minutes, and a unit with no lease, `not measured`, refuse). The
  CLI reads the end of each transcript, never the file's age. The session's other subagents
  (grill, spec, critics, Drivers already replaced, a Driver's own subagents) and the replaced
  Foremans never block: those still running or unreadable are listed apart, and their calls are
  counted in the final cost only up to now. The steering session offers or runs `close` only
  after its retro critic has handed back. A held agent that stopped without its hand-back passes
  only on the user's word (`close --stopped <name>`, a held agent only), recorded in the batch's
  record. A batch has one of three **modes**, set by
  `open --mode parallel|series|stack` and shown by `status`. **Parallel** (the default, when the
  user names none): every CR with no open dependency starts from the default branch at once and
  its PR is on the default branch; a CR with a dependency starts only once that dependency is
  `ready` (`take` refuses it until then), on the branch of its last dependency still open, else on
  the default branch (see **Dependencies**), and its PR stays a draft on that branch until the
  dependency merges; the first one ready to merge wins, and the user merges in the order things become ready to merge unless
  told otherwise; after each merge, every PR still open is rebased onto the default branch and
  its checks run again. **Series**: the CRs have a precise order, the one given to `open` (`order
  add` puts a CR on top); the next CR starts once the previous one is `ready`, from the previous
  CR's pushed branch, and its PR is a draft; once the previous one merges, the next is rebased
  onto the default branch and turns ready; a running batch switches between any two modes with
  `order mode --note parallel|series|stack`, on the user's word, and the record changes at once:
  the open CRs of a series or a stack made by the switch are ordered with the CRs already handed
  back `ready` at the bottom, in the order they became ready, then the others in the batch's
  order, the chains (`after`) kept; leaving a stack clears every CR's place in it; each open PR is
  then moved by its Driver on a rebase note (`rebase: mode <mode>`), the Foreman and the stack
  driver acting as their cards say; a merged CR never changes (its record, PR, branch and folder).
  **Stack**: parallel, with a stack driver: every CR with no open
  dependency starts at once, on the nearest earlier CR of the batch (by order) that already has a
  PR, else on the default branch, recorded at its first `take` (a branch with no PR is never a
  base), so its PR is already on the stack; a CR with a dependency starts only once that
  dependency is `ready` (`take` refuses it until then), on the branch of its last dependency still
  open, else on the default branch (see **Dependencies**), and the stack driver puts the PRs each on the
  previous one (`stack` marks the CRs it orders; `ship` records a stacked CR's place in the stack,
  and the start base for any other). As soon as two PRs are handed back ready (the moment the stack
  can form) the stack driver makes the native stack on the forge, once (the `gh stack` extension, or `$CHANTIER forge-stack create` when the user
  declined the extension); each further CR joins on top as a draft when it has its PR
  (`$CHANTIER forge-stack rebuild`: unstack, then create); the PRs ready to merge come first in readiness
  order, a CR always above its dependencies; the user merges the mergeable part at any time, in
  one action from its top PR or one PR at a time from the bottom, the release commit last. The
  stack-driver runs during the batch keep the stack current (made at two PRs ready, a CR that
  joins on top, a newly ready CR moved below the drafts, a restack after a merge at once, as
  today); one run at the batch's end, once every non-release CR has handed back (`ready` or
  `blocked`) and before the release's take, sets the final order, free to move any CR: one linear
  native stack on the forge. A queued CR whose dependency is blocked or cancelled does not hold
  that run back. The user may merge a ready CR on the default branch at any time before it. On
  GitHub, a chain of PRs based on each other is not a stack. On GitHub a stack is the forge's
  native stacked-PR stack; on GitLab, which has none, it is the chain of MRs `forge-stack` makes
  and checks, each targeting the one below, the first on the default branch, MRs ready to merge below and
  drafts on top, merged one MR at a time from the bottom (a middle MR merged folds into the one
  below it); unproved on GitLab. Merging a PR of the mergeable part "with those under it" in one
  action is GitHub's; on GitLab the MRs under it are merged first, one at a time from the bottom.
  **Stack as it stands:** the
  bottom CRs of the stack with a PR on its place, whatever their status (a working CR whose PR is
  on another base than its place is to come until its Driver rebases; a working CR the stack
  driver has not placed yet is to come until a stack driver names it in `stack`). **Mergeable part:** those of it from
  the bottom while each CR is ready to merge; its commit is the head of its highest
  PR. **Drafts on top:** the CRs above it (PR in draft, or not ready). **To come:** the open CRs
  of the stack with no PR yet, and those the stack as it stands leaves out. **Stack ready to merge** means five checks hold on the forge
  (`$CHANTIER forge-stack show` prints the failing ones): the stack is open; it holds every PR of
  the stack as it stands, and no other; in the record's order, bottom first; no PR of a CR ready to merge
  is a draft and every draft sits above the PRs ready to merge; the release PR, when it is in the stack, is
  on top; the five checks are read on both forges.
  **Inserting a change into a stack ready to merge:** before anything else every PR that will sit above the
  new one goes back to draft; then the new CR's PR is inserted at its place, the PRs above are
  restacked on it, the stack is rebuilt on the forge (`$CHANTIER forge-stack rebuild`) and
  verified, and only then the PRs above turn ready again; the release PR stays on top and its
  notes name the new change (the steps are the stack driver's, in [driver](driver.md)). A CR in
  the middle of a stack ready to merge that goes back for a new round puts the PRs above it to draft first,
  the same way. **A CR dropped from the stack** is removed: the PRs above go to draft first, its
  commits come out of the branches above (by the stack driver, or by the Driver of a working CR),
  its PR is closed when it goes to the trash (otherwise it goes to draft and the rebuild puts it
  on the default branch) and its branch kept, the stack is rebuilt without it and judged again where it
  changed, and a release above is redone. **A CR held out of the stack** (`order hold <cr>`, a
  ready CR of a stack batch, until `order unhold <cr>`) leaves it without being dropped: its PR goes
  to the default branch as a draft, the stack is rebuilt without it, and it comes back on top; no
  release starts while a CR is held. A CR stands on another
  only by a dependency: a real one (`depends.json`) or a chain the Foreman decided, or the plan
  proposed and the user's go approved (`order after`). A fix CR sits outside a series and a stack,
  on the default branch. A release CR is
  their top: it starts on the top CR's branch once every other CR is handed back ready and the top branch
  holds them all, and its PR is the top PR. When a stack merges only in part, what remains forms another stack in the same batch, restacked on
  the default branch, silently, and it goes on growing (one restack for one merge action of the user, none when the whole stack merged). Each CR is named a branch
  `chantier/<batch>/<cr>-<slug>` and a worktree `<repo>.worktrees/<batch>-<cr>` (`<worktrees>/<batch>-<cr>` from `checkout.yml` in
  external mode): its Driver
  creates them; a merged CR's are removed by the CLI at the batch's end (the end of its last
  CR), or by the steering session when the CLI kept them; the Chief of Staff removes a dropped
  CR's on the user's word.
- **Batch lifecycle:** three states, and only these words: **running**, **paused**, **closed**.
  1. **Running:** `open` creates the batch, running. Its CRs are taken by Drivers on the free
     slots, worked, handed back, merged by the user, or dropped. `open` with no CR creates the
     batch **paused**, with no CR: no cost to show, no retro, no close offer at that pause (steps 3
     and 4 do not apply to it); `order add` joins CRs and the first `take` sets it running, as in
     step 3. A **factory** batch (opened empty, with `--factory`, or by `order factory on`) takes
     each CR made ready with `triage --ready` at once; at its last CR's end it is paused with no
     retro and no close offer; it ends on the user's word (`order factory off`, then the retro and
     the close; a batch that never held a CR goes straight to the close), or after a release CR it
     took, which turns the factory off.
  2. **Complete:** every CR is merged or cancelled. The CLI removes each merged CR's worktree
     and branch (one whose agent is still held, or that git refuses, is kept and named) and runs
     `pause` itself: the batch is **paused**. With a note, a QA or a stack Driver pending, it
     says `not paused` and the steering session runs `pause` once they are done; it removes the
     worktrees the CLI kept once their Driver has ended.
  3. **Paused:** nothing runs. The cost to date has been computed and shown, and the steering
     session writes, after the pause (and, when the CLI paused the batch, with its retro critic,
     before `final`; in direct mode, before the close offer), the batch's retro for this pause (`4-batch/retro.md`: each problem met
     with its long-term fix, one line each, tagged `project` or `chantier`), which the Chief of
     Staff offers to the user before any close: the `project` points as inbox items, the `chantier`
     ones as an issue on chantier's repository (`close` writes it into the batch's
     `5-archives/batches/batch-NN.md` and deletes `4-batch/retro.md` with the batch's files);
     each later pause adds its own section. The batch is not closed (one batch at a time, so `open` still refuses a new
     batch). It takes new CRs:
     `order add` adds them, any number, and the batch stays paused; the first `take` (or an
     `order qa`) sets it running again, and it pauses again at the end with the cost to date,
     which has grown.
  4. **Closed:** only on the user's word: the close is offered at the pause, unprompted, once the
     retro critic has handed back (the check and the final cost from `close` without `--yes`),
     then `close --yes` on the user's yes in that turn.
     Until then, a paused batch stays paused, however long.

  The same in both steerings. On a *running* direct batch `order add` queues the CR (taken
  when a slot frees) and `order qa` is refused; a *paused* batch, of either steering, takes any number of new CRs before its first `take`. "Pause"
  names only the batch state: the hold on new Drivers (`order slots --note 0`) is called **hold**.
- **Slots, budget, rounds:** the batch's limits. The slots of a new batch are `batch.slots` (4 by default, set in a `chantier.yaml` or on the board's Configuration page; `--slots` wins at `open`); a running batch keeps its own until an `order slots`. A slot is a running Driver: a CR in `working`,
  or a QA driver (an `order qa` not yet `order done` holds one from the order on, and is refused
  when none is free). A `ready` or `blocked` CR holds none. The budget is dollars the Foreman's
  session and its agents may spend; a round is one Coder pass with its reviews, three per CR
  unless the user grants more, or the Chief of Staff under the rounds exception ([chief-of-staff](chief-of-staff.md), Steering). The CLI refuses what passes a limit: `take` and `round` are refused
  (exit 5) once the budget is spent, on the spend each of them first refreshes from the
  transcripts (when the batch has a budget), the budget before the round limit; `order qa`, the
  Foreman's granted fix and `release go` check the same refreshed figure; when the transcripts
  cannot be read, the check uses the last recorded spend and the command says so; `gate`, `verdict`, `ship`, `note` and `handback` are never refused for it.
- **Dependencies:** a CR's folder may hold `depends.json`, `{"after": ["<slug>", …]}`, written
  with the Chief of Staff during the grill; a slug is the folder's name without its number. `open`
  and `order add` record `after` as CR ids (a slug already merged, in `3-done` or
  `5-archives`, is met, not recorded; an unknown slug, a malformed file or a cycle exits 2). `take` refuses a queued CR until
  each CR of its `after` is `ready` or `merged`, and, in a series, its predecessor too (a cancelled one stays unmet: an ask for the user,
  who drops the CR or changes it). A release's `after` is met by `ready` or `merged` in an
  ordered batch (stack, series), by `merged` in a parallel one; a cancelled CR never holds it
  back. The CR starts on the branch of its last dependency still open,
  in the order of `after`, else, in a stack, on the nearest earlier CR of the batch that has a PR,
  else on the default branch: a CR's start base and its place in the stack are two
  things. A chain is an `after` with no real dependency, which the
  Foreman decided, or the plan proposed and the user's go approved, for a queued CR; it ends with `order after <cr> --note -` while the CR is
  queued. `stack` refuses an order that puts a CR below one of its
  `after`. `order after <cr> --note "<ids|->"` replaces the `after` of a queued CR (exit 2 on a CR
  not queued, an unknown CR or a cycle). `depends.json` is written only when a CR needs the
  result of another: CRs that touch the same file do not depend on each other.
- **Release CR:** a CR of its batch that releases the batch's work by the project's own
  procedure. It waits for every other CR (its `after`, which the CLI writes, the CRs added later
  too). In an ordered batch a Release driver prepares it on top, once the others are handed back ready and
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
- **Session title:** `[<code>] 💬 Project · <role>` for a session the user talks to, `[<code>] ⚙️ Project · Foreman (Batch <nn>)` for the Foreman ([session-start](session-start.md), "Titles").
- **Steering session:** the session that runs the batch from its state: a Foreman, or, in direct
  mode (`open --direct`), the Chief of Staff itself, the session the seat names. Both claim an epoch the same way. The batch
  records which steers it. A later epoch claimed by a transcript other than the recorded Chief of
  Staff transcript makes a direct batch a Foreman batch; a later epoch claimed by the recorded
  Chief of Staff transcript makes a Foreman batch direct. To the user, a claim's number is the
  Foreman's number within its batch (`batch-18, Foreman n°2`), never the word epoch; the flag
  stays `--epoch`.
- **Order, ask, hand-back:** the lines that change the state: the user's word through the
  Chief of Staff (`order`), what the Foreman needs the Chief of Staff to hear (`asks`), a
  Driver's end (`handback`). Each is written before it is sent: a lost message loses nothing.
  A **long-gate waiver** is one such order, the user's word recorded by the Chief of Staff:
  `order waive stack --note "<words>"` (a stack batch: one long gate on the top PR only; the CLI
  writes the waiver on each open CR of the stack but the top, and on a CR added later) or
  `order waive <cr> --note "<words>" --follow-up <backlog folder>` (one CR, with nothing in the
  batch to validate it: the follow-up CR runs the gate on main, and exists first); `--note -`
  withdraws it. It is a fact on each CR it covers, never a line in a brief: `take` and `handoff`
  print its `gate:` line, `handback ready` skips the gate pass for a covered CR (the head, clean,
  pushed and `VERIFIED` checks stay) and records the waiver in its event, and `status`,
  `STATUS.md`, `STATUS.json`, the pane and the web board show each CR's long gate and which CR's
  gate validates it.
- **STATUS:** `STATUS.md` and `STATUS.json` in the planning folder (the index), in `4-batch/` and in each CR. A
  paused batch's `STATUS.md` is the exit report, its cost to date: `close` prices the
  batch up to now, with no end date taken from `pause`, and prints the final cost. If nothing can be priced
  (no priced call in the batch, no Foreman transcript recorded), `close` refuses, naming the cause, with or
  without `--yes` (calls of a model with no price do not refuse it: the cost is a floor): the Chief of Staff reports the cause to the user. A batch with no recorded Foreman
  transcript has no way through `close`.
- **Step:** the Driver's `phase <cr> <phase> [detail]` records what it is doing (`coder r2`, `gate scenario`, `CI`); a working CR's `STATUS.json` holds it as `phase`, and the board, `chantier status` and the pane show it.
- **`$CHANTIER`:** the CLI, exactly as your prompt gives it (in chantier's own checkout `uv run --no-sync --project "<…>" chantier`, the environment synced once by the steering session with `uv sync --locked --project "<…>"`, never by a command; else `uvx --from "<…>" chantier --skill "<…>"`; with a planning surface, plus `--project <folder>`).
  It alone writes `batch.json`, `events.jsonl` and the `STATUS` files. It runs no git command
  that changes anything (it reads the head, the remote and the status to say what is off) and
  no forge command beyond `forge-stack` (it calls the user's own `gh` or `glab`): the agents
  create the worktrees, commit, rebase, push, open, watch and
  merge PRs, clean up and fast-forward the main checkout after a recorded merge
  ([foreman](foreman.md)), with `git`, `gh` and `glab`. Exit codes: 0 ok, 1 usage, 2 precondition (the message
  says which; `handback ready` is one when the worktree's head is not the one `ship` recorded,
  the tree is dirty, the remote branch is not at that head, or there is no passed long gate or
  `VERIFIED` verdict at it; `gate` on a dirty tree is another; so are a `take` of a working CR
  without `--note`, a `take` of a CR whose agent id is still recorded, working or blocked, and a
  steering command without `--epoch` (the cards list them)), 3 a stale Foreman (a later Foreman n° claimed the batch), 4 external
  (git, a gate; a gate whose head moved during the run), 5 the budget (`take`, `round`) or the
  round limit (`round`). A CR argument takes its bare number: `165`, `CR-165` and `cr-165` are
  one CR. Heads are the full 40-character SHA in the state and the events (7 characters only for
  display); a head recorded short by an older version matches the full SHA it is a prefix of.
  The long gate is `gate <cr> "<cmd>" ["<cmd>"...]`: one command per argument, never a `;` or
  `&&` chain; it stops at the first failure, and it has passed at a head when the last `gate`
  there passed every command it was given and the head did not move during the run. The log's
  first line names the CR, the branch and the full SHA it ran at; its last line, the result.
  As many long gates run at once as `chantier.yaml`'s `long_gate.parallel` says (one when absent),
  the others wait in this order: the next merge's first, then those moved first (`gate --first`),
  then arrival order. The next merge is, in a stack or series batch, the first CR of the order
  that is not merged or cancelled (a fix CR and the release CR do not count); in a parallel
  batch there is none by the record. A running gate is never stopped. A pass carries over a
  clean rebase, which the CLI proves with git by the exact patch-ids of the CR's own commits
  above the base it was judged on, and records at `ship` (a `carry` event with `gate_from`); so
  does the Verifier's verdict (`verdict_from`), recorded at the same `ship`; a rebase with a conflict, shipped with `ship
  --conflict`, needs a new gate. Under a stack waiver the top of the stack is never
  covered: its gate (or a carried pass) is the one that validates the lower CRs, and when a CR
  joins on top the validation moves to it. `gate` is only for the long gate the project's
  rules name, and a short gate runs outside it. `gate` is refused (exit 2) only when a gate has held a slot, or its
  suite has run on, for over an hour; the refusal names that gate.
  `gate <cr> --stop` acts on the slot that names that CR: it stops that CR's running long gate (its suite and the slot's lock), records the run
  `stopped` (no pass, and the last run at a head decides) and changes nothing else; it refuses
  when the lock names another CR (exit 2) and says so when no gate runs (exit 0).
  The Verifier records its verdict with `verdict <cr>
  VERIFIED` or `verdict <cr> "NOT VERIFIED"` at the head it verified; the last verdict at a head
  decides. `verdict <cr> VERIFIED` is refused (exit 2) unless `work/verify.md` in the CR's folder
  has a `Head:` line naming the full SHA of the head it records; `NOT VERIFIED` is not.
  `handback <cr> ready` needs both at the PR's head (or carried to it over a clean rebase, proved by
  git with the patch-ids of the CR's own commits), committed, clean and pushed;
  `--no-gate "<the project's rule>"` waives the long gate check only, for a project whose rules
  declare none, exempt this CR, or name a pipeline job as the long gate, and the steering session checks it; a waiver is not a project
  rule, so `--no-gate` is never its flag.
  A project's rule may name a pipeline job as its long gate (for instance "the long gate is the
  pipeline's `<job name>` job, green at the PR's head"): its Driver runs no `gate`, pushes and
  opens the PR after the approved round, waits for that job green at the PR's head, and hands back
  `--no-gate "<the rule>"`; the steering session reads that job's state at the PR's head on the
  forge (`gh pr checks <pr>` on GitHub; `glab ci status --branch <branch>` on GitLab, unproved).
  The Copilot host's path is unproved.
  Output is ten lines at most, except `status`, `take`, `round`, `handoff`, `rules`, `log`,
  `cost`, `asks`, `pause`, `close`, `playbook`, `preflight` and `order qa`.

## Starting an agent

A parent starts an agent, by its host's means (the host's reference gives the tool and the
agent's name). Which agent and which model come from the playbook, the configuration in layers
(the plugin's defaults, then optional `chantier.yaml` files) that only the CLI reads, merges,
validates and resolves (it may also carry `prices:` for
models the built-in table lacks, read by the CLI only when it prices, and `ci:` with
`beside_gate: true`, which the CLI prints as one `ci:` line, and `hosts.<host>.timing`, which the
CLI prints as `timing:` lines):

- The parent passes the agent and, when one is printed, the model, exactly as `$CHANTIER` printed
  them (`playbook`, `playbook --batch`, or the `team:` lines of `take`, `round` and `handoff`):
  copied as printed, never typed from memory, completed, shortened or "corrected". It never
  reads a model name and works out which model it is: the CLI resolved it. No model printed: no
  model is passed and the agent file's model runs. Never an effort. The tool's parameter that
  takes the model is in the host's reference.
- `agent=(generic)` printed: start the host's generic agent (the host reference's row "Start a
  generic agent"), pass the model as printed, and put the printed contract lines after the opening
  lines. Its tools are the caller's, not restricted; the card bounds what it does. A parent never
  chooses it, it only follows what the CLI prints.
- Who reads what: the Chief of Staff, for its own subagents (the Spec-writer, the Spec critic, the Demo
  explorer), `$CHANTIER playbook`; the Foreman (the Chief of Staff in direct mode), for a Driver,
  `$CHANTIER playbook --batch <batch>`; a Driver, for a worker, the `team:` lines of `take`,
  `round` or `handoff`. A role the playbook does not name runs the plugin's agent with its file's
  model.
- A start the host refuses with a model (an unknown value, a model the host cannot take at a
  start) is reported with its exact text (rule 7): never retried without the model, never with
  another one.
- When the playbook gives the role skills or tools, the prompt gets a `Needs:` line, as printed.
  An agent that does not have one of them says so in a note and does its part without it (never `$CHANTIER`: a CLI that cannot run is a stop, `startup-core.md`) (rule
  2).

The prompt is the agent's whole brief. A prompt names the card and section it expects the role to read:

```text
chantier <role> for <cr> "<title>" of batch <batch>, in the project <root>.
Read <skill>/references/startup-core.md, the host core, role core, and the short startup section
named by <skill>/references/startup-manifest.json; defer the rest until an action names it.
Read <skill>/references/<role>.md;   (a worker's prompt; an extra review step reads review-step.md)
the project's rules rank above them (a worker's prompt: above it): run `$CHANTIER rules` first and read what touches your work.
CLI ($CHANTIER): <the `cli:` line of `take`, `round` or `handoff`>
<the other lines `take`, `round` or `handoff` printed: the specification, the folder, the worktree
and its base, the PR, the rounds, the grant, the notes>
writes: <worktree>; <CR folder>
Steering: <who steers> <how to reach it>   (a Driver's prompt only: CR, stack, release and QA driver)
Team: <the `team:` lines, as printed, then the review steps>   (a Driver's prompt, where "A Driver's prompt" says so: who runs which worker)
Needs: skills <…>; tools <…>            (only when the playbook gives the role some, as printed)
Note: <why the CR is with it, or the round's brief>
```

`take`, `round` and `handoff` print a worker's first three lines (the first line, the `Read` line
and the rules line) under `<role> prompt, opening lines:`, to copy unchanged.

The `writes:` line: a worker's holds the worktree first, then the CR folder; a Driver's is in "A
Driver's prompt" (for a CR Driver, its CR folder, then the absolute archive path). Every entry on
a `writes:` line is a bare absolute path with nothing after it. A worker's line is copied from
the `worker writes line` that `take`, `round` or `handoff` printed.

A Driver's prompt holds the `Steering:` line: the steering session (the Foreman, or the Chief of
Staff in direct mode) and the means of the host's reference row "A Driver messages its steering
session" ([Claude Code](hosts/claude-code.md) or [Copilot](hosts/copilot.md)), written out as
that reference says it, with the steering session's id for the record when the host gives one.
Workers get no such line (they answer their Driver). Sending to the session id instead of the
reference's means is not introduced: the id is in the line for the record only (a message from a
Driver to its own parent session by id is unproved).

On Claude Code the plugin starts an agent whose prompt holds the `writes:` line in its first
folder (a CR Driver, whose prompt also holds `worktree:`, in that worktree, or in the project's root while the worktree does not exist yet: never in its CR folder) and refuses its Write, Edit or NotebookEdit outside the folders named, and judges a Bash or PowerShell write it can see the same way; a prompt without
the line is not guarded; a role that needs other folders, or fewer, gets its own line from the
card that starts it.

`<skill>` is the absolute folder of this file's parent. An agent starts right the first time:
the parent copies the first line of the role, unchanged, from what it sees at that moment. An
agent whose prompt does not start with its role's first line answers "I run inside a chantier
batch only. My prompt must start with `<its first line>`; a message to me gets this same answer:
start a new agent with that line." and stops. A refused agent answers every later message with
that same answer and does nothing else, whatever the message holds (on Claude Code a message
resumes an agent that ended its turn, with its context, not one the host stopped (a `killed` task),
which the host refuses to resume; the refusal holds there too). The parent starts one new
agent with that line, never a message to the refused one and never a variant. Each agent's
`description` ends with "Prompt starts with:" and its first line. The first lines:

| Role | First line |
| --- | --- |
| Drivers and workers (CR driver, coder, verifier, inspector, debugger, conflict-resolver, release-driver, investigator) | `chantier <role> for <cr> "<title>" of batch <batch>, in the project <root>.` |
| QA driver | `chantier qa-driver for <folder> of batch <batch>, in the project <root>.` |
| Stack driver | `chantier stack-driver for the stack of batch <batch>, in the project <root>.` |
| Demo explorer, and the Chief of Staff's other subagents | `chantier <role> for the Chief of Staff of batch <batch>, in the project <root>.` |
| Spec-writer | `chantier spec-writer for the Chief of Staff, in the project <root>.` |
| Spec critic | `chantier spec-critic for the Chief of Staff, in the project <root>.` |
| Retro critic | `chantier retro-critic for the Chief of Staff, in the project <root>.` |

A subagent of the Chief of Staff (the Demo explorer, or an exploration, a prototype or a study)
is started the same way: its first line is the one of the table above. When the work is for a CR,
its brief names that CR's folder and the place in it (a `prototypes/NN-<idea>/` or `experiments/`),
and its result (the study, the report) is written there as a file, not only returned in the
conversation. When it is for no CR yet, its brief names a folder it writes to, and when a CR comes
of it, the Chief of Staff moves what it kept into that CR's folder. It never implements: no commit,
no push, no PR, nothing in a CR's worktree.

Every file a subagent writes takes a number prefix (`04-result.md`, `04-report.md`), except a
name a card fixes (`03-change-spec.md`, `delivery.md`, `STATUS.md`, `retro.md`, the `work/` files
the cards name), which the probe of 2026-11-10 accepted. The parent that starts a subagent tells
it so. The host refuses some unprefixed names (`report`, `summary`, `findings`, `analysis`, a
`.md` file) on the name alone ([host's reference](hosts/claude-code.md)): it is not the auto-mode
classifier, and no allow rule fixes it.

**An agent that ends before its part is done.** This holds for every parent and every agent (a
Driver of any kind, a worker, a spec-writer, a spec critic, a retro critic, a Demo explorer).

- Each such end is restarted **once** (except a Driver stopped from outside, restarted at each such
  stop as `foreman.md`'s "A Driver stopped from outside" says, which counts toward nothing; other
  agents and other causes keep "once"), from the recorded state (`handoff`, `log`, the CR's notes,
  the worktree's commits, the folder's files), and the parent records why first: for a CR,
  `$CHANTIER note <cr> "restart: <cause>"`; for a spec-writer or a spec critic, the line of `work/specifying`; for a retro critic, the cause in
  the parent's own words in its turn (there is no CR to `note`).
- The causes, one word each: `stopped from outside: <the host's text>` (the host stopped the agent: its `task_status` `killed`
  record or its refusal of a message), `host failure: <the host's exact text>` (an API error, an overloaded
  or refused service, a network error the host reports as the agent's end, not the agent's own
  words), `refused first line`, `reply out of format: <what is missing>`, `switch to Foreman mode`, `switch to direct mode`, plus those `foreman.md` already names
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
[`spec-writer.md`](spec-writer.md), not `driver.md` (every role the Chief of Staff or a Driver
starts reads its own card; only a Driver reads `driver.md`), and its brief gives the CR folder. It writes `03-change-spec.md` there and takes no slot and no budget of a batch.
The Spec critic is a subagent of the Chief of Staff or of a Griller too, outside any batch: it
reads [`spec-critic.md`](spec-critic.md), its brief gives the CR folder, it writes nothing and
takes no slot and no budget of a batch.
The Retro critic is a subagent of the Foreman or of the Chief of Staff: it reads
[`retro-critic.md`](retro-critic.md), its brief gives the points and the files that carry their
evidence, it writes nothing and takes no slot. Its cost counts in the batch when a batch's steering
session starts it.

### A Driver's prompt

This table is the only source of which template lines each Driver's prompt holds. The CLI reads
it, and [foreman](foreman.md) and [chief-of-staff](chief-of-staff.md) point to it.

| Driver | Started after | Card | `writes:` | `Team:` |
| --- | --- | --- | --- | --- |
| `cr-driver` | `take <cr>`, a CR of kind `change` or `fix` | `driver.md` | the CR folder, then the absolute archive path when `take` prints one | yes |
| `release-driver` | `take <cr>`, a CR of kind `release` | `driver.md` | none | none |
| `stack-driver` | `take stack` | `driver.md` | none | yes |
| `qa-driver` | `order qa` | `driver.md` | none | none |

- Every Driver's prompt holds the opening lines, `CLI ($CHANTIER):`, the lines its command printed
  for it, `Steering:`, `Needs:` when the playbook gives the role some, and `Note:`. It holds
  `writes:` and `Team:` only where the table says so.
- `writes: none` means the prompt has **no** `writes:` line: the guard would refuse the Driver's
  worktree writes ([host's reference](hosts/claude-code.md)).
- Every path on a `writes:` line is absolute and bare (nothing after it): the CR folder as `folder:` prints it, and the archive
  as `<worktree>/<archive path>`.
- `take`, `take stack` and `order qa` print this skeleton, filled in where they can. The steering
  session copies it whole and fills in each `<...>` left. It adds no template line the skeleton
  does not print and drops none it prints.

## Escalation

An agent's model is fixed when it starts. Escalation is a **new** agent for the same task,
started with the escalation model that the role's `escalation` setting names in the
configuration, as `$CHANTIER playbook` (or `playbook --batch <batch>`) prints it: on its
`escalate:` line, or as `escalation=` on a `team:` line. It is passed as printed like any model;
a printed generic start is started as "Starting an agent" says for `agent=(generic)`. It is never
a change of a running agent's model, never a retry of the same agent, and never a model typed
from memory (rule 2). It happens only on one of four triggers, seen by the parent named for each.

- **Who escalates.** Only the roles that write code: `coder`, `debugger` and `conflict-resolver`.
  The Drivers never escalate: blocked twice escalates the next rounds' Coder, a failed restack its
  `conflict-resolver`. The judging agents (`inspector`, `verifier`, `investigator`,
  `spec-writer`, `spec-critic`, `retro-critic`, `demo-explorer`) never escalate: a new one of them
  runs on its own model.

| Trigger | Who sees it | The new agent on the escalation model |
| --- | --- | --- |
| The rounds used up: a `blocked rounds:` hand-back, whatever the round's failure (a red CI job, a gate broken after a rebase, a Verifier `NOT VERIFIED`, an Inspector `FIX-REQUIRED`) | the CR Driver hands back `blocked rounds:` as always; the round limit stays the user's (`order rounds`), except the rounds exception (the Chief of Staff grants up to two more when the batch caused the red): escalation never grants a round | once the user grants more rounds (a grant whose CR holds a `rounds exception:` note is taken with that note and does not escalate), the CR's next Driver is told `escalate: rounds` and starts the Coder of each new round on the coder's escalation model |
| A CR blocked twice, for other reasons: two hand-backs `blocked` of the same CR that show trouble in the work: `refused`, `infra:` after its re-runs, `driver ended twice`, `stopped`, `rounds:` (never one covered by the rounds exception) and `fix:` (a `question:`, `approval:`, `merge:`, `waits:`, `budget:` never counts; a Driver stopped from outside never counts either: it is no hand-back, and it does not make `driver ended twice`), when the row above has not already escalated it | the Foreman (in direct mode the Chief of Staff), from `log <cr>` and the hand-backs | the CR's next Driver is told `take <cr> --note "escalate: blocked twice: <reasons>"` and starts the Coder of each new round on the coder's escalation model. A CR with no rounds (a release CR, a QA order's CR, whose `fix:` has no Coder to escalate): blocked twice goes straight to the user's question of "Once per CR, then the user" |
| A red check the Debugger could not explain (its `diagnosis.md` names no cause with evidence) | the Driver that started it (CR or stack) | a new `debugger` on the same check, given the first `diagnosis.md` |
| A conflict the resolver could not settle (other than "two product intents in conflict", which stays a question for the user) | the Driver that started it (CR or stack) | a new `conflict-resolver` on the same rebase, given the first `conflicts.md` |

A Debugger whose explained fix fails again, and a stack driver's red check that needs code (sent
as `anomaly` to the Foreman, then worked in the CR's rounds), need no row of their own: they end
in the CR's hand-backs, which the first two rows count. A failed restack is the fourth row: the
stack driver's `conflict-resolver` escalates, the stack driver keeps the batch's model.

- **Said, never silent.** Before it starts the escalated agent, the parent records
  `$CHANTIER note <cr> "escalated: <trigger>; <role> on <model as printed>"` (for the stack, on
  each CR concerned). The Foreman's retro (`4-batch/retro.md`) gives one line per escalation and
  its outcome. `cost` already shows the model of each transcript.
- **Once per CR, then the user.** A CR that holds an `escalated:` note made for that CR (its
  rounds' Coder, its own `debugger` or `conflict-resolver`) never escalates again and never swaps
  back. An `escalated:` note written on each CR of the stack for a stack-wide escalation (the
  stack driver's `conflict-resolver` on a restack) does not count for it. If such a CR fails again
  (a new `blocked` hand-back that counts for either of the first two rows, or its escalated
  `debugger` or `conflict-resolver` failing the same way), the Foreman (the Chief of Staff in
  direct mode) does not `take` it again: the CR stays `blocked` and goes up to the Chief of Staff
  as a question for the user, with the options one more round, drop it, another approach. No
  further round without the user's answer. A CR with no rounds blocked twice takes this same ask
  at once. The parent knows from the CR's `escalated:` note.
- **No escalation printed** (`escalate: (none on this host)`, or no `escalation=` for that
  role): the trigger takes the existing route, and the note says `no escalation on this host`.
  It is not a stop and not a look-alike.

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
   role says so in a note and works without it (never `$CHANTIER`: a CLI that cannot run is a stop, `startup-core.md`), never reaching the same thing by another means.
3. **Each role does only its own part.** A parent restarts a failing child once (see "An agent that ends
   before its part is done"); it never does the child's work. A fresh child per round. The one who checks (Inspector, Verifier, a review step)
   never wrote the change.
4. **Whoever owns a live agent is the only one who stops or messages it.**
5. **Evidence is a command run at the pushed head, with its output** (except a matrix probe, run at the committed head before the CR's
   first push: [verifier](verifier.md)). Notes and green CI are
   not proof. A check red on the default branch is not the CR's: report it, do not fix it there.
   Every judgment names the SHA it covers; after a move, what the move touched is judged again and
   the rest is carried, saying so. A clean rebase that leaves the CR's patch unchanged, proved by
   git's exact patch-ids, recorded at `ship` (the same, commit by commit), touches no judgment; CI at the new head still runs.
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
   (except two bounded waits, each once: the one before a second CI look that [driver](driver.md), "Means: when CI lists no check",
   names, and the one after a `pending` answer of GitHub's asynchronous merge, a single `sleep` of at
   most 30 seconds then one read, at most once per merge: [foreman](foreman.md), "Merging on GitHub").
   For a Driver and the steering session (the workers keep their cards' ground rules): a
   background task is a background shell or a host monitor (a tool that streams a command's output
   to its owner). A task that waits on a file or on another task's output (`until grep …; do sleep
   …; done`) is a polling loop. No shell call changes its folder (`cd`, `Set-Location`, `pushd`,
   alone or chained before a command) into a CR folder (any stage). The steering session's never
   changes it into a worktree either. A Driver's shells run from the folder it starts in (its
   worktree on Claude Code). Name the target instead: `git -C <worktree>`, absolute paths,
   `gh … --repo <owner>/<name>`, `glab … -R <owner>/<name>`. Whoever starts a background task
   stops it by its id, with the host's stop of a background task, once its result is read or no
   longer counts (the board and the Chief of Staff's watcher, `$CHANTIER watch`, keep
   `session-start.md`'s and `chief-of-staff.md`'s start and stop rules: the watcher is started on
   the user's yes, started again after each end, and stops itself (at its end, or when the seat is another session's); only the current-folder rule
   applies to them). The shell that runs `$CHANTIER gate` is the gate itself: it
   ends when the gate ends and records its result, and it is stopped only with `gate <cr> --stop`.
   The reasons: on Windows a process whose current folder is inside a folder keeps that folder from
   being moved or removed (WinError 32), so a CR's move between stages or a worktree's removal
   fails; and a task left running wakes its owner each time it reports. [driver](driver.md) and
   [foreman](foreman.md) say when each role stops its tasks.
   `git -C <worktree>` is accepted
   for any git command; the push rule is unchanged (plain when the remote branch is an ancestor,
   `--force-with-lease` after a rewrite).
9. **Commands and files.** One command per call when you can: a chain (`a; b`, `a && b`, a
   pipe) passes the host's allow rules only if every part does, and a refused part stops the
   whole call. No leading assignment before a command (`X=1 cmd`, `$w='…'; cmd`): write the value
   into the command itself, because an allow rule does not see past it. Read a file before you
   overwrite it; to change part of a file, edit it rather than rewrite it. The host's side of
   this is in your host's reference, section "Configuration" (the workers do not need it: their
   cards hold what they use).
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
