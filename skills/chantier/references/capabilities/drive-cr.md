# Capability: drive a CR

## Purpose

Take one CR from its brief to a green PR, then hand it back.

## Who uses it

CR Driver.

## Commands

1. Use `$CHANTIER path <cr> --batch <batch>` for the CR folder and add `--spec` for the
   specification. Read the specification, project guidance and any relevant preserved hand-over;
   use `$CHANTIER status --batch <batch> --json` for current state, not an old `STATE.md` snapshot.
2. Round: start a **foreground** `coder` subagent with the brief and the previous hand-over
   note; then a foreground `inspector` on the round's diff.
3. Verdict `APPROVE`: `$CHANTIER gate <cr> --long` (in the background if long), then
   [ship-and-forge](ship-and-forge.md). `FIX-REQUIRED`: next round with the blocking findings.
4. `$CHANTIER report <cr> round-done "r<n> <verdict>"` after each round.
5. CI: [waits-and-ci](waits-and-ci.md).
6. Green: `[driver <cr>→foreman] hand-back ready <pr-link>` and end.

## Rules

- Use the batch's recorded `settings.max_rounds` (default 3) for all causes; only the user grants
  more (through the Foreman).
- No automatic model change. Before each child, run `$CHANTIER models get <role> --cr <cr>` and do
  exactly what it prints ([models](models.md)): spawn the agent its `agent:` line names (the
  plugin's, or the repository's own one from `AGENTS.md`), with your own `skill:` and `changes:`
  lines in its prompt ([message formats](../message-formats.md)).
- One foreground child at a time; a background spawn from a Driver becomes foreground anyway.
- Never code, review, or touch another CR. Never message the Foreman for routine milestones.
- Follow the target project's commit, rebase and PR conventions in `AGENTS.md` and linked
  guidance; use [ship-and-forge](ship-and-forge.md) for the CLI's mechanics.

## Failure handling

- Past the round limit, or a decision only the user can take: `hand-back blocked <reason>`.
- A "change" message arrives: decide steer (next round), restart (new brief) or defer (after the
  PR), record it with `$CHANTIER report <cr> round-done "change <decision>"`, and say which in
  the hand-back.
