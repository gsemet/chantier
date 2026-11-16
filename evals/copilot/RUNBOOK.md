# Campaign copilot

One frozen CR on a Copilot SDK host (the Copilot app), on the eval sandbox with the real `gh`: the
mechanics that differ from Claude, as cheaply as possible. About $1.

**What it proves:**

- **The Foreman and its heartbeat:** the Foreman starts with `create_session`, the Chief of Staff
  arms `/every` in its chat, and a wake runs `chantier status --refresh`.
- **The Driver and its workers:** the Driver runs in the background (`task`), starts each worker
  with a prompt written from its card and the facts `chantier round` prints, and ends with a
  hand-back.
- **The models:** each role runs on its agent file's model, from the host's own record.
- **The cost:** `chantier cost` measures the batch through copilot-session-usage, as a breakdown (`Agent <type>` lines).

Follow the sandbox campaign text in [the evals README](../README.md#a-sandbox-campaign) (the
preparation, the run's number and prefix, a merge, the audit), on Copilot, with:

| Step | Value |
| --- | --- |
| Setup | `uv run --no-project python evals/kit/setup.py copilot <workspace>` |
| Batch | `copilot` |
| CRs | `delete-item` |
| Open | `$CHANTIER open 3-ready/delete-item --slots 1 --budget 3 --default-branch main` |

## Start

Setup prints the operator's `prompt` line last, with this checkout's path filled in (the template is
`Run the chantier eval campaign copilot: follow <this checkout>/evals/copilot/RUNBOOK.md.`). Open a
new chat of the Copilot app on the workspace and paste it. **Unproved:** this form has not been run
on Copilot yet; the first run of the campaign proves it, and the report says what the app did.

## The user's turns

1. Give the go once the plan is shown.
2. When `ask ready CR-<n> <link>` arrives: merge the PR (`uv run --no-project python <this
   checkout>/evals/kit/sandbox.py merge <pr>`, from the workspace, alone), then `$CHANTIER order
   merged CR-<n>` and send the line it prints.
3. A `budget:` ask, as the README says (the raise is to `$5`: `$CHANTIER order budget --note 5`).
4. Wait for `final <report>`, then "what did it cost?", run the audit (`audit.py <workspace>
   --sandbox`), then `$CHANTIER close --yes`, and delete the `/every` heartbeat. The report's cost figure is read
after `close --yes`, from the closed batch's record `.agents/changes/5-archives/batches/batch-NN.md`;
the audit's cost stays before it.

## Expected

- At least one heartbeat in the batch's event log.
- One Driver; one coder, one Inspector, one verifier.
- The audit runs before `close --yes` (it needs the batch folder).
- The CR ends `merged` (in `4-batch/3-done/`, waiting for `close`), the batch `paused`; `chantier cost` prints the breakdown, an `Agent <type>` line per agent type.
- The judge: the hidden tests of `delete-item` on the PR's head.

## Models

Run in the same Copilot App chat, before the batch's go or after `close --yes`. Supported hosts:
the Copilot App (on the Copilot SDK) and the Copilot CLI.

1. Ask the Chief of Staff to start, with `task` and no model, each plugin agent `chantier-<role>`
   once (all fourteen), in this order, one at a time (each waits for its answer before the next
   starts): cr-driver, stack-driver, qa-driver, release-driver, investigator, coder, inspector,
   debugger, verifier, conflict-resolver, demo-explorer, spec-writer, spec-critic, retro-critic.
   Each gets the prompt `model probe` and answers its refusal line (a prompt that is not
   chantier's); that answer runs on the agent's model, so the host records it. About fourteen
   short calls.
2. Run `uv run --no-project python <this checkout>/evals/kit/copilot_models.py` on the Chief of
   Staff's session and paste its output into the report.
3. Where available, record the account's identifiers with
   `copilot --silent -p "/model --list --json"` (it works only sometimes,
   [copilot-cli#700](https://github.com/github/copilot-cli/issues/700)); a difference with the
   agent files' identifiers (`gpt-5.6-luna` among them) is reported, not fixed in the run.
4. When a role ran on another model than its file's, or the host printed an enforcement or
   refusal message (a plan without the model included): the report names the role, the expected
   identifier, the recorded one and the host's exact text. Nothing is worked around: the agent
   file is not changed to follow the host, no override is passed. The finding goes to
   `hosts/copilot.md` ("Models" rows) through an inbox CR, which the Chief of Staff offers the user.

## Still to fill in from a real run

- The Copilot part of `evals/kit/audit.py` (roles, prompts and tools from the host's logs): until
  then the audit checks only what every host shares, the run, the judge and the cost, with no rail
  ids and no scorecard.
