# Capability: stack

## Purpose

Keep a stack of PRs ordered, rebased and green.

## Who uses it

Stack driver.

## Commands

```bash
$CHANTIER stack order <cr>...     # set the stack order
$CHANTIER stack restack           # rebase every PR above a merged or changed one
```

Stack rules and heavy CI on top: [stacked-prs.md](../../../change-request-factory/references/stacked-prs.md).

## Rules

- Started when every CR of the stack is ready or blocked, and again after each merge the Foreman
  passes on.
- Heavy CI runs once, on the top of the stack.
- Never code; a conflict that needs code is `anomaly <cr> conflict`, and the Foreman sends a round
  to that CR's Driver.

## Failure handling

Restack fails twice on the same CR: `anomaly <cr> restack`.
