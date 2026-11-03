# Capability: gates

## Purpose

Run the project's checks the same way for every role.

## Who uses it

Coder (fast), Inspector (to verify a claim), Drivers (long).

## Commands

```bash
$CHANTIER gate <cr>          # the batch's fast gates, in the CR worktree; exit 4 on a failure
$CHANTIER gate <cr> --long   # long suites; Drivers only, in the background
```

## Rules

- Gates use the project's own environment (`uv run`, `npm run`, `just`), never a global tool.
- The Chief of Staff infers and records fast and long gate commands when opening the batch; no
  recorded gate is an error, never a pass.
- Output is the first failures only; the full log is in `<CR-folder>/scratch/gates/`. Find the
  folder with `$CHANTIER path <cr> --batch <batch>`.
- `$CHANTIER open` creates worktrees but does not install dependencies. Follow the project's
  guidance and obtain approval where needed before per-worktree setup.

## Failure handling

Exit 2 for a missing gate: report the configuration problem to your parent. Exit 4 with an
environment error (not a test failure): report `anomaly gate-env`.
