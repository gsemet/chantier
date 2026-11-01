# Capability: waits and CI

## Purpose

Wait for CI or a long suite without an LLM turn, and classify failures.

## Who uses it

CR Driver, stack driver.

## Commands

```bash
$CHANTIER wait ci <cr> --max 3300      # run in the background; exit 0 pass or timeout, 4 fail
$CHANTIER ci classify <cr>             # product | known-red-on-main | infra
```

## Rules

- Start `$CHANTIER wait` as a background shell and end your turn; its result wakes you. Your one-hour
  cache keeps the wake cheap.
- `product`: a new round. `known-red-on-main`: `$CHANTIER report <cr> ci-red-known`, not fixed.
  `infra`: one re-run, then `anomaly infra`.
- Never poll in a loop, never `sleep`.

## Failure handling

Timeout at 3300 s: re-arm once; a second timeout is `anomaly ci-stuck`.
