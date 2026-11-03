# Capability: drive a CR

## Purpose

Take one CR from its brief to a green PR, then hand it back.

## Who uses it

CR Driver.

## Commands

1. Read `crs/<cr>/STATE.md` and the CR's `task.md`.
2. Round: start a **foreground** `coder` subagent with the brief and the previous hand-over
   note; then a foreground `inspector` on the round's diff.
3. Verdict `APPROVE`: `$CHANTIER gate <cr> --long` (in the background if long), then
   [ship-and-forge](ship-and-forge.md). `FIX-REQUIRED`: next round with the blocking findings.
4. `$CHANTIER report <cr> round-done "r<n> <verdict>"` after each round.
5. CI: [waits-and-ci](waits-and-ci.md).
6. Green: `[driver <cr>→foreman] hand-back ready <pr-link>` and end.

## Rules

- At most 3 rounds per CR, all causes; only the user grants more (through the Foreman).
- No automatic model change. Before each child, run `$CHANTIER models get <role> --cr <cr>` and do
  exactly what it prints ([models](models.md)): spawn the agent its `agent:` line names (the
  plugin's, or the repository's own one from `AGENTS.md`), with your own `skill:` line first in
  its prompt ([message formats](../message-formats.md)).
- One foreground child at a time; a background spawn from a Driver becomes foreground anyway.
- Never code, review, or touch another CR. Never message the Foreman for routine milestones.
- Lifecycle details (commit, rebase, PR) follow change-request-factory:
  [lifecycle.md](../../../change-request-factory/references/lifecycle.md).

## Failure handling

- Past the round limit, or a decision only the user can take: `hand-back blocked <reason>`.
- A "change" message arrives: decide steer (next round), restart (new brief) or defer (after the
  PR), record it with `$CHANTIER report <cr> round-done "change <decision>"`, and say which in
  the hand-back.
