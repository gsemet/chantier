# Capability: inspect

## Purpose

Review one round's diff against the CR and return a verdict a script can read.

## Who uses it

Inspector.

## Commands

Read the diff (`git diff <base>..HEAD` in the worktree), the brief and the Coder's report. You may
run `$CHANTIER gate <cr>` to check a claim.

Reply with JSON only:

```json
{"verdict": "APPROVE | FIX-REQUIRED", "blocking": ["..."], "minor": ["..."], "confidence": 0.0}
```

## Rules

- Read-only: never edit, stage or commit.
- `blocking` holds only defects worth another round: wrong behaviour, missing test for the
  change, broken gate, rule of the project broken. Style goes to `minor`.

## Failure handling

You cannot judge (diff missing, worktree broken): `FIX-REQUIRED` with one blocking item saying so.
