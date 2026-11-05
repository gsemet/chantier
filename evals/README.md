# chantier evals

An eval campaign runs chantier for real, with real agents, on a small fictional project
(`tasks-cli`, a to-do list in Python), and checks that every agent got its role and behaved as
its role says. The `real` campaign instead runs on this repository, with the real forge and CI;
its [runbook](real/RUNBOOK.md) replaces the steps below. Each run is reported in
[`results/`](results/), in words anyone can follow.

The scripted scenario (`just scenario`, no model, free) is not an eval: it tests the CLI's
mechanics and lives in [`scenario/`](../scenario/run_scenario.py).

## Campaigns

| Campaign | What it covers | Cost | Last run |
| --- | --- | --- | --- |
| [real](real/RUNBOOK.md) | Real CRs on this repository, in parallel, with real `gh` and CI, up to draft PRs nobody merges | ~$7 for 4 CRs, 30 min | 2026-11-05: passed with findings, $4.42 for 2 CRs and a QA, [report](results/real-2026-11-05-v0-5-0.md) |
| [claude-smoke](claude-smoke/RUNBOOK.md) | One CR end to end on Claude: every role, the project's own review step, simulated CI | ~$1, 15 min | 2026-11-04: passed with findings, $1.34, [report](results/claude-smoke-2026-11-04.md) |
| [claude-full](claude-full/RUNBOOK.md) | Six CRs on Claude: parallel and added work, a change order, a question, QA, rebases, a red CI from the product, the round limit; then a release with a fix, approvals and a grant | ~$15, 3 h | 2026-11-04: passed with findings, $8.41, [report](results/claude-full-2026-11-04-ask-only.md) |
| [copilot](copilot/RUNBOOK.md) | One CR on Copilot: the Foreman's session and heartbeat, background Driver and workers, cost | ~$1 | not run yet |

## Run a campaign

A campaign starts from a prompt in a chat. On Claude: a Code session of the Claude Desktop app,
opened on this repository, with the branch to test checked out. On Copilot: a chat of the
Copilot app, on this repository.

```text
Run the chantier eval campaign claude-smoke: follow evals/claude-smoke/RUNBOOK.md.
```

The session that gets the prompt is the operator: it plays both the Chief of Staff (with the
chantier skill) and the user (it answers, merges and gives orders as the runbook says).

### Before you start

- The chantier plugin installed from this checkout, and the session restarted:
  `claude plugin marketplace add <this checkout>`, then `claude plugin install chantier@chantier`.
  The plugin is read live from the checkout: do not switch branches during a run.
- `uv` and `git`. The forge is local (`evals/kit/forge.py`, a fake `gh` whose CI runs the long
  gate in a fresh clone): nothing reaches GitHub. `setup.py` puts it first on the `PATH` of
  every session in the workspace, so the Drivers' own `gh pr create` and the Foreman's
  `gh pr merge` reach it too.
- On Claude Desktop, the go must be typed in the desktop app: under Remote Control, starting
  the Foreman's session is refused.

### The host's limits

Claude Desktop sets these and no setting changes them: a campaign is written to live with them.

- **10 messages per session.** A session can send 10 messages to other Desktop sessions since
  someone last typed in it; the next ones are refused, and refused sends count. Each session has
  its own count, attached or detached. Messages from other sessions do not reset it, and a line
  typed during a turn counts only once that turn ends.
- **Every campaign stays under it**, for the Foreman and for the operator: at most 10 messages
  from the Foreman in the whole run, nobody types in its session, and at most 10 orders from the
  operator between two lines the user types. Only a campaign made to test long exchanges goes
  past it, and its report says so. `claude-full` can still reach it: a long batch has many
  `ask` lines.
- **Past the limit,** the Foreman's messages are lost, but the host still tells the operator of
  each of its turns: follow these notes and `status`, and merge from there. Never send through
  another tool: the limit is the host's, and a refusal is reported.
- **Starting the Foreman** needs a line typed in the desktop app (see above). From a phone, the
  user starts the session and pastes the Foreman's prompt; the Foreman claims its epoch itself.

### The steps

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
4. **When the batch lands** (`final <report>`): run the audit and the cost.

   ```bash
   uv run --no-project python evals/kit/audit.py <workspace>
   ```

   and `$CHANTIER cost --by role`, `$CHANTIER cost --by cr` from the workspace.
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

## What was tested
Two or three sentences: the project, the CRs, what the user did during the run.

## What happened
Per CR, in plain words: what it asked, how it went, how it ended.

## Findings
Numbered. Each: what went wrong or could be better, why it matters, what to do.

## Numbers
Duration, cost (total, by role, by CR), agents started, audit checks passed.

## For maintainers
chantier version and commit, failed audit checks verbatim, anything to reproduce.
```

## The kit

| File | Role |
| --- | --- |
| [`kit/setup.py`](kit/setup.py) | Stages a campaign's workspace: the project, a bare origin, the local forge, the CRs |
| [`kit/forge.py`](kit/forge.py) | The local forge, called as `gh`: PRs, CI in a fresh clone, CI-only contract tests |
| [`kit/merge.py`](kit/merge.py) | The user's merge |
| [`kit/audit.py`](kit/audit.py) | What happened to each CR, the agent tree, and one PASS/FAIL line per check |
| [`kit/fixture/`](kit/fixture/) | `tasks-cli`, with its `AGENTS.md` and two review agents of its own |
| [`kit/crs/`](kit/crs/) | The prepared CRs (request, intent, answers, specification) |
| [`kit/contracts/`](kit/contracts/) | Tests only the simulated CI runs |
