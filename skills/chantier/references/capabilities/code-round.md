# Capability: code round

## Purpose

Implement one round of one CR and stop.

## Who uses it

Coder.

## Commands

1. `cd` into the CR worktree; read `AGENTS.md`, the brief and the hand-over note.
2. Implement; run `$CHANTIER gate <cr>` (fast gates only).
3. Use `$CHANTIER path <cr> --batch <batch>` and write `<CR-folder>/scratch/coder/r<n>.md`:
   what changed, gates run with results, open points,
   and a hand-over note for the next round.
4. Reply in at most 10 lines.

## Rules

- Never commit, push or rebase; the Driver does.
- Never claim a gate passed that you did not run.
- No long suites (the Driver runs `$CHANTIER gate --long`), no `sleep`, no background shells: they die
  with you.
- Targeted reads: open the files the change needs, not whole folders.

## Failure handling

Blocked (missing access, unclear brief): stop and say why in your reply; do not guess.
