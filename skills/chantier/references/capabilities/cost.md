# Capability: cost

## Purpose

Report what a batch cost, by role and by CR, from measured usage.

## Who uses it

Chief of Staff; the Foreman for the budget stop.

## Commands

```bash
$CHANTIER cost --batch <batch> --by role
$CHANTIER cost --batch <batch> --by cr
$CHANTIER cost --batch <batch> --update   # Foreman, at each heartbeat: stores the total as spent_usd
```

The Foreman records its session id once with `$CHANTIER foreman transcript <id>`
(`$CLAUDE_CODE_SESSION_ID` on Claude, `$COPILOT_AGENT_SESSION_ID` on Copilot). The figures cover
that session and its subagents:

- **Claude:** the Foreman's transcript and its `subagents/`, priced in
  `scripts/cli/src/chantier/costs.py`.
- **Copilot:** the billed per-call records of
  [copilot-session-usage](https://github.com/gsemet/copilot-session-usage) >= 1
  (`--agent cli calls`); chantier does no pricing of its own. Nothing to install: uv fetches it
  from pypi.org using the inline metadata of `scripts/cli/session_usage.py`. The default command
  ignores uv configuration files and index or find-links environment variables; proxy,
  certificate and offline settings still apply. `CHANTIER_SESSION_USAGE` swaps in another
  command, for tests.
  A call the tool could only estimate is counted and flagged in the first line.

The budget check in `$CHANTIER event` uses the last `--update`, so it lags by at most one heartbeat.
The Chief of Staff's own wakes are not in it: count them from its own session.

## Rules

- Measured, never estimated by a role: only `$CHANTIER cost` gives a figure.
- Budget: when spending reaches the brief's budget, `$CHANTIER event` returns `ask-chief-of-staff budget`; the
  Foreman spawns nothing new until the Chief of Staff answers.
- Reference figures: design 5's `02-cost-detail.md`
  (`projects/aps/changes/1-inbox/workflow-optimization/design-5-nested-session/` in the
  agentic-planning-surface repository).

## Failure handling

`$CHANTIER cost` fails (a missing or unreadable transcript, an unpriced Claude model, uv unable
to fetch copilot-session-usage, or a call without a price): report its line as is and give no
figure. Never estimate a cost from token counts, another tool or memory; for the Foreman, a
failed `--update` is a question for the Chief of Staff before the next spawn.
