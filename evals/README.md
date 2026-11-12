# chantier evals

An eval campaign runs chantier for real, with real agents, and checks that every agent got its
role and behaved as its role says. The staged campaign (`claude-planted`) runs on a small
fictional project (`tasks-cli`, a to-do list in Python) with a local forge. The real campaigns
(`full`, `real-foreman`, `real-direct`, `copilot`) run on the [sandbox](#the-sandbox) (`shelf`),
reset to its recorded base before each run, with the real forge and CI, frozen CRs and a judge
that runs hidden tests on each PR: only the plugin changes from one run to the next. Each run is
reported in [`results/`](results/), in words anyone can follow, with the same
[scorecard](SCORECARD.md): every rail marked `seen, right`, `seen, wrong` or `not seen`, plus the
cost and the steering share, so two runs compare line by line. The Claude campaigns use it;
Copilot's report stays as it is.

The scripted scenario (`just scenario`, no model, free) is not an eval: it tests the CLI's
mechanics and lives in [`scenario/`](../scenario/run_scenario.py).

## Campaigns

| Campaign | What it covers | Cost | Last run |
| --- | --- | --- | --- |
| [full](full/RUNBOOK.md) | Two batches end to end on the sandbox, with real `gh` and CI: 8 feature CRs plus a release, a 9th feature CR injected while they run (the batch's 10th CR), then 2 feature CRs plus a release; four slots, a Foreman steers, the operator plays the user, the judge on every CR and both releases | the budgets, $40 and $15; measured by the first run | not run yet |
| [real-foreman](real-foreman/RUNBOOK.md) | 5 frozen CRs on the sandbox, no release, in the mode chosen at launch, with real `gh` and CI; a Foreman steers, the operator plays the user, merges included | budget $20; measured by the first run | not run yet. The campaign moved to the sandbox; the last run, on this repository before the sandbox: 2026-11-12, passed with findings, $5.03 for 2 CRs, [report](results/real-foreman-2026-11-12.md) |
| [real-direct](real-direct/RUNBOOK.md) | The same 5 frozen CRs, steered in direct mode by the Chief of Staff alone, with no Foreman | budget $20; measured by the first run | not run yet |
| [claude-planted](claude-planted/RUNBOOK.md) | The planted failures a real run does not produce, on `tasks-cli`: parallel and added work, a change order, a question, QA, rebases, a red CI from the product, the round limit; then a release with a fix, approvals and a grant | ~$15, 3 h | 2026-11-04 (as `claude-full`): passed with findings, $8.41, [report](results/claude-full-2026-11-04-ask-only.md) |
| [copilot](copilot/RUNBOOK.md) | One frozen CR on the sandbox, on Copilot, with the real `gh`: the Foreman's session and heartbeat, background Driver and workers, cost | ~$1 | not run yet |

Past reports keep their names: a report named `real-*` is a `real-foreman` run on this repository
(before the sandbox), and one named `claude-smoke-*` or `claude-full-*` is a `claude-planted` run,
from before the campaigns merged. New ones are `results/<campaign>-<date>.md`, and
`results/<campaign>-<date>-run<n>.md` for a sandbox campaign.

Which campaign, after a change: a role or flow change runs one quick campaign (`real-foreman` or
`real-direct`, five frozen CRs on the sandbox), in the mode the change touched. Before a release,
`full` with both quick campaigns. `claude-planted` runs after a change to how a batch handles
failures.

## Run a campaign

A campaign starts from a prompt in a chat. On Claude: a Code session of the Claude Desktop app.
On Copilot: a chat of the Copilot app. The prompt is in the campaign's runbook. The sandbox
campaigns (`full`, `real-foreman`, `real-direct`, `copilot`) are described first, then the steps
of the staged campaign, `claude-planted`.

### A sandbox campaign

The text common to the four sandbox campaigns; each runbook refers to it. All the commands run
from this checkout, with `uv`, `git` and `gh` (logged in to an account that can push to the
sandbox).

- **Preparation, before the run.** The user does it in a terminal; these commands prepare the run
  and are not steps of it.
  1. `uv run --no-project python evals/kit/sandbox.py reset`: read the plan, then the same with
     `--yes`. This puts the sandbox back at its recorded base; it is the only force push on the
     sandbox, and no runbook gives another. One run at a time on the sandbox: a reset ends any
     other run.
  2. `uv run --no-project python evals/kit/setup.py <campaign> <workspace>`, with `<workspace>`
     outside this repository, for example `../chantier-eval/<campaign>-<date>`. Setup refuses
     when the sandbox is not at its base, never resets and never pushes. It clones the sandbox
     into the workspace, runs `chantier init` and `uv sync --locked` there, places the campaign's
     frozen CRs in `.agents/changes/3-ready/`, writes `<workspace>.run.json` (the run's record)
     and prints the campaign, the run, the prefix, the CRs placed and each batch's `open` line,
     ready to paste (`--mode <stack|parallel|series>` is left to fill in for the quick
     campaigns). The agents use the real `gh`.
- **The run's number and prefix.** The number is 1 plus the highest `<n>` among the sandbox's PR
  titles that start with `[eval <n> `. A run that opened no PR leaves its number free for the next
  one. The prefix is `[eval <run> <date> <campaign>]`, for example `[eval 4 2026-11-14 full]`.
  Every PR a run opens has a title that starts with it, followed by the title it would have
  anyway: each frozen CR copied into the workspace says so in its "Eval run" section. The audit
  and the judge read the run's record, so the prefix is how a run's PRs are told apart from older
  ones left on the sandbox.
- **The operator** is a new Code session of the Claude Desktop app opened on the workspace (not
  under Remote Control: it starts the Foreman's sessions), started with the runbook's prompt, which
  names the runbook by its absolute path in this checkout. It is the Chief of Staff and plays the
  user in full: the go after the plan, every merge, every answer, every approval, the release's
  confirmation, the injected CR, `pause` coming and the "close the batch". Nothing waits on the
  real user. `$CHANTIER` is `uv run --script "<this checkout>/skills/chantier/scripts/cli/chantier.py"`,
  run from the workspace. The plugin must be installed from this checkout (see "Before you
  start").
- **A merge** is the user's, and the operator plays the user: `chief-of-staff.md`'s "Never merge"
  is about the real user's PRs, which an eval has none of. (The Foreman still merges the release
  PR itself, as the card says.) The operator merges with `uv run --no-project python <this
  checkout>/evals/kit/sandbox.py merge <n>` (the `merge` line `setup.py` prints), from the
  workspace, alone, never chained; it never uses a raw `gh pr merge`. The sandbox's `main` is not
  protected, so the forge refuses only a conflict; the merge command refuses a PR that is not
  open, whose title lacks the run's prefix, or whose checks are not all green at its head (a
  pending check included), and merges nothing then. A refused merge is reported as it is, and the
  steering session sees the PR not merged, as usual. Then `$CHANTIER order merged CR-<n>` and its
  line to the steering session. In parallel mode the operator merges in the order the CRs become
  ready; in series, in the series' order; in a stack, from the bottom up, as `chief-of-staff.md`
  says for the mode.
- **A question** (`blocked question:`): the frozen CRs leave none open, so a question is a
  finding. The operator answers `Follow the specification as written; where it is silent, choose
  the simplest behaviour and say so in the PR.`, records it in the CR's `02-answers.md`, and sends
  `$CHANTIER order note CR-<n> --note "answer: …"`.
- **A CR stuck** (the round limit, or blocked twice): the operator drops it (`order drop`), so the
  batch can pause; the report says why.
- **A `budget:` ask** (`ask blocked CR-<n> budget: …`, or `status` says the budget is spent): the
  first in a batch, the operator raises the budget once, `$CHANTIER order budget --note <the
  opening budget × 1.5, rounded up to whole dollars>`, sends its line, and the report records it
  as a finding (the cost of the kit's CRs is part of what a run measures). Any later `budget:` ask
  in the same batch: `$CHANTIER order drop CR-<n>` for the CR that asked, and its line; the report
  says why. No other raise.
- **The audit** runs when the steering session reports `final` (the batch paused), before
  `close --yes`:

  ```bash
  uv run --no-project python evals/kit/audit.py <workspace> --sandbox
  ```

  then `$CHANTIER cost --explain` and `$CHANTIER cost --by cr` from the workspace. Then the
  operator runs the `close` flow and `close --yes`. The audit prints the run's table, the facts,
  the checks, the judge (the hidden tests on each CR's head, on `main`, and the release judge),
  the scorecard and the cost. It exits 1 on a failed check, an unknown rail or a judge `fail`;
  `not run` is not a failure.
- **The report** goes in `results/<campaign>-<date>-run<n>.md`, written in a worktree of this
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

- The chantier plugin installed from this checkout, and the session restarted:
  `claude plugin marketplace add <this checkout>`, then `claude plugin install chantier@chantier`.
  The plugin is read live from the checkout: during a run, change neither its files nor its
  branch; other work goes in a worktree. This install is what reaches the workspace: the
  workspace is outside this repository and does not read its `.claude/settings.json`.
- `uv` and `git`. In the staged campaign the forge is local (`evals/kit/forge.py`, a fake `gh`
  whose CI runs the long gate in a fresh clone): nothing reaches GitHub. `setup.py` puts it first
  on the `PATH` of every session in the workspace, so the Drivers' own `gh pr create` and the
  Foreman's `gh pr merge` reach it too. A sandbox campaign has no local forge: it needs `gh`
  logged in.
- On Claude Desktop, the go must be typed in the desktop app: under Remote Control, starting
  the Foreman's session is refused.
- On Claude, for a sandbox campaign, `setup.py` writes the workspace's
  `.claude/settings.local.json` (ignored by the sandbox's git) with the merge command's rule and,
  for `full`, the release's tag push and `gh release create` for its versions: rules the user's
  own settings may lack. Nothing else is allowed there.

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

### The steps

These steps are for `claude-planted`.

1. **Stage** the workspace next to this checkout, for example
   `../chantier-eval/<campaign>-<date>`: `uv run --no-project python evals/kit/setup.py
   <campaign> <workspace>`.
2. **Be the Chief of Staff** in that workspace: load the chantier skill, run its CLI from the
   workspace (`$CHANTIER` is `uv run --script "<this checkout>/skills/chantier/scripts/cli/chantier.py"`),
   and start the batch as `chief-of-staff.md` says (preflight, plan, go), with the `open`
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
```

`full` has one report for both batches: one scorecard, where a row is `seen, wrong` if it was
wrong in either batch, and the cost per batch and in total.

## The kit

| File | Role |
| --- | --- |
| [`kit/setup.py`](kit/setup.py) | Sets up a campaign's workspace. `claude-planted`: the project, a bare origin, the local forge, the CRs. A sandbox campaign: a clone of the sandbox at its base, the frozen CRs, the run's number and prefix, `<workspace>.run.json`, and on Claude the workspace's ignored `.claude/settings.local.json` (the merge, the release's tag push and GitHub release) |
| [`kit/forge.py`](kit/forge.py) | The local forge, called as `gh`: PRs, CI in a fresh clone, CI-only contract tests |
| [`kit/merge.py`](kit/merge.py) | `claude-planted`'s merge, on the local forge |
| [`kit/audit.py`](kit/audit.py) | What happened to each CR, the agent tree, one PASS/FAIL line per check, each naming its rail, and the scorecard; `--sandbox` for the sandbox campaigns: also the run table, the real forge read-only and the judge |
| [`kit/judge.py`](kit/judge.py) | The judge: the hidden tests on a PR's head in a clean clone of the sandbox, and a release judged by the tag, the version, the notes and the GitHub release |
| [`SCORECARD.md`](SCORECARD.md) | The single list of rails, one row each: id, rail, source, where seen, how marked |
| [`kit/fixture/`](kit/fixture/) | `tasks-cli`, with its `AGENTS.md` and two review agents of its own |
| [`kit/crs/`](kit/crs/) | The prepared CRs (request, intent, answers, specification) |
| [`kit/contracts/`](kit/contracts/) | Tests only the simulated CI runs |
| [`kit/sandbox-crs/`](kit/sandbox-crs/) | The frozen CRs of the sandbox campaigns (request, intent, answers, specification): 11 features and 2 releases |
| [`kit/sandbox-judge/`](kit/sandbox-judge/) | The hidden tests of the feature CRs: never copied to a workspace, never pushed to the sandbox |
| [`kit/sandbox/`](kit/sandbox/) | `shelf`, the sandbox project, the source of the sandbox's initial commit |
| [`kit/sandbox.py`](kit/sandbox.py) | `build` (the deterministic initial commit, its SHA-1 recorded in `kit/sandbox.json`) `reset` (the sandbox back at that commit, comparing branches and tags only; the only force push) and `merge` (the operator's merge of a run's PR, which refuses a PR not open, without the run's prefix or not all green) |
| [`kit/dry_run.py`](kit/dry_run.py) | The dry run (`just eval-dry-run`): reset, setup, a staged run, audit and judge, on a local sandbox, with its planted faults (a stray merge, a leftover after the reset, a refused merge, a stale `uv.lock`); no model, no GitHub |
| [`kit/sandbox_forge.py`](kit/sandbox_forge.py) | The sandbox's GitHub played locally, called as `gh`, for the dry run only |
| [`kit/dry-run/`](kit/dry-run/) | The reference solution of the staged CR, `delete-item` (`delete-item.patch`) |

### Changing the kit

- A change to `evals/kit/` passes `just eval-dry-run` at its pushed head. Its output is the
  Verifier's evidence (`work/verifier/evidence/`), quoted in the PR body.
- A new campaign behaviour, or a fault a run found, gets its case in the dry run in the same PR.
- An eval-kit change gets an independent review of the whole campaign path (setup, a run, the
  audit, the judge) before its merge, by a reviewer that did not write it. The dry run does not
  replace it.

## The sandbox

The eval campaigns run on a frozen project: `shelf`, a small reading list in Python, kept in
[`kit/sandbox/`](kit/sandbox/) and published at
[gsemet/chantier-eval-sandbox](https://github.com/gsemet/chantier-eval-sandbox) (public, `main`
not protected). Its initial commit is the same everywhere, down to the SHA-1, and that SHA-1 is
the recorded base in [`kit/sandbox.json`](kit/sandbox.json).

- `uv run --no-project python evals/kit/sandbox.py build [<dest>]` builds that commit, and exits 2
  when its SHA-1 is not the recorded one. `just check` runs it as a structure test.
- To change the project: edit `kit/sandbox/`, run `build --record`, and commit `sandbox.json` in
  the same PR, or `just check` is red. Once that PR is reviewed, run `reset --yes`.
- `uv run --no-project python evals/kit/sandbox.py reset` prints what it would do and changes
  nothing; `reset --yes` closes the open PRs, deletes the releases, tags and other branches, and
  force-pushes the base to `main`. It compares branches and tags only: GitHub keeps
  `refs/pull/*` and no push can delete them.
- `uv run --no-project python evals/kit/sandbox.py merge <pr>` merges a run's PR by rebase, for the
  operator who plays the user, and refuses what the user would not merge (see "A merge" above).

Nothing else resets the sandbox: the repository is a constant of the script, and `reset` is
the only force push.
