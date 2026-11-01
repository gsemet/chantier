# Capability: QA

## Purpose

Exercise a green CR or stack as a user would, and report what breaks.

## Who uses it

QA driver.

## Commands

1. `$CHANTIER qa start <cr>`.
2. From the brief's QA notes: run the app or the long suite in the worktree, follow the user
   scenarios, try edge cases near the change. Capture proof with [evidence](evidence.md).
3. Each finding: `[qa <cr>→foreman] anomaly <cr> <finding>`.
4. `$CHANTIER qa done <cr> --findings <file>`, then `[qa <cr>→foreman] qa done <cr> <n> findings`.

## Rules

- Never fix: findings go to the Foreman, which sends a round to the CR's Driver.
- Reproduce before reporting; a finding names the steps, the expected and the actual result.
- Runs only for CRs whose brief asks for QA; one per stack in stack mode.

## Failure handling

The app cannot start (screen locked, missing device): `anomaly <cr> qa-env` and end.
