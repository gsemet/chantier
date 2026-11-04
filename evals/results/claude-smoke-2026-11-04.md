# claude-smoke, 2026-11-04

**Verdict:** passed with findings. The change was built and merged and every check passed, but this
run also shows that keeping the Foreman attached does not lift the host's limit of 10 messages.

## What was tested

chantier was asked to fix one bug in `tasks-cli`, a to-do list program: `tasks done 42` crashed on an
unknown task. The Foreman stayed attached to the operator, and the operator sent it 12 orders on top
of the runbook, `pause` and `resume` in turn, each of which the Foreman must confirm. The aim was to
make it send 15 messages and see whether the limit applies to an attached session.

## What happened

- **CR-101, an error instead of a crash.** The docs reviewer asked for the error to be documented in
  the README, so it took two rounds. CI was green, the verifier confirmed it, the operator merged it,
  and the batch landed.
- **The limit.** The Foreman's 10 messages went through. Its 11th, `ok O-11`, was refused, and so
  were its next ones, `ready CR-101` and `final` among them. They were never sent: nobody typed in
  its session.

## Findings

1. **An attached session is not spared the limit.** The host's refusal reads "this session has
   already messaged Claude Desktop sessions 10 times since your user last typed here". Attached or
   not, a Foreman falls silent after 10 messages, and a normal batch will reach that. To do: send
   the Foreman only the `ask` lines, since the `ok` lines repeat what `status` shows.
2. **The app's own notes still arrive.** When an attached Foreman ends a turn, the app tells the
   operator, and that note passed the limit: the operator learned of the ready PR and of the landing
   that way, and from `status`. This is why a batch still ended without anyone typing in the
   Foreman's session. To do: decide whether the Chief of Staff can rely on these notes, since a
   detached Foreman has none, and whether the Foreman should stay attached outside evals.
3. **The Foreman started only from a message typed in the desktop app.** Under Remote Control the app
   refused twice, so an eval cannot start from a phone. The user also saw a "trusted workspace"
   dialog on the go, and which of the two blocks a remote start is unknown. To do: try a workspace
   inside the project, in a folder git ignores.
4. **The Foreman merged two confirmations into one message.** It answered O-3 and O-4 together, so
   orders sent in a burst count once. The operator then sent them one at a time.

## Numbers

- **Duration:** 23 minutes, from opening the batch to its landing.
- **Cost:** $1.34 in all, for a budget of $5.
  - By role: Foreman $0.73, Driver $0.24, coders $0.11, Inspectors $0.09, verifier $0.08, docs
    reviewers $0.08. The Foreman's share is high because of the extra orders.
  - By change: CR-101 $0.61 (the Foreman's $0.73 apart).
- **Agents:** 8 under the Foreman: 1 Driver, 7 workers.
- **Audit:** 67 of 67 checks passed.

## For maintainers

- chantier 0.1.0, `main` at 02cf7a0. Foreman and every other agent on Sonnet 5.5, operator on
  Opus 5.5; Windows 11, Claude Desktop.
- The runbook expects one coder, one Inspector and one docs reviewer: there were two of each, one
  per round. It does not plan the extra orders: 12 were sent, O-1 to O-12, then O-13 for the merge.
- The Foreman sent 10 messages, not 15: the 11th was refused, so the run stopped counting there.
- The operator's own messages all passed: it sent 13, and the user typed in its session on the way.
  Run outside the workspace, `$CHANTIER` needs the `env` of `.claude/settings.local.json` to reach
  the local forge.
