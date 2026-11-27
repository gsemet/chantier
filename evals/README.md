# chantier evals

An eval campaign runs chantier for real, with real agents, and checks that every agent got its
role and behaved as its role says. The staged campaign (`claude-planted`) runs on a small
fictional project (`tasks-cli`, a to-do list in Python) with a local forge. The real campaigns
(`full`, `real-foreman`, `real-direct`, `ticket-summary`, `copilot`) run on the [sandbox](#the-sandbox) (`shelf`),
reset to its recorded base before each run, with the real forge and CI, frozen CRs and a judge
that runs hidden tests on each PR: only the plugin changes from one run to the next. Each run is
reported in [`results/`](results/), in words anyone can follow, with the same
[scorecard](SCORECARD.md): every rail marked `seen, right`, `seen, wrong` or `not seen`, plus the
cost and the steering share, so two runs compare line by line. The Claude campaigns use it;
Copilot's report stays as it is.

The scripted scenario (`just scenario`, no model, free) is not an eval: it tests the CLI's
mechanics and lives in [`scenario/`](../scenario/run_scenario.py).

## Prerequisites

What a person needs to run a campaign, in one list; the sections below point here and do not
repeat it. The `claude-planted` campaign needs only the first two items and the Claude Desktop and eval root item; setup refuses every campaign without a valid eval root file.

- This repository cloned, and the chantier plugin installed from it, the session restarted:
  `claude plugin marketplace add <this checkout>`, then `claude plugin install chantier@chantier`.
- `uv` and `git`.
- `gh` logged in (`gh auth status`) with the `workflow` scope (`gh auth refresh -s workflow`) and
  git's credential helper set (`gh auth setup-git`), on an account that can push to the sandbox.
- A sandbox of your own (`uv run --no-project python evals/kit/sandbox.py publish <you>/<name>`,
  see [the sandbox](#the-sandbox)), or push rights on the maintainer's.
- Claude Desktop, and an **eval root**: one folder outside this repository, named in
  `evals/kit/eval-root.local.json` (git-ignored, written by you: `{"root": "C:/Users/<user>/chantier-eval"}`).
  Trust it once, at the desk: open a Code session on that folder in Claude Desktop and answer the
  app's trust question. chantier never grants or edits that trust. Every workspace is created
  inside the eval root (setup refuses any other), so a workspace asks for no new trust (unproved
  until the trial in "The operator" reports). A Foreman campaign (`real-foreman`, `full`) still
  needs the desk, to start the Foreman and type the go; only the campaigns with no Foreman
  (`real-direct`, `ticket-summary`, `claude-planted`) start from the phone.
- The host's PR automations off: global Auto-fix and auto-archive on merge (see "A sandbox
  campaign", "Preparation").

The steps of a sandbox campaign, in order: the preparation (the automations off, no board left
running, then `sandbox.py publish` the first time or `reset`, then `setup.py`); start the operator
with the `prompt` line setup printed; the runbook's turns; the audit; `close --yes`; the cost; the
report. Each is described under "A sandbox campaign".

## Campaigns

| Campaign | What it covers | Cost | Last run |
| --- | --- | --- | --- |
| [full](full/RUNBOOK.md) | Two batches end to end on the sandbox, with real `gh` and CI: 8 feature CRs plus a release, a 9th feature CR injected while they run (the batch's 10th CR), then 2 feature CRs plus a release; four slots, a Foreman steers, the operator plays the user, the judge on every CR and both releases | the budgets, $40 and $15; measured by the first run | not run yet |
| [real-foreman](real-foreman/RUNBOOK.md) | 5 frozen CRs on the sandbox, no release, in the mode chosen at launch, with real `gh` and CI; a Foreman steers, the operator plays the user, merges included | budget $20; the first sandbox run (stack): $10.28, about 28 min to the last merge | 2026-11-15, run 2, stack: passed with findings, 5 of 5 CRs merged, judge 2 pass and 4 not run, audit 513/514, $10.28, [report](results/real-foreman-2026-11-15-run2.md). The run before the sandbox, on this repository: 2026-11-12, passed with findings, $5.03 for 2 CRs, [report](results/real-foreman-2026-11-12.md) |
| [real-direct](real-direct/RUNBOOK.md) | The same 5 frozen CRs, steered in direct mode by the Chief of Staff alone, with no Foreman | budget $20; run 3 (parallel): $11.52 at the audit, about 23 min; run 1: $11.84 (corrected; `cost` said $9.41) | 2026-11-15, run 3, parallel: passed with findings, 5 of 5 CRs merged, judge 6 pass, audit 553/555, $11.52, [report](results/real-direct-2026-11-15-run3.md). Run 1: 2026-11-12, passed with findings, judge 6 pass, audit 630/636, $11.84 (corrected; `cost` said $9.41), [report](results/real-direct-2026-11-12-run1.md) |
| [claude-planted](claude-planted/RUNBOOK.md) | The planted failures a real run does not produce, on `tasks-cli`: parallel and added work, a change order, a question, QA, rebases, a red CI from the product, the round limit; then a release with a fix, approvals and a grant | ~$15, 3 h | 2026-11-04 (as `claude-full`): passed with findings, $8.41, [report](results/claude-full-2026-11-04-ask-only.md) |
| [ticket-summary](ticket-summary/RUNBOOK.md) | One issue on the sandbox, the Chief of Staff alone, no batch: the ticket summary (comment, plan, demo) drafted, refused, then posted on the user's yes; a CR with no ticket gets none | ~$1 | not run yet |
| [copilot](copilot/RUNBOOK.md) | One frozen CR on the sandbox, on Copilot, with the real `gh`: the Foreman's session and heartbeat, background Driver and workers, cost | ~$1 | not run yet |

Past reports keep their names: a report named `real-*` is a `real-foreman` run on this repository
(before the sandbox), and one named `claude-smoke-*` or `claude-full-*` is a `claude-planted` run,
from before the campaigns merged. New ones are `results/<campaign>-<date>.md`, and
`results/<campaign>-<date>-run<n>.md` for a sandbox campaign. The behaviour measure (`just behaviour`)
writes `results/behaviour-<date>-v<X.Y.Z>.json` and `.md` (`-run<n>` when the name is taken): counts
and message templates only, never a transcript's text.

Which campaign, after a change: a role or flow change runs one quick campaign (`real-foreman` or
`real-direct`, five frozen CRs on the sandbox), in the mode the change touched. Before a release,
`full` with both quick campaigns, in the modes the release's claims file names. `claude-planted` runs after a change to how a batch handles
failures.

## Run a campaign

A campaign starts from a prompt in a chat. On Claude: a Code session of the Claude Desktop app.
On Copilot: a chat of the Copilot app. The prompt is in the campaign's runbook, and a sandbox
campaign's `setup.py` prints it ready to paste. The sandbox
campaigns (`full`, `real-foreman`, `real-direct`, `ticket-summary`, `copilot`) are described first, then the steps
of the staged campaign, `claude-planted`.

### A sandbox campaign

The text common to the five sandbox campaigns; each runbook refers to it. All the commands run
from this checkout, with the [prerequisites](#prerequisites) met.

- **Preparation, before the run.** The user does it, in this order; these steps prepare the run
  and are not steps of it.
  1. **Turn the host's PR automations off**, in Claude Desktop (Settings > Code, or Settings >
     Claude Code, by the app's version): **global Auto-fix off**, marked **unproved** (the
     [official documentation](https://code.claude.com/docs/en/desktop.md#monitor-pull-request-status)
     describes only the per-PR switch and no default for PRs opened later, and third-party reports
     say the global toggle may not reach PRs of local sessions), and **auto-archive / auto-close on
     PR merge or close off**, so the app does not archive a session when a run's PR merges. The
     per-PR switch is the operator's own job during the run (see "Auto-fix during the run").
  2. **No board left running from an earlier run:** stop any `chantier serve` still running; a
     board left running no longer makes the next run's board fail (it takes the next free port
     above 8765), but it still serves the old surface and holds its writer. Check for a running
     board on 8765 and the ports just above it, on PowerShell,
     `Get-NetTCPConnection -State Listen` filtered on the `chantier` process; on POSIX,
     `lsof -iTCP -sTCP:LISTEN`; or by the surface's `server.json`.
  3. **The sandbox.** The first time, your own:
     `uv run --no-project python evals/kit/sandbox.py publish <you>/<name>` (the plan; then the
     same with `--yes`). It creates a public repository, pushes the base to its `main` and writes
     `evals/kit/sandbox.local.json` (git-ignored) so the kit names it from then on; no `reset` is
     needed after it. Every later run, and on the maintainer's sandbox:
     `uv run --no-project python evals/kit/sandbox.py reset`, read the plan, then the same with
     `--yes`. This puts the sandbox back at its recorded base; it is the only force push on the
     sandbox, and no runbook gives another. `reset` refuses a repository that is not a chantier
     eval sandbox (no `main`, or a branch, tag or `main` whose history does not hold the recorded
     base), so a misnamed real repository is safe. One run at a time on a sandbox: a reset ends
     any other run. Each of these commands prints the repository it acts on, and where the name
     was read, on its first line.
  4. `uv run --no-project python evals/kit/setup.py <campaign> <workspace>`, with `<workspace>`
     a new folder inside the eval root (see the [prerequisites](#prerequisites)), for example
     `<eval root>/<campaign>-<date>`. Setup refuses any other workspace, and a missing or
     malformed `evals/kit/eval-root.local.json`, before it creates anything: a workspace inside the
     trusted root does not ask for trust (unproved until the trial reports, below), so the
     operator's session can start from Remote Control. Setup refuses
     when the sandbox is not at its base, never resets and never pushes. It clones the sandbox
     into the workspace, runs `chantier init` and `uv sync --locked` there, places the campaign's
     frozen CRs in `.agents/changes/3-ready/`, writes `<workspace>.run.json` (the run's record)
     and prints the campaign, the run, the prefix, the `workspace` (in the platform's own
     spelling: use it when the app asks for the folder), the CRs placed and each batch's `open`
     line, ready to paste (`--mode <stack|parallel|series>` is left to fill in for the quick
     campaigns), and last the operator's `prompt` line. The agents use the real `gh`. For
     `ticket-summary`, setup places no CR and prints, instead of `open` lines, the issue's `gh
     issue create` line and the chat request's file; it creates nothing on the forge.
- **The run's number and prefix.** The number is 1 plus the highest `<n>` among the sandbox's PR
  titles that start with `[eval <n> `. A run that opened no PR leaves its number free for the next
  one. The prefix is `[eval <run> <date> <campaign>]`, for example `[eval 4 2026-11-14 full]`.
  Every PR a run opens has a title that starts with it, followed by the title it would have
  anyway: each frozen CR copied into the workspace says so in its "Eval run" section. The audit
  and the judge read the run's record, so the prefix is how a run's PRs are told apart from older
  ones left on the sandbox.
- **The operator** is a new Code session of the Claude Desktop app opened on the workspace (at the
  desk for a Foreman campaign: it starts the Foreman's sessions), started with the `prompt` line setup
  printed: the runbook's prompt, with the runbook named by its absolute path in this checkout
  (the mode of the quick campaigns is the blank to fill: `stack`, `parallel` or `series`). Three
  ways to start it; the first two worked on 2026-11-15: **from New session** in the app's Code tab, picking the
  workspace folder (its native spelling, the `workspace` line setup printed; backslashes on
  Windows), then pasting the `prompt` line; or **from a chantier session at the desk**, asking a
  Claude Desktop session (for example the one in this checkout) to start a new session on the
  workspace with the `prompt` line; or **away from the desk**, for a campaign with no Foreman
  only (**unproved** until the trial below reports): from the phone, under Remote Control, start a
  new Code session on the workspace folder and paste the `prompt` line. The session must be on the
  workspace's main checkout, not a worktree of it. **The trust step:** a workspace inside the
  trusted eval root does not ask for trust (unproved until the trial reports); a folder outside it
  would ask, and only at the desk, which is why setup refuses it. A Foreman campaign is started at
  the desk. The trial (the first `real-direct` run after this change): from the phone, before
  `preflight`, the operator runs `git rev-parse --git-dir`, `git rev-parse --git-common-dir` and
  `git rev-parse --show-toplevel`; the first two must be the same folder and the top level the
  workspace, else it is a Fail. The report quotes the output and records how the session was
  created from the phone (the app, the screen, the choices made). On Copilot: a new
  chat of the Copilot app opened on the workspace, with the `prompt` line (**unproved** until
  the campaign's first run). The operator is the Chief of Staff and plays the
  user in full: the go after the plan, every merge, every answer, every approval, the release's
  confirmation, the injected CR, `pause` coming and the "close the batch". Nothing waits on the
  real user. `$CHANTIER` is `uv run --locked --project "<this checkout>" chantier`,
  run from the workspace. The plugin must be installed from this checkout (see the
  [prerequisites](#prerequisites)).
- **Auto-fix during the run.** As soon as a PR of the run appears (an `ask ready`, a hand-back,
  or the PR bound to its session), the operator turns that PR's Auto-fix monitor off with `mcp__ccd_pr__set_monitor`, only on the run's own sandbox PRs (a PR of the sandbox repository whose title starts with the run's prefix), never on another PR and never to arm one. It is what
  real-direct run 3 of 2026-11-15 did after Auto-fix events arrived on a sandbox PR. When the tool
  is refused or absent, the user turns the monitor off from the PR's menu (the three dots) in the
  operator's Changes card, and the report records the refusal as a finding.
- **A merge** is the user's, and the operator plays the user: the floor's "Never merge without
  the user's word" ([floor.md](../skills/chantier/references/floor.md)) is about the real user's
  PRs, which an eval has none of. (The Foreman still merges the release
  PR itself, as the card says.) The operator merges with `uv run --no-project python <this
  checkout>/evals/kit/sandbox.py merge <n>` (the `merge` line `setup.py` prints), from the
  workspace, alone, never chained; it never uses a raw `gh pr merge`. The sandbox's `main` is not
  protected, so the forge refuses only a conflict; the merge command refuses a PR that is not
  open, whose title lacks the run's prefix, or with a check finished and not green, and merges
  nothing then; a pending check (as after a stack's restack) is waited for, up to the bound
  (5 minutes), then refused, so the operator needs no `gh pr checks --watch` before a merge. A refused merge is reported as it is, and the
  steering session sees the PR not merged, as usual. Then `$CHANTIER order merged CR-<n>` and its
  line to the steering session. The workspace's main checkout does not stay at the base during a
  run: after each merge it records, the steering session fast-forwards it to the sandbox's `main`
  (a clean checkout on `main`, `merge --ff-only --no-overwrite-ignore` only, J26); the operator
  leaves the workspace's tracked files alone, so it does. In parallel mode the operator merges in the order the CRs become
  ready; in series, in the series' order; in a stack, from the bottom up, as the merge topics say
  for the mode (`chantier help merge`, `chantier help merge-series-stack`).
- **A question** (`blocked question:`): the frozen CRs leave none open, so a question is a
  finding. The operator answers `Follow the specification as written; where it is silent, choose
  the simplest behaviour and say so in the PR.`, records it in the CR's `02-answers.md`, and sends
  `$CHANTIER order note CR-<n> --note "answer: …"`.
- **A CR stuck** (the round limit, or blocked twice): the operator drops it to the trash (`order drop --note trash`), so the
  batch can pause; the report says why.
- **A `budget:` ask** (`ask blocked CR-<n> budget: …`, or `status` says the budget is spent): the
  first in a batch, the operator raises the budget once, `$CHANTIER order budget --note <the
  opening budget × 1.5, rounded up to whole dollars>`, sends its line, and the report records it
  as a finding (the cost of the kit's CRs is part of what a run measures). Any later `budget:` ask
  in the same batch: `$CHANTIER order drop CR-<n> --note trash` for the CR that asked, and its line; the report
  says why. No other raise.
- **The audit** runs when the steering session reports `final` (the batch paused), before
  `close --yes`:

  ```bash
  uv run --no-project python evals/kit/audit.py <workspace> --sandbox
  ```

  then `$CHANTIER cost --explain` and `$CHANTIER cost --by cr` from the workspace. Then the
  operator runs the `close` flow and `close --yes`. The report's cost figure is the one in the
  closed batch's record, `.agents/changes/5-archives/batches/batch-NN.md`, read after `close
  --yes` (run 2's cost rose from $11.47 to $11.91 between the audit and the close). The audit prints the run's table, the facts,
  the checks, the judge (the hidden tests on each CR's PR head as the forge reports it, its head
  at merge once merged, which a stack's restack may have replaced since the CR's hand-back; the row
  names the head judged and, when it differs, the head the record holds; then `main`, and the
  release judge), the scorecard and the cost. It exits 1 on a failed check, an unknown rail or a judge `fail`;
  `not run` is not a failure.
- **The report** goes in `results/<campaign>-<date>-run<n>.md` (its cost figure is read from the
  closed batch's record, as above), written in a worktree of this
  repository on its own branch, with its PR (the main checkout does not change during an eval).
  The sandbox is left as the run ends: its PRs and releases stay for inspection until the next
  reset.
- **The 10-message limit:** `full` goes past it and says how it lives with it; a quick campaign
  aims to stay under it (the Foreman's start and at most one send per merge wave); if a send is
  refused anyway, the campaign's runbook says how to go on (`full`'s way).

### The staged campaign

`claude-planted` runs on `tasks-cli` with a local forge, from this repository. Its steps follow;
the prompt:

```text
Run the chantier eval campaign claude-planted: follow evals/claude-planted/RUNBOOK.md.
```

The session that gets the prompt is the operator: it plays both the Chief of Staff (with the
chantier skill) and the user (it answers, merges and gives orders as the runbook says).
### Before you start

What the [prerequisites](#prerequisites) do not hold:

- The plugin is read live from the checkout: during a run, change neither its files nor its
  branch; other work goes in a worktree. The plugin install is what reaches the workspace: the
  workspace is outside this repository and does not read its `.claude/settings.json`.
- In `claude-planted` the forge is local (`evals/kit/forge.py`, a fake `gh` whose CI runs the long
  gate in a fresh clone): nothing reaches GitHub. `setup.py` puts it first on the `PATH` of every
  session in the workspace, so the Drivers' own `gh pr create` and the Foreman's `gh pr merge`
  reach it too. A sandbox campaign has no local forge: it needs `gh` logged in.
- Auto-fix (Claude Desktop, a real campaign on the sandbox: `full`, `real-foreman`, `real-direct`):
  its events skew the measured cost and the run's record, so it is turned off before the run
  (global setting, **unproved**) and by the operator on each of the run's PRs, as the
  [prerequisites](#prerequisites) and "Auto-fix during the run" say. The topic
  [`skills/chantier/references/topics/host-auto-fix.md`](../skills/chantier/references/topics/host-auto-fix.md),
  "Claude Code: Auto-fix events" (`chantier help host-auto-fix`), has the rule.
- On Claude, for a sandbox campaign, `setup.py` writes the workspace's
  `.claude/settings.local.json` (ignored by the sandbox's git) with the rules the user's own
  settings may lack: the merge command's rule, `mcp__ccd_pr__set_monitor` for the operator's
  Auto-fix switch (not for `ticket-summary`, which opens no PR) and, for `full`, the release's tag
  push and `gh release create` for its versions. Nothing else is allowed there. It also sets `CHANTIER_CONFIG_HOME` to a folder beside the workspace, so that no profile of the maintainer's (`chantier login`) turns an eval's commands remote.

### The host's limits

Claude Desktop sets these and no setting changes them: a campaign is written to live with them.

- **10 messages per session.** A session can send 10 messages to other Desktop sessions since
  someone last typed in it; the next ones are refused, and refused sends count. Each session has
  its own count, attached or detached. Messages from other sessions do not reset it, and a line
  typed during a turn counts only once that turn ends.
- **Every campaign stays under it**, for the Foreman and for the operator: at most 10 messages
  from the Foreman in the whole run, nobody types in its session, and at most 10 orders from the
  operator between two lines the user types. Only a campaign made to test long exchanges goes
  past it, and its report says so. `full` does: see its
  [runbook](full/RUNBOOK.md#living-with-the-10-message-limit) for how the operator lives with it.
  `claude-planted` can still reach it: a long batch has many `ask` lines.
- **Past the limit,** the Foreman's messages are lost, but the host still tells the operator of
  each of its turns: follow these notes and `status`, and merge from there. Never send through
  another tool: the limit is the host's, and a refusal is reported.
- **Starting the Foreman** needs a line typed in the desktop app (see above). From a phone, the
  user starts the session and pastes the Foreman's prompt; the Foreman claims its epoch itself.
  The trusted eval root removes only the trust step. It does not lift the host's rule that a
  session started or driven under Remote Control cannot start another session, so a Foreman
  campaign needs the desk, to start the Foreman and type the go. See the "classes of session"
  table, row "Desktop, Remote Control"
  ([topics/host-sessions.md](../skills/chantier/references/topics/host-sessions.md), `chantier help
  host-sessions`).

### The steps

These steps are for `claude-planted`.

1. **Stage** the workspace inside the
   eval root, for example `<eval root>/<campaign>-<date>` (setup refuses any other workspace):
   `uv run --no-project python evals/kit/setup.py <campaign> <workspace>`.
2. **Be the Chief of Staff** in that workspace: load the chantier skill, run its CLI from the
   workspace (`$CHANTIER` is `uv run --locked --project "<this checkout>" chantier`),
   and start the batch as `chantier help batch-plan` says (preflight, plan, go), with the `open`
   command of the runbook. The Foreman's session starts with the workspace as its folder. The
   operator's shell lacks the workspace's `.claude/settings.local.json`: set its `env` before
   running `$CHANTIER`.
3. **Be the user**: play the runbook's turns, in order, and nothing else. Merge with
   `evals/kit/merge.py <workspace> <pr>` alone, never chained: a conflict merges nothing; the
   Foreman notices a ready PR that stopped merging with the forge's CLI (`gh pr view --json
   mergeable`) and sends it back to a Driver.
4. **When the batch is paused** (`final <report>`): run the audit and the cost.

   ```bash
   uv run --no-project python evals/kit/audit.py <workspace>
   ```

   and `$CHANTIER cost --explain`, `$CHANTIER cost --by cr` from the workspace. The audit prints
   the scorecard filled for the rows it checks; it exits 1 on a failed check. Copilot's audit
   has no rail ids and no scorecard yet.
5. **Read the transcripts** for what a script cannot judge: did each agent do its role well
   (the Inspector's findings, the verifier's proof, the QA's scenarios, how a question was
   handled)?
6. **Write the report** in `results/<campaign>-<date>.md` (format below), update the campaign's
   "Last run" in the table above, and commit both on a branch. Nothing else from the run is
   committed: no transcript, no log, no screenshot.
7. **Clean up**: ask the user to archive the Foreman's session; the workspace may go.

### The report

For someone who does not know chantier's insides. Short sentences, no jargon left unexplained.

```markdown
# <campaign>, <date>

**Verdict:** passed / passed with findings / failed — one sentence why.

## The run
A sandbox campaign only: paste the audit's `## The run` table: the campaign, the run and the
date, the PR prefix, chantier's version and commit, the sandbox's base SHA-1, the batch's mode and
steering, the host and the models each role used. Two reports with the same base compare line by
line.

## What was tested
Two or three sentences: the project, the CRs, what the user did during the run.

## What happened
Per CR, in plain words: what it asked, how it went, how it ended.

## Findings
Numbered. Each: what went wrong or could be better, why it matters, what to do.

## Scorecard
The table of SCORECARD.md, each rail marked seen and right, seen and wrong (with the evidence),
or not seen (never a failure); then the cost and the steering share, `not measured` when the CLI
could not price them, never $0.00.

## Numbers
Duration, cost (total, the breakdown, by CR), agents started, audit checks passed, the steering
share, and for a sandbox campaign the judge's line (`Judge: <n> pass, <n> fail, <n> not run`).

## For maintainers
chantier version and commit, failed audit checks verbatim, anything to reproduce.

## Claims
A run made before a release only: the claims file's name (`claims-vX.Y.Z.md`) and the claims this
run exercised, by rail id.
```

`full` has one report for both batches: one scorecard, where a row is `seen, wrong` if it was
wrong in either batch, and the cost per batch and in total.

### Before a release: the claims

A release claims its changes; an eval run may not have brought them to the test. Each release
has a claims file, `evals/results/claims-vX.Y.Z.md`, written before that release's campaigns and
completed after them, and committed with the campaigns' reports.

- **The claims.** One row per `feat:` and `fix:` commit since the previous tag (the set the
  release notes cover once each): `git log --no-merges --format="%h %s" vPREVIOUS..origin/main`,
  keeping the subjects that start with `feat` or `fix`. A claim that lands later gets its row
  before the release's version PR is prepared.
- **The columns.** The file opens with `# Claims of vX.Y.Z`, then `Since vPREVIOUS, at <sha7 of
  origin/main>. Runs: <report file names>.` and a table: `Claim` (the subject without its type
  prefix), `Commit`, `Rail` (the SCORECARD id(s) whose situation proves it, or `none: <why no run
  can see it>`), `Can come up in` (the campaign and the launch choice, mode and Foreman or direct,
  read from the rail's `where seen`, or `no campaign`), `Result` and `Evidence`.
- **The three results.** `exercised`: a run of this release's campaigns marked the rail `seen,
  right` or `seen, wrong` (a `seen, wrong` is a finding of that report); the evidence is the
  report's file name and the rail's mark. `scenario only`: no run saw it and a named check of
  `just scenario` or `just test` proves it; the evidence is the unit and case. `not exercised`:
  neither; the evidence is empty.
- **The runs' modes.** The campaigns are launched so that every claim whose `Can come up in`
  names a campaign has at least one run that can bring it.
- **The release notes.** They list each claim not `exercised`, under `For contributors`
  ([release-process](../docs/release-process.md)).

## The situation quiz

A cheap check of a role's cards, beside the campaigns: `just quiz <role> [<role> ...]` gives the role the
text it boots on, adds one situation from `quiz/<role>/<id>.json`, asks "what do you do next, and why,
without running anything", and runs that three times; a separate judge model then reads each reply
against the behaviour the case expects, and the case scores its passes out of three. It runs
by hand, never in CI or in `just check`, and each model call is spend on your machine.

- **Models.** The role runs on its shipped model (`config/chantier.defaults.yml`,
  `hosts.claude.roles.<role>.model`, never the project's `chantier.yaml`). `chief-of-staff`,
  `foreman` and `griller` have none: pass `--model <id>` (refused for a role that has one). The judge is
  `quiz_judge.JUDGE_MODEL`, never a role's model: a role that would run on it is refused. The host is
  Claude Code only (`CHANTIER_HOST=copilot` is refused), run headless with the board's Griller
  flags (`griller_host.CLAUDE`): no settings, no MCP, the plugin, every tool refused, in an empty
  temporary folder. Their limits are unproved until the first real run, as the Griller's.
- **Boot text.** `--cards` names a git ref (the tree is read with `git archive`) or a folder; with none,
  the working tree. While the startup manifest exists, a tree or a ref is read as the manifest says
  (what `tests/test_start_reading.py` counts); a folder is read by `chantier brief <role> --cards <folder>`:
  the boot is its short prompt, then the brief file it names.
- **Spend.** The plan and its estimate print first, one line per role (`--plan` stops there); above
  `--max-usd` (default 10) nothing runs (exit 2), and while running no call starts once the measured
  cost reaches the cap (`incomplete`). The spend printed is the host's own `total_cost_usd`; a call
  that did not carry one is `not measured`, never `$0.00`. The batch's `cost` does not see it.
- **Pass rule (F4).** `--against <results.json> ...` compares each case with the newest earlier
  file that holds it: the new cards pass when no case scores 0 of 3 that scored at least 1 of 3
  before (exit 1 names each; a case with no baseline is new; one absent now is `not run`).
- **Cases.** One JSON object per file: `id` (the file's stem), `role` (its folder), `rules` (a
  non-empty list: `floor-1`..`floor-10`, a `J` row of `SCORECARD.md`,
  later an `R-nnn` id; several make a grouped case), `situation` (facts only, never the expected behaviour) and `expected`. Every key is
  required and no other is allowed; a bad file exits 2 naming it. The dry run reads them all.
- **Results.** `--save <label>` writes `results/quiz-<date>-<label>.json` and `.md`: scores, verdicts, short reasons, models
  (`shipped` or `given`), boot bytes, `claude --version` and the spend. No reply and no prompt is saved, and the
  home folder is `~` and the username `<user>` in every reason; the replies stay in a temporary
  folder whose path is printed. The baseline on a card set is
  `quiz-<date>-baseline-old-cards-<role>.json` and `.md`, one pair per role.
- **Rails with no case.** A judgement rail that a reply to one situation cannot show has no case:
  - J1 and J2, who starts whom: a transcript shows it, not a reply;
  - J5, a PR's state on the forge, which only a sandbox run has;
  - J13 and J14, the main checkout's state and the worktrees after a batch;
  - J17, a measured context window;

  Every other `J` row has a case, for the role its `from` column names first (the steering session is `foreman`, or
  `chief-of-staff` where the row names it alone; a `concepts.md` row takes the role whose reply shows it). Two rails are
  a `rules` entry of a floor case for the same role instead of a case of their own: J4 (`floor-2-cr-driver-push`) and J15
  (`floor-9-cr-driver-refused-send`). C21 is no judgement rail and has none.

  A rail the floor already covers for a role is a `rules` entry of that case.

## The kit

| File | Role |
| --- | --- |
| [`kit/setup.py`](kit/setup.py) | Sets up a campaign's workspace, and refuses one that is not inside the eval root named in `kit/eval-root.local.json` (git-ignored; also refused: no file, a malformed file; nothing is created). `claude-planted`: the project, a bare origin, the local forge, the CRs. A sandbox campaign: a clone of the sandbox at its base, the frozen CRs, the run's number and prefix, `<workspace>.run.json`, and on Claude the workspace's ignored `.claude/settings.local.json` (the merge, the operator's `set_monitor`, the release's tag push and GitHub release); its last line is the operator's `prompt`. For `ticket-summary`, the issue's `gh issue create` line and the chat request, with the two posting commands allowed |
| [`kit/forge.py`](kit/forge.py) | The local forge, called as `gh`: PRs, CI in a fresh clone, CI-only contract tests |
| [`kit/merge.py`](kit/merge.py) | `claude-planted`'s merge, on the local forge |
| [`kit/audit.py`](kit/audit.py) | What happened to each CR, the agent tree, one PASS/FAIL line per check, each naming its rail, and the scorecard; `--sandbox` for the sandbox campaigns: also the run table, the real forge read-only and the judge |
| [`kit/judge.py`](kit/judge.py) | The judge: the hidden tests on a PR's head in a clean clone of the sandbox, and a release judged by the tag, the version, the notes and the GitHub release |
| [`SCORECARD.md`](SCORECARD.md) | The single list of rails, one row each: id, rail, source, where seen, how marked |
| [`kit/fixture/`](kit/fixture/) | `tasks-cli`, with its `AGENTS.md` and two review agents of its own |
| [`kit/crs/`](kit/crs/) | The prepared CRs (request, intent, answers, specification) |
| [`kit/contracts/`](kit/contracts/) | Tests only the simulated CI runs |
| [`kit/ticket-summary/`](kit/ticket-summary/) | The `ticket-summary` campaign's frozen issue and ticket-less request |
| [`kit/sandbox-crs/`](kit/sandbox-crs/) | The frozen CRs of the sandbox campaigns (request, intent, answers, specification): 11 features and 2 releases |
| [`kit/sandbox-judge/`](kit/sandbox-judge/) | The hidden tests of the feature CRs: never copied to a workspace, never pushed to the sandbox |
| [`kit/sandbox/`](kit/sandbox/) | `shelf`, the sandbox project, the source of the sandbox's initial commit |
| [`kit/sandbox.py`](kit/sandbox.py) | `build` (the deterministic initial commit, its SHA-1 recorded in `kit/sandbox.json`), `publish` (your own public sandbox, created, given the base and named in `kit/sandbox.local.json`), `reset` (the sandbox back at that commit, comparing branches and tags only; the only force push; it refuses a repository whose history does not hold the base) and `merge` (the operator's merge of a run's PR, which refuses a PR not open, without the run's prefix or with a check finished and not green, and waits, for at most 5 minutes, for a pending check). It is the one reader of the sandbox's name: `kit/sandbox.local.json` (git-ignored), else `kit/sandbox.json` |
| [`kit/behaviour.py`](kit/behaviour.py) | The behaviour measure (`just behaviour [--since <date>]`, never in CI): reads your local Claude Code transcripts (`~/.claude/projects`, or `$CLAUDE_CONFIG_DIR/projects`, or `--projects <dir>`; `--folders <glob>` keeps some project folders) and writes `results/behaviour-<date>-v<X.Y.Z>.json` and `.md`: per role, the card bytes read, the files read, the CLI's usage errors and refusals, the `--help` and help-topic reads, the host's denials, the write guard's refusals, the waits, the tools not in the role's list and the pushes; the Drivers' runs per CR and the Foreman's and Chief of Staff's wake shares; each detector's rate, the S-list (a message seen in more than 2 % of a role's runs) and the regressions against the previous file. Counts and message templates only; a privacy guard refuses a result that holds the home folder's path or the login name. `--prune` reads no transcript and lists the deletion candidates from the two latest results files. Copilot is not measured |
| [`kit/detectors.json`](kit/detectors.json) | The behaviour measure's detectors: a regex on tool calls for each checkable rule (a merge by a Driver, a plain `--force`, a stash, `git add -A`...), with its floor rule, the roles it applies to and a positive and a negative example, which the dry run checks |
| [`kit/behaviour-fixture/`](kit/behaviour-fixture/) | Hand-written transcript lines for the behaviour measure, its `expected.json` figures, a `previous.json` and a `leak/` folder for the privacy guard; read by the dry run's `behaviour` case |
| [`kit/quiz.py`](kit/quiz.py) | The situation quiz (`just quiz <role> [--cards <git ref or folder>] [--case <id>] [--model <id>] [--max-usd <dollars>] [--plan] [--against <results.json>] [--save <label>]`, model spend, never in CI or `just check`): a role's boot text and one case's situation, three runs on the role's own model, each reply judged; see "The situation quiz". Imports the `chantier` package, so it runs in the root project's environment |
| [`kit/quiz_judge.py`](kit/quiz_judge.py) | The quiz's judge: `JUDGE_MODEL`, its prompt and `run_judge`; alone, `quiz_judge.py --situation <file> --expected <file> --reply <file>` re-judges one reply |
| [`quiz/`](quiz/) | The quiz's cases, `quiz/<role>/<id>.json`, one situation and the behaviour expected |
| [`kit/dry_run.py`](kit/dry_run.py) | The dry run (`just eval-dry-run`): reset, setup, a staged run, audit and judge, on a local sandbox, with its planted faults (a stray merge, a leftover after the reset, a refused merge, a stale `uv.lock`; the audit's own detectors, each with its planted breach: a retro critic's `for the Chief of Staff` first line, a QA driver's `for <folder> of batch <batch>` first line, a rules read in the claim's own shell call, a here-doc's text holding a git move), the `eval-root` case (setup refuses a workspace outside the eval root, with no file and with a malformed one; inside, the same allow rules and no trust entry), the `ticket-summary` setup case (no CR placed, the issue line, no forge write), the other sandbox (a `sandbox.local.json` naming another repository flows through setup, merge, the judge and the audit), `reset` refusing a foreign or an empty repository, `publish`, the `prompt` lines of setup and the `behaviour` case (the behaviour measure on its fixture: figures, regressions, detectors, the privacy guard, `--prune`) and the five `quiz-*` cases (the quiz's plumbing with staged runs and judge: the cases and their rules, the boots, the scores, `--save`, `--against`, the cap, `--cards <ref>` and `<folder>`); no model, no GitHub, and never the checkout's own `sandbox.local.json` or `eval-root.local.json` |
| [`kit/sandbox_forge.py`](kit/sandbox_forge.py) | The sandbox's GitHub played locally, called as `gh`, for the dry run only |
| [`kit/dry-run/`](kit/dry-run/) | The reference solution of the staged CR, `delete-item` (`delete-item.patch`) |

### Changing the kit

- A change to `evals/kit/` passes `just eval-dry-run` at its pushed head. Its output is the
  Verifier's evidence (`work/verifier/evidence/`), quoted in the PR body.
- A kit change that adds a CI job or changes the steps of one also runs that job's work steps once
  with `UV_CACHE_DIR` set to a new empty folder, before the push: its output is kept as the
  Verifier's evidence and quoted in the PR body. [CONTRIBUTING.md](../CONTRIBUTING.md) ("Daily
  work") has the full rule.
- A new campaign behaviour, or a fault a run found, gets its case in the dry run in the same PR.
- An eval-kit change gets an independent review of the whole campaign path (setup, a run, the
  audit, the judge) before its merge, by a reviewer that did not write it. The dry run does not
  replace it.

## The sandbox

The eval campaigns run on a frozen project: `shelf`, a small reading list in Python, kept in
[`kit/sandbox/`](kit/sandbox/) and published at
[gsemet/chantier-eval-sandbox](https://github.com/gsemet/chantier-eval-sandbox) (public, `main`
not protected), the maintainer's. Its initial commit is the same everywhere, down to the SHA-1, and
that SHA-1 is the recorded base in [`kit/sandbox.json`](kit/sandbox.json), which also names this
repository. A person's own sandbox is named in `kit/sandbox.local.json`
(`{"repository": "<owner>/<name>"}`, git-ignored, so it never dirties the checkout), which wins
when it is there; a malformed one stops the command (exit 2), it never falls back to the
maintainer's repository. No argument and no environment variable names the repository.

- `uv run --no-project python evals/kit/sandbox.py publish <owner>/<name>` prints its plan and
  changes nothing; with `--yes` it creates the public repository (or takes an existing one that is
  public and empty), pushes the base to `main` (a plain push: it never force-pushes and refuses a
  repository with history), checks `main` is the default branch and unprotected (a protected one
  is reported, not changed), and writes `kit/sandbox.local.json`. It refuses when that file names
  another repository: remove it yourself.

- `uv run --no-project python evals/kit/sandbox.py build [<dest>]` builds that commit, and exits 2
  when its SHA-1 is not the recorded one. `just check` runs it as a structure test.
- To change the project: edit `kit/sandbox/`, run `build --record`, and commit `sandbox.json` in
  the same PR, or `just check` is red. Once that PR is reviewed, run `reset --yes`.
- `uv run --no-project python evals/kit/sandbox.py reset` prints what it would do and changes
  nothing; before the plan it refuses (exit 2, nothing changed) a repository with no `main`, or
  whose `main`, another branch or a tag does not hold the recorded base. `reset --yes` closes the open PRs, deletes the releases, tags and other branches, and
  force-pushes the base to `main`. It compares branches and tags only: GitHub keeps
  `refs/pull/*` and no push can delete them.
- `uv run --no-project python evals/kit/sandbox.py merge <pr>` merges a run's PR by rebase, for the
  operator who plays the user, and refuses what the user would not merge (see "A merge" above).
  It merges through GitHub's asynchronous merge (`PUT .../pulls/<n>/merge-async`, then its
  result read until it is no longer pending), the only merge GitHub accepts for a PR in a native
  stack. A PR in an open stack merges with every PR below it in that stack, in one merge, as on
  GitHub's page: each of them must pass the same refusals, or nothing is merged. A pending check
  (after a stack's restack, the new head's CI) is waited for: `merge` prints `waiting for the
  checks of PR #<n> ...` and reads again every 10 s, at most 31 reads (300 s in all), then refuses.

Nothing else resets the sandbox: one file names the repository, `reset` refuses what is not a
chantier eval sandbox, and `reset` is the only force push.
